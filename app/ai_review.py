"""AI pre-review — the platform's Layer-3 step (AI-IDENTITY.md).

Every submitted item is checked before an expert sees it: completeness, limit
values, applicability consistency, evidence age, and the supplier certificates
behind each component. Each check cites the knowledge-base source it rests on.

In this pilot the reasoning is a deterministic rule engine over the PPWR
knowledge base (the same approach as the V3.1 prototype's "IMA rule engine").
In production the `review()` interface stays the same and wraps an LLM + RAG
call over `PPWR Knowledgebase/`; the AI verdict is advisory — the expert decides.
"""
from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass, field

from . import applicability, catalogue, config
from .db import Evidence, PackagingUnit, Project, Submission, now

REG = "PPWR (EU) 2025/40"
KB = {
    "a5": f"{REG} Art 5(4)", "a5pfas": f"{REG} Art 5(5)", "a6": f"{REG} Art 6 + Annex II",
    "a7": f"{REG} Art 7", "a10": f"{REG} Art 10 + Annex IV", "a24": f"{REG} Art 24",
    "a11": f"{REG} Art 11", "a12": f"{REG} Art 12, Art 15(5)-(6)", "annex7": f"{REG} Annex VII",
    "annex8": f"{REG} Art 39 + Annex VIII", "checklist": "PPWR Support File Checklist V1.5",
    "bom": "PPWR BOM template V1.1", "en13430": "EN 13430 (harmonised under 94/62/EC)",
    "faq": "Commission PPWR FAQ 2026",
}


@dataclass
class Ctx:
    sub: Submission
    item: dict
    project: Project
    unit: PackagingUnit | None
    evidence: list[Evidence] = field(default_factory=list)   # files attached to this item

    @property
    def data(self) -> dict:
        return self.sub.data or {}

    def sibling(self, item_id: str) -> Submission | None:
        for s in self.project.submissions:
            if s.item_id == item_id and s.unit_id in ((self.unit.id if self.unit else None), None):
                return s
        return None

    @property
    def components(self):
        units = [self.unit] if self.unit else self.project.units
        return [c for u in units for c in u.components]


def check(desc: str, ok, msg: str = "", ref: str = "") -> dict:
    return {"desc": desc, "ok": ok, "msg": msg, "ref": ref}


def _filled(ctx: Ctx, key: str) -> bool:
    return bool(str(ctx.data.get(key, "")).strip())


def _number(text) -> float | None:
    m = re.search(r"(\d+(?:[.,]\d+)?)", str(text or ""))
    return float(m.group(1).replace(",", ".")) if m else None


def _months_old(d: dt.date) -> float:
    return (dt.date.today() - d).days / 30.44


# ---------------------------------------------------------------------------
# Item-specific rules
# ---------------------------------------------------------------------------

def _r_upi(ctx):
    return [check("UPI filled — the single index of the packaging in the TD and DoC",
                  _filled(ctx, "upi"), ctx.data.get("upi") or "UPI missing", KB["annex8"]),
            check("Packaging name and level given", _filled(ctx, "pkgName") and _filled(ctx, "pkgType"),
                  "" if _filled(ctx, "pkgType") else "Packaging level missing", KB["annex7"])]


def _r_sku(ctx):
    return [check("Product / SKU scope stated (DoC object of declaration)", _filled(ctx, "sku"),
                  ctx.data.get("sku") or "No SKU mapping", KB["checklist"])]


def _r_supplier_site(ctx):
    ok = _filled(ctx, "sup") and _filled(ctx, "country")
    return [check("Packaging supplier and country of manufacture given", ok,
                  "✓" if ok else "Supplier or country missing", "Art 15(4)")]


def _r_mass(ctx):
    out = []
    mass = _number(ctx.data.get("mass"))
    out.append(check("Packaging mass (g) given — Art 10 minimisation baseline", bool(mass and mass > 0),
                     f"{mass:g} g" if mass else "Mass missing", KB["a10"]))
    out.append(check("Dimensions (mm) given — Art 24 empty-space input", _filled(ctx, "dims"),
                     ctx.data.get("dims") or "Dimensions missing", KB["a24"]))
    comps = ctx.components
    bom = sum(c.mass_g or 0 for c in comps)
    if mass and bom:
        dev = abs(bom - mass) / mass
        out.append(check("Unit mass agrees with the BOM (sum of component masses, ±10 %)", dev <= 0.10,
                         f"BOM {bom:g} g vs declared {mass:g} g ({dev:.0%} deviation)", KB["bom"]))
    return out


def _r_photos(ctx):
    photos = [e for e in ctx.evidence if e.type_code == "PHO"]
    return [check("Photo / artwork reference or photo files present", _filled(ctx, "ref") or bool(photos),
                  f"{len(photos)} photo file(s)" if photos else (ctx.data.get("ref") or "None"),
                  KB["checklist"])]


def _r_heavy_metals(ctx):
    out = []
    v = _number(ctx.data.get("res"))
    if v is None:
        out.append(check("Art 5(4) limit: Pb+Cd+Hg+Cr(VI) ≤ 100 mg/kg", None,
                         "No numeric result — expert to read the report", KB["a5"]))
    else:
        out.append(check("Art 5(4) limit: Pb+Cd+Hg+Cr(VI) ≤ 100 mg/kg", v <= 100,
                         f"{v:g} mg/kg " + ("≤ 100 ✓" if v <= 100 else "exceeds 100 mg/kg — may not be placed on the market"),
                         KB["a5"]))
    method = str(ctx.data.get("method", ""))
    known = bool(re.search(r"ICP|AAS|XRF|EN\s*13657|EN\s*71|IEC\s*62321", method, re.I))
    out.append(check("Recognised test method (ICP-OES/MS, AAS, EN 13657, IEC 62321)",
                     known if method else False, method or "Method not stated", KB["checklist"]))
    out += _supplier_certs(ctx, "hm", "Heavy-metal evidence for every component (supplier library)")
    return out


def _food_expected(ctx):
    """Is this unit expected to touch food? The project flag says the *product* is
    food; its sales unit is then food-contact, while a shipper or outer case may not be."""
    if not ctx.project.food_contact:
        return False
    if ctx.unit is None or ctx.unit.level == "Sales":
        return True
    return None  # grouped / transport: either answer can be right — the expert confirms


def _consistent(declared: bool, expected) -> bool | None:
    return None if expected is None else declared == expected


def _r_pfas(ctx):
    app = str(ctx.data.get("app", ""))
    if not app:
        return [check("PFAS applicability decided", False, "Not selected", KB["a5pfas"])]
    declared_na = app.startswith("Not applicable")
    expected = _food_expected(ctx)
    out = [check("PFAS applicability consistent with the profile (food contact expected: "
                 f"{ {True: 'yes', False: 'no', None: 'depends on this unit'}[expected] })",
                 _consistent(not declared_na, expected), app, KB["a5pfas"])]
    if declared_na:
        out.append(check("N/A rationale recorded", _filled(ctx, "note"),
                         "✓" if _filled(ctx, "note") else "Add the reason for N/A", KB["a5pfas"]))
    else:
        out.append(check("PFAS test report / declaration attached", bool(ctx.evidence),
                         f"{len(ctx.evidence)} file(s)" if ctx.evidence else "No file", KB["a5pfas"]))
        out += _supplier_certs(ctx, "pf", "PFAS evidence for every component (supplier library)")
    return out


def _r_food_contact(ctx):
    app = str(ctx.data.get("app", ""))
    if not app:
        return [check("Food-contact status stated", False, "Not selected", KB["a5pfas"])]
    expected = _food_expected(ctx)
    return [check("Food-contact status consistent with the project profile"
                  + (" (outer packaging — expert to confirm)" if expected is None else ""),
                  _consistent(app.startswith("Yes"), expected), app, KB["a5pfas"])]


def _r_recyclability(ctx):
    method = ctx.sibling("C05-21")
    m = (method.data.get("method") if method else "") or ""
    return [check("Recyclability conclusion written (Art 6(1), Annex II)", _filled(ctx, "concl"),
                  "" if _filled(ctx, "concl") else "Conclusion missing", KB["a6"]),
            check("Assessment method stated (C05-21, e.g. EN 13430 / EN 18120)", bool(m.strip()),
                  m or "Method not stated on C05-21", KB["en13430"]),
            *_supplier_certs(ctx, "rc", "Recyclability declarations for key components", soft=True)]


def _r_method(ctx):
    return [check("Transitional assessment method stated", _filled(ctx, "method"),
                  ctx.data.get("method") or "State e.g. EN 13430 material recycling", KB["en13430"])]


def _r_recycled(ctx):
    app = str(ctx.data.get("app", ""))
    plastic = [c for c in ctx.components if c.material_group == "plastic"]
    out = [check("Applicability consistent with the BOM (plastic components: "
                 f"{len(plastic)})", bool(app) and (app.startswith("Not applicable") == (not plastic)),
                 app or "Not selected", KB["a7"])]
    if plastic:
        pcr = _number(ctx.data.get("pcr"))
        bom_pcr = [c.recycled_pct for c in plastic if c.recycled_pct is not None]
        out.append(check("PCR % recorded for the plastic part", pcr is not None,
                         f"{pcr:g} %" if pcr is not None else "PCR % missing", KB["a7"]))
        if pcr is not None and bom_pcr:
            out.append(check("PCR % agrees with the BOM", abs(pcr - max(bom_pcr)) < 0.5,
                             f"declared {pcr:g} % · BOM {max(bom_pcr):g} %", KB["bom"]))
    return out


def _r_minimisation(ctx):
    text = str(ctx.data.get("concl", ""))
    hits = sum(1 for k in ("protect", "manufactur", "logistic", "function", "information", "hygien", "safety")
               if k in text.lower())
    return [check("Minimisation conclusion written (Art 10(1))", bool(text.strip()),
                  "" if text.strip() else "Conclusion missing", KB["a10"]),
            check("Annex IV performance criteria addressed", None if 0 < hits < 4 else bool(hits),
                  f"{hits} of 7 criteria mentioned", KB["a10"])]


def _r_void(ctx):
    levels = {ctx.unit.level} if ctx.unit else {u.level for u in ctx.project.units}
    relevant = bool(levels & {"Grouped", "Transport", "E-commerce"})
    note = str(ctx.data.get("note", ""))
    ratio = _number(note)
    if not relevant:
        return [check("Empty-space ratio (Art 24) — sales unit: record applicability", bool(note.strip()) or None,
                      note or "Record why Art 24 does not apply to this level", KB["a24"])]
    return [check("Empty-space ratio ≤ 50 % (Art 24, from 2030)",
                  None if ratio is None else ratio <= 50,
                  f"{ratio:g} %" if ratio is not None else "No ratio found in the note", KB["a24"])]


def _r_reuse(ctx):
    app = str(ctx.data.get("app", ""))
    single = app.startswith("Single-use")
    return [check("Single-use / reusable consistent with the project profile",
                  bool(app) and single != ctx.project.reusable, app or "Not selected", KB["a11"])]


def _r_label_loc(ctx):
    return [check("Position of manufacturer / identification information on the artwork", _filled(ctx, "loc"),
                  ctx.data.get("loc") or "Not stated", KB["a12"])]


def _r_standards(ctx):
    rows = [r for r in (ctx.sub.table or []) if r and str(r[0]).strip()]
    return [check("Standards list has at least one entry (Annex VII 2(d))", bool(rows),
                  f"{len(rows)} standard(s)" if rows else "Empty", KB["annex7"])]


def _r_doc(ctx):
    return [check("EU DoC number", _filled(ctx, "docNo"), ctx.data.get("docNo") or "Missing", KB["annex8"]),
            check("TD number / version referenced", _filled(ctx, "tdNo"), ctx.data.get("tdNo") or "Missing", KB["annex8"]),
            check("Signatory (name, function)", _filled(ctx, "sign"), ctx.data.get("sign") or "Missing", KB["annex8"]),
            check("Place of issue", _filled(ctx, "place"), ctx.data.get("place") or "Missing", KB["annex8"])]


def _r_approval(ctx):
    ok = all(_filled(ctx, k) for k in ("prep", "rev", "appr"))
    return [check("Prepared / Reviewed / Approved all named (TD §21)", ok,
                  "✓" if ok else "Approval chain incomplete", KB["annex7"])]


def _supplier_certs(ctx, doc_type: str, desc: str, soft: bool = False) -> list[dict]:
    """Each component that comes from the supplier library must carry a valid
    certificate of this type — this is where a supplier change bites."""
    comps = [c for c in ctx.components if c.supplier_material is not None]
    if not comps:
        return []
    today = dt.date.today()
    missing, expired, bad = [], [], []
    for c in comps:
        certs = [x for x in c.supplier_material.certificates if x.doc_type == doc_type and x.status == "valid"]
        if not certs:
            missing.append(c.code)
            continue
        cert = max(certs, key=lambda x: x.issued or dt.date.min)
        if cert.expires and cert.expires < today:
            expired.append(f"{c.code} ({cert.number} expired {cert.expires:%d %b %Y})")
        if doc_type == "hm":
            v = _number(cert.value)
            if v is not None and v > 100:
                bad.append(f"{c.code}: {v:g} mg/kg")
    if bad or expired:
        return [check(desc, False, "; ".join(bad + expired), KB["a5"] if doc_type == "hm" else KB["checklist"])]
    if missing and not ctx.evidence:
        return [check(desc, None if soft else False, "No certificate for " + ", ".join(missing),
                      KB["checklist"])]
    return [check(desc, True, f"{len(comps) - len(missing)} of {len(comps)} components covered by valid "
                              f"{catalogue.CERT_SHORT[doc_type]} certificates"
                              + (f"; {', '.join(missing)} covered by uploaded evidence" if missing else ""),
                  KB["checklist"])]


def _supplier_item(doc_type: str):
    def rule(ctx):
        return _supplier_certs(ctx, doc_type, f"{catalogue.CERT_SHORT[doc_type]} certificate valid for every "
                                              "supplied component") or \
            [check("Supplier evidence attached", bool(ctx.evidence) or None,
                   f"{len(ctx.evidence)} file(s)" if ctx.evidence else "No file — confirm with the supplier",
                   KB["checklist"])]
    return rule


RULES = {
    "C01-01": _r_upi, "C01-02": _r_sku, "C01-03": _r_supplier_site, "C01-04": _r_mass,
    "C01-05": _r_photos, "C04-16": _r_heavy_metals, "C04-17": _r_pfas, "C04-18": _r_food_contact,
    "C05-19": _r_recyclability, "C05-21": _r_method, "C06-22": _r_recycled, "C09-29": _r_minimisation,
    "C09-35": _r_void, "C10-37": _r_reuse, "C11-40": _r_label_loc, "C14-54": _r_standards,
    "C16-66": _r_doc, "C16-69": _r_approval,
    "C15-57": _supplier_item("td"), "C15-58": _supplier_item("comp"), "C15-59": _supplier_item("hm"),
    "C15-60": _supplier_item("pf"), "C15-56": _supplier_item("doc"), "C15-63": _supplier_item("rc"),
    "C15-62": _supplier_item("pcr"),
}


def _generic(ctx) -> list[dict]:
    out = []
    for f in ctx.item.get("fields", []):
        out.append(check(f"“{f['label']}” completed", _filled(ctx, f["k"]),
                         str(ctx.data.get(f["k"], ""))[:80] or "Empty", KB["checklist"]))
    return out


# Items whose entry is itself the evidence (register data, decisions, sign-offs) — no file expected.
FIELD_ONLY = {"C01-01", "C01-02", "C01-03", "C01-04", "C03-15", "C04-18", "C05-21", "C07-24", "C08-26",
              "C09-35", "C09-36", "C10-37", "C14-54", "C16-66", "C16-69"}


def _evidence_checks(ctx) -> list[dict]:
    out = []
    has_fields = bool(ctx.item.get("fields")) or bool(ctx.item.get("table"))
    if not ctx.evidence and ctx.item["id"] not in FIELD_ONLY:
        out.append(check("Evidence file attached", None if has_fields else False,
                         "No file — acceptable only if the entry itself is the evidence"
                         if has_fields else "No file uploaded", KB["checklist"]))
    for e in ctx.evidence:
        if e.type_code == "TST" and e.issued_date:
            age = _months_old(e.issued_date)
            out.append(check(f"{e.code}: test report within {config.REPORT_MAX_AGE_MONTHS} months",
                             age <= config.REPORT_MAX_AGE_MONTHS,
                             f"issued {e.issued_date:%d %b %Y} ({age:.0f} months)", KB["checklist"]))
        if e.conformity and e.conformity.lower().startswith("non"):
            out.append(check(f"{e.code}: evidence states conformity", False,
                             "Marked non-conform — explain or replace", KB["annex7"]))
    return out


def review(sub: Submission, project: Project, unit: PackagingUnit | None,
           evidence: list[Evidence]) -> tuple[str, list[dict]]:
    it = catalogue.item(sub.item_id)
    ctx = Ctx(sub=sub, item=it, project=project, unit=unit, evidence=evidence)
    if sub.na_requested:
        status, basis = applicability.status_for(project, it["article"])
        reason = sub.na_reason or ""
        checks = [check("N/A reason given (≥ 20 characters)", len(reason) >= 20, reason[:120] or "Missing",
                        KB["annex7"]),
                  check("N/A consistent with the applicability matrix",
                        True if status == applicability.NA else None,
                        f"Matrix: {status}" + (" — expert to confirm the exception" if status != applicability.NA else ""),
                        KB["annex7"])]
    else:
        checks = (RULES.get(sub.item_id, _generic))(ctx) + _evidence_checks(ctx)
    oks = [c["ok"] for c in checks]
    verdict = "fail" if False in oks else "warn" if None in oks else "pass"
    return verdict, checks


def apply(sub: Submission, project: Project, unit, evidence) -> None:
    sub.ai_verdict, sub.ai_checks = review(sub, project, unit, evidence)
    sub.ai_at = now()
    sub.status = "ai_reviewed"


VERDICT_LABEL = {"pass": "AI: no issues found", "warn": "AI: check needed", "fail": "AI: issues found"}
VERDICT_BADGE = {"pass": "badge-ok", "warn": "badge-warn", "fail": "badge-high"}

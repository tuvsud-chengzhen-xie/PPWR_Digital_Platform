"""Collection & review workflow.

    pending ──submit──▶ submitted ──AI pre-review──▶ ai_reviewed ──expert──▶ approved
       ▲                                                     │                    │
       └──────────────── rejected ◀──────────────────────────┘      na (reason) ◀─┘

Only approved / N/A items feed the generated TD and DoC. Items whose article is
N/A per the applicability matrix are set N/A automatically (with the matrix
rationale); four catalogue items are assembled by the platform itself.
"""
from __future__ import annotations

from collections import Counter

from sqlalchemy.orm import Session

from . import applicability, catalogue
from .db import (Component, Evidence, PackagingUnit, Project, Submission, log, now)

DONE = ("approved", "na")
UNIT_REGISTER_ITEMS = {
    "C01-01": lambda u: {"upi": u.upi or "", "pkgName": u.name or "", "pkgType": u.level or ""},
    "C01-02": lambda u: {"sku": u.skus or ""},
    "C01-03": lambda u: {"sup": u.supplier_name or "", "site": u.site or "", "country": u.country or ""},
    "C01-04": lambda u: {"mass": _num(u.mass_g), "dims": u.dims or ""},
    "C01-05": lambda u: {"ref": u.artwork_ref or ""},
}


def _num(v) -> str:
    if v is None:
        return ""
    return f"{v:g}"


# ---------------------------------------------------------------------------
# Setup / sync
# ---------------------------------------------------------------------------

def ensure_submissions(session: Session, project: Project) -> None:
    existing = {(s.unit_id, s.item_id) for s in project.submissions}
    for it in catalogue.project_items():
        if (None, it["id"]) not in existing:
            session.add(Submission(project=project, unit_id=None, item_id=it["id"]))
    for unit in project.units:
        if unit.id is None:
            session.flush()
        for it in catalogue.unit_items():
            if (unit.id, it["id"]) not in existing:
                sub = Submission(project=project, unit_id=unit.id, item_id=it["id"])
                if it["id"] in UNIT_REGISTER_ITEMS:
                    sub.data = UNIT_REGISTER_ITEMS[it["id"]](unit)
                session.add(sub)
    session.flush()
    session.refresh(project)
    sync(session, project)


def sync(session: Session, project: Project) -> None:
    """Re-apply the applicability matrix and refresh platform-assembled items."""
    for sub in project.submissions:
        it = catalogue.item(sub.item_id)
        if it is None:
            continue
        status, basis = applicability.status_for(project, it["article"])
        if status == applicability.NA:
            if sub.status == "pending" or (sub.na_auto and sub.status != "na"):
                sub.status, sub.na_auto = "na", True
                sub.na_reason = f"Not applicable per applicability matrix — {basis}"
                sub.reviewed_by, sub.reviewed_at = "Platform (applicability matrix)", now()
        elif sub.na_auto:
            # the profile changed and the article now applies — collect it after all
            sub.status, sub.na_auto, sub.na_reason = "pending", False, ""
            sub.reopened_reason = "Article became applicable after a change to the project profile or BOM."
        if it.get("system"):
            _sync_system_item(project, sub)


def _sync_system_item(project: Project, sub: Submission) -> None:
    ok = True
    if sub.item_id == "C02-06":
        unit = next((u for u in project.units if u.id == sub.unit_id), None)
        ok = bool(unit and unit.components and all(c.material and c.mass_g for c in unit.components))
    elif sub.item_id == "C14-55":
        ok = bool(project.evidence)
    if ok and sub.status not in DONE:
        sub.status, sub.reviewed_by, sub.reviewed_at = "approved", "Platform", now()
        sub.review_comment = catalogue.item(sub.item_id)["system"]
    elif not ok and sub.status == "approved" and sub.reviewed_by == "Platform":
        sub.status = "pending"


def sync_unit_register(session: Session, unit: PackagingUnit, actor: str) -> None:
    """Keep C01-xx in step with the packaging register. A change to an approved
    value re-opens the item — the TD must describe the packaging as it is."""
    for sub in unit.project.submissions:
        if sub.unit_id != unit.id or sub.item_id not in UNIT_REGISTER_ITEMS:
            continue
        fresh = UNIT_REGISTER_ITEMS[sub.item_id](unit)
        if fresh == sub.data:
            continue
        was_done = sub.status == "approved"
        sub.data = fresh
        if was_done:
            sub.status = "submitted"
            sub.reopened_reason = "Packaging register changed after approval."
            log(session, "reopened", actor, unit.project_id, unit.id, sub.item_id,
                "Packaging register changed after approval")


# ---------------------------------------------------------------------------
# Transitions
# ---------------------------------------------------------------------------

def submit(session: Session, sub: Submission, actor: str) -> None:
    sub.status, sub.na_requested, sub.na_reason = "submitted", False, ""
    sub.submitted_by, sub.submitted_at = actor, now()
    sub.ai_verdict, sub.ai_checks = None, []
    log(session, "submitted", actor, sub.project_id, sub.unit_id, sub.item_id)


def request_na(session: Session, sub: Submission, reason: str, actor: str) -> None:
    sub.status, sub.na_requested, sub.na_reason = "submitted", True, reason.strip()
    sub.submitted_by, sub.submitted_at = actor, now()
    log(session, "N/A requested", actor, sub.project_id, sub.unit_id, sub.item_id, reason)


def decide(session: Session, sub: Submission, decision: str, comment: str, actor: str) -> None:
    """Expert decision: approve | reject | na."""
    if decision == "approve":
        sub.status = "na" if sub.na_requested else "approved"
    elif decision == "reject":
        sub.status = "rejected"
    elif decision == "na":
        sub.status = "na"
        sub.na_reason = sub.na_reason or comment
    sub.review_comment, sub.reviewed_by, sub.reviewed_at = comment, actor, now()
    sub.reopened_reason = ""
    log(session, {"approve": "approved", "reject": "rejected", "na": "marked N/A"}[decision],
        actor, sub.project_id, sub.unit_id, sub.item_id, comment)


def reopen(session: Session, sub: Submission, reason: str, actor: str) -> None:
    sub.status, sub.na_auto = "pending", False
    sub.reopened_reason = reason
    log(session, "reopened", actor, sub.project_id, sub.unit_id, sub.item_id, reason)


# ---------------------------------------------------------------------------
# Progress
# ---------------------------------------------------------------------------

def subs_for(project: Project, unit: PackagingUnit | None) -> list[Submission]:
    """Unit view = that unit's items + the project-level items."""
    if unit is None:
        return list(project.submissions)
    return [s for s in project.submissions if s.unit_id in (unit.id, None)]


def progress(subs: list[Submission]) -> dict:
    c = Counter(s.status for s in subs)
    total = len(subs)
    done = c["approved"] + c["na"]
    return {"total": total, "done": done, "pct": round(100 * done / total) if total else 0,
            "counts": dict(c), "open": total - done,
            "awaiting_expert": c["ai_reviewed"], "awaiting_ai": c["submitted"],
            "rejected": c["rejected"], "pending": c["pending"]}


def category_progress(subs: list[Submission]) -> list[dict]:
    rows = []
    for cat in catalogue.categories():
        cs = [s for s in subs if catalogue.item(s.item_id)["cat"] == cat["id"]]
        rows.append({"cat": cat, **progress(cs)})
    return rows


def td_readiness(subs: list[Submission]) -> list[dict]:
    by_item: dict[str, list[Submission]] = {}
    for s in subs:
        by_item.setdefault(s.item_id, []).append(s)
    out = []
    for sec in catalogue.td_sections():
        rel = [s for iid in sec["items"] for s in by_item.get(iid, [])]
        done = sum(1 for s in rel if s.is_done)
        out.append({"section": sec, "total": len(rel), "done": done,
                    "pct": round(100 * done / len(rel)) if rel else 100})
    return out


def readiness(subs: list[Submission]) -> float:
    return progress(subs)["pct"] / 100


def project_stage(project: Project) -> str:
    if any(d.status == "issued" for d in project.documents) and \
            not any(d.status == "outdated" for d in project.documents):
        return "issued"
    p = progress(project.submissions)
    if p["done"] == p["total"]:
        return "ready"
    if p["awaiting_expert"] or p["awaiting_ai"]:
        return "review"
    return "collecting"


STAGE_LABEL = {"collecting": "Collecting data", "review": "Under review",
               "ready": "Ready to issue", "issued": "TD & DoC issued"}
STAGE_BADGE = {"collecting": "badge-muted", "review": "badge-info", "ready": "badge-warn",
               "issued": "badge-ok"}


# ---------------------------------------------------------------------------
# Identifiers
# ---------------------------------------------------------------------------

def next_unit_code(project: Project) -> str:
    n = max((int(u.code.split("-")[1]) for u in project.units if u.code.count("-") == 1), default=0)
    return f"PU-{n + 1:03d}"


def next_component_code(unit: PackagingUnit) -> str:
    n = max((int(c.code.rsplit("C", 1)[1]) for c in unit.components if "-C" in c.code), default=0)
    return f"{unit.code}-C{n + 1:03d}"


def next_evidence_code(session: Session, project: Project, unit: PackagingUnit | None,
                       component: Component | None, type_code: str) -> str:
    """PU-001-C001-TST-001 (evidence_id_structure.png). Project-level files use the PS code."""
    prefix = component.code if component else (unit.code if unit else project.ps_code)
    stem = f"{prefix}-{type_code}-"
    used = [e.code for e in session.query(Evidence).filter(Evidence.project_id == project.id,
                                                           Evidence.code.like(stem + "%"))]
    n = max((int(c.rsplit("-", 1)[1]) for c in used if c.rsplit("-", 1)[1].isdigit()), default=0)
    return f"{stem}{n + 1:03d}"

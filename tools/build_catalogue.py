"""Build app/seeds/catalogue.json from the V3.1 prototype's data model.

The V3.1 bilingual prototype (PPWR_资料收集与批复系统_V3.1_中英对照.html) defines the
16 categories / 69 data items, the TD V1.5 section map and the DoC V2.3 structure.
`tools/v31_prototype_data.json` is a verbatim dump of its JS constants. This script
turns it into the platform's catalogue: English-first, Chinese kept for the
bilingual labels, with the field definitions, applicability keys and evidence
type codes the platform needs.

    python3 tools/build_catalogue.py
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "tools" / "v31_prototype_data.json"
OUT = ROOT / "app" / "seeds" / "catalogue.json"

# Which PPWR requirement an item evidences. "core" items are always applicable;
# the others follow the project's applicability matrix (app/applicability.py).
ARTICLE = {
    4: "a5", 5: "a6", 6: "a7", 7: "a8", 8: "a9", 9: "a10", 10: "a11", 11: "a12",
}
ARTICLE_OVERRIDE = {
    "C04-17": "a5pfas", "C04-18": "a5pfas", "C15-60": "a5pfas", "C15-61": "a5pfas",
    "C15-62": "a7", "C11-44": "a11", "C07-25": "a8", "C08-28": "a9",
}

# Items the platform assembles itself — they are never "collected" from the client.
SYSTEM_ITEMS = {
    "C02-06": "Built from the packaging BOM (Packaging & BOM tab).",
    "C14-55": "Built from the evidence vault — every file carries its Evidence ID.",
    "C16-67": "Cross-references are generated with the TD from approved items and evidence.",
    "C16-68": "Generated from the applicability matrix (Overview tab).",
}

# Items collected once per project rather than per packaging unit.
PROJECT_LEVEL = {"C12-46", "C14-54", "C14-55", "C16-66", "C16-67", "C16-68", "C16-69"}

# Suggested evidence type code (evidence_id_structure.png):
# DRW Drawing · TST Test report · DCL Declaration · MSD Material spec · PHO Photo
# BOM · CAL Calculation · plus REC Record · CRT Certificate · RPT Assessment report
EVIDENCE_CODE = {
    "C01-01": "BOM", "C01-02": "BOM", "C01-03": "DCL", "C01-04": "REC", "C01-05": "PHO",
    "C02-06": "BOM", "C02-07": "MSD", "C02-08": "DCL", "C02-09": "DCL",
    "C03-10": "DRW", "C03-11": "DRW", "C03-12": "DRW", "C03-13": "MSD", "C03-14": "REC",
    "C03-15": "RPT", "C04-16": "TST", "C04-17": "TST", "C04-18": "DCL",
    "C05-19": "RPT", "C05-20": "TST", "C05-21": "RPT", "C06-22": "CAL", "C06-23": "CRT",
    "C07-24": "TST", "C07-25": "PHO", "C08-26": "RPT", "C08-27": "TST", "C08-28": "PHO",
    "C09-29": "RPT", "C09-30": "TST", "C09-31": "REC", "C09-32": "TST", "C09-33": "RPT",
    "C09-34": "RPT", "C09-35": "CAL", "C09-36": "RPT", "C10-37": "RPT", "C10-38": "TST",
    "C10-39": "RPT", "C11-40": "PHO", "C11-41": "PHO", "C11-42": "PHO", "C11-43": "PHO",
    "C11-44": "PHO", "C11-45": "PHO", "C12-46": "RPT", "C12-47": "REC", "C12-48": "RPT",
    "C12-49": "REC", "C12-50": "REC", "C13-51": "REC", "C13-52": "REC", "C13-53": "REC",
    "C14-54": "REC", "C14-55": "REC", "C15-56": "DCL", "C15-57": "MSD", "C15-58": "DCL",
    "C15-59": "TST", "C15-60": "DCL", "C15-61": "DCL", "C15-62": "CRT", "C15-63": "DCL",
    "C15-64": "DCL", "C15-65": "DCL", "C16-66": "DCL", "C16-67": "REC", "C16-68": "RPT",
    "C16-69": "REC",
}

# English legal basis (the prototype's `legal` mixes article refs with Chinese notes).
LEGAL_EN = {
    "C01-01": "Art 3(1), Art 12(2); Annex VII", "C01-02": "Annex VII (identification in the TD)",
    "C01-03": "Annex VII; Art 15(4) series production stays in conformity",
    "C01-04": "Art 10 minimisation; Art 24 empty space; Annex IV",
    "C01-05": "Annex VII (identification and verification)",
    "C02-06": "Art 6(1)(2), Annex II criteria; Art 10", "C02-07": "Art 6; Art 5(4) evidence chain",
    "C02-08": "Art 5(4); Annex II", "C02-09": "Art 6(3) component compatibility; Art 5(4)",
    "C03-10": "Art 6(1); Art 10(1); Annex VII 2(b)", "C03-11": "Art 6(1); Art 10(1); Annex VII 2(b)",
    "C03-12": "Art 12 labelling; Art 6(3) label separability", "C03-13": "Annex VII point 3 (manufacturing)",
    "C03-14": "Annex VII point 3 (manufacturing)", "C03-15": "Art 6(1), Art 10(1); Annex IV; Annex VII 2(c)",
    "C04-16": "Art 5(4): Pb+Cd+Hg+Cr(VI) ≤ 100 mg/kg from 12 Aug 2026",
    "C04-17": "Art 5(5): PFAS limits for food-contact packaging (25 ppb / 250 ppb / 50 ppm)",
    "C04-18": "Art 5(5) applicability; Regulation (EC) 1935/2004 where food-contact",
    "C05-19": "Art 6(1), Annex II; transitional method (EN 13430 / EN 18120 series)",
    "C05-20": "Art 6(3) separable / integrated components", "C05-21": "Art 6(4) — method before the delegated acts apply",
    "C06-22": "Art 7 (plastic packaging only), from 1 Jan 2030", "C06-23": "Art 7(8) verification of recycled content",
    "C07-24": "Art 8 (biobased feedstock in plastic packaging)", "C07-25": "Art 8; Art 12 labelling of claims",
    "C08-26": "Art 9: tea/coffee pods, fruit stickers, very lightweight bags (from 12 Feb 2028)",
    "C08-27": "Art 9; Annex III; EN 13432 industrial composting", "C08-28": "Art 9(2); Art 12 labelling",
    "C09-29": "Art 10(1) from 1 Jan 2030; Annex IV performance criteria",
    "C09-30": "Annex IV — product protection", "C09-31": "Annex IV — manufacturing process",
    "C09-32": "Annex IV — logistics", "C09-33": "Annex IV — packaging functionality",
    "C09-34": "Annex IV — information, hygiene and safety",
    "C09-35": "Art 24: empty space ratio ≤ 50 % (grouped, transport, e-commerce) from 2030",
    "C09-36": "Art 10(2)-(3): double walls, false bottoms; design rights before 11 Feb 2025",
    "C10-37": "Art 11 (reusable packaging criteria)", "C10-38": "Art 11(1)(c)(d)",
    "C10-39": "Art 11(1)(e)(f); Annex VI", "C11-40": "Art 15(6) manufacturer name and postal address; Art 12",
    "C11-41": "Art 15(5) type, batch or serial number",
    "C11-42": "Art 12(1) material composition and sorting label",
    "C11-43": "Art 12(4) data carrier (QR code)", "C11-44": "Art 12(3) reusable / DRS marking",
    "C11-45": "Art 12(9) Member-State specific information", "C12-46": "Annex VII point 2: risk analysis",
    "C12-47": "Art 15(4) re-assessment when design or supply changes", "C12-48": "Art 39(2) DoC continuously updated",
    "C12-49": "Art 10 conclusion maintained", "C12-50": "Art 12 labelling maintained",
    "C13-51": "Art 15(4); Annex VII point 3", "C13-52": "Art 15(4); Annex VII point 3",
    "C13-53": "Art 15(4); Annex VII point 3",
    "C14-54": "Annex VII 2(d); Art 36–37 harmonised standards and common specifications",
    "C14-55": "Annex VII 2(f) test reports; Annex VIII", "C15-56": "Supply-chain evidence for Art 15(2) conformity assessment",
    "C15-57": "Art 6; Art 5(4)", "C15-58": "Art 5(4); Annex II", "C15-59": "Art 5(4) (≤ 100 mg/kg)",
    "C15-60": "Art 5(5)", "C15-61": "Art 5(5); Regulation (EC) 1935/2004", "C15-62": "Art 7",
    "C15-63": "Art 6", "C15-64": "Art 6(3); Art 5(4)", "C15-65": "Art 15(4) change notification",
    "C16-66": "Art 39 + Annex VIII (EU declaration of conformity)",
    "C16-67": "Annex VII / VIII — conclusions ↔ evidence", "C16-68": "Annex VII — rationale for N/A items",
    "C16-69": "Annex VII point 4 — manufacturer approval before the DoC is signed",
}

SEL = "sel"
FIELDS_EN = {
    "C01-01": [("upi", "UPI — unique packaging identifier", "text"),
               ("pkgName", "Packaging name / description", "text"),
               ("pkgType", "Packaging level (sales / grouped / transport / e-commerce)", "text")],
    "C01-02": [("sku", "Packaged product / SKU / model range", "text")],
    "C01-03": [("sup", "Packaging supplier", "text"), ("site", "Manufacturing site", "text"),
               ("country", "Country of manufacture", "text")],
    "C01-04": [("mass", "Total packaging mass (g)", "text"), ("dims", "Dimensions L × W × H (mm)", "text")],
    "C01-05": [("ref", "Photo / artwork reference", "text")],
    "C03-10": [("docno", "Drawing number / revision", "text")],
    "C03-11": [("docno", "Drawing number / revision", "text")],
    "C03-12": [("docno", "Artwork number / revision", "text")],
    "C03-13": [("docno", "Specification number / revision", "text")],
    "C03-14": [("docno", "Control plan number / revision", "text")],
    "C03-15": [("rationale", "Design rationale (protection, logistics, function, information)", "ta")],
    "C04-16": [("res", "Result — sum of Pb+Cd+Hg+Cr(VI) (mg/kg)", "text"),
               ("method", "Test method (e.g. EN 13657 digestion + ICP-OES)", "text")],
    "C04-17": [("app", "PFAS applicability", SEL, ["Not applicable (non food-contact)",
                                                    "Applicable (food-contact)", "To be confirmed"]),
               ("note", "Rationale / result", "ta")],
    "C04-18": [("app", "Food-contact status", SEL, ["No — not food-contact", "Yes — food-contact",
                                                     "To be confirmed"])],
    "C05-19": [("concl", "Recyclability assessment conclusion", "ta")],
    "C05-21": [("method", "Method / standard applied (e.g. EN 13430, EN 18120-x)", "text")],
    "C06-22": [("app", "Recycled-content applicability", SEL, ["Not applicable (no plastic part)",
                                                                "Applicable (plastic packaging)",
                                                                "To be confirmed"]),
               ("pcr", "Recycled content (%) — plastic part", "text")],
    "C07-24": [("app", "Biobased feedstock", SEL, ["Not applicable", "Applicable (biobased claim)",
                                                    "To be confirmed"])],
    "C08-26": [("app", "Compostability (Art 9 packaging)", SEL, ["Not applicable",
                                                                  "Applicable (Art 9 packaging)",
                                                                  "To be confirmed"])],
    "C09-29": [("concl", "Minimisation assessment conclusion", "ta")],
    "C09-35": [("note", "Empty-space ratio assessment", "ta")],
    "C09-36": [("app", "Double wall / false bottom", SEL, ["None", "Present — exemption applies",
                                                            "Present — to be assessed"])],
    "C10-37": [("app", "Single-use or reusable", SEL, ["Single-use (not applicable)", "Reusable",
                                                        "To be confirmed"])],
    "C11-40": [("loc", "Position of the information on the artwork", "text")],
    "C14-54": [],
    "C16-66": [("docNo", "EU DoC number", "text"), ("tdNo", "TD number / version", "text"),
               ("sign", "Signatory (name, function)", "text"), ("place", "Place of issue", "text")],
    "C16-69": [("prep", "Prepared by", "text"), ("rev", "Reviewed by", "text"),
               ("appr", "Approved by", "text")],
}

TABLES = {
    "C14-54": ["Standard / specification", "Edition", "Clause", "Requirement covered", "Evidence"],
}

# Short, practical "what good looks like" hints shown on the item page.
EXAMPLES = {
    "C01-01": "UPI format PU-001 within packaging system PS-001; every SKU must trace to ≥ 1 UPI.",
    "C01-05": "JPG/PNG ≥ 1024×768, plain background, natural light, scale reference; name PU-001-C001-PHO-001.",
    "C02-07": "e.g. Corrugated fibreboard, B-flute, 250 g/m² — supplier TDS as PDF.",
    "C03-10": "Drawing revision must match the artwork revision.",
    "C04-16": "Third-party report (ICP-OES / ICP-MS) covering every component incl. inks and adhesives, "
              "dated within 24 months. Example: Pb < 20, Cd < 10, Hg < 10, Cr(VI) < 10 → sum < 50 mg/kg ✓",
    "C04-17": "Non food-contact packaging: record 'Not applicable' with the reason.",
    "C05-19": "Mono-material paper: EN 13430 material-recycling route — material ID, main-component mass "
              "share, collection/sorting, compatibility of inks, adhesives, coatings and labels.",
    "C06-22": "Plastic parts only: plastic mass (g), PCR mass (g), PCR %, with ISCC PLUS / RCS chain of custody.",
    "C09-29": "Address each Annex IV criterion separately; if no further reduction is possible, give the "
              "technical reason.",
    "C09-30": "ISTA / ASTM transport, stacking, drop and compression tests.",
    "C12-46": "Risk of non-conformity per applicable article — likelihood, impact, control.",
    "C14-54": "EN 13427–EN 13432 (PPWD harmonised standards), EN 13657 + ICP-OES for heavy metals, "
              "EN 18120 series (design for recycling).",
    "C15-56": "Signed supplier declaration per key component, dated and referencing PPWR (EU) 2025/40.",
    "C16-66": "DoC number with year-month, e.g. DoC-2026-09-PS001; signed by a person with authority.",
    "C16-69": "Prepared (compliance engineer) → Reviewed (QA) → Approved (management).",
}


def main() -> None:
    src = json.loads(SRC.read_text(encoding="utf-8"))
    cats = []
    for c in src["CATS"]:
        cats.append({
            "id": c["id"], "name": c["en"], "name_zh": c["name"],
            "logic": src["CAT_EN_LOGIC"].get(str(c["id"]), ""), "td": c["td"],
            "article": ARTICLE.get(c["id"], "core"),
        })
    items = []
    for it in src["ITEMS"]:
        en = src["ITEM_EN"][it["id"]]
        fields = []
        for spec in FIELDS_EN.get(it["id"], []):
            f = {"k": spec[0], "label": spec[1], "type": spec[2]}
            if spec[2] == SEL:
                f["options"] = spec[3]
            fields.append(f)
        items.append({
            "id": it["id"], "cat": it["cat"], "name": en["n"], "name_zh": it["name"],
            "requirement": en["r"], "form_zh": it.get("form", ""),
            "legal": LEGAL_EN[it["id"]], "logic": en["lg"], "td": it["td"],
            "fields": fields, "table": TABLES.get(it["id"]),
            "article": ARTICLE_OVERRIDE.get(it["id"], ARTICLE.get(it["cat"], "core")),
            "evidence_code": EVIDENCE_CODE[it["id"]],
            "system": SYSTEM_ITEMS.get(it["id"]),
            "scope": "project" if it["id"] in PROJECT_LEVEL else "unit",
            "example": EXAMPLES.get(it["id"], ""),
        })
    names = {"T00": "Cover Information 封面信息表"}
    td_sections = [{"no": s["no"], "name": names.get(s["no"], s["nm"]), "items": s["items"]}
                   for s in src["TD_SECTIONS"]]
    OUT.write_text(json.dumps({"categories": cats, "items": items, "td_sections": td_sections},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}: {len(cats)} categories, {len(items)} items, "
          f"{len(td_sections)} TD sections")


if __name__ == "__main__":
    main()

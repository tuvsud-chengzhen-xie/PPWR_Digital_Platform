"""PPWR applicability matrix (TD §5).

Derived from the project profile (food contact, reusable, Art 9 packaging, biobased
claim) and the BOM (which material groups are present). Each row says whether an
article applies, from when, and why — the rationale is what TD §5 / §19 and the
N/A items (C16-68) quote. Items whose article is N/A are set to "Not applicable"
automatically, with this rationale, so nobody collects evidence that is not needed.
"""
from __future__ import annotations

from dataclasses import dataclass

from .db import Project

YES, NA, TRANSITIONAL = "Applicable", "Not applicable", "Transitional"


@dataclass
class Row:
    key: str
    article: str
    status: str
    applies_from: str
    basis: str
    evidence: str

    @property
    def badge(self) -> str:
        return {"Applicable": "badge-high", "Transitional": "badge-warn"}.get(self.status, "badge-muted")


def material_groups(project: Project) -> set[str]:
    return {c.material_group for u in project.units for c in u.components if c.material_group}


def matrix(project: Project) -> list[Row]:
    groups = material_groups(project)
    has_plastic = "plastic" in groups
    levels = {u.level for u in project.units}
    rows = [
        Row("a5", "Art 5 — Substances of concern (heavy metals)", YES, "12 Aug 2026",
            "Art 5(4): sum of Pb, Cd, Hg and Cr(VI) ≤ 100 mg/kg in packaging and each packaging component.",
            "Heavy-metal test report or supplier declaration (C04-16, C15-59)"),
        Row("a5pfas", "Art 5 — PFAS in food-contact packaging",
            YES if project.food_contact else NA, "12 Aug 2026",
            ("Art 5(5): food-contact packaging — PFAS limits 25 ppb (targeted), 250 ppb (sum), 50 ppm (total fluorine)."
             if project.food_contact else
             "Art 5(5) applies to food-contact packaging only; this packaging is declared non food-contact."),
            "PFAS test / declaration (C04-17, C04-18)" if project.food_contact else "N/A rationale (C16-68)"),
        Row("a6", "Art 6 — Recyclable packaging (design for recycling)", YES, "12 Aug 2026",
            "Art 6(1): all packaging shall be recyclable; assessed against Annex II categories. Until the "
            "delegated acts apply, the EN 13430 / EN 18120 methods are used.",
            "Recyclability assessment (C05-19–C05-21)"),
        Row("a6g", "Art 6 — Recyclability performance grades A/B/C", TRANSITIONAL, "1 Jan 2030",
            "Grades by delegated act; grade C minimum from 2030, grade B from 2038. Record the expected grade now.",
            "Grade estimate in the recyclability assessment"),
        Row("a7", "Art 7 — Minimum recycled content in plastic packaging",
            TRANSITIONAL if has_plastic else NA, "1 Jan 2030",
            ("Plastic part present — minimum recycled-content targets (30 % / 10 % / 35 % by format) apply from 2030; "
             "collect the PCR baseline now." if has_plastic else
             "Art 7 covers the plastic part of packaging only; the BOM contains no plastic component."),
            "PCR data and chain-of-custody (C06-22, C06-23)" if has_plastic else "N/A rationale (C16-68)"),
        Row("a8", "Art 8 — Biobased feedstock in plastic packaging",
            YES if project.biobased_claim else NA, "Review 2028",
            ("A biobased claim is made — biobased content must be substantiated (EN 16640)."
             if project.biobased_claim else "No biobased feedstock claim is made for this packaging."),
            "Biobased content test (C07-24)" if project.biobased_claim else "N/A rationale (C16-68)"),
        Row("a9", "Art 9 — Compostable packaging",
            YES if project.compostable_type else NA, "12 Feb 2028",
            ("Art 9(1) packaging (tea/coffee units, fruit stickers, very lightweight bags) — industrial "
             "compostability per Annex III / EN 13432." if project.compostable_type else
             "Not one of the packaging types listed in Art 9(1)."),
            "EN 13432 certificate (C08-26–C08-28)" if project.compostable_type else "N/A rationale (C16-68)"),
        Row("a10", "Art 10 — Packaging minimisation", TRANSITIONAL, "1 Jan 2030",
            "Art 10(1): weight and volume reduced to the minimum necessary, assessed with the Annex IV "
            "performance criteria. Art 24 empty-space ratio ≤ 50 % for grouped, transport and e-commerce "
            "packaging." + (" Transport / grouped level present." if levels & {"Grouped", "Transport", "E-commerce"} else ""),
            "Minimisation assessment (C09-29–C09-36)"),
        Row("a11", "Art 11 — Reusable packaging",
            YES if project.reusable else NA, "12 Aug 2026",
            ("Packaging is placed on the market as reusable — Art 11(1) criteria and Annex VI apply."
             if project.reusable else "Single-use packaging; not designed or placed on the market as reusable."),
            "Reusability assessment (C10-37–C10-39)" if project.reusable else "N/A rationale (C16-68)"),
        Row("a12", "Art 12 — Labelling of packaging", TRANSITIONAL, "12 Aug 2028",
            "Harmonised material-composition label from 12 Aug 2028 (implementing act). Collect the current "
            "artwork, material marking and Art 15(5)/(6) identification now.",
            "Artwork and label evidence (C11-40–C11-45)"),
    ]
    return rows


def status_for(project: Project, article_key: str) -> tuple[str, str]:
    """(status, rationale) of the article an item evidences. 'core' always applies."""
    if article_key == "core":
        return YES, ""
    for r in matrix(project):
        if r.key == article_key:
            return r.status, r.basis
    return YES, ""


def is_na(project: Project, article_key: str) -> bool:
    return status_for(project, article_key)[0] == NA

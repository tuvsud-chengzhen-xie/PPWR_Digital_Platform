"""The data-item catalogue: 16 categories · 69 items · TD V1.5 section map.

Source: the V3.1 bilingual prototype and Checklist V1.5 (built by tools/build_catalogue.py).
Read-only at runtime — the catalogue is the service definition, not client data.
"""
from __future__ import annotations

import json
from functools import lru_cache

from . import config

STATUS_LABEL = {
    "pending": "Not collected", "submitted": "Awaiting AI pre-review",
    "ai_reviewed": "Awaiting expert review", "approved": "Approved",
    "rejected": "Rejected — rework", "na": "Not applicable",
}
STATUS_BADGE = {
    "pending": "badge-muted", "submitted": "badge-info", "ai_reviewed": "badge-violet",
    "approved": "badge-ok", "rejected": "badge-high", "na": "badge-outline",
}
EVIDENCE_TYPES = {
    "DRW": "Drawing", "TST": "Test report", "DCL": "Declaration", "MSD": "Material spec / TDS",
    "PHO": "Photo / artwork", "BOM": "BOM / register", "CAL": "Calculation", "REC": "Record",
    "CRT": "Certificate", "RPT": "Assessment report", "DOC": "Other document",
}
CERT_TYPES = {
    "hm": "Heavy-metal test report (Pb+Cd+Hg+Cr(VI) ≤ 100 mg/kg)",
    "pf": "PFAS declaration / test (food contact)",
    "rc": "Recyclability declaration / assessment",
    "doc": "Supplier declaration of compliance",
    "td": "Technical data sheet (TDS)",
    "comp": "Material composition declaration",
    "pcr": "Recycled-content certificate (ISCC PLUS / RCS)",
    "iso": "ISO 9001 / 14001 certificate",
    "fsc": "FSC / PEFC chain of custody",
    "oth": "Other certificate / report",
}
CERT_SHORT = {"hm": "Heavy metals", "pf": "PFAS", "rc": "Recyclability", "doc": "Supplier DoC",
              "td": "TDS", "comp": "Composition", "pcr": "PCR", "iso": "ISO", "fsc": "FSC/PEFC",
              "oth": "Other"}
# Which catalogue items a supplier certificate evidences — the edges the change engine walks.
CERT_ITEMS = {
    "hm": ["C04-16", "C15-59"], "pf": ["C04-17", "C15-60"], "rc": ["C05-19", "C15-63"],
    "doc": ["C15-56"], "td": ["C02-07", "C15-57"], "comp": ["C02-08", "C15-58"],
    "pcr": ["C06-22", "C06-23", "C15-62"], "iso": ["C13-52"], "fsc": ["C15-56"], "oth": [],
}
# A material/formulation change re-opens the substance, recyclability and BOM items.
MATERIAL_CHANGE_ITEMS = ["C02-06", "C02-07", "C02-08", "C04-16", "C05-19", "C06-22",
                         "C12-48", "C15-57", "C15-58", "C15-59", "C15-63"]

MATERIAL_GROUPS = ["paper", "plastic", "glass", "metal", "wood", "textile", "other"]
UNIT_LEVELS = ["Sales", "Grouped", "Transport", "E-commerce"]
STRUCTURES = ["Mono-material", "Multi-layer", "Composite", "Other"]


@lru_cache(maxsize=1)
def _load() -> dict:
    return json.loads((config.SEEDS_DIR / "catalogue.json").read_text(encoding="utf-8"))


def categories() -> list[dict]:
    return _load()["categories"]


def items() -> list[dict]:
    return _load()["items"]


def td_sections() -> list[dict]:
    return _load()["td_sections"]


@lru_cache(maxsize=1)
def _by_id() -> dict:
    return {i["id"]: i for i in items()}


def item(item_id: str) -> dict | None:
    return _by_id().get(item_id)


def category(cat_id: int) -> dict | None:
    return next((c for c in categories() if c["id"] == cat_id), None)


def items_in(cat_id: int) -> list[dict]:
    return [i for i in items() if i["cat"] == cat_id]


def unit_items() -> list[dict]:
    return [i for i in items() if i["scope"] == "unit"]


def project_items() -> list[dict]:
    return [i for i in items() if i["scope"] == "project"]


def material_group_for(text: str) -> str:
    """Best-effort material group from a free-text material (BOM import)."""
    t = (text or "").lower()
    if any(k in t for k in ("paper", "board", "carton", "fibre", "fiber", "kraft", "pap")):
        return "paper"
    if any(k in t for k in ("pe", "pp", "pet", "ps", "pvc", "plastic", "film", "ldpe", "hdpe",
                            "laminate", "polymer", "opp", "bopp")):
        return "plastic"
    if "glass" in t:
        return "glass"
    if any(k in t for k in ("alu", "steel", "tin", "metal")):
        return "metal"
    if "wood" in t or "pallet" in t:
        return "wood"
    return "other"

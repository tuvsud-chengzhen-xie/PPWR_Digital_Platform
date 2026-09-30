"""Knowledge base: the regulation library, key dates, and the requirement catalogue."""
from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from .. import auth, catalogue, config
from ..db import User, get_session
from ..web import base_context, render

router = APIRouter()

FOLDER_LABEL = {
    "01": "PPWR and related regulation & acts", "02": "Harmonised standards under the PPWD",
    "03": "Implementing / delegated acts (in consultation)", "04": "Technical & common specifications",
    "05": "Interpretation and guidance",
}
KEY_DATES = [
    ("11 Feb 2025", "Entry into force", "PPWR (EU) 2025/40 enters into force; Directive 94/62/EC to be repealed.", "past"),
    ("12 Aug 2026", "General application", "Conformity assessment (Art 38), technical documentation (Annex VII), "
                                          "EU DoC (Art 39), Art 5 substance limits incl. PFAS for food contact.", "now"),
    ("12 Feb 2028", "Compostable packaging", "Art 9 — listed formats must be industrially compostable.", "next"),
    ("12 Aug 2028", "Harmonised labels", "Art 12 material-composition labelling (implementing act).", "next"),
    ("1 Jan 2030", "Design for recycling · recycled content · minimisation",
     "Art 6 grades A–C, Art 7 minimum recycled content, Art 10 minimisation, Art 24 empty space ≤ 50 %.", "next"),
    ("1 Jan 2035", "Recycled at scale", "Art 6 recyclable-at-scale requirement.", "next"),
    ("1 Jan 2038", "Grade B minimum", "Only recyclability grades A and B may be placed on the market.", "next"),
    ("1 Jan 2040", "Higher recycled content targets", "Art 7 targets rise (e.g. 65 % for contact-sensitive PET).", "next"),
]
ARTICLE_MAP = [
    ("Art 5", "Substances of concern", "Heavy-metal report, REACH/SVHC screening, PFAS report or declaration"),
    ("Art 6", "Recyclability", "DfR assessment, recycling compatibility, ink / adhesive / coating data"),
    ("Art 7", "Recycled content", "PCR %, recycled-content calculation, chain-of-custody certificates"),
    ("Art 8", "Biobased feedstock", "Biobased content declaration and test (EN 16640)"),
    ("Art 9", "Compostability", "Compostability declaration, EN 13432 test"),
    ("Art 10", "Minimisation", "Mass / volume calculation, performance evidence against Annex IV"),
    ("Art 11", "Reusability", "Reusability screening, system design record"),
    ("Art 12", "Labelling & information", "Final artwork, material marking, warnings, data carrier"),
]


@router.get("/knowledge", response_class=HTMLResponse)
def knowledge(request: Request, session: Session = Depends(get_session), user: User = Depends(auth.require_user)):
    folders = []
    if config.KNOWLEDGE_DIR.exists():
        for d in sorted(p for p in config.KNOWLEDGE_DIR.iterdir() if p.is_dir()):
            files = sorted(f for f in d.iterdir() if f.is_file() and f.suffix.lower() in (".pdf", ".html"))
            folders.append({"label": FOLDER_LABEL.get(d.name[:2], d.name), "name": d.name,
                            "files": [{"name": f.stem, "ext": f.suffix.lstrip(".").upper(), "size": f.stat().st_size,
                                       "href": f"/kb-files/{quote(d.name)}/{quote(f.name)}"} for f in files]})
    kit = []
    if config.TEMPLATE_KIT_DIR.exists():
        for f in sorted(config.TEMPLATE_KIT_DIR.iterdir()):
            if f.suffix.lower() in (".xlsx", ".png"):
                kit.append({"name": f.name, "href": f"/kit/{quote(f.name)}", "ext": f.suffix.lstrip(".").upper(),
                            "size": f.stat().st_size})
    return render("knowledge.html", base_context(request, session, "knowledge", folders=folders, kit=kit,
                                                 dates=KEY_DATES, article_map=ARTICLE_MAP,
                                                 cats=catalogue.categories(), items=catalogue.items(),
                                                 sections=catalogue.td_sections()))

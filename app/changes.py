"""Change impact engine — "one change anywhere, traceable everywhere".

A supplier-side change (a new certificate, a resin swap, an expiring report) is
walked down the graph: supplier material → components → packaging units →
projects → catalogue items → TD / DoC documents. The impact is shown before
anything moves; applying it re-opens the affected items for AI pre-review +
expert review and marks the issued TD / DoC "update required" — Art 39(2):
the DoC shall be continuously updated.
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy.orm import Session

from . import applicability, catalogue, config
from .db import (Certificate, ChangeEvent, Component, Document, Project, Submission,
                 SupplierMaterial, log, now)

KIND_LABEL = {"certificate_update": "Certificate updated", "material_change": "Material / formulation change",
              "certificate_expiry": "Certificate expiring", "supplier_change": "Supplier change"}


def affected_items(doc_types: list[str], kind: str) -> list[str]:
    """Catalogue items that rest on the changed supplier data. Platform-assembled
    items (BOM, evidence register) are left out — they re-sync themselves."""
    out: list[str] = []
    if kind in ("material_change", "supplier_change"):
        out = list(catalogue.MATERIAL_CHANGE_ITEMS)
    for t in doc_types:
        for iid in catalogue.CERT_ITEMS.get(t, []):
            if iid not in out:
                out.append(iid)
    return [i for i in out if not catalogue.item(i).get("system")]


def impact_of(session: Session, material: SupplierMaterial, doc_types: list[str], kind: str) -> dict:
    comps = session.query(Component).filter(Component.supplier_material_id == material.id).all()
    item_ids = affected_items(doc_types, kind)
    units, projects, subs, docs, skus = {}, {}, [], [], set()
    for c in comps:
        u, p = c.unit, c.unit.project
        units[u.id] = {"unit": u.code, "name": u.name, "project": p.code, "project_id": p.id}
        projects[p.id] = {"code": p.code, "title": p.title, "scenario": p.scenario}
        skus.update(s.strip() for s in (u.skus or "").replace(";", "/").split("/") if s.strip())
    for pid in projects:
        project = session.get(Project, pid)
        unit_ids = {uid for uid, v in units.items() if v["project_id"] == pid}
        for s in project.submissions:
            if s.item_id not in item_ids or s.unit_id not in unit_ids | {None}:
                continue
            if s.unit_id is None and s.item_id not in ("C16-66",):
                continue
            if s.status == "pending" or (s.status == "na" and s.na_auto):
                continue  # nothing collected yet — the new supplier data is used when it is
            art = catalogue.item(s.item_id)["article"]
            if applicability.is_na(project, art):
                continue
            subs.append(s.id)
        for d in project.documents:
            if d.status in ("issued", "draft") and (d.unit_id is None or d.unit_id in unit_ids):
                docs.append(d.id)
    return {
        "material": f"{material.code} · {material.name}", "supplier": material.supplier.name,
        "components": [c.code for c in comps], "units": list(units.values()),
        "projects": list(projects.values()), "skus": sorted(skus), "items": item_ids,
        "submissions": subs, "documents": docs,
        "td_due": sum(1 for d in session.query(Document).filter(Document.id.in_(docs)) if d.kind == "TD") if docs else 0,
        "doc_due": sum(1 for d in session.query(Document).filter(Document.id.in_(docs)) if d.kind == "DOC") if docs else 0,
    }


def next_code(session: Session) -> str:
    n = session.query(ChangeEvent).count()
    return f"CHG-{n + 1:04d}"


def raise_change(session: Session, material: SupplierMaterial, kind: str, title: str,
                 description: str, doc_types: list[str], actor: str,
                 certificate: Certificate | None = None) -> ChangeEvent:
    ev = ChangeEvent(code=next_code(session), client_id=material.supplier.client_id,
                     supplier_material_id=material.id, certificate_id=certificate.id if certificate else None,
                     kind=kind, title=title, description=description, created_by=actor)
    ev.doc_types = doc_types
    ev.impact = impact_of(session, material, doc_types, kind)
    session.add(ev)
    session.flush()
    log(session, f"change raised {ev.code}", actor, comment=title)
    return ev


def apply_change(session: Session, ev: ChangeEvent, actor: str) -> dict:
    """Re-open affected items and flag documents. Recomputes the impact first —
    the BOM may have moved since the change was raised."""
    impact = impact_of(session, ev.supplier_material, ev.doc_types, ev.kind)
    reason = f"{ev.code}: {ev.title}"
    reopened = 0
    for sid in impact["submissions"]:
        s = session.get(Submission, sid)
        if s.status in ("approved", "ai_reviewed", "rejected"):
            # data stays; the AI pre-review re-runs against the changed supplier data
            s.status, s.reopened_reason = "submitted", reason
            s.ai_verdict, s.ai_checks = None, []
            reopened += 1
            log(session, "reopened by change", actor, s.project_id, s.unit_id, s.item_id, reason)
        elif s.status == "na" and not s.na_auto:
            s.status, s.reopened_reason = "pending", reason
            reopened += 1
    flagged = 0
    for did in impact["documents"]:
        d = session.get(Document, did)
        d.status, d.outdated_reason = "outdated", f"Update required — {reason}"
        flagged += 1
    impact.update(reopened=reopened, flagged=flagged)
    ev.impact, ev.status, ev.applied_at, ev.applied_by = impact, "applied", now(), actor
    log(session, f"change applied {ev.code}", actor, comment=f"{reopened} items re-opened, {flagged} documents flagged")
    return impact


def expiring(session: Session, client_ids: list[int] | None = None, window: int | None = None):
    window = config.EXPIRY_WINDOW_DAYS if window is None else window
    limit = dt.date.today() + dt.timedelta(days=window)
    q = session.query(Certificate).filter(Certificate.status == "valid", Certificate.expires.isnot(None),
                                          Certificate.expires <= limit)
    certs = q.all()
    if client_ids is not None:
        certs = [c for c in certs if c.material.supplier.client_id in client_ids]
    return sorted(certs, key=lambda c: c.expires)


def scan_expiries(session: Session) -> int:
    """Raise one open change per certificate entering the expiry window (deduplicated)."""
    raised = 0
    for cert in expiring(session):
        exists = session.query(ChangeEvent).filter(ChangeEvent.certificate_id == cert.id,
                                                   ChangeEvent.kind == "certificate_expiry").first()
        if exists:
            continue
        days = (cert.expires - dt.date.today()).days
        when = f"expired {-days} days ago" if days < 0 else f"expires in {days} days"
        raise_change(session, cert.material, "certificate_expiry",
                     f"{catalogue.CERT_SHORT[cert.doc_type]} certificate {cert.number or ''} {when}".replace("  ", " "),
                     f"{cert.material.supplier.name} — {cert.material.name} ({cert.material.trace_code}). "
                     f"Request a renewed report from the supplier; the evidence behind the items below lapses on "
                     f"{cert.expires:%d %b %Y}.", [cert.doc_type], "Platform (expiry watch)", cert)
        raised += 1
    return raised

"""Supplier library (materials + certificates) and the change-impact engine."""
from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from sqlalchemy.orm import Session

from .. import auth, catalogue, changes, config, storage
from ..db import Certificate, ChangeEvent, Client, Supplier, SupplierMaterial, User, get_session, log
from ..web import base_context, redirect, render

router = APIRouter()


def _cert_state(cert: Certificate) -> str:
    if not cert.expires:
        return "valid"
    days = (cert.expires - dt.date.today()).days
    return "expired" if days < 0 else "expiring" if days <= config.EXPIRY_WINDOW_DAYS else "valid"


@router.get("/suppliers", response_class=HTMLResponse)
def library(request: Request, q: Optional[str] = None, session: Session = Depends(get_session),
            user: User = Depends(auth.require_user)):
    sups = auth.visible_suppliers(session, user).order_by(Supplier.client_id, Supplier.code).all()
    if q:
        ql = q.lower()
        sups = [s for s in sups if ql in s.name.lower() or any(ql in (m.trace_code or "").lower()
                                                               or ql in m.name.lower() for m in s.materials)]
    rows = []
    for s in sups:
        certs = [c for m in s.materials for c in m.certificates if c.status == "valid"]
        rows.append({"s": s, "materials": len(s.materials), "certs": len(certs),
                     "flags": sum(1 for c in certs if _cert_state(c) != "valid"),
                     "used": sum(len(m.components) for m in s.materials)})
    clients = session.query(Client).order_by(Client.name).all() if user.is_expert else [user.client]
    return render("suppliers.html", base_context(request, session, "suppliers", rows=rows, q=q or "",
                                                 clients=clients,
                                                 expiring=changes.expiring(session, auth.client_ids(session, user))))


@router.post("/suppliers")
def supplier_create(name: str = Form(...), country: str = Form(""), address: str = Form(""), contact: str = Form(""),
                    client_id: Optional[int] = Form(None), session: Session = Depends(get_session),
                    user: User = Depends(auth.require_user)):
    cid = client_id if user.is_expert and client_id else user.client_id
    n = session.query(Supplier).filter(Supplier.client_id == cid).count() + 1
    s = Supplier(client_id=cid, code=f"SUP-{n:03d}", name=name.strip(), country=country.strip(),
                 address=address.strip(), contact=contact.strip())
    session.add(s)
    session.commit()
    return redirect(f"/suppliers/{s.id}", f"{s.code} {s.name} added")


@router.get("/suppliers/{sid}", response_class=HTMLResponse)
def supplier(sid: int, request: Request, session: Session = Depends(get_session),
             user: User = Depends(auth.require_user)):
    s = auth.get_supplier(session, user, sid)
    mats = []
    for m in s.materials:
        mats.append({"m": m, "certs": [{"c": c, "state": _cert_state(c)} for c in m.certificates],
                     "uses": [{"c": c, "u": c.unit, "p": c.unit.project} for c in m.components]})
    events = session.query(ChangeEvent).filter(ChangeEvent.supplier_material_id.in_([m.id for m in s.materials])) \
        .order_by(ChangeEvent.created_at.desc()).all() if s.materials else []
    n_mat = session.query(SupplierMaterial).join(Supplier).filter(Supplier.client_id == s.client_id).count() + 1
    return render("supplier.html", base_context(request, session, "suppliers", s=s, mats=mats, events=events,
                                                next_spt=f"SPT-{n_mat:03d}"))


@router.post("/suppliers/{sid}/materials")
def material_add(sid: int, name: str = Form(...), trace_code: str = Form(""), material: str = Form(""),
                 material_group: str = Form(""), session: Session = Depends(get_session),
                 user: User = Depends(auth.require_user)):
    s = auth.get_supplier(session, user, sid)
    n = session.query(SupplierMaterial).join(Supplier).filter(Supplier.client_id == s.client_id).count() + 1
    m = SupplierMaterial(supplier=s, code=f"SPT-{n:03d}", name=name.strip(), trace_code=trace_code.strip(),
                         material=material.strip(),
                         material_group=material_group or catalogue.material_group_for(material or name))
    session.add(m)
    session.commit()
    return redirect(f"/suppliers/{sid}", f"{m.code} added — link it to BOM components on the project's Packaging tab.")


@router.post("/suppliers/{sid}/materials/{mid}/certificates")
async def certificate_add(sid: int, mid: int, doc_type: str = Form(...), number: str = Form(""),
                          issuer: str = Form(""), issued: str = Form(""), expires: str = Form(""),
                          value: str = Form(""), conclusion: str = Form("conform"),
                          file: Optional[UploadFile] = File(None), session: Session = Depends(get_session),
                          user: User = Depends(auth.require_user)):
    s = auth.get_supplier(session, user, sid)
    m = next((x for x in s.materials if x.id == mid), None)
    if m is None:
        raise HTTPException(404)
    cert = Certificate(material=m, doc_type=doc_type, number=number.strip(), issuer=issuer.strip(),
                       issued=dt.date.fromisoformat(issued) if issued else None,
                       expires=dt.date.fromisoformat(expires) if expires else None,
                       value=value.strip(), conclusion=conclusion)
    if file is not None and file.filename:
        data = await file.read()
        if data:
            cert.filename = storage.safe_name(file.filename)
            cert.stored_path = str(storage.save(f"suppliers/{s.code}", m.code, cert.filename, data))
    replaced = [c for c in m.certificates if c.doc_type == doc_type and c.status == "valid" and c is not cert]
    for old in replaced:
        old.status = "superseded"
    session.add(cert)
    session.flush()
    msg = f"{catalogue.CERT_SHORT[doc_type]} certificate saved"
    if m.components:
        # the evidence behind every component using this material has changed — trace it
        ev = changes.raise_change(
            session, m, "certificate_update",
            f"New {catalogue.CERT_SHORT[doc_type]} certificate {cert.number} for {m.name}",
            f"{s.name} provided {cert.number}" + (f" (result {cert.value})" if cert.value else "")
            + (f", replacing {', '.join(o.number for o in replaced)}" if replaced else "")
            + ". Items relying on this certificate should be re-checked.", [doc_type], user.display_name, cert)
        # an expiry warning for the certificate it replaces is resolved by this upload
        for old in replaced:
            for exp in session.query(ChangeEvent).filter(ChangeEvent.certificate_id == old.id,
                                                         ChangeEvent.status == "open"):
                exp.status = "dismissed"
        msg += f" — {ev.code} raised: {len(ev.impact['submissions'])} item(s) in " \
               f"{len(ev.impact['projects'])} project(s) are affected. Review the impact."
        session.commit()
        return redirect(f"/changes/{ev.id}", msg, "info")
    session.commit()
    return redirect(f"/suppliers/{sid}", msg)


@router.post("/suppliers/{sid}/materials/{mid}/change")
def material_change(sid: int, mid: int, title: str = Form(...), description: str = Form(""),
                    kind: str = Form("material_change"), session: Session = Depends(get_session),
                    user: User = Depends(auth.require_user)):
    s = auth.get_supplier(session, user, sid)
    m = next((x for x in s.materials if x.id == mid), None)
    if m is None:
        raise HTTPException(404)
    ev = changes.raise_change(session, m, kind, title.strip(), description.strip(), [], user.display_name)
    session.commit()
    return redirect(f"/changes/{ev.id}", f"{ev.code} raised — here is where it lands.", "info")


@router.get("/certificates/{cid}/download")
def certificate_download(cid: int, session: Session = Depends(get_session), user: User = Depends(auth.require_user)):
    c = session.get(Certificate, cid)
    if c is None:
        raise HTTPException(404)
    auth.get_supplier(session, user, c.material.supplier_id)
    if not c.stored_path or not Path(c.stored_path).exists():
        raise HTTPException(404, "No file on record")
    return FileResponse(c.stored_path, filename=c.filename)


# ---------------------------------------------------------------------------
# Change impact
# ---------------------------------------------------------------------------

@router.get("/changes", response_class=HTMLResponse)
def change_list(request: Request, session: Session = Depends(get_session), user: User = Depends(auth.require_user)):
    evs = auth.visible_changes(session, user).order_by(ChangeEvent.created_at.desc()).all()
    return render("changes.html", base_context(request, session, "changes", events=evs, KIND=changes.KIND_LABEL))


@router.get("/changes/{cid}", response_class=HTMLResponse)
def change_detail(cid: int, request: Request, session: Session = Depends(get_session),
                  user: User = Depends(auth.require_user)):
    ev = session.get(ChangeEvent, cid)
    if ev is None or (not user.is_expert and ev.client_id != user.client_id):
        raise HTTPException(404)
    live = changes.impact_of(session, ev.supplier_material, ev.doc_types, ev.kind) if ev.status == "open" else ev.impact
    from ..db import Document, Submission
    subs = session.query(Submission).filter(Submission.id.in_(live.get("submissions", []))).all() \
        if live.get("submissions") else []
    docs = session.query(Document).filter(Document.id.in_(live.get("documents", []))).all() \
        if live.get("documents") else []
    return render("change.html", base_context(request, session, "changes", ev=ev, impact=live, subs=subs, docs=docs,
                                              KIND=changes.KIND_LABEL))


@router.post("/changes/{cid}/apply")
def change_apply(cid: int, session: Session = Depends(get_session), user: User = Depends(auth.require_user)):
    ev = session.get(ChangeEvent, cid)
    if ev is None or (not user.is_expert and ev.client_id != user.client_id):
        raise HTTPException(404)
    if ev.status != "open":
        return redirect(f"/changes/{cid}", "This change has already been handled.", "info")
    impact = changes.apply_change(session, ev, user.display_name)
    session.commit()
    return redirect(f"/changes/{cid}", f"{ev.code} applied — {impact['reopened']} item(s) re-opened for review, "
                                       f"{impact['flagged']} document(s) flagged “update required”.")


@router.post("/changes/{cid}/dismiss")
def change_dismiss(cid: int, reason: str = Form(""), session: Session = Depends(get_session),
                   user: User = Depends(auth.require_expert)):
    ev = session.get(ChangeEvent, cid)
    if ev is None:
        raise HTTPException(404)
    ev.status = "dismissed"
    log(session, f"change dismissed {ev.code}", user.display_name, comment=reason)
    session.commit()
    return redirect("/changes", f"{ev.code} dismissed", "info")

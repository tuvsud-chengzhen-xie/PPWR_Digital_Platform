"""Evidence vault — every file gets an Evidence ID (PU-001-C001-TST-001)."""
from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, Response
from sqlalchemy.orm import Session

from .. import auth, catalogue, config, excel_io, storage, workflow
from ..db import Component, Evidence, Submission, User, get_session, log
from ..web import project_context, redirect, render

router = APIRouter()


@router.get("/projects/{pid}/evidence", response_class=HTMLResponse)
def vault(pid: int, request: Request, unit: Optional[str] = None, type: Optional[str] = None,
          session: Session = Depends(get_session), user: User = Depends(auth.require_user)):
    p = auth.get_project(session, user, pid)
    rows = list(p.evidence)
    if unit:
        rows = [e for e in rows if (str(e.unit_id) == unit) or (unit == "project" and e.unit_id is None)]
    if type:
        rows = [e for e in rows if e.type_code == type]
    today = dt.date.today()
    stale = {e.id for e in p.evidence if e.type_code == "TST" and e.issued_date
             and (today - e.issued_date).days / 30.44 > config.REPORT_MAX_AGE_MONTHS}
    uncovered = [c for u in p.units for c in u.components
                 if not any(e.component_id == c.id for e in p.evidence) and not c.supplier_material]
    return render("project/evidence.html", project_context(
        request, session, p, "evidence", rows=rows, unit_filter=unit or "", type_filter=type or "",
        stale=stale, uncovered=uncovered, total_size=sum(e.size or 0 for e in p.evidence)))


@router.post("/projects/{pid}/evidence")
async def upload(pid: int, file: UploadFile = File(...), title: str = Form(""), type_code: str = Form("DOC"),
                 sub_id: Optional[int] = Form(None), component_id: Optional[int] = Form(None),
                 unit_id: Optional[int] = Form(None), file_no: str = Form(""), issuer: str = Form(""),
                 issued_date: str = Form(""), conformity: str = Form("Conform"), back: str = Form(""),
                 session: Session = Depends(get_session), user: User = Depends(auth.require_user)):
    p = auth.get_project(session, user, pid)
    data = await file.read()
    back = back or f"/projects/{pid}/evidence"
    if not data:
        return redirect(back, "The file is empty.", "error")
    if len(data) > config.MAX_UPLOAD_MB * 1024 * 1024:
        return redirect(back, f"Files over {config.MAX_UPLOAD_MB} MB belong in object storage — not in this pilot.", "error")
    sub = session.get(Submission, sub_id) if sub_id else None
    if sub and sub.project_id != p.id:
        raise HTTPException(404)
    unit = None
    if sub and sub.unit_id:
        unit = sub.unit
    elif unit_id:
        unit = next((u for u in p.units if u.id == unit_id), None)
    comp = session.get(Component, component_id) if component_id else None
    if comp and comp.unit.project_id != p.id:
        comp = None
    if comp and unit is None:
        unit = comp.unit
    if sub and not type_code:
        type_code = catalogue.item(sub.item_id)["evidence_code"]
    code = workflow.next_evidence_code(session, p, unit, comp, type_code)
    fname = storage.safe_name(file.filename or "file")
    path = storage.save(p.code, code, fname, data)
    e = Evidence(project=p, unit_id=unit.id if unit else None, component_id=comp.id if comp else None,
                 item_id=sub.item_id if sub else None, code=code,
                 title=title.strip() or Path(fname).stem, type_code=type_code, file_no=file_no.strip(),
                 issuer=issuer.strip(), issued_date=dt.date.fromisoformat(issued_date) if issued_date else None,
                 responsible="Applicant", conformity=conformity, filename=fname, stored_path=str(path),
                 size=len(data), uploaded_by=user.display_name,
                 supplier_name=comp.supplier.name if comp and comp.supplier else "")
    session.add(e)
    session.flush()
    session.refresh(p)
    workflow.sync(session, p)
    log(session, "evidence uploaded", user.display_name, p.id, unit.id if unit else None,
        sub.item_id if sub else None, f"{code} {fname}")
    session.commit()
    return redirect(back, f"{code} added to the evidence vault")


@router.get("/evidence/{eid}/download")
def download(eid: int, session: Session = Depends(get_session), user: User = Depends(auth.require_user)):
    e = session.get(Evidence, eid)
    if e is None:
        raise HTTPException(404)
    auth.get_project(session, user, e.project_id)
    if not e.stored_path or not Path(e.stored_path).exists():
        raise HTTPException(404, "File not on disk")
    return FileResponse(e.stored_path, filename=f"{e.code}__{e.filename}")


@router.post("/evidence/{eid}/delete")
def delete(eid: int, back: str = Form(""), session: Session = Depends(get_session),
           user: User = Depends(auth.require_user)):
    e = session.get(Evidence, eid)
    if e is None:
        raise HTTPException(404)
    p = auth.get_project(session, user, e.project_id)
    if e.item_id:
        sub = next((s for s in p.submissions if s.item_id == e.item_id and s.unit_id in (e.unit_id, None)), None)
        if sub and sub.status == "approved" and not user.is_expert:
            return redirect(back or f"/projects/{p.id}/evidence",
                            "This file supports an approved item — ask the expert to re-open it first.", "warn")
    log(session, "evidence removed", user.display_name, p.id, e.unit_id, e.item_id, e.code)
    session.delete(e)
    session.commit()
    return redirect(back or f"/projects/{p.id}/evidence", "Evidence removed", "info")


@router.get("/projects/{pid}/evidence.xlsx")
def export(pid: int, session: Session = Depends(get_session), user: User = Depends(auth.require_user)):
    p = auth.get_project(session, user, pid)
    return Response(excel_io.export_evidence(p),
                    media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": f'attachment; filename="{p.code}_PPWR_Evidence_List.xlsx"'})

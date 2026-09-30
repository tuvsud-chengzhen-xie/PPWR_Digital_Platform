"""TD & DoC: readiness, generation, issue, download, authority dossier."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, Response
from sqlalchemy.orm import Session

from .. import auth, generator, workflow
from ..db import Document, User, get_session, log, now
from ..web import project_context, redirect, render

router = APIRouter()


@router.get("/projects/{pid}/documents", response_class=HTMLResponse)
def documents(pid: int, request: Request, session: Session = Depends(get_session),
              user: User = Depends(auth.require_user)):
    p = auth.get_project(session, user, pid)
    scopes = []
    for u in (p.units if p.scenario == "A" else [None]):
        subs = workflow.subs_for(p, u) if u else list(p.submissions)
        scopes.append({"unit": u, "prog": workflow.progress(subs), "sections": workflow.td_readiness(subs),
                       "td_no": generator.td_number(p, u), "doc_no": generator.doc_number(p, u)})
    current = [d for d in p.documents if d.status in ("draft", "issued", "outdated")]
    history = [d for d in p.documents if d.status == "superseded"]
    return render("project/documents.html", project_context(
        request, session, p, "documents", scopes=scopes, current=current, history=history[:20],
        ready=workflow.progress(p.submissions)["done"] == workflow.progress(p.submissions)["total"]))


@router.post("/projects/{pid}/documents/generate")
def generate(pid: int, session: Session = Depends(get_session), user: User = Depends(auth.require_user)):
    p = auth.get_project(session, user, pid)
    made = generator.generate(session, p, user.display_name)
    log(session, "documents generated", user.display_name, p.id, comment=", ".join(d.number for d in made))
    session.commit()
    return {"ok": True, "message": f"{len(made)} document(s) generated from live data.",
            "redirect": f"/projects/{pid}/documents"}


@router.post("/projects/{pid}/documents/issue")
def issue(pid: int, session: Session = Depends(get_session), user: User = Depends(auth.require_expert)):
    p = auth.get_project(session, user, pid)
    pr = workflow.progress(p.submissions)
    if pr["done"] < pr["total"]:
        return redirect(f"/projects/{pid}/documents", f"{pr['open']} item(s) are still open — issue is blocked.", "warn")
    drafts = [d for d in p.documents if d.status == "draft"]
    if not drafts or any(d.readiness < 1 for d in drafts):
        return redirect(f"/projects/{pid}/documents", "Generate the documents again first — the drafts pre-date the last approval.", "warn")
    for d in p.documents:
        if d.status in ("issued", "outdated"):
            d.status = "superseded"
    for d in drafts:
        d.status, d.issued_at, d.issued_by = "issued", now(), user.display_name
    log(session, "documents issued", user.display_name, p.id, comment=", ".join(d.number for d in drafts))
    session.commit()
    return redirect(f"/projects/{pid}/documents", f"{len(drafts)} document(s) issued — hand them to the client for signature.")


@router.get("/documents/{did}/download")
def download(did: int, session: Session = Depends(get_session), user: User = Depends(auth.require_user)):
    d = session.get(Document, did)
    if d is None:
        raise HTTPException(404)
    auth.get_project(session, user, d.project_id)
    if not Path(d.path).exists():
        raise HTTPException(404, "File not on disk — generate again")
    return FileResponse(d.path, filename=Path(d.path).name)


@router.get("/projects/{pid}/dossier.zip")
def dossier(pid: int, session: Session = Depends(get_session), user: User = Depends(auth.require_user)):
    p = auth.get_project(session, user, pid)
    docs = [d for d in p.documents if d.status == "issued"] or [d for d in p.documents if d.status == "draft"]
    data = generator.dossier_zip(p, docs)
    log(session, "dossier exported", user.display_name, p.id)
    session.commit()
    return Response(data, media_type="application/zip",
                    headers={"Content-Disposition": f'attachment; filename="{p.code}_PPWR_dossier.zip"'})

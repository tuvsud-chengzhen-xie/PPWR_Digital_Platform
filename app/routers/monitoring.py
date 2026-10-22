"""Regulatory monitoring: updates list, impact on the client's projects, acknowledgement, scan."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from .. import auth, monitor, rag
from ..db import RegUpdate, User, get_session, log
from ..web import base_context, redirect, render

router = APIRouter()


@router.get("/updates", response_class=HTMLResponse)
def updates(request: Request, kind: Optional[str] = None, unread: Optional[str] = None,
            session: Session = Depends(get_session), user: User = Depends(auth.require_user)):
    rows = monitor.visible_updates(session).all()
    seen = monitor.acked_ids(session, user)
    projects = auth.visible_projects(session, user).all()
    if kind:
        rows = [u for u in rows if u.kind == kind]
    if unread:
        rows = [u for u in rows if u.id not in seen]
    impacts = {u.id: monitor.impact(u, projects) for u in rows}
    return render("updates.html", base_context(request, session, "updates", rows=rows, seen=seen, impacts=impacts,
                                               kind=kind or "", unread=bool(unread), KIND=monitor.KIND_LABEL,
                                               STATUS=monitor.STATUS_LABEL, SEV=monitor.SEVERITY_BADGE,
                                               kb_url=rag.kb_url))


@router.get("/updates/{uid}", response_class=HTMLResponse)
def update_page(uid: int, request: Request, session: Session = Depends(get_session),
                user: User = Depends(auth.require_user)):
    u = session.get(RegUpdate, uid)
    if u is None:
        raise HTTPException(404)
    projects = auth.visible_projects(session, user).all()
    monitor.acknowledge(session, u, user)
    session.commit()
    src = rag.kb_url(u.source_path) if u.source_path and not u.source_path.startswith("http") else u.source_path
    return render("update.html", base_context(request, session, "updates", u=u, impact=monitor.impact(u, projects),
                                              KIND=monitor.KIND_LABEL, STATUS=monitor.STATUS_LABEL,
                                              SEV=monitor.SEVERITY_BADGE, src=src))


@router.post("/updates/ack-all")
def ack_all(session: Session = Depends(get_session), user: User = Depends(auth.require_user)):
    for u in session.query(RegUpdate):
        monitor.acknowledge(session, u, user)
    session.commit()
    return redirect("/updates", "All updates marked as read · 已全部标为已读", "info")


@router.post("/updates/scan")
def scan(session: Session = Depends(get_session), user: User = Depends(auth.require_expert)):
    res = monitor.scan(session, user.display_name)
    session.commit()
    n = len(res["created"])
    msg = (f"Baseline recorded for {res['files']} knowledge-base documents · 已建立基线" if res["baseline"] else
           f"{n} new or changed source(s) detected · 检测到 {n} 项新增或变更" if n else
           f"No changes in {res['files']} documents · {res['files']} 份文件无变化")
    return {"ok": True, "message": msg, "redirect": "/updates"}


@router.post("/updates/{uid}/review")
def mark_reviewed(uid: int, impact: str = Form(""), impact_zh: str = Form(""), severity: str = Form("info"),
                  session: Session = Depends(get_session), user: User = Depends(auth.require_expert)):
    u = session.get(RegUpdate, uid)
    if u is None:
        raise HTTPException(404)
    if impact.strip():
        u.impact = impact.strip()
    if impact_zh.strip():
        u.impact_zh = impact_zh.strip()
    u.severity = severity if severity in monitor.SEVERITY_BADGE else u.severity
    u.reviewed = True
    if u.status == "detected":
        u.status = "published" if u.kind in ("implementing", "regulation", "standard") else "guidance"
    log(session, f"regulatory update reviewed {u.code}", user.display_name)
    session.commit()
    return redirect(f"/updates/{uid}", "Update reviewed · 已审核")


@router.post("/updates/{uid}/recheck")
def recheck(uid: int, project_id: int = Form(...), session: Session = Depends(get_session),
            user: User = Depends(auth.require_expert)):
    u = session.get(RegUpdate, uid)
    if u is None:
        raise HTTPException(404)
    p = auth.get_project(session, user, project_id)
    n = monitor.recheck(session, u, p, user.display_name)
    session.commit()
    return redirect(f"/updates/{uid}", f"{n} approved item(s) in {p.code} sent back for re-assessment · {n} 项已退回重新评估")

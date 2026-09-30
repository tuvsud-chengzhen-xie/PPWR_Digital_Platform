"""Data collection (per item) and the two-stage review: AI pre-review → expert."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from .. import ai_review, applicability, auth, catalogue, workflow
from ..db import AuditEvent, Project, Submission, User, get_session
from ..web import base_context, project_context, redirect, render

router = APIRouter()


def _sub(session: Session, p: Project, sid: int) -> Submission:
    s = session.get(Submission, sid)
    if s is None or s.project_id != p.id:
        raise HTTPException(404, "Item not found")
    return s


def _evidence_for(p: Project, s: Submission):
    return [e for e in p.evidence if e.item_id == s.item_id and e.unit_id in (s.unit_id, None)]


# ---------------------------------------------------------------------------
# Collection board
# ---------------------------------------------------------------------------

@router.get("/projects/{pid}/collect", response_class=HTMLResponse)
def collect(pid: int, request: Request, unit: Optional[str] = None, status: Optional[str] = None,
            q: Optional[str] = None, session: Session = Depends(get_session),
            user: User = Depends(auth.require_user)):
    p = auth.get_project(session, user, pid)
    # unit="project" → project-level items; otherwise a unit id; default first unit
    if unit == "project":
        current, subs = None, [s for s in p.submissions if s.unit_id is None]
    else:
        current = next((u for u in p.units if str(u.id) == str(unit)), p.units[0] if p.units else None)
        subs = [s for s in p.submissions if current and s.unit_id == current.id]
    ev_count = {}
    for e in p.evidence:
        ev_count[(e.item_id, e.unit_id)] = ev_count.get((e.item_id, e.unit_id), 0) + 1
    shown = subs
    if status:
        shown = [s for s in shown if s.status == status]
    if q:
        ql = q.lower()
        shown = [s for s in shown if ql in s.item_id.lower() or ql in catalogue.item(s.item_id)["name"].lower()
                 or ql in catalogue.item(s.item_id)["name_zh"]]
    groups = []
    for cat in catalogue.categories():
        rows = [s for s in shown if catalogue.item(s.item_id)["cat"] == cat["id"]]
        if rows:
            all_in_cat = [s for s in subs if catalogue.item(s.item_id)["cat"] == cat["id"]]
            groups.append({"cat": cat, "rows": sorted(rows, key=lambda s: s.item_id),
                           "prog": workflow.progress(all_in_cat)})
    unit_tabs = [{"u": u, "prog": workflow.progress([s for s in p.submissions if s.unit_id == u.id])} for u in p.units]
    project_prog = workflow.progress([s for s in p.submissions if s.unit_id is None])
    return render("project/collect.html", project_context(
        request, session, p, "collect", current=current, groups=groups, unit_tabs=unit_tabs,
        project_prog=project_prog, unit_param=unit or (str(current.id) if current else "project"),
        status_filter=status or "", q=q or "", ev_count=ev_count, subs_prog=workflow.progress(subs)))


# ---------------------------------------------------------------------------
# One item
# ---------------------------------------------------------------------------

@router.get("/projects/{pid}/items/{sid}", response_class=HTMLResponse)
def item_page(pid: int, sid: int, request: Request, session: Session = Depends(get_session),
              user: User = Depends(auth.require_user)):
    p = auth.get_project(session, user, pid)
    s = _sub(session, p, sid)
    it = catalogue.item(s.item_id)
    art_status, art_basis = applicability.status_for(p, it["article"])
    history = session.query(AuditEvent).filter(AuditEvent.project_id == p.id, AuditEvent.item_id == s.item_id,
                                                AuditEvent.unit_id == s.unit_id).order_by(AuditEvent.at.desc()).all()
    # neighbours within the same unit, for keyboard-free next / previous
    peers = sorted([x for x in p.submissions if x.unit_id == s.unit_id], key=lambda x: x.item_id)
    idx = next(i for i, x in enumerate(peers) if x.id == s.id)
    open_peers = [x for x in peers[idx + 1:] + peers[:idx] if not x.is_done]
    unit_comps = s.unit.components if s.unit else [c for u in p.units for c in u.components]
    table = s.table or []
    if it.get("table") and not table:
        table = [[""] * len(it["table"]) for _ in range(3)]
    return render("project/item.html", project_context(
        request, session, p, "collect", s=s, it=it, cat=catalogue.category(it["cat"]),
        evidence=_evidence_for(p, s), art_status=art_status, art_basis=art_basis, history=history,
        prev=peers[idx - 1] if idx > 0 else None, next=peers[idx + 1] if idx + 1 < len(peers) else None,
        next_open=open_peers[0] if open_peers else None, comps=unit_comps, table=table,
        locked=s.status in ("approved", "na") and not user.is_expert))


@router.post("/projects/{pid}/items/{sid}/save")
async def item_save(pid: int, sid: int, request: Request, session: Session = Depends(get_session),
                    user: User = Depends(auth.require_user)):
    p = auth.get_project(session, user, pid)
    s = _sub(session, p, sid)
    form = await request.form()
    it = catalogue.item(s.item_id)
    if s.status in ("approved", "na") and not user.is_expert:
        return redirect(f"/projects/{pid}/items/{sid}", "Approved items are locked — ask the expert to re-open.", "warn")
    data = dict(s.data or {})
    for f in it.get("fields", []):
        if f"f_{f['k']}" in form:
            data[f["k"]] = str(form[f"f_{f['k']}"]).strip()
    s.data = data
    if it.get("table"):
        rows = []
        for r in range(int(form.get("t_rows", 0))):
            row = [str(form.get(f"t_{r}_{c}", "")).strip() for c in range(len(it["table"]))]
            if any(row):
                rows.append(row)
        s.table = rows
    action = form.get("action", "save")
    if action == "submit":
        workflow.submit(session, s, user.display_name)
        msg = "Submitted — the AI pre-review runs next."
    else:
        msg = "Saved as draft"
    session.commit()
    if action == "submit" and form.get("then") == "next":
        nxt = form.get("next_id")
        if nxt:
            return redirect(f"/projects/{pid}/items/{nxt}", msg)
    return redirect(f"/projects/{pid}/items/{sid}", msg)


@router.post("/projects/{pid}/items/{sid}/na")
def item_na(pid: int, sid: int, reason: str = Form(...), session: Session = Depends(get_session),
            user: User = Depends(auth.require_user)):
    p = auth.get_project(session, user, pid)
    s = _sub(session, p, sid)
    if user.is_expert:
        s.na_requested = True
        s.na_reason = reason.strip()
        workflow.decide(session, s, "na", reason.strip(), user.display_name)
        msg = "Marked not applicable"
    else:
        workflow.request_na(session, s, reason, user.display_name)
        msg = "N/A requested — the expert confirms it at review."
    session.commit()
    return redirect(f"/projects/{pid}/items/{sid}", msg)


@router.post("/projects/{pid}/items/{sid}/decide")
def item_decide(pid: int, sid: int, decision: str = Form(...), comment: str = Form(""),
                go_next: Optional[str] = Form(None), session: Session = Depends(get_session),
                user: User = Depends(auth.require_expert)):
    p = auth.get_project(session, user, pid)
    s = _sub(session, p, sid)
    if decision == "reject" and not comment.strip():
        return redirect(f"/projects/{pid}/items/{sid}", "Tell the client what to fix — a comment is required.", "warn")
    workflow.decide(session, s, decision, comment.strip(), user.display_name)
    session.commit()
    label = {"approve": "Approved", "reject": "Sent back for rework", "na": "Marked N/A"}[decision]
    if go_next:
        nxt = session.query(Submission).filter(Submission.project_id == p.id,
                                               Submission.status == "ai_reviewed").order_by(Submission.item_id).first()
        if nxt:
            return redirect(f"/projects/{pid}/items/{nxt.id}", f"{label} · next in queue")
        return redirect(f"/review?project={pid}", f"{label} — queue for this project is empty")
    return redirect(f"/projects/{pid}/items/{sid}", label)


@router.post("/projects/{pid}/items/{sid}/reopen")
def item_reopen(pid: int, sid: int, reason: str = Form("Re-opened by expert"), session: Session = Depends(get_session),
                user: User = Depends(auth.require_expert)):
    p = auth.get_project(session, user, pid)
    s = _sub(session, p, sid)
    workflow.reopen(session, s, reason, user.display_name)
    session.commit()
    return redirect(f"/projects/{pid}/items/{sid}", "Item re-opened", "info")


@router.post("/projects/{pid}/items/{sid}/ai")
def item_ai(pid: int, sid: int, session: Session = Depends(get_session), user: User = Depends(auth.require_user)):
    p = auth.get_project(session, user, pid)
    s = _sub(session, p, sid)
    if s.status not in ("submitted", "ai_reviewed"):
        return {"ok": False, "message": "Submit the item first."}
    ai_review.apply(s, p, s.unit, _evidence_for(p, s))
    session.commit()
    return {"ok": True, "verdict": s.ai_verdict, "message": ai_review.VERDICT_LABEL[s.ai_verdict],
            "redirect": f"/projects/{pid}/items/{sid}"}


# ---------------------------------------------------------------------------
# Review queue
# ---------------------------------------------------------------------------

@router.get("/review", response_class=HTMLResponse)
def queue(request: Request, project: Optional[int] = None, verdict: Optional[str] = None,
          session: Session = Depends(get_session), user: User = Depends(auth.require_user)):
    projects = auth.visible_projects(session, user).order_by(Project.code).all()
    scope = [p for p in projects if project is None or p.id == project]
    if user.is_expert:
        waiting_ai = [s for p in scope for s in p.submissions if s.status == "submitted"]
        waiting_expert = [s for p in scope for s in p.submissions if s.status == "ai_reviewed"]
        if verdict:
            waiting_expert = [s for s in waiting_expert if s.ai_verdict == verdict]
        rank = {"fail": 0, "warn": 1, "pass": 2}
        waiting_expert.sort(key=lambda s: (rank.get(s.ai_verdict, 3), s.project_id, s.item_id))
        waiting_ai.sort(key=lambda s: (s.project_id, s.item_id))
        recent = session.query(AuditEvent).filter(AuditEvent.project_id.in_([p.id for p in scope]),
                                                  AuditEvent.action.in_(("approved", "rejected", "marked N/A"))) \
            .order_by(AuditEvent.at.desc()).limit(15).all()
        return render("review.html", base_context(request, session, "review", projects=projects, scope_id=project,
                                                  waiting_ai=waiting_ai, waiting_expert=waiting_expert,
                                                  verdict=verdict or "", recent=recent,
                                                  pass_count=sum(1 for s in waiting_expert if s.ai_verdict == "pass")))
    rework = [s for p in scope for s in p.submissions if s.status == "rejected"]
    todo = [s for p in scope for s in p.submissions if s.status == "pending"]
    return render("my_actions.html", base_context(request, session, "review", projects=projects, scope_id=project,
                                                  rework=rework, todo=todo))


@router.post("/review/ai-run")
def run_ai(project: Optional[int] = Form(None), session: Session = Depends(get_session),
           user: User = Depends(auth.require_user)):
    projects = auth.visible_projects(session, user).all()
    scope = [p for p in projects if project is None or p.id == project]
    counts = {"pass": 0, "warn": 0, "fail": 0}
    for p in scope:
        for s in p.submissions:
            if s.status == "submitted":
                ai_review.apply(s, p, s.unit, _evidence_for(p, s))
                counts[s.ai_verdict] += 1
    session.commit()
    n = sum(counts.values())
    msg = (f"AI pre-review finished — {n} item(s): {counts['pass']} clear, {counts['warn']} to check, "
           f"{counts['fail']} with issues." if n else "Nothing waiting for AI pre-review.")
    return {"ok": True, "message": msg, "counts": counts,
            "redirect": "/review" + (f"?project={project}" if project else "")}


@router.post("/review/approve-clear")
def approve_clear(project: int = Form(...), session: Session = Depends(get_session),
                  user: User = Depends(auth.require_expert)):
    p = auth.get_project(session, user, project)
    n = 0
    for s in p.submissions:
        if s.status == "ai_reviewed" and s.ai_verdict == "pass":
            workflow.decide(session, s, "approve", "Approved in batch — AI pre-review clear.", user.display_name)
            n += 1
    session.commit()
    return redirect(f"/review?project={project}", f"{n} AI-clear item(s) approved")

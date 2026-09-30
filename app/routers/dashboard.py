"""Dashboard — action-first: what needs doing, then the portfolio."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from .. import auth, changes, workflow
from ..db import ChangeEvent, User, get_session
from ..web import base_context, render

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
def dashboard(request: Request, session: Session = Depends(get_session), user: User = Depends(auth.require_user)):
    projects = auth.visible_projects(session, user).order_by().all()
    subs = [s for p in projects for s in p.submissions]
    prog = workflow.progress(subs)
    docs = [d for p in projects for d in p.documents]
    issued = [d for d in docs if d.status == "issued"]
    outdated = [d for d in docs if d.status == "outdated"]
    expiring = changes.expiring(session, auth.client_ids(session, user))
    open_changes = auth.visible_changes(session, user).filter(ChangeEvent.status == "open") \
        .order_by(ChangeEvent.created_at.desc()).all()

    rows = []
    for p in sorted(projects, key=lambda p: p.target_date or p.created_at.date()):
        pr = workflow.progress(p.submissions)
        rows.append({"p": p, "prog": pr, "stage": workflow.project_stage(p),
                     "docs": [d for d in p.documents if d.status in ("issued", "outdated", "draft")]})

    todo = []
    for p in projects:
        pr = workflow.progress(p.submissions)
        link = f"/projects/{p.id}"
        if pr["rejected"]:
            todo.append(dict(level="red", owner="client", title=f"{pr['rejected']} item(s) sent back for rework",
                             sub=f"{p.code} · {p.title}", href=f"{link}/collect?status=rejected"))
        if pr["awaiting_ai"]:
            todo.append(dict(level="orange", owner="expert", title=f"{pr['awaiting_ai']} submission(s) waiting for AI pre-review",
                             sub=f"{p.code} · {p.client.name}", href=f"/review?project={p.id}"))
        if pr["awaiting_expert"]:
            todo.append(dict(level="orange", owner="expert", title=f"{pr['awaiting_expert']} item(s) ready for expert decision",
                             sub=f"{p.code} · {p.client.name}", href=f"/review?project={p.id}"))
        if workflow.project_stage(p) == "ready":
            todo.append(dict(level="green", owner="expert", title="All items closed — issue TD & DoC",
                             sub=f"{p.code} · {p.title}", href=f"{link}/documents"))
        if pr["pending"] and not user.is_expert:
            todo.append(dict(level="yellow", owner="client", title=f"{pr['pending']} item(s) still to collect",
                             sub=f"{p.code} · {p.title}", href=f"{link}/collect?status=pending"))
    for d in outdated:
        todo.append(dict(level="red", owner="expert", title=f"{d.kind} {d.number} needs an update",
                         sub=d.outdated_reason, href=f"/projects/{d.project_id}/documents"))
    for ev in open_changes:
        todo.append(dict(level="orange", owner="both", title=f"{ev.code} {ev.title}",
                         sub=f"{len(ev.impact.get('components', []))} component(s) · "
                             f"{len(ev.impact.get('submissions', []))} item(s) affected — review the impact",
                         href=f"/changes/{ev.id}"))
    rank = {"red": 0, "orange": 1, "yellow": 2, "green": 3}
    mine = [t for t in todo if t["owner"] in ("both", "expert" if user.is_expert else "client")]
    mine.sort(key=lambda t: rank[t["level"]])

    kpis = {
        "readiness": prog["pct"], "awaiting": prog["awaiting_expert"] + prog["awaiting_ai"],
        "to_action": prog["pending"] + prog["rejected"], "projects": len(projects),
        "issued": len(issued), "outdated": len(outdated), "expiring": len(expiring),
        "changes": len(open_changes), "total_items": prog["total"], "done": prog["done"],
        "drafts": sum(1 for d in docs if d.status == "draft"),
    }
    flow = [
        ("Collect", f"{prog['pending'] + prog['rejected']:,} open", "Client uploads data & evidence per item"),
        ("AI pre-review", f"{prog['awaiting_ai']:,} waiting", "Checks against the PPWR knowledge base"),
        ("Expert review", f"{prog['awaiting_expert']:,} waiting", "TÜV SÜD approves, rejects or marks N/A"),
        ("Generate", f"{kpis['drafts']:,} draft docs", "TD (Annex VII) & DoC (Annex VIII) from live data"),
        ("Issue & maintain", f"{len(issued):,} issued · {len(outdated)} outdated", "Changes re-open what they touch"),
    ]
    return render("dashboard.html", base_context(request, session, "dashboard", rows=rows, todo=mine[:9],
                                                 kpis=kpis, flow=flow, expiring=expiring[:6]))

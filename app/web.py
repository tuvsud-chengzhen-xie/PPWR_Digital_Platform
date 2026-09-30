"""Templates, filters and the shared page context."""
from __future__ import annotations

import datetime as dt
from typing import Optional
from urllib.parse import quote

import markupsafe
from fastapi import Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from . import ai_review, applicability, catalogue, config, workflow

templates = Jinja2Templates(directory=str(config.TEMPLATES_DIR))


def fmt_date(v) -> str:
    if not v:
        return "—"
    if isinstance(v, dt.datetime):
        return v.strftime("%d %b %Y %H:%M")
    if isinstance(v, dt.date):
        return v.strftime("%d %b %Y")
    return str(v)


def fmt_day(v) -> str:
    if not v:
        return "—"
    return v.strftime("%d %b %Y")


def days_until(v) -> Optional[int]:
    if not v:
        return None
    if isinstance(v, dt.datetime):
        v = v.date()
    return (v - dt.date.today()).days


def fmt_size(n) -> str:
    n = n or 0
    if n < 1024:
        return f"{n} B"
    if n < 1024 ** 2:
        return f"{n / 1024:.0f} KB"
    return f"{n / 1024 ** 2:.1f} MB"


def num(v) -> str:
    if v is None:
        return "—"
    if isinstance(v, float):
        return f"{v:,.2f}".rstrip("0").rstrip(".")
    return f"{v:,}"


def ago(v) -> str:
    if not v:
        return ""
    delta = dt.datetime.now() - v
    if delta.days >= 1:
        return f"{delta.days} d ago"
    h = delta.seconds // 3600
    if h:
        return f"{h} h ago"
    return f"{max(1, delta.seconds // 60)} min ago"


def nl2br(v):
    return markupsafe.Markup(markupsafe.escape(v or "").replace("\n", markupsafe.Markup("<br>")))


templates.env.filters.update(date=fmt_date, day=fmt_day, size=fmt_size, num=num, ago=ago, nl2br=nl2br,
                             days_until=days_until)
templates.env.globals.update(
    APP_NAME=config.APP_NAME, APP_SUB=config.APP_SUB, APP_VERSION=config.APP_VERSION,
    SERVICE_LINE=config.SERVICE_LINE, DISCLAIMER=config.DISCLAIMER,
    STATUS_LABEL=catalogue.STATUS_LABEL, STATUS_BADGE=catalogue.STATUS_BADGE,
    VERDICT_LABEL=ai_review.VERDICT_LABEL, VERDICT_BADGE=ai_review.VERDICT_BADGE,
    STAGE_LABEL=workflow.STAGE_LABEL, STAGE_BADGE=workflow.STAGE_BADGE,
    EVIDENCE_TYPES=catalogue.EVIDENCE_TYPES, CERT_TYPES=catalogue.CERT_TYPES, CERT_SHORT=catalogue.CERT_SHORT,
    MATERIAL_GROUPS=catalogue.MATERIAL_GROUPS, UNIT_LEVELS=catalogue.UNIT_LEVELS,
    STRUCTURES=catalogue.STRUCTURES, catalogue=catalogue, EXPIRY_WINDOW=config.EXPIRY_WINDOW_DAYS,
    today=dt.date.today,
)


def base_context(request: Request, session: Session, active: str, **extra) -> dict:
    from . import auth
    from .db import ChangeEvent, Submission
    user = auth.current_user(request, session)
    is_expert = bool(user and user.is_expert)
    ctx = {"request": request, "active": active, "user": user, "is_expert": is_expert}
    if user:
        projects = auth.visible_projects(session, user).all()
        pids = [p.id for p in projects]
        if is_expert:
            queue = session.query(Submission).filter(Submission.project_id.in_(pids),
                                                     Submission.status.in_(("submitted", "ai_reviewed"))).count()
        else:
            queue = session.query(Submission).filter(Submission.project_id.in_(pids),
                                                     Submission.status == "rejected").count()
        open_changes = auth.visible_changes(session, user).filter(ChangeEvent.status == "open").count()
        ctx.update(nav_queue=queue, nav_changes=open_changes)
    ctx.update(extra)
    return ctx


def render(name: str, ctx: dict):
    return templates.TemplateResponse(ctx["request"], name, ctx)


def redirect(url: str, message: str = "", kind: str = "success") -> RedirectResponse:
    if message:
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}toast={quote(message)}&toast_type={kind}"
    return RedirectResponse(url, status_code=303)


def project_context(request: Request, session: Session, project, tab: str, **extra) -> dict:
    ctx = base_context(request, session, "projects", project=project, tab=tab,
                       stage=workflow.project_stage(project),
                       prog=workflow.progress(project.submissions),
                       matrix=applicability.matrix(project), **extra)
    return ctx

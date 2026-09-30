"""Authentication and data scoping.

Two roles, one platform: TÜV SÜD experts (review, approve, issue) see every
client; client users (the manufacturer's packaging / compliance team) see only
their own projects, suppliers and documents — enforced here, not in templates.

PBKDF2-HMAC-SHA256 from the standard library, as in the other CPS CoE pilots; a
production deployment moves to the corporate IdP (SSO).
"""
from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import os
import secrets
from typing import Optional

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from .db import Client, ChangeEvent, Project, Supplier, User, get_session

ITERATIONS = 240_000


def hash_password(password: str, salt: Optional[str] = None) -> str:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), ITERATIONS)
    return f"pbkdf2_sha256${ITERATIONS}${salt}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, iterations, salt, digest = (stored or "").split("$")
        expected = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), int(iterations))
        return hmac.compare_digest(expected.hex(), digest)
    except (ValueError, AttributeError):
        return False


def session_secret() -> str:
    """Stable across restarts: env var, else a secret kept in the data folder."""
    if os.getenv("SESSION_SECRET"):
        return os.environ["SESSION_SECRET"]
    from . import config
    path = config.DATA_DIR / ".session_secret"
    if not path.exists():
        path.write_text(secrets.token_hex(32))
    return path.read_text().strip()


def current_user(request: Request, session: Session = Depends(get_session)) -> Optional[User]:
    user_id = request.session.get("user_id")
    return session.get(User, user_id) if user_id else None


def require_user(request: Request, session: Session = Depends(get_session)) -> User:
    user = current_user(request, session)
    if user is None:
        raise HTTPException(status_code=303, headers={"Location": "/login"})
    return user


def require_expert(request: Request, session: Session = Depends(get_session)) -> User:
    user = require_user(request, session)
    if not user.is_expert:
        raise HTTPException(status_code=303, headers={
            "Location": "/?toast=That%20action%20is%20for%20T%C3%9CV%20S%C3%9CD%20experts.&toast_type=warn"})
    return user


def login_user(request: Request, user: User) -> None:
    request.session["user_id"] = user.id
    user.last_login = dt.datetime.now().strftime("%Y-%m-%d %H:%M")


def logout_user(request: Request) -> None:
    request.session.clear()


# ---------------------------------------------------------------------------
# Scoping — the one place that decides what a user may see
# ---------------------------------------------------------------------------

def client_ids(session: Session, user: Optional[User]) -> Optional[list]:
    """None = all clients (expert)."""
    if user is None:
        return []
    if user.is_expert:
        return None
    return [user.client_id] if user.client_id else []


def visible_projects(session: Session, user: Optional[User]):
    q = session.query(Project)
    ids = client_ids(session, user)
    if ids is not None:
        q = q.filter(Project.client_id.in_(ids))
    return q


def visible_suppliers(session: Session, user: Optional[User]):
    q = session.query(Supplier)
    ids = client_ids(session, user)
    if ids is not None:
        q = q.filter(Supplier.client_id.in_(ids))
    return q


def visible_changes(session: Session, user: Optional[User]):
    q = session.query(ChangeEvent)
    ids = client_ids(session, user)
    if ids is not None:
        q = q.filter(ChangeEvent.client_id.in_(ids))
    return q


def get_project(session: Session, user: User, project_id: int) -> Project:
    p = session.get(Project, project_id)
    if p is None or (not user.is_expert and p.client_id != user.client_id):
        raise HTTPException(status_code=404, detail="Project not found")
    return p


def get_supplier(session: Session, user: User, supplier_id: int) -> Supplier:
    s = session.get(Supplier, supplier_id)
    if s is None or (not user.is_expert and s.client_id != user.client_id):
        raise HTTPException(status_code=404, detail="Supplier not found")
    return s


# ---------------------------------------------------------------------------
# Demo accounts
# ---------------------------------------------------------------------------

DEMO_ACCOUNTS = [
    dict(username="expert", password="demo", display_name="HDL PPWR Expert", role="expert", client=None),
    dict(username="lumen", password="demo", display_name="Lumen Home — Packaging Compliance",
         role="client", client="Lumen Home Products Co., Ltd."),
    dict(username="aurora", password="demo", display_name="Aurora Foods — Quality & Regulatory",
         role="client", client="Aurora Foods GmbH"),
]


def ensure_demo_users(session: Session) -> None:
    for spec in DEMO_ACCOUNTS:
        if session.query(User).filter_by(username=spec["username"]).first():
            continue
        client = session.query(Client).filter_by(name=spec["client"]).first() if spec["client"] else None
        session.add(User(username=spec["username"], display_name=spec["display_name"],
                         password_hash=hash_password(spec["password"]), role=spec["role"],
                         client_id=client.id if client else None))
    session.commit()

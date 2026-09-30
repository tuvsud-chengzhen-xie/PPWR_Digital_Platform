"""PPWR Digital Platform — TD & EU DoC service (CPS CoE × HDL).

Run from the project root:
    python3 -m uvicorn app.main:app --port 8130
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.sessions import SessionMiddleware

from . import auth, changes, config, seed
from .db import Base, SessionLocal, User, engine, get_session, init_db
from .routers import catalogue_views, dashboard, documents, evidence, projects, review, suppliers
from .web import base_context, redirect, render


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    with SessionLocal() as session:
        seed.seed(session)
        changes.scan_expiries(session)
        session.commit()
    yield


app = FastAPI(title=config.APP_NAME, lifespan=lifespan)
app.add_middleware(SessionMiddleware, secret_key=auth.session_secret(), session_cookie="ppwr_session",
                   max_age=60 * 60 * 12, same_site="lax")

app.mount("/ds", StaticFiles(directory=str(config.DESIGN_SYSTEM_DIR)), name="ds")
app.mount("/static", StaticFiles(directory=str(config.STATIC_DIR)), name="static")
if config.KNOWLEDGE_DIR.exists():
    app.mount("/kb-files", StaticFiles(directory=str(config.KNOWLEDGE_DIR)), name="kb")
if config.TEMPLATE_KIT_DIR.exists():
    app.mount("/kit", StaticFiles(directory=str(config.TEMPLATE_KIT_DIR)), name="kit")

for r in (dashboard, projects, review, evidence, documents, suppliers, catalogue_views):
    app.include_router(r.router)


@app.exception_handler(StarletteHTTPException)
async def http_exception(request: Request, exc: StarletteHTTPException):
    if exc.status_code == 303 and exc.headers and "Location" in exc.headers:
        return RedirectResponse(exc.headers["Location"], status_code=303)
    with SessionLocal() as session:
        ctx = base_context(request, session, "", code=exc.status_code, detail=exc.detail)
        resp = render("error.html", ctx)
        resp.status_code = exc.status_code
        return resp


# ---------------------------------------------------------------------------
# Sign-in
# ---------------------------------------------------------------------------

@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request, session: Session = Depends(get_session)):
    return render("login.html", base_context(request, session, "login", accounts=auth.DEMO_ACCOUNTS))


@app.post("/login")
def login(request: Request, username: str = Form(...), password: str = Form(...),
          session: Session = Depends(get_session)):
    user = session.query(User).filter_by(username=username.strip().lower()).first()
    if not user or not auth.verify_password(password, user.password_hash):
        return render("login.html", base_context(request, session, "login", accounts=auth.DEMO_ACCOUNTS,
                                                 error="Unknown user or wrong password."))
    auth.login_user(request, user)
    session.commit()
    return redirect("/", f"Signed in as {user.display_name}")


@app.post("/logout")
def logout(request: Request):
    auth.logout_user(request)
    return redirect("/login")


@app.post("/admin/reset")
def reset(request: Request, user: User = Depends(auth.require_expert)):
    """Restore the demo seed. Uploaded files of the demo stay on disk."""
    Base.metadata.drop_all(engine)
    init_db()
    with SessionLocal() as session:
        seed.seed(session)
        session.commit()
    auth.logout_user(request)
    return redirect("/login", "Demo data restored — please sign in again.", "info")

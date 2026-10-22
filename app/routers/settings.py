"""Expert settings: the optional LLM endpoint and the knowledge-base index."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from .. import auth, llm, rag
from ..db import User, get_session, log
from ..web import base_context, redirect, render

router = APIRouter()


@router.get("/settings/ai", response_class=HTMLResponse)
def page(request: Request, session: Session = Depends(get_session), user: User = Depends(auth.require_expert)):
    return render("settings_ai.html", base_context(request, session, "settings", s=llm.settings(),
                                                   key=llm.masked_key(), configured=llm.configured(),
                                                   kb=rag.status(), pool=rag.pool()))


@router.post("/settings/ai")
def save(provider: str = Form("azure"), endpoint: str = Form(""), api_key: str = Form(""), model: str = Form(""),
         api_version: str = Form("2024-06-01"), enabled: Optional[str] = Form(None),
         session: Session = Depends(get_session), user: User = Depends(auth.require_expert)):
    llm.save_settings(provider, endpoint, api_key or None, model, api_version, bool(enabled))
    log(session, "AI settings changed", user.display_name, comment=f"{provider} {endpoint} {model} enabled={bool(enabled)}")
    session.commit()
    return redirect("/settings/ai", "AI settings saved · AI 设置已保存")


@router.post("/settings/ai/test")
def test(user: User = Depends(auth.require_expert)):
    ok, msg = llm.test_connection()
    return {"ok": ok, "message": ("Connection OK · 连接成功: " if ok else "Connection failed · 连接失败: ") + msg}


@router.post("/settings/kb/reindex")
def reindex(user: User = Depends(auth.require_expert)):
    rag.CORPUS.ensure(rebuild=True)
    st = rag.status()
    return {"ok": st["state"] == "ready",
            "message": f"Knowledge base indexed: {st['indexed']} documents, {st['chunks']} passages · 知识库索引完成",
            "redirect": "/settings/ai"}

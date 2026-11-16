"""Manual knowledge-base update (人工更新知识库): upload an act → review the draft → publish.

Publishing adds the entry to the knowledge pool, applies its rule in the AI pre-review and
re-runs the AI on the submissions it touches; the update page then shows the verdict changes.
"""
from __future__ import annotations

import re

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from .. import auth, catalogue, config, kb_rules
from ..db import KnowledgeEntry, User, get_session
from ..web import base_context, redirect, render

router = APIRouter()

ARTICLES = ["a5", "a5pfas", "a6", "a7", "a8", "a9", "a10", "a11", "a12", "core"]


def _page(request, session, **extra):
    entries = session.query(KnowledgeEntry).order_by(KnowledgeEntry.id.desc()).all()
    return render("kb_manual.html", base_context(request, session, "knowledge", entries=entries,
                                                 articles=ARTICLES, items=catalogue.items(),
                                                 RULES=kb_rules.RULE_TYPES, **extra))


@router.get("/knowledge/manual", response_class=HTMLResponse)
def manual(request: Request, session: Session = Depends(get_session), user: User = Depends(auth.require_expert)):
    return _page(request, session, draft=None)


@router.post("/knowledge/manual/upload", response_class=HTMLResponse)
async def upload(request: Request, file: UploadFile = File(...), session: Session = Depends(get_session),
                 user: User = Depends(auth.require_expert)):
    data = await file.read()
    if not data:
        return redirect("/knowledge/manual", "Empty file · 文件为空", "error")
    if len(data) > config.MAX_UPLOAD_MB * 1024 * 1024:
        return redirect("/knowledge/manual", f"Files over {config.MAX_UPLOAD_MB} MB are not accepted.", "error")
    token, text = kb_rules.stage_upload(file.filename or "act.pdf", data)
    if len(text.strip()) < 200:
        return redirect("/knowledge/manual", "No extractable text in this file (scanned?) · 无法提取文本", "error")
    draft = kb_rules.draft_for(text, file.filename or "")
    return _page(request, session, draft=draft, token=token, original_name=file.filename or "",
                 n_chars=len(text))


def _lines(text: str) -> list[str]:
    return [x.strip() for x in (text or "").splitlines() if x.strip()]


def _csv(text: str) -> list[str]:
    return [x.strip() for x in re.split(r"[,，;；\n]", text or "") if x.strip()]


@router.post("/knowledge/manual/publish")
async def publish(request: Request, session: Session = Depends(get_session), user: User = Depends(auth.require_expert)):
    f = await request.form()
    g = lambda k: str(f.get(k, "") or "").strip()  # noqa: E731
    if not g("ref") or not g("title"):
        return redirect("/knowledge/manual", "Reference and title are required · 须填写法规编号与标题", "error")
    rule = {}
    if g("rule_on"):
        conds = []
        for line in _lines(g("conditions")):
            parts = [p.strip() for p in line.split("|")]
            if parts[0]:
                conds.append({"en": parts[0], "zh": parts[1] if len(parts) > 1 else "",
                              "terms": _csv(parts[2]) if len(parts) > 2 else [],
                              "ref": parts[3] if len(parts) > 3 else ""})
        rule = {"type": "limit_derogation", "article": g("rule_article") or "a5", "provision": g("provision"),
                "limit_label": g("limit_label") or "100 mg/kg", "scope_terms": _csv(g("scope_terms")),
                "manufactured_until": g("manufactured_until"), "market_until": g("market_until"),
                "conditions": conds}
        if not rule["scope_terms"]:
            return redirect("/knowledge/manual", "A rule needs at least one scope term · 规则至少需要一个适用范围关键词",
                            "error")
    d = {"kind": g("kind") or "implementing", "binding": bool(g("binding")), "ref": g("ref"), "title": g("title"),
         "title_zh": g("title_zh"), "text": g("text"), "text_zh": g("text_zh"), "impact": g("impact"),
         "impact_zh": g("impact_zh"), "published": g("published"), "applies_from": g("applies_from"),
         "page": int(g("page")) if g("page").isdigit() else 0,
         "articles": [a for a in f.getlist("articles") if a in ARTICLES],
         "items": [i for i in f.getlist("items") if catalogue.item(i)], "rule": rule}
    e = kb_rules.publish(session, d, user.display_name, token=g("token"), original_name=g("original_name"))
    session.commit()
    n = (e.rerun or {}).get("changed", 0)
    return redirect(f"/updates/{e.update_id}#ai-change",
                    f"Knowledge base updated ({e.code}) — AI re-ran, {n} judgement(s) changed · "
                    f"知识库已更新，AI 已重新判断，{n} 项结论变化")


def _entry(session, eid: int) -> KnowledgeEntry:
    e = session.get(KnowledgeEntry, eid)
    if e is None:
        raise HTTPException(404)
    return e


@router.post("/knowledge/manual/{eid}/withdraw")
def withdraw(eid: int, session: Session = Depends(get_session), user: User = Depends(auth.require_expert)):
    e = _entry(session, eid)
    res = kb_rules.set_status(session, e, "withdrawn", user.display_name)
    session.commit()
    return redirect(f"/updates/{e.update_id}#ai-change" if e.update_id else "/knowledge/manual",
                    f"{e.code} withdrawn — AI re-ran, {res['changed']} judgement(s) changed · "
                    f"已撤回，AI 已重新判断，{res['changed']} 项结论变化", "info")


@router.post("/knowledge/manual/{eid}/activate")
def activate(eid: int, session: Session = Depends(get_session), user: User = Depends(auth.require_expert)):
    e = _entry(session, eid)
    res = kb_rules.set_status(session, e, "active", user.display_name)
    session.commit()
    return redirect(f"/updates/{e.update_id}#ai-change" if e.update_id else "/knowledge/manual",
                    f"{e.code} active again — AI re-ran, {res['changed']} judgement(s) changed · "
                    f"已重新启用，AI 已重新判断，{res['changed']} 项结论变化")

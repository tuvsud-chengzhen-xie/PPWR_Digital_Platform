"""Client guidance: project compliance guide, live pre-check, templates, the RAG assistant, language."""
from __future__ import annotations

from collections import Counter
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from sqlalchemy.orm import Session

from .. import applicability, assistant, auth, catalogue, guidance, i18n, monitor, rag
from ..db import Submission, User, get_session
from ..web import project_context, render

router = APIRouter()


@router.get("/lang/{code}")
def set_lang(code: str, request: Request):
    if code in i18n.LANGS:
        request.session["lang"] = code
    back = request.headers.get("referer") or "/"
    return RedirectResponse(back if back.startswith(("http://", "https://", "/")) else "/", status_code=303)


def _sub(session: Session, pid: int, sid: int) -> Submission:
    s = session.get(Submission, sid)
    if s is None or s.project_id != pid:
        raise HTTPException(404, "Item not found")
    return s


@router.get("/projects/{pid}/guide", response_class=HTMLResponse)
def guide(pid: int, request: Request, level: Optional[str] = None, session: Session = Depends(get_session),
          user: User = Depends(auth.require_user)):
    p = auth.get_project(session, user, pid)
    report = guidance.project_gaps(p)
    rows = report["rows"]
    if level:
        rows = [r for r in rows if r["ob"].code == level]
    by_article = Counter(r["ob"].article for r in report["rows"] if r["ob"].code == "mandatory_now")
    timeline = sorted({(r["ob"].applies_from, r["ob"].article) for r in report["rows"]
                       if r["ob"].code == "mandatory_from" and r["ob"].applies_from}, key=lambda x: x[0])
    return render("project/guide.html", project_context(
        request, session, p, "guide", report=report, rows=rows, level=level or "", by_article=by_article,
        timeline=timeline, alerts=monitor.project_alerts(session, p),
        art_label={r.key: r.article for r in applicability.matrix(p)}))


async def _overrides(request: Request, s: Submission) -> tuple[dict, list | None]:
    form = await request.form()
    it = catalogue.item(s.item_id)
    data = {}
    for f in it.get("fields", []):
        if f"f_{f['k']}" in form:
            data[f["k"]] = str(form[f"f_{f['k']}"]).strip()
    table = None
    if it.get("table") and "t_rows" in form:
        table = []
        for r in range(int(form.get("t_rows", 0) or 0)):
            row = [str(form.get(f"t_{r}_{c}", "")).strip() for c in range(len(it["table"]))]
            if any(row):
                table.append(row)
    return data, table


@router.post("/projects/{pid}/items/{sid}/precheck")
async def precheck(pid: int, sid: int, request: Request, session: Session = Depends(get_session),
                   user: User = Depends(auth.require_user)):
    """Validate the entry *before* it is submitted. Dry run — nothing is saved."""
    p = auth.get_project(session, user, pid)
    s = _sub(session, p.id, sid)
    data, table = await _overrides(request, s)
    ev = guidance.evaluate(p, s, data_override=data, table_override=table)
    ob = ev["ob"]
    return JSONResponse({
        "ok": True, "item": s.item_id, "ready_pct": ev["ready_pct"],
        "obligation": {"code": ob.code, "label": i18n.LEVEL[ob.code][0], "label_zh": i18n.LEVEL[ob.code][1],
                       "applies_from": ob.applies_from.isoformat() if ob.applies_from else "",
                       "why": ob.why, "why_zh": ob.why_zh},
        "gaps": ev["gaps"],
        "minimum": [{"en": m["en"], "zh": m["zh"], "ok": m["ok"]} for m in ev["minimum"]],
        "checks": [{"desc": c["desc"], "desc_zh": c.get("desc_zh", ""), "ok": c["ok"], "msg": c.get("msg", ""),
                    "msg_zh": c.get("msg_zh", ""), "ref": c.get("ref", "")} for c in ev["ai_checks"]],
        "hints": ev["hints"], "blocking": bool(ev["gaps"]) and ob.code == "mandatory_now"})


@router.get("/projects/{pid}/items/{sid}/template.docx")
def template(pid: int, sid: int, session: Session = Depends(get_session), user: User = Depends(auth.require_user)):
    p = auth.get_project(session, user, pid)
    s = _sub(session, p.id, sid)
    data = guidance.template_docx(s.item_id, p, s.unit)
    return Response(data, media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    headers={"Content-Disposition": f'attachment; filename="{s.item_id}_template.docx"'})


@router.get("/catalogue/{item_id}/template.docx")
def template_generic(item_id: str, user: User = Depends(auth.require_user)):
    if catalogue.item(item_id) is None:
        raise HTTPException(404)
    return Response(guidance.template_docx(item_id),
                    media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    headers={"Content-Disposition": f'attachment; filename="{item_id}_template.docx"'})


@router.post("/assistant/ask")
async def ask(request: Request, session: Session = Depends(get_session), user: User = Depends(auth.require_user)):
    form = await request.form()
    q = str(form.get("q", "")).strip()
    if not q:
        return JSONResponse({"ok": False, "message": "Type a question. 请输入问题。"}, status_code=400)
    ctx = None
    pid, sid = form.get("pid"), form.get("sid")
    if pid and sid and str(pid).isdigit() and str(sid).isdigit():
        p = auth.get_project(session, user, int(pid))
        s = _sub(session, p.id, int(sid))
        ctx = {"eval": guidance.evaluate(p, s)}
    out = assistant.answer(q, ctx)
    out["ok"] = True
    return JSONResponse(out)


@router.get("/assistant/status")
def kb_status(user: User = Depends(auth.require_user)):
    st = rag.status()
    st.pop("doc_list", None)
    return st

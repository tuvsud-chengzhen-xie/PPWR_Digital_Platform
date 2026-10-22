"""Smart import — one-click upload with AI identification (ported from the V4.2 prototype)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session

from .. import auth, catalogue, config, importer
from ..db import ImportBatch, User, get_session
from ..web import project_context, redirect, render

router = APIRouter()


def _batch(session: Session, p, user) -> ImportBatch:
    return importer.open_batch(session, p, user.display_name)


@router.get("/projects/{pid}/import", response_class=HTMLResponse)
def page(pid: int, request: Request, session: Session = Depends(get_session), user: User = Depends(auth.require_user)):
    p = auth.get_project(session, user, pid)
    batch = session.query(ImportBatch).filter_by(project_id=p.id, status="staged").first()
    history = session.query(ImportBatch).filter(ImportBatch.project_id == p.id, ImportBatch.status == "imported") \
        .order_by(ImportBatch.imported_at.desc()).limit(10).all()
    staged = [f for f in batch.files if f.status == "staged"] if batch else []
    table = batch.table if batch and batch.table else {}
    rows = importer.table_rows(table) if table else []
    return render("project/import.html", project_context(
        request, session, p, "import", batch=batch, staged=staged, table=table, table_rows=rows,
        targets=importer.targets(), history=history, cats=catalogue.categories(), items=catalogue.items(),
        max_mb=importer.MAX_TOTAL_MB, sample=importer.SAMPLE_TABLE,
        stat={"hi": sum(1 for f in staged if f.item_id and f.confidence >= 0.9),
              "mid": sum(1 for f in staged if f.item_id and 0.7 <= f.confidence < 0.9),
              "lo": sum(1 for f in staged if f.item_id and f.confidence < 0.7),
              "none": sum(1 for f in staged if not f.item_id)}))


@router.post("/projects/{pid}/import/files")
async def upload(pid: int, request: Request, session: Session = Depends(get_session),
                 user: User = Depends(auth.require_user)):
    p = auth.get_project(session, user, pid)
    form = await request.form()
    files = []
    for f in form.getlist("files"):
        if isinstance(f, (UploadFile,)) or hasattr(f, "read"):
            data = await f.read()
            if len(data) > config.MAX_UPLOAD_MB * 1024 * 1024 and not (f.filename or "").lower().endswith(".zip"):
                continue
            files.append((f.filename or "file", data))
    if not files:
        return JSONResponse({"ok": False, "message": "No files received · 未收到文件"}, status_code=400)
    res = importer.stage_files(session, p, files, user.display_name)
    session.commit()
    msg = (f"AI identified {res['added']} file(s): {res['hi']} high, {res['mid']} medium, {res['lo']} to confirm, "
           f"{res['none']} not recognised · AI 已识别 {res['added']} 个文件——请核对后一键入库")
    return {"ok": True, "message": msg, "redirect": f"/projects/{pid}/import"}


@router.post("/projects/{pid}/import/table")
async def table(pid: int, request: Request, session: Session = Depends(get_session),
                user: User = Depends(auth.require_user)):
    p = auth.get_project(session, user, pid)
    form = await request.form()
    grid = []
    up = form.get("tablefile")
    if up is not None and hasattr(up, "read") and getattr(up, "filename", ""):
        data = await up.read()
        try:
            grid = importer.parse_xlsx(data) if up.filename.lower().endswith((".xlsx", ".xlsm")) else \
                importer.parse_delimited(data.decode("utf-8-sig", errors="ignore"))
        except Exception as exc:
            return redirect(f"/projects/{pid}/import", f"Could not read the table: {exc}", "error")
    elif str(form.get("text", "")).strip():
        grid = importer.parse_delimited(str(form["text"]))
    if len(grid) < 2:
        return redirect(f"/projects/{pid}/import", "A header row and at least one data row are needed · 需要表头及至少一行数据", "warn")
    b = _batch(session, p, user)
    b.table = importer.build_table(grid)
    session.commit()
    n = len(importer.table_rows(b.table))
    return redirect(f"/projects/{pid}/import#table", f"Table parsed: {n} row(s) — check the column mapping · 已解析 {n} 行，请核对列映射")


@router.post("/projects/{pid}/import/table/map")
async def table_map(pid: int, request: Request, session: Session = Depends(get_session),
                    user: User = Depends(auth.require_user)):
    p = auth.get_project(session, user, pid)
    form = await request.form()
    b = _batch(session, p, user)
    t = b.table or {}
    if t.get("grid"):
        col_map = [str(form.get(f"col_{i}", "")) for i in range(len(t.get("header", [])))]
        b.table = importer.build_table(t["grid"], col_map)
    session.commit()
    return redirect(f"/projects/{pid}/import#table", "Column mapping saved · 列映射已保存")


@router.post("/projects/{pid}/import/table/clear")
def table_clear(pid: int, session: Session = Depends(get_session), user: User = Depends(auth.require_user)):
    p = auth.get_project(session, user, pid)
    b = _batch(session, p, user)
    b.table = {}
    session.commit()
    return redirect(f"/projects/{pid}/import", "Table cleared · 表格已清空", "info")


@router.post("/projects/{pid}/import/save")
async def save(pid: int, request: Request, session: Session = Depends(get_session),
               user: User = Depends(auth.require_user)):
    p = auth.get_project(session, user, pid)
    form = await request.form()
    b = _batch(session, p, user)
    n = importer.update_files(session, b, form)
    session.commit()
    return redirect(f"/projects/{pid}/import", f"{n} correction(s) saved · 已保存 {n} 处更正")


@router.post("/projects/{pid}/import/confirm")
async def confirm(pid: int, request: Request, session: Session = Depends(get_session),
                  user: User = Depends(auth.require_user)):
    p = auth.get_project(session, user, pid)
    form = await request.form()
    b = session.query(ImportBatch).filter_by(project_id=p.id, status="staged").first()
    if b is None or (not any(f.status == "staged" for f in b.files) and not (b.table or {}).get("grid")):
        return JSONResponse({"ok": False, "message": "Nothing staged to import · 没有待入库内容"}, status_code=400)
    importer.update_files(session, b, form)
    du = form.get("default_unit")
    stats = importer.confirm(session, p, b, user.display_name, auto_submit=bool(form.get("auto_submit")),
                             auto_ai=bool(form.get("auto_ai")), default_unit_id=int(du) if du and du.isdigit() else None)
    session.commit()
    msg = (f"Imported {stats['files']} file(s)" + (f", {stats.get('table_rows', 0)} table row(s)" if stats.get("table_rows") else "")
           + f" · {stats['submitted']} item(s) submitted · {stats['ai']} AI-reviewed"
           + (f" · {stats['corrections']} correction(s) learned" if stats["corrections"] else "")
           + f" · 一键入库完成：{stats['files']} 个文件")
    return {"ok": True, "message": msg, "redirect": f"/projects/{pid}/import"}


@router.post("/projects/{pid}/import/discard")
def discard(pid: int, session: Session = Depends(get_session), user: User = Depends(auth.require_user)):
    p = auth.get_project(session, user, pid)
    b = session.query(ImportBatch).filter_by(project_id=p.id, status="staged").first()
    if b:
        importer.discard(session, b)
        session.commit()
    return redirect(f"/projects/{pid}/import", "Staged files discarded · 已丢弃待入库文件", "info")

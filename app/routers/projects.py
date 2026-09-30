"""Projects: list, set-up, overview, packaging register & BOM, traceability."""
from __future__ import annotations

import datetime as dt
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, Response
from sqlalchemy.orm import Session

from .. import applicability, auth, catalogue, changes, excel_io, workflow
from ..db import Client, Component, PackagingUnit, Project, Supplier, SupplierMaterial, User, get_session, log
from ..web import base_context, project_context, redirect, render

router = APIRouter()


def _f(v: Optional[str]) -> Optional[float]:
    try:
        return float(str(v).replace(",", ".")) if v not in (None, "") else None
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# List / new
# ---------------------------------------------------------------------------

@router.get("/projects", response_class=HTMLResponse)
def project_list(request: Request, session: Session = Depends(get_session), user: User = Depends(auth.require_user)):
    projects = auth.visible_projects(session, user).order_by(Project.created_at.desc()).all()
    rows = [{"p": p, "prog": workflow.progress(p.submissions), "stage": workflow.project_stage(p)} for p in projects]
    return render("projects.html", base_context(request, session, "projects", rows=rows))


@router.get("/projects/new", response_class=HTMLResponse)
def project_new(request: Request, session: Session = Depends(get_session), user: User = Depends(auth.require_user)):
    clients = session.query(Client).order_by(Client.name).all() if user.is_expert else [user.client]
    year = dt.date.today().year
    n = session.query(Project).filter(Project.code.like(f"PRJ-{year}-%")).count() + 1
    return render("project_new.html", base_context(request, session, "projects", clients=clients,
                                                   suggested_code=f"PRJ-{year}-{n:03d}"))


@router.post("/projects/new")
def project_create(request: Request, title: str = Form(...), client_id: int = Form(...),
                   scenario: str = Form("B"), ps_code: str = Form("PS-001"), product_description: str = Form(""),
                   target_date: str = Form(""), food_contact: Optional[str] = Form(None),
                   reusable: Optional[str] = Form(None), compostable_type: Optional[str] = Form(None),
                   biobased_claim: Optional[str] = Form(None), first_unit: str = Form(""),
                   first_level: str = Form("Sales"),
                   session: Session = Depends(get_session), user: User = Depends(auth.require_user)):
    if not user.is_expert:
        client_id = user.client_id
    year = dt.date.today().year
    n = session.query(Project).filter(Project.code.like(f"PRJ-{year}-%")).count() + 1
    p = Project(code=f"PRJ-{year}-{n:03d}", client_id=client_id, title=title.strip(), scenario=scenario,
                ps_code=ps_code.strip() or "PS-001", product_description=product_description.strip(),
                target_date=dt.date.fromisoformat(target_date) if target_date else None,
                food_contact=bool(food_contact), reusable=bool(reusable), compostable_type=bool(compostable_type),
                biobased_claim=bool(biobased_claim), created_by=user.display_name)
    session.add(p)
    session.flush()
    if first_unit.strip():
        session.add(PackagingUnit(project=p, code="PU-001", name=first_unit.strip(), level=first_level))
        session.flush()
    session.refresh(p)
    workflow.ensure_submissions(session, p)
    log(session, "project created", user.display_name, p.id, comment=p.title)
    session.commit()
    return redirect(f"/projects/{p.id}/packaging", f"{p.code} created — register the packaging and its BOM next.")


# ---------------------------------------------------------------------------
# Overview
# ---------------------------------------------------------------------------

@router.get("/projects/{pid}", response_class=HTMLResponse)
def overview(pid: int, request: Request, session: Session = Depends(get_session),
             user: User = Depends(auth.require_user)):
    p = auth.get_project(session, user, pid)
    unit_rows = [{"u": u, "prog": workflow.progress(workflow.subs_for(p, u))} for u in p.units]
    from ..db import AuditEvent
    history = session.query(AuditEvent).filter(AuditEvent.project_id == p.id) \
        .order_by(AuditEvent.at.desc()).limit(12).all()
    return render("project/overview.html", project_context(
        request, session, p, "overview", cats=workflow.category_progress(p.submissions), units=unit_rows,
        history=history, groups=sorted(applicability.material_groups(p))))


@router.post("/projects/{pid}/profile")
def update_profile(pid: int, title: str = Form(...), scenario: str = Form("B"), ps_code: str = Form("PS-001"),
                   product_description: str = Form(""), target_date: str = Form(""),
                   food_contact: Optional[str] = Form(None), reusable: Optional[str] = Form(None),
                   compostable_type: Optional[str] = Form(None), biobased_claim: Optional[str] = Form(None),
                   session: Session = Depends(get_session), user: User = Depends(auth.require_user)):
    p = auth.get_project(session, user, pid)
    before = [(r.key, r.status) for r in applicability.matrix(p)]
    p.title, p.scenario, p.ps_code = title.strip(), scenario, ps_code.strip() or p.ps_code
    p.product_description = product_description.strip()
    p.target_date = dt.date.fromisoformat(target_date) if target_date else None
    p.food_contact, p.reusable = bool(food_contact), bool(reusable)
    p.compostable_type, p.biobased_claim = bool(compostable_type), bool(biobased_claim)
    workflow.sync(session, p)
    after = [(r.key, r.status) for r in applicability.matrix(p)]
    changed = sum(1 for a, b in zip(before, after) if a != b)
    log(session, "profile updated", user.display_name, p.id,
        comment=f"{changed} applicability row(s) changed" if changed else "")
    session.commit()
    msg = "Project profile saved" + (f" — {changed} article(s) changed applicability; items re-synced." if changed else ".")
    return redirect(f"/projects/{pid}", msg)


# ---------------------------------------------------------------------------
# Packaging register & BOM
# ---------------------------------------------------------------------------

def _library(session: Session, p: Project):
    suppliers = session.query(Supplier).filter(Supplier.client_id == p.client_id).order_by(Supplier.code).all()
    return suppliers


@router.get("/projects/{pid}/packaging", response_class=HTMLResponse)
def packaging(pid: int, request: Request, unit: Optional[int] = None, edit: Optional[int] = None,
              session: Session = Depends(get_session), user: User = Depends(auth.require_user)):
    p = auth.get_project(session, user, pid)
    current = next((u for u in p.units if u.id == unit), p.units[0] if p.units else None)
    return render("project/packaging.html", project_context(
        request, session, p, "packaging", current=current, suppliers=_library(session, p), edit=edit,
        next_unit=workflow.next_unit_code(p),
        next_comp=workflow.next_component_code(current) if current else None))


@router.post("/projects/{pid}/units")
def unit_save(pid: int, unit_id: Optional[int] = Form(None), name: str = Form(...), level: str = Form("Sales"),
              pack_type: str = Form(""), upi: str = Form(""), skus: str = Form(""), mass_g: str = Form(""),
              dims: str = Form(""), supplier_name: str = Form(""), site: str = Form(""), country: str = Form(""),
              artwork_ref: str = Form(""), session: Session = Depends(get_session),
              user: User = Depends(auth.require_user)):
    p = auth.get_project(session, user, pid)
    u = next((x for x in p.units if x.id == unit_id), None) if unit_id else None
    created = u is None
    if created:
        u = PackagingUnit(project=p, code=workflow.next_unit_code(p))
        session.add(u)
    u.name, u.level, u.pack_type, u.upi, u.skus = name.strip(), level, pack_type.strip(), upi.strip(), skus.strip()
    u.mass_g, u.dims = _f(mass_g), dims.strip()
    u.supplier_name, u.site, u.country, u.artwork_ref = supplier_name.strip(), site.strip(), country.strip(), artwork_ref.strip()
    session.flush()
    session.refresh(p)
    if created:
        workflow.ensure_submissions(session, p)
        log(session, "unit added", user.display_name, p.id, u.id, comment=f"{u.code} {u.name}")
    else:
        workflow.sync_unit_register(session, u, user.display_name)
        workflow.sync(session, p)
    session.commit()
    return redirect(f"/projects/{pid}/packaging?unit={u.id}", f"{u.code} saved")


@router.post("/projects/{pid}/units/{uid}/delete")
def unit_delete(pid: int, uid: int, session: Session = Depends(get_session), user: User = Depends(auth.require_user)):
    p = auth.get_project(session, user, pid)
    u = next((x for x in p.units if x.id == uid), None)
    if u:
        for s in [s for s in p.submissions if s.unit_id == u.id]:
            session.delete(s)
        for e in [e for e in p.evidence if e.unit_id == u.id]:
            e.unit_id, e.component_id = None, None
        log(session, "unit removed", user.display_name, p.id, comment=f"{u.code} {u.name}")
        session.delete(u)
        session.commit()
    return redirect(f"/projects/{pid}/packaging", "Packaging unit removed", "info")


@router.post("/projects/{pid}/components")
def component_save(pid: int, unit_id: int = Form(...), comp_id: Optional[int] = Form(None),
                   pack_type: str = Form(""), description: str = Form(""), structure: str = Form("Mono-material"),
                   material: str = Form(""), material_group: str = Form(""), mass_g: str = Form(""),
                   dims: str = Form(""), supplier_material_id: Optional[int] = Form(None),
                   recycled_pct: str = Form(""), biobased_pct: str = Form(""), remarks: str = Form(""),
                   session: Session = Depends(get_session), user: User = Depends(auth.require_user)):
    p = auth.get_project(session, user, pid)
    u = next((x for x in p.units if x.id == unit_id), None)
    if u is None:
        return redirect(f"/projects/{pid}/packaging", "Unknown packaging unit", "error")
    c = next((x for x in u.components if x.id == comp_id), None) if comp_id else None
    if c is None:
        c = Component(unit=u, code=workflow.next_component_code(u))
        session.add(c)
    c.pack_type, c.description, c.structure = pack_type.strip(), description.strip(), structure
    c.material = material.strip()
    c.material_group = material_group or catalogue.material_group_for(material)
    c.mass_g, c.dims, c.remarks = _f(mass_g), dims.strip(), remarks.strip()
    c.recycled_pct, c.biobased_pct = _f(recycled_pct), _f(biobased_pct)
    mat = session.get(SupplierMaterial, supplier_material_id) if supplier_material_id else None
    if mat and mat.supplier.client_id == p.client_id:
        c.supplier_material_id, c.supplier_id = mat.id, mat.supplier_id
    else:
        c.supplier_material_id, c.supplier_id = None, None
    session.flush()
    session.refresh(p)
    workflow.sync(session, p)
    log(session, "BOM line saved", user.display_name, p.id, u.id, comment=f"{c.code} {c.material}")
    session.commit()
    return redirect(f"/projects/{pid}/packaging?unit={u.id}", f"{c.code} saved")


@router.post("/projects/{pid}/components/{cid}/delete")
def component_delete(pid: int, cid: int, session: Session = Depends(get_session),
                     user: User = Depends(auth.require_user)):
    p = auth.get_project(session, user, pid)
    c = session.get(Component, cid)
    if c and c.unit.project_id == p.id:
        uid = c.unit_id
        for e in p.evidence:
            if e.component_id == c.id:
                e.component_id = None
        session.delete(c)
        session.flush()
        session.refresh(p)
        workflow.sync(session, p)
        session.commit()
        return redirect(f"/projects/{pid}/packaging?unit={uid}", "Component removed", "info")
    return redirect(f"/projects/{pid}/packaging")


@router.post("/projects/{pid}/bom/import")
async def bom_import(pid: int, file: UploadFile = File(...), session: Session = Depends(get_session),
                     user: User = Depends(auth.require_user)):
    p = auth.get_project(session, user, pid)
    try:
        stats = excel_io.import_bom(session, p, await file.read(), user.display_name)
    except Exception as exc:  # malformed workbook → message, not a 500
        session.rollback()
        return JSONResponse({"ok": False, "message": f"Could not read the workbook: {exc}"}, status_code=400)
    session.commit()
    msg = (f"BOM imported — {stats['components_created']} component(s) created, "
           f"{stats['components_updated']} updated, {stats['units_created']} new unit(s).")
    return {"ok": True, "message": msg, "warnings": stats["warnings"][:8],
            "redirect": f"/projects/{pid}/packaging"}


@router.get("/projects/{pid}/bom.xlsx")
def bom_export(pid: int, session: Session = Depends(get_session), user: User = Depends(auth.require_user)):
    p = auth.get_project(session, user, pid)
    return Response(excel_io.export_bom(p), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": f'attachment; filename="{p.code}_PPWR_BOM.xlsx"'})


# ---------------------------------------------------------------------------
# Traceability
# ---------------------------------------------------------------------------

@router.get("/projects/{pid}/trace", response_class=HTMLResponse)
def trace(pid: int, request: Request, session: Session = Depends(get_session),
          user: User = Depends(auth.require_user)):
    p = auth.get_project(session, user, pid)
    today = dt.date.today()
    rows = []
    for u in p.units:
        for c in u.components:
            certs = {}
            m = c.supplier_material
            for cert in (m.certificates if m else []):
                if cert.status != "valid":
                    continue
                days = (cert.expires - today).days if cert.expires else None
                state = "expired" if days is not None and days < 0 else \
                    "expiring" if days is not None and days <= 30 else "valid"
                certs[cert.doc_type] = {"cert": cert, "state": state, "days": days}
            rows.append({"u": u, "c": c, "m": m, "certs": certs})
    related = [ev for ev in auth.visible_changes(session, user).all()
               if p.code in {x["code"] for x in ev.impact.get("projects", [])}]
    return render("project/trace.html", project_context(request, session, p, "trace", rows=rows,
                                                        cert_cols=["hm", "pf", "rc", "doc", "td", "comp"],
                                                        related=related))

"""Catalogue, applicability, workflow, AI pre-review, change impact, generation."""
import datetime as dt
from pathlib import Path

from app import ai_review, applicability, catalogue, changes, generator, workflow
from app.db import (ChangeEvent, Component, Document, Evidence, PackagingUnit, Project, Submission,
                    SupplierMaterial)


def _project(session, code):
    return session.query(Project).filter_by(code=code).one()


def _sub(project, item_id, unit_code=None):
    return next(s for s in project.submissions if s.item_id == item_id
                and (s.unit.code if s.unit else None) == unit_code)


# --- catalogue ---------------------------------------------------------------

def test_catalogue_shape():
    assert len(catalogue.categories()) == 16
    assert len(catalogue.items()) == 69
    ids = {i["id"] for i in catalogue.items()}
    for sec in catalogue.td_sections():
        assert set(sec["items"]) <= ids, sec["no"]
    for it in catalogue.items():
        assert it["evidence_code"] in catalogue.EVIDENCE_TYPES
        assert it["legal"] and all("一" > ch for ch in it["legal"][:3])  # English legal basis


def test_cert_items_exist():
    for items in catalogue.CERT_ITEMS.values():
        for iid in items:
            assert catalogue.item(iid), iid


def test_material_group_detection():
    assert catalogue.material_group_for("Corrugated fibreboard B-flute") == "paper"
    assert catalogue.material_group_for("PET/PE laminate") == "plastic"
    assert catalogue.material_group_for("Clear glass") == "glass"


# --- applicability -------------------------------------------------------------

def test_matrix_follows_profile_and_bom(session):
    lumen = _project(session, "PRJ-2026-001")      # paper, not food contact
    aurora = _project(session, "PRJ-2026-002")     # plastic, food contact
    assert applicability.status_for(lumen, "a5pfas")[0] == applicability.NA
    assert applicability.status_for(lumen, "a7")[0] == applicability.NA
    assert applicability.status_for(aurora, "a5pfas")[0] == applicability.YES
    assert applicability.status_for(aurora, "a7")[0] == applicability.TRANSITIONAL
    assert applicability.status_for(aurora, "core")[0] == applicability.YES


def test_na_items_closed_automatically_and_reopened_when_profile_changes(session):
    p = _project(session, "PRJ-2026-001")
    s = _sub(p, "C04-17", "PU-001")
    assert s.status == "na" and s.na_auto
    p.food_contact = True
    workflow.sync(session, p)
    assert s.status == "pending" and not s.na_auto
    p.food_contact = False
    workflow.sync(session, p)
    assert s.status == "na"


def test_every_unit_gets_the_full_item_set(session):
    p = _project(session, "PRJ-2026-002")
    n_unit, n_proj = len(catalogue.unit_items()), len(catalogue.project_items())
    assert len(p.submissions) == n_unit * len(p.units) + n_proj


def test_register_change_reopens_approved_identification(session):
    p = _project(session, "PRJ-2026-001")
    u = p.units[0]
    s = _sub(p, "C01-04", u.code)
    assert s.status == "approved"
    u.mass_g = 15.2
    workflow.sync_unit_register(session, u, "test")
    assert s.status == "submitted" and s.data["mass"] == "15.2"


# --- AI pre-review -----------------------------------------------------------

def test_heavy_metals_limit(session):
    p = _project(session, "PRJ-2026-002")
    s = _sub(p, "C04-16", "PU-001")
    ev = [e for e in p.evidence if e.item_id == "C04-16"]
    s.data = {"res": "38", "method": "EN 13657 + ICP-MS"}
    verdict, checks = ai_review.review(s, p, s.unit, ev)
    assert verdict == "pass", checks
    s.data = {"res": "120", "method": "ICP-OES"}
    verdict, checks = ai_review.review(s, p, s.unit, ev)
    assert verdict == "fail"
    assert any("exceeds" in c["msg"] for c in checks)


def test_expired_supplier_certificate_fails_the_check(session):
    p = _project(session, "PRJ-2026-002")
    s = _sub(p, "C04-16", "PU-001")
    cert = next(c for c in p.units[0].components[0].supplier_material.certificates if c.doc_type == "hm")
    cert.expires = dt.date.today() - dt.timedelta(days=1)
    verdict, checks = ai_review.review(s, p, s.unit, [e for e in p.evidence if e.item_id == "C04-16"])
    assert verdict == "fail"
    assert any("expired" in c["msg"] for c in checks)


def test_food_contact_is_judged_per_unit(session):
    p = _project(session, "PRJ-2026-002")   # food-contact product
    shipper = _sub(p, "C04-18", "PU-002")
    shipper.data = {"app": "No — not food-contact"}
    verdict, _ = ai_review.review(shipper, p, shipper.unit, [])
    assert verdict != "fail"                # outer packaging may legitimately be non-food
    pouch = _sub(p, "C04-18", "PU-001")
    pouch.data = {"app": "No — not food-contact"}
    verdict, _ = ai_review.review(pouch, p, pouch.unit, [])
    assert verdict == "fail"                # the sales pouch holds the sauce


def test_bom_mass_cross_check(session):
    p = _project(session, "PRJ-2026-002")
    s = _sub(p, "C01-04", "PU-001")
    s.data = {"mass": "20", "dims": "130 × 190 × 70"}   # BOM sums to 10.9 g
    verdict, checks = ai_review.review(s, p, s.unit, [])
    assert verdict == "fail"
    assert any("deviation" in c["msg"] for c in checks)


def test_na_request_needs_a_reason(session):
    p = _project(session, "PRJ-2026-002")
    s = _sub(p, "C09-36", "PU-001")
    workflow.request_na(session, s, "n/a", "test")
    verdict, _ = ai_review.review(s, p, s.unit, [])
    assert verdict == "fail"


# --- identifiers -------------------------------------------------------------

def test_evidence_codes_follow_the_convention(session):
    p = _project(session, "PRJ-2026-001")
    u = p.units[0]
    c = u.components[0]
    code = workflow.next_evidence_code(session, p, u, c, "TST")
    assert code.startswith("PU-001-C001-TST-")
    assert workflow.next_component_code(u) == "PU-001-C003"
    assert workflow.next_unit_code(p) == "PU-003"


# --- change impact -----------------------------------------------------------

def test_expiry_watch_raises_one_change_per_certificate(session):
    n = session.query(ChangeEvent).filter_by(kind="certificate_expiry").count()
    assert n == 1
    assert changes.scan_expiries(session) == 0   # deduplicated


def test_change_reopens_items_and_flags_documents(session):
    p = _project(session, "PRJ-2026-001")
    for d in p.documents:
        d.status = "issued"
    ev = session.query(ChangeEvent).filter_by(kind="certificate_expiry").one()
    impact = changes.apply_change(session, ev, "test")
    assert impact["reopened"] >= 1 and impact["flagged"] == 2
    s = _sub(p, "C04-16", "PU-002")
    assert s.status == "submitted" and ev.code in s.reopened_reason
    assert all(d.status == "outdated" for d in p.documents)
    assert workflow.project_stage(p) != "issued"


def test_material_change_skips_platform_items_and_uncollected(session):
    ev = session.query(ChangeEvent).filter_by(kind="material_change").one()
    impact = changes.impact_of(session, ev.supplier_material, ev.doc_types, ev.kind)
    assert "C02-06" not in impact["items"]
    assert "C04-17" in impact["items"]       # the PFAS certificate type named on the change
    subs = session.query(Submission).filter(Submission.id.in_(impact["submissions"])).all()
    assert subs and all(s.status != "pending" for s in subs)


# --- generation --------------------------------------------------------------

def test_generate_scenario_b_and_a(session):
    b = _project(session, "PRJ-2026-001")
    made = generator.generate(session, b, "test")
    assert {d.kind for d in made} == {"TD", "DOC"}
    assert all(Path(d.path).exists() for d in made)
    a = _project(session, "PRJ-2026-002")
    made = generator.generate(session, a, "test")
    kinds = [d.kind for d in made]
    assert kinds.count("TD") == 2 and kinds.count("DOC") == 2 and "PACKAGE" in kinds


def test_td_marks_open_items(session):
    from docx import Document as Docx
    a = _project(session, "PRJ-2026-002")
    made = generator.generate(session, a, "test")
    td = next(d for d in made if d.kind == "TD")
    text = "\n".join(p.text for p in Docx(td.path).paragraphs)
    assert "DRAFT" in text and "OPEN" in text


def test_dossier_zip_uses_appendix_a_folders(session):
    import io
    import zipfile
    p = _project(session, "PRJ-2026-001")
    data = generator.dossier_zip(p, p.documents)
    names = zipfile.ZipFile(io.BytesIO(data)).namelist()
    assert any("/16_Test_Reports/" in n for n in names)
    assert any("/00_Document_Control/" in n and n.endswith(".docx") for n in names)

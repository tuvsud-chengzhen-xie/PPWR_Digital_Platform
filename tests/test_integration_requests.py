"""Client integration requests (Nov 2026): optional TD content, REACH / FCM items, importer marking,
consistent counts, 'if applicable' timing, LOD results, Chinese gap wording, navigation and sources."""
from app import catalogue, generator, guidance, rag, workflow
from app.db import Project, SessionLocal
from tests.conftest import login


def _sub(p, item_id, unit_code=None):
    return next(s for s in p.submissions if s.item_id == item_id and
                ((s.unit.code if s.unit else None) == unit_code))


def test_reach_and_fcm_items_exist_with_declaration_as_minimum():
    for iid in ("C04-74", "C04-75", "C04-76"):
        it = catalogue.item(iid)
        assert it and it["cat"] == 4
        assert guidance.level_of(iid)[0] == "supporting"
    mins = [m[2] for m in guidance.item_guidance("C04-74")["minimum"]]
    assert any(m.startswith("file:DCL") for m in mins)
    order = [i["id"] for i in catalogue.items()]
    assert order.index("C05-21") < order.index("C05-20")   # required item before the recommended one


def test_standards_list_covers_annex_vii_2d():
    cols = catalogue.item("C14-54")["table"]
    assert cols[:5] == ["Standard / specification", "Edition", "Clause", "Requirement covered", "Evidence"]
    assert any("harmonised standard" in c for c in cols) and any("in part" in c for c in cols)


def test_importer_required_only_when_imported(session):
    p = session.query(Project).filter_by(code="PRJ-2026-001").one()
    s = _sub(p, "C11-40", p.units[0].code)
    s.data = {"mfr": "Lumen GmbH, Hafenstr. 12, Hamburg", "imported": "Yes — imported from outside the EU", "loc": "back"}
    gaps = [g["en"] for g in guidance.evaluate(p, s)["gaps"]]
    assert any("importer" in g.lower() for g in gaps)
    s.data = {**s.data, "importer": "EU Import GmbH, Kaiserstr. 5, Frankfurt"}
    assert not any("importer" in g["en"].lower() for g in guidance.evaluate(p, s)["gaps"])


def test_guide_counts_match_listed_rows(session):
    for p in session.query(Project):
        rep = guidance.project_gaps(p)
        listed = {}
        for r in rep["rows"]:
            listed[r["ob"].code] = listed.get(r["ob"].code, 0) + 1
        for code in ("mandatory_now", "mandatory_from", "supporting", "practice"):
            assert rep["counts"][code] == listed.get(code, 0), (p.code, code)


def test_optional_content_can_be_left_out_of_the_td(session):
    p = session.query(Project).filter_by(code="PRJ-2026-002").one()
    u = p.units[0]
    opt = next(s for s in p.submissions if s.unit_id == u.id and not s.is_done
               and guidance.obligation(p, u, s.item_id).code == "supporting")
    req = next(s for s in p.submissions if s.unit_id == u.id and not s.is_done
               and guidance.obligation(p, u, s.item_id).code == "mandatory_now")
    before = workflow.progress(p.submissions)["total"]
    assert workflow.set_td_include(session, opt, False, "test")
    assert not workflow.set_td_include(session, req, False, "test")   # legally required stays in
    assert req.in_td and not opt.in_td
    assert workflow.progress(p.submissions)["total"] == before - 1
    assert all(r["sub"].id != opt.id for r in guidance.project_gaps(p)["rows"])
    scope = generator.Scope(p, u if p.scenario == "A" else None)
    assert opt in scope.left_out and opt not in scope.subs


def test_if_applicable_timing_for_na_items(session):
    p = session.query(Project).filter_by(code="PRJ-2026-001").one()
    ob = guidance.if_applicable(p, p.units[0], "C08-28")
    assert ob.code in ("mandatory_from", "mandatory_now") and ob.applies_from is not None


def test_below_lod_and_chinese_todo_wording(session):
    p = session.query(Project).filter_by(code="PRJ-2026-001").one()
    s = _sub(p, "C04-70", p.units[0].code)
    s.data = {"res": "< LOD"}
    ev = guidance.evaluate(p, s)
    assert next(m for m in ev["minimum"] if m["spec"].startswith("num_le"))["ok"] is True
    s.data = {}
    ev = guidance.evaluate(p, s)
    assert any(g["zh"].startswith("需填写报告编号") for g in ev["gaps"])
    # the AI check 'Report number and laboratory registered' repeats the minimum line — listed once
    assert sum("laboratory" in g["en"].lower() for g in ev["gaps"]) == 1


def test_pages_and_source_fallback(client, session):
    login(client, "expert")
    p = session.query(Project).filter_by(code="PRJ-2026-001").one()
    r = client.get(f"/projects/{p.id}/collect")
    assert r.status_code == 200 and "Annex VII" in r.text and 'id="row-' in r.text
    assert client.get("/projects/new").status_code == 200
    assert "目标完成日期" in client.get("/projects").text
    s = _sub(p, "C03-15", p.units[0].code)
    r = client.get(f"/projects/{p.id}/items/{s.id}")
    assert "data-back-to-list" in r.text and "Functionality" in r.text
    assert rag.kb_url("missing/none.pdf", 3).startswith("/kb-source/")
    r = client.get("/kb-source/missing/none.pdf?page=3")
    assert r.status_code == 404 and "eur-lex.europa.eu" in r.text and "data-go-back" in r.text
    p = session.query(Project).filter_by(code="PRJ-2026-002").one()
    opt = next(x for x in p.submissions if x.unit_id == p.units[0].id and not x.is_done
               and guidance.obligation(p, x.unit, x.item_id).code == "supporting")
    r = client.post(f"/projects/{p.id}/td-scope", data={"opt_ids": str(opt.id), "back": f"/projects/{p.id}/collect"},
                    follow_redirects=False)
    assert r.status_code == 303
    with SessionLocal() as s2:
        from app.db import Submission
        assert s2.get(Submission, opt.id).td_include is False

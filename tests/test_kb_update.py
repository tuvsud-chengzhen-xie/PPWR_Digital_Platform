"""Manual knowledge-base update → AI judgement change (Delegated Decision (EU) 2026/1948 showcase)."""
from app import assistant, kb_rules, rag
from app.db import KnowledgeEntry, Project, RegUpdate

from .conftest import login

ACT = """COMMISSION DELEGATED DECISION (EU) 2026/1948 of 12 August 2026 amending Decision 2001/171/EC as regards
crystal glass packaging (Text with EEA relevance) THE EUROPEAN COMMISSION, Official Journal of the European Union
EN L series 2026/1948 28.10.2026 HAS ADOPTED THIS DECISION: Article 5a 1. For the purposes of this Article,
"manufactured" means made. 2. By way of derogation from Article 5(4) of Regulation (EU) 2025/40, crystal glass
packaging shall be allowed to exceed the concentration levels referred to in that provision until 31 December 2029,
provided that it complies with Articles 5b and 5c of this Decision. 3. Crystal glass packaging containing lead may only
be manufactured until 31 December 2028. Article 5b 2. Crystal glass packaging covered by the derogation shall undergo a
dealkalisation treatment. Article 5c 1. Crystal glass packaging covered by the derogation shall bear a permanent
marking enabling identification of the crystal glass producer. Article 2 This Decision shall enter into force on the
day following that of its publication in the Official Journal of the European Union."""


def _sub(project, unit_code, item):
    return next(s for s in project.submissions if s.item_id == item and s.unit and s.unit.code == unit_code)


def test_extraction_reads_the_act():
    d = kb_rules.heuristic_draft(ACT, "act.pdf")
    assert d["ref"] == "Commission Delegated Decision (EU) 2026/1948"
    assert d["published"] == "2026-10-28" and d["applies_from"] == "2026-10-29"
    r = d["rule"]
    assert r["article"] == "a5" and r["scope_terms"] == ["crystal glass"]
    assert r["market_until"] == "2029-12-31" and r["manufactured_until"] == "2028-12-31"
    assert any("dealkalis" in c["terms"] for c in r["conditions"])
    assert "C04-16" in d["items"]
    assert kb_rules.draft_for(ACT)["origin"] == "desk"      # the regulatory desk has read this act


def test_publish_changes_ai_judgement_and_withdraw_reverts(client, session):
    login(client, "expert")
    p = session.query(Project).filter_by(code="PRJ-2026-003").one()
    pouch = session.query(Project).filter_by(code="PRJ-2026-002").one()
    assert _sub(p, "PU-001", "C04-16").ai_verdict == "fail"
    assert _sub(pouch, "PU-001", "C04-16").ai_verdict == "pass"
    before = assistant.answer("水晶玻璃香水瓶铅含量超过 100 mg/kg 可以豁免吗？")
    assert all(h["id"] != "KB-2026-1948" for h in before["sources"])

    d = kb_rules.draft_for(ACT)
    form = {"ref": d["ref"], "title": d["title"], "title_zh": d["title_zh"], "text": d["text"],
            "text_zh": d["text_zh"], "impact": d["impact"], "impact_zh": d["impact_zh"], "kind": d["kind"],
            "binding": "1", "published": d["published"], "applies_from": d["applies_from"], "page": "3",
            "articles": d["articles"], "items": d["items"], "rule_on": "1", "rule_article": "a5",
            "provision": "Art 5(4)", "limit_label": "100 mg/kg", "scope_terms": ", ".join(d["rule"]["scope_terms"]),
            "manufactured_until": d["rule"]["manufactured_until"], "market_until": d["rule"]["market_until"],
            "conditions": "\n".join(f"{c['en']} | {c['zh']} | {', '.join(c['terms'])} | {c['ref']}"
                                    for c in d["rule"]["conditions"])}
    r = client.post("/knowledge/manual/publish", data=form, follow_redirects=False)
    assert r.status_code == 303 and "/updates/" in r.headers["location"]
    session.expire_all()
    e = session.query(KnowledgeEntry).one()
    assert e.status == "active" and e.update_id and session.get(RegUpdate, e.update_id).origin == "manual"
    s = _sub(p, "PU-001", "C04-16")
    assert s.ai_verdict == "warn"
    assert any("2026/1948" in c["msg"] for c in s.ai_checks)
    assert any(c["ok"] is True and "Dealkalisation" in c["desc"] for c in s.ai_checks)  # evidence on file
    assert _sub(p, "PU-002", "C04-16").ai_verdict == "pass"            # gift box: not crystal glass
    assert _sub(pouch, "PU-001", "C04-16").ai_verdict == "pass"        # other client: unchanged
    assert e.rerun["changed"] == 2
    assert assistant.answer("水晶玻璃香水瓶铅含量超过 100 mg/kg 可以豁免吗？")["sources"][0]["id"] == "KB-2026-1948"
    assert rag.pool_entry("KB-2026-1948")["custom"]
    page = client.get(r.headers["location"].split("#")[0]).text
    assert "ai-change" in page and "PRJ-2026-003" in page
    assert client.get(f"/projects/{p.id}/items/{s.id}").status_code == 200   # live pre-check uses the rule too
    from app import monitor
    hit = {row["project"].code for row in monitor.impact(session.get(RegUpdate, e.update_id),
                                                         session.query(Project).all())}
    assert hit == {"PRJ-2026-003"}             # paper cards and the pouch are out of the rule's scope

    client.post(f"/knowledge/manual/{e.id}/withdraw", follow_redirects=False)
    session.expire_all()
    assert _sub(p, "PU-001", "C04-16").ai_verdict == "fail"
    assert rag.pool_entry("KB-2026-1948") is None
    client.post(f"/knowledge/manual/{e.id}/activate", follow_redirects=False)
    session.expire_all()
    assert _sub(p, "PU-001", "C04-16").ai_verdict == "warn"
    kb_rules.invalidate()


def test_manual_update_is_expert_only(client):
    login(client, "lumen")
    r = client.get("/knowledge/manual", follow_redirects=False)
    assert r.status_code in (303, 403)

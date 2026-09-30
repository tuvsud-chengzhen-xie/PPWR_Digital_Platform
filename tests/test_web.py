"""HTTP layer: pages render, access is scoped, the workflow round-trips."""
import io

from openpyxl import Workbook

from app.db import Project, Submission
from tests.conftest import login

PAGES = ["/", "/projects", "/projects/new", "/review", "/suppliers", "/changes", "/knowledge"]


def test_login_required(client):
    r = client.get("/", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/login"


def test_expert_pages_render(client, session):
    login(client, "expert")
    pages = list(PAGES)
    for p in session.query(Project):
        pages += [f"/projects/{p.id}{t}" for t in ("", "/packaging", "/collect", "/collect?unit=project",
                                                     "/evidence", "/documents", "/trace")]
    for url in pages:
        r = client.get(url)
        assert r.status_code == 200, url


def test_client_is_scoped_to_its_own_projects(client, session):
    login(client, "lumen")
    other = session.query(Project).filter_by(code="PRJ-2026-002").one()
    assert client.get(f"/projects/{other.id}").status_code == 404
    assert "PRJ-2026-002" not in client.get("/projects").text
    own = session.query(Project).filter_by(code="PRJ-2026-001").one()
    assert client.get(f"/projects/{own.id}").status_code == 200


def test_client_cannot_decide_or_issue(client, session):
    login(client, "lumen")
    p = session.query(Project).filter_by(code="PRJ-2026-001").one()
    s = next(x for x in p.submissions if x.status == "ai_reviewed")
    r = client.post(f"/projects/{p.id}/items/{s.id}/decide", data={"decision": "approve"}, follow_redirects=False)
    assert r.status_code == 303 and "experts" in r.headers["location"]
    session.refresh(s)
    assert s.status == "ai_reviewed"


def test_submit_ai_decide_round_trip(client, session):
    login(client, "expert")
    p = session.query(Project).filter_by(code="PRJ-2026-002").one()
    s = next(x for x in p.submissions if x.item_id == "C09-29" and x.unit and x.unit.code == "PU-001")
    r = client.post(f"/projects/{p.id}/items/{s.id}/save",
                    data={"f_concl": "Minimum mass for product protection, manufacturing, logistics and "
                                     "functionality; information and safety needs met.", "action": "submit"})
    assert r.status_code == 200
    r = client.post(f"/projects/{p.id}/items/{s.id}/ai")
    assert r.json()["ok"]
    r = client.post(f"/projects/{p.id}/items/{s.id}/decide", data={"decision": "reject", "comment": ""},
                    follow_redirects=False)
    assert "comment" in r.headers["location"]          # rejecting needs a reason
    client.post(f"/projects/{p.id}/items/{s.id}/decide", data={"decision": "approve", "comment": "ok"})
    session.expire_all()
    assert session.get(Submission, s.id).status == "approved"


def test_bom_import_from_template_layout(client, session):
    login(client, "aurora")
    p = session.query(Project).filter_by(code="PRJ-2026-002").one()
    wb = Workbook()
    ws = wb.active
    ws.append(["PPWR Packaging BOM"])
    ws.append(["No.", "Packaging System ID 包装编号", "Packaging Unit ID 包装单元编号", "Component ID  包装组件编号",
               "Packaging Type 包装类型", "Packaging Level 包装层级", "Packaging Description 包装描述",
               "Packaging Structure 包装结构", "Material 材质", "Component Mass (g) 重量", "Dimension (mm)  尺寸",
               "Supplier 供应商", "Recycled Content (%) (if yes)"])
    ws.append([1, "e.g. PS-001", "e.g. PU-001", "e.g. PU-001-C001"])
    ws.append([1, "PS-001", "PU-002", "PU-002-C002", "Stretch film", "Transport", "Pallet wrap", "Mono-material",
               "LDPE film", 12.5, "", "Rhein Wellpappe GmbH", 30])
    ws.append([2, "PS-001", "PU-003", "PU-003-C001", "Tray", "Grouped", "Display tray", "Mono-material",
               "Corrugated board", 95, "", "Unknown Supplier Ltd", ""])
    buf = io.BytesIO()
    wb.save(buf)
    r = client.post(f"/projects/{p.id}/bom/import", files={"file": ("bom.xlsx", buf.getvalue())})
    body = r.json()
    assert body["ok"], body
    session.expire_all()
    p = session.get(Project, p.id)
    codes = {c.code: c for u in p.units for c in u.components}
    assert codes["PU-002-C002"].material_group == "plastic" and codes["PU-002-C002"].recycled_pct == 30
    assert codes["PU-002-C002"].supplier is not None
    assert "PU-003" in {u.code for u in p.units}
    assert any("Unknown Supplier" in w for w in body["warnings"])


def test_certificate_renewal_raises_a_change(client, session):
    login(client, "lumen")
    from app.db import SupplierMaterial
    m = session.query(SupplierMaterial).filter_by(trace_code="CB-BF250-2025B").one()
    r = client.post(f"/suppliers/{m.supplier_id}/materials/{m.id}/certificates",
                    data={"doc_type": "hm", "number": "PRTC-2026-2201", "value": "35 mg/kg",
                          "issued": "2026-09-20", "expires": "2027-09-20"}, follow_redirects=False)
    assert r.status_code == 303 and "/changes/" in r.headers["location"]
    session.expire_all()
    from app.db import ChangeEvent
    assert session.query(ChangeEvent).filter_by(kind="certificate_expiry").one().status == "dismissed"


def test_downloads(client, session):
    login(client, "expert")
    p = session.query(Project).filter_by(code="PRJ-2026-001").one()
    assert client.get(f"/projects/{p.id}/bom.xlsx").status_code == 200
    assert client.get(f"/projects/{p.id}/evidence.xlsx").status_code == 200
    assert client.get(f"/projects/{p.id}/dossier.zip").headers["content-type"] == "application/zip"
    e = p.evidence[0]
    assert client.get(f"/evidence/{e.id}/download").status_code == 200
    d = p.documents[0]
    assert client.get(f"/documents/{d.id}/download").status_code == 200

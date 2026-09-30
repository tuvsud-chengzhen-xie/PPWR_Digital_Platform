"""Demo seed — two fictitious clients at different points of the service.

Lumen Home Products (scenario B, paper colour cards) is almost ready to issue;
Aurora Foods (scenario A, food-contact stand-up pouch, the deck's M-114 film
example) is early in collection and has an open supplier change to walk through.
All names, numbers and reports are invented for the pilot.
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy.orm import Session

from . import ai_review, auth, catalogue, changes, generator, storage, workflow
from .db import (Certificate, Client, Component, Evidence, PackagingUnit, Project, Supplier,
                 SupplierMaterial, now)
from .pdfmini import make_pdf

TODAY = dt.date.today()


def d(days: int) -> dt.date:
    return TODAY + dt.timedelta(days=days)


def _cert(mat, doc_type, number, issuer, issued, expires=None, value="", conclusion="conform"):
    c = Certificate(material=mat, doc_type=doc_type, number=number, issuer=issuer, issued=issued,
                    expires=expires, value=value, conclusion=conclusion)
    pdf = make_pdf(f"{catalogue.CERT_TYPES[doc_type]}", [
        f"Report / certificate no.: {number}", f"Issued by: {issuer}", f"Supplier: {mat.supplier.name}",
        f"Material: {mat.name} (trace code {mat.trace_code})", f"Result: {value or 'conform'}",
        f"Issued: {issued:%d %b %Y}" + (f"   Valid until: {expires:%d %b %Y}" if expires else ""),
        "", "DEMO DOCUMENT - generated for the PPWR Digital Platform pilot."])
    c.filename = f"{number}.pdf"
    c.stored_path = str(storage.save(f"suppliers/{mat.supplier.code}", mat.code, c.filename, pdf))
    return c


def _supplier(session, client, code, name, country, address, materials):
    s = Supplier(client=client, code=code, name=name, country=country, address=address,
                 contact=f"compliance@{name.split()[0].lower()}.example")
    session.add(s)
    out = {}
    for m in materials:
        mat = SupplierMaterial(supplier=s, code=m["code"], trace_code=m["trace"], name=m["name"],
                               material=m["material"], material_group=m["group"])
        session.add(mat)
        for cert in m.get("certs", []):
            session.add(_cert(mat, *cert))
        out[m["code"]] = mat
    return s, out


def _evidence(session, project, unit, comp, item_id, title, type_code, file_no, issuer, issued, actor,
              conformity="Conform", supplier=""):
    code = workflow.next_evidence_code(session, project, unit, comp, type_code)
    pdf = make_pdf(title, [f"Evidence ID: {code}", f"Document no.: {file_no}", f"Issued by: {issuer}",
                           f"Issue date: {issued:%d %b %Y}", f"Project: {project.code} - {project.title}",
                           "", "DEMO DOCUMENT - generated for the PPWR Digital Platform pilot."])
    fn = f"{file_no}.pdf"
    path = storage.save(project.code, code, fn, pdf)
    e = Evidence(project=project, unit_id=unit.id if unit else None, component_id=comp.id if comp else None,
                 item_id=item_id, code=code, title=title, type_code=type_code, file_no=file_no, issuer=issuer,
                 issued_date=issued, responsible="Applicant", conformity=conformity, supplier_name=supplier,
                 filename=fn, stored_path=str(path), size=len(pdf), uploaded_by=actor)
    session.add(e)
    session.flush()
    return e


def _set(project, unit, item_id, data=None, table=None):
    for s in project.submissions:
        if s.item_id == item_id and s.unit_id == (unit.id if unit and catalogue.item(item_id)["scope"] == "unit" else None):
            if data:
                s.data = {**(s.data or {}), **data}
            if table:
                s.table = table
            return s
    raise KeyError(item_id)


def _advance(session, project, target: dict, actor_client: str, default="approved"):
    """Walk every open submission through the workflow to its target state."""
    for s in project.submissions:
        if s.status == "na" or s.status == "approved":
            continue
        want = target.get((s.item_id, s.unit.code if s.unit else None), target.get(s.item_id, default))
        if want == "pending":
            continue
        unit = s.unit
        ev = [e for e in project.evidence if e.item_id == s.item_id and e.unit_id in ((unit.id if unit else None), None)]
        it = catalogue.item(s.item_id)
        if not ev and it["id"] not in ai_review.FIELD_ONLY and want in ("approved", "ai_reviewed"):
            # a near-finished file has its evidence: one demo document per open narrative item
            no = f"{project.client.name.split()[0].upper()[:3]}-{s.item_id}-{unit.code if unit else 'ALL'}"
            ev = [_evidence(session, project, unit, None, s.item_id, it["name"], it["evidence_code"], no,
                            project.client.name, TODAY - dt.timedelta(days=30 + len(project.evidence)),
                            actor_client)]
        workflow.submit(session, s, actor_client)
        if want == "submitted":
            continue
        ai_review.apply(s, project, unit, ev)
        if want == "ai_reviewed":
            continue
        if want == "rejected":
            workflow.decide(session, s, "reject", "Drawing revision R2 does not match artwork R1 — please "
                                                  "upload the matching revision.", "HDL PPWR Expert")
        else:
            workflow.decide(session, s, "approve", "", "HDL PPWR Expert")


def seed(session: Session) -> None:
    if session.query(Client).count():
        return

    # ------------------------------------------------------------------ Lumen
    lumen = Client(name="Lumen Home Products Co., Ltd.", country="China",
                   address="No. 88 Innovation Road, Songshan Lake, Dongguan, Guangdong, China",
                   contact_name="Grace Lin", contact_email="packaging@lumen-home.example",
                   eu_representative="Lumen Home Europe B.V., Keizersgracht 100, 1015 CS Amsterdam, NL")
    session.add(lumen)
    _, hengda = _supplier(session, lumen, "SUP-001", "Hengda Paperboard Co., Ltd.", "China",
                          "Dongguan, Guangdong", [dict(
                              code="SPT-001", trace="PAP20-300GSM-2024A", name="Coated paperboard 300 g/m²",
                              material="Coated paperboard (PAP 20)", group="paper", certs=[
                                  ("hm", "PRTC-2026-0412", "Pearl River Testing Centre", d(-200), d(165), "32 mg/kg"),
                                  ("doc", "HD-DCL-2026-07", "Hengda Paperboard", d(-80), d(285)),
                                  ("td", "HD-TDS-300C", "Hengda Paperboard", d(-400)),
                                  ("rc", "HD-RC-EN13430", "Hengda Paperboard", d(-120), d(245)),
                                  ("fsc", "FSC-C123456", "FSC accredited CB", d(-300), d(800))])])
    _, bright = _supplier(session, lumen, "SUP-002", "Brightink Printing Materials Ltd.", "China",
                          "Shenzhen, Guangdong", [dict(
                              code="SPT-002", trace="INK-LM-4C-2025", name="Low-migration offset ink set (CMYK)",
                              material="Offset ink, mineral-oil free", group="other", certs=[
                                  ("hm", "BI-HM-2025-118", "Pearl River Testing Centre", d(-310), d(55), "12 mg/kg"),
                                  ("doc", "BI-DCL-2026-02", "Brightink", d(-150), d(215)),
                                  ("comp", "BI-COMP-4C", "Brightink", d(-150))])])
    _, dcw = _supplier(session, lumen, "SUP-003", "Dongguan Carton Works", "China", "Humen, Dongguan", [dict(
        code="SPT-003", trace="CB-BF250-2025B", name="Corrugated board B-flute 250 g/m²",
        material="Corrugated fibreboard", group="paper", certs=[
            ("hm", "PRTC-2025-1187", "Pearl River Testing Centre", d(-348), d(17), "41 mg/kg"),
            ("doc", "DCW-DCL-2026", "Dongguan Carton Works", d(-90), d(275)),
            ("rc", "DCW-RC-2026", "Dongguan Carton Works", d(-90), d(275))])])

    p1 = Project(code="PRJ-2026-001", client=lumen, title="Printed colour card set (20 cards)",
                 product_description="Printed colour reference cards sold in retail as a set of 20; the card "
                                     "is the sales packaging of the product information set and is shipped "
                                     "in corrugated cartons. Non food-contact, single-use.",
                 ps_code="PS-001", scenario="B", target_date=d(24), created_by="HDL PPWR Expert",
                 created_at=now() - dt.timedelta(days=41))
    session.add(p1)
    u1 = PackagingUnit(project=p1, code="PU-001", name="Printed colour card", level="Sales", pack_type="Card",
                       upi="LUM-PS001-PU001", skus="CC-2026-A / CC-2026-B", mass_g=14, dims="210 × 297 × 0.3",
                       supplier_name="Hengda Paperboard Co., Ltd.", site="Dongguan plant 2", country="China",
                       artwork_ref="ART-2026-001 R1")
    u2 = PackagingUnit(project=p1, code="PU-002", name="Shipping carton (20 sets)", level="Transport",
                       pack_type="Carton", upi="LUM-PS001-PU002", skus="CC-2026-A / CC-2026-B", mass_g=212,
                       dims="400 × 300 × 250", supplier_name="Dongguan Carton Works", site="Humen",
                       country="China", artwork_ref="ART-2026-014 R1")
    session.add_all([u1, u2])
    session.flush()
    session.add_all([
        Component(unit=u1, code="PU-001-C001", pack_type="Card", description="Printed card body",
                  structure="Mono-material", material="Coated paperboard 300 g/m² (PAP 20)", material_group="paper",
                  mass_g=13.6, dims="210 × 297 × 0.3", supplier=hengda["SPT-001"].supplier,
                  supplier_material=hengda["SPT-001"], recycled_pct=0),
        Component(unit=u1, code="PU-001-C002", pack_type="Ink", description="4-colour offset print",
                  structure="Other", material="Offset ink, mineral-oil free", material_group="other",
                  mass_g=0.4, supplier=bright["SPT-002"].supplier, supplier_material=bright["SPT-002"]),
        Component(unit=u2, code="PU-002-C001", pack_type="Carton", description="RSC shipping carton",
                  structure="Mono-material", material="Corrugated fibreboard B-flute", material_group="paper",
                  mass_g=205, dims="400 × 300 × 250", supplier=dcw["SPT-003"].supplier,
                  supplier_material=dcw["SPT-003"]),
        Component(unit=u2, code="PU-002-C002", pack_type="Tape", description="Water-activated paper tape",
                  structure="Mono-material", material="Kraft paper tape, starch adhesive", material_group="paper",
                  mass_g=7),
    ])
    session.flush()
    session.refresh(p1)
    workflow.ensure_submissions(session, p1)
    actor = "Lumen Home — Packaging Compliance"

    c = {x.code: x for u in p1.units for x in u.components}
    _evidence(session, p1, u1, None, "C01-05", "Product photographs (front / back / scale)", "PHO", "LUM-PHO-001",
              "Lumen Home", d(-35), actor)
    _evidence(session, p1, u1, c["PU-001-C001"], "C02-07", "TDS coated paperboard 300 g/m²", "MSD", "HD-TDS-300C",
              "Hengda Paperboard", d(-400), actor, supplier="Hengda Paperboard Co., Ltd.")
    _evidence(session, p1, u1, None, "C03-10", "Card design drawing", "DRW", "DWG-CC-2026-01 R1", "Lumen Home",
              d(-60), actor)
    _evidence(session, p1, u1, None, "C03-11", "Die-cut drawing", "DRW", "DIE-CC-2026-01 R2", "Lumen Home",
              d(-58), actor)
    _evidence(session, p1, u1, c["PU-001-C001"], "C04-16", "Heavy-metal test report — card incl. inks", "TST",
              "PRTC-2026-0412", "Pearl River Testing Centre", d(-200), actor, supplier="Hengda Paperboard Co., Ltd.")
    _evidence(session, p1, u2, c["PU-002-C001"], "C04-16", "Heavy-metal test report — carton", "TST",
              "PRTC-2025-1187", "Pearl River Testing Centre", d(-348), actor, supplier="Dongguan Carton Works")
    _evidence(session, p1, u1, None, "C05-19", "Recyclability assessment EN 13430 — colour card", "RPT",
              "LUM-RC-2026-01", "Lumen Home", d(-30), actor)
    _evidence(session, p1, u2, None, "C09-30", "ISTA 3A transport test — shipping carton", "TST", "ISTA-26-0931",
              "Pearl River Testing Centre", d(-45), actor)
    _evidence(session, p1, u1, None, "C11-40", "Final artwork with manufacturer address and batch field", "PHO",
              "ART-2026-001 R1", "Lumen Home", d(-60), actor)
    _evidence(session, p1, None, None, "C12-46", "PPWR risk analysis workbook", "RPT", "LUM-RA-2026-01",
              "Lumen Home", d(-20), actor)

    for u in (u1, u2):
        _set(p1, u, "C03-10", {"docno": "DWG-CC-2026-01 R1" if u is u1 else "DWG-SC-2026-04 R1"})
        _set(p1, u, "C03-11", {"docno": "DIE-CC-2026-01 R2" if u is u1 else "DIE-SC-2026-04 R1"})
        _set(p1, u, "C03-12", {"docno": "ART-2026-001 R1" if u is u1 else "ART-2026-014 R1"})
        _set(p1, u, "C03-13", {"docno": "SPEC-CC-01" if u is u1 else "SPEC-SC-04"})
        _set(p1, u, "C03-14", {"docno": "CP-DG2-2026"})
        _set(p1, u, "C03-15", {"rationale": "Card thickness is the minimum that keeps the colour swatches flat "
                                            "and legible; no additional wrapping."})
        _set(p1, u, "C04-16", {"res": "< 50" if u is u1 else "41", "method": "EN 13657 digestion + ICP-OES"})
        _set(p1, u, "C04-17", {"app": "Not applicable (non food-contact)",
                               "note": "Colour cards are not intended to contact food (Art 5(5))."})
        _set(p1, u, "C04-18", {"app": "No — not food-contact"})
        _set(p1, u, "C05-19", {"concl": "Mono-material paper-based packaging; recyclable in the paper stream. "
                                        "Inks are mineral-oil free and do not impair repulping. Expected grade A."})
        _set(p1, u, "C05-21", {"method": "EN 13430 (material recycling), EN 18120-3 draft for paper"})
        _set(p1, u, "C09-29", {"concl": "Mass and volume are the minimum for protection and information of the "
                                        "product; manufacturing and logistics constraints documented; "
                                        "functionality and safety unaffected."})
        _set(p1, u, "C09-35", {"note": "Sales card — no empty space." if u is u1 else
                               "Empty-space ratio 18 % (20 sets, 400 × 300 × 250 mm)."})
        _set(p1, u, "C09-36", {"app": "None"})
        _set(p1, u, "C10-37", {"app": "Single-use (not applicable)"})
        _set(p1, u, "C11-40", {"loc": "Back panel, lower left: manufacturer name, postal address, batch no."})
    _set(p1, None, "C14-54", table=[
        ["EN 13427:2004", "2004", "all", "Use of the EN 13428–13432 set", "—"],
        ["EN 13428:2004", "2004", "4", "Prevention by source reduction (Art 10)", "LUM-RA-2026-01"],
        ["EN 13430:2004", "2004", "4–5", "Material recycling (Art 6)", "LUM-RC-2026-01"],
        ["EN 13657 + ICP-OES", "2002", "—", "Heavy metals (Art 5(4))", "PRTC-2026-0412"],
    ])
    _set(p1, None, "C12-46", {})
    session.flush()
    _advance(session, p1, {
        ("C03-11", "PU-001"): "rejected", "C09-29": "ai_reviewed", ("C09-35", "PU-002"): "submitted",
        ("C11-43", "PU-001"): "pending", ("C11-43", "PU-002"): "pending", "C16-66": "pending", "C16-69": "pending",
        "C12-46": "ai_reviewed", ("C13-53", "PU-002"): "submitted",
    }, actor)

    # ------------------------------------------------------------------ Aurora
    aurora = Client(name="Aurora Foods GmbH", country="Germany",
                    address="Industriestraße 12, 70565 Stuttgart, Germany",
                    contact_name="Jonas Weber", contact_email="qa@aurora-foods.example")
    session.add(aurora)
    _, flexi = _supplier(session, aurora, "SUP-001", "FlexiFilm Packaging s.r.o.", "Czechia", "Brno", [dict(
        code="SPT-001", trace="M-114", name="PET/PE laminate film 12/80 µm", material="PET/PE laminate",
        group="plastic", certs=[
            ("hm", "TR-2026-0841", "Labor Mitte GmbH", d(-150), d(215), "38 mg/kg"),
            ("pf", "TR-2026-0902", "Labor Mitte GmbH", d(-120), d(310), "PFAS not detected (TF < 10 ppm)"),
            ("doc", "FF-DoC-2026-M114", "FlexiFilm", d(-100), d(265)),
            ("td", "FF-TDS-M114", "FlexiFilm", d(-500))])])
    _, captec = _supplier(session, aurora, "SUP-002", "CapTec Closures AG", "Switzerland", "St. Gallen", [dict(
        code="SPT-002", trace="PP-SPOUT-82", name="PP spout with cap 8.2 mm", material="PP",
        group="plastic", certs=[
            ("hm", "CT-HM-2026-11", "Labor Mitte GmbH", d(-60), d(305), "15 mg/kg"),
            ("pf", "CT-PF-2026-11", "Labor Mitte GmbH", d(-60), d(305), "PFAS not detected"),
            ("doc", "CT-DoC-2026", "CapTec", d(-60), d(305))])])
    _, rhein = _supplier(session, aurora, "SUP-003", "Rhein Wellpappe GmbH", "Germany", "Mannheim", [dict(
        code="SPT-003", trace="RW-EF-2026", name="Corrugated shipper E-flute", material="Corrugated fibreboard",
        group="paper", certs=[
            ("hm", "RW-HM-2026-03", "Labor Mitte GmbH", d(-210), d(155), "29 mg/kg"),
            ("rc", "RW-RC-2026", "Rhein Wellpappe", d(-210), d(155)),
            ("fsc", "FSC-C654321", "FSC accredited CB", d(-400), d(700))])])

    p2 = Project(code="PRJ-2026-002", client=aurora, title="Stand-up pouch 200 ml — tomato & herb sauce",
                 product_description="Retort stand-up pouch with spout for a 200 ml sauce; 24 pouches per "
                                     "shipper. Food-contact, single-use.",
                 ps_code="PS-001", scenario="A", food_contact=True, target_date=d(52),
                 created_by="HDL PPWR Expert", created_at=now() - dt.timedelta(days=9))
    session.add(p2)
    a1 = PackagingUnit(project=p2, code="PU-001", name="Stand-up pouch 200 ml", level="Sales",
                       pack_type="Pouch", upi="AUR-F2047-PU001", skus="AF-SAU-200-TH / AF-SAU-200-TB",
                       mass_g=10.9, dims="130 × 190 × 70", supplier_name="FlexiFilm Packaging s.r.o.",
                       site="Brno", country="Czechia", artwork_ref="AUR-ART-2047 R3")
    a2 = PackagingUnit(project=p2, code="PU-002", name="Shipper (24 pouches)", level="Transport",
                       pack_type="Carton", upi="AUR-F2047-PU002", skus="AF-SAU-200-TH / AF-SAU-200-TB",
                       mass_g=180, dims="395 × 265 × 205", supplier_name="Rhein Wellpappe GmbH",
                       site="Mannheim", country="Germany")
    session.add_all([a1, a2])
    session.flush()
    session.add_all([
        Component(unit=a1, code="PU-001-C001", pack_type="Pouch", description="Laminate pouch body",
                  structure="Multi-layer", material="PET/PE laminate 12/80 µm", material_group="plastic",
                  mass_g=7.8, supplier=flexi["SPT-001"].supplier, supplier_material=flexi["SPT-001"],
                  recycled_pct=0),
        Component(unit=a1, code="PU-001-C002", pack_type="Spout & cap", description="Spout with tamper cap",
                  structure="Mono-material", material="PP", material_group="plastic", mass_g=3.1,
                  supplier=captec["SPT-002"].supplier, supplier_material=captec["SPT-002"], recycled_pct=0),
        Component(unit=a2, code="PU-002-C001", pack_type="Carton", description="Shipper, E-flute",
                  structure="Mono-material", material="Corrugated fibreboard E-flute", material_group="paper",
                  mass_g=180, supplier=rhein["SPT-003"].supplier, supplier_material=rhein["SPT-003"]),
    ])
    session.flush()
    session.refresh(p2)
    workflow.ensure_submissions(session, p2)
    actor2 = "Aurora Foods — Quality & Regulatory"
    c2 = {x.code: x for u in p2.units for x in u.components}
    _evidence(session, p2, a1, c2["PU-001-C001"], "C04-16", "Heavy-metal report — laminate M-114", "TST",
              "TR-2026-0841", "Labor Mitte GmbH", d(-150), actor2, supplier="FlexiFilm Packaging s.r.o.")
    _evidence(session, p2, a1, c2["PU-001-C001"], "C04-17", "PFAS total fluorine — laminate M-114", "TST",
              "TR-2026-0902", "Labor Mitte GmbH", d(-120), actor2, supplier="FlexiFilm Packaging s.r.o.")
    _set(p2, a1, "C04-16", {"res": "38", "method": "EN 13657 + ICP-MS"})
    _set(p2, a1, "C04-17", {"app": "Applicable (food-contact)",
                            "note": "Total fluorine < 10 ppm; targeted PFAS not detected (TR-2026-0902)."})
    _set(p2, a1, "C04-18", {"app": "Yes — food-contact"})
    _set(p2, a2, "C04-18", {"app": "No — not food-contact"})
    session.flush()
    target = {k: "pending" for k in [i["id"] for i in catalogue.items()]}
    target.update({"C01-01": "approved", "C01-02": "approved", "C01-03": "approved", "C01-04": "approved",
                   ("C04-16", "PU-001"): "ai_reviewed", ("C04-17", "PU-001"): "ai_reviewed",
                   "C04-18": "submitted"})
    _advance(session, p2, target, actor2, default="pending")

    session.flush()
    for p in (p1, p2):
        session.refresh(p)
        workflow.sync(session, p)
    generator.generate(session, p1, "HDL PPWR Expert", trigger="seed")
    session.flush()

    # the deck's showcase: Supplier B swaps the resin on film M-114 (open, ready to apply)
    changes.raise_change(session, flexi["SPT-001"], "material_change",
                         "Resin swap on laminate film M-114 (PE sealant layer)",
                         "FlexiFilm notified a change of the PE sealant resin grade on M-114 from Q4 2026 "
                         "(supplier change notice FF-CN-2026-17). New heavy-metal / PFAS evidence and a "
                         "recyclability re-check are needed for every packaging using M-114.",
                         ["hm", "pf", "rc"], "Aurora Foods — Quality & Regulatory")
    changes.scan_expiries(session)
    auth.ensure_demo_users(session)
    session.commit()

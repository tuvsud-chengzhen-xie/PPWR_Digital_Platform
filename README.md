# PPWR Digital Platform — TD & EU DoC service

A TÜV SÜD **CPS CoE × HDL** pilot of the client-facing platform proposed in
*20260921_CPS CoE & HDL_PPWR Digital Platform.pptx*: it digitalises the PPWR
**Technical Documentation (TD)** and **EU Declaration of Conformity (DoC)** service under
Regulation (EU) 2025/40 — packaging & BOM registration, evidence collection, two-stage review,
automated TD / DoC generation, and a supplier library whose changes are traced to every
affected document.

Built with Python / FastAPI / SQLite (SQLAlchemy) / Jinja2 on the
[`cps-coe-design-system_v1.1`](cps-coe-design-system_v1.1/README.md) — same shell, tokens,
glass cards and AI identity as the other CPS CoE apps.

## Run

Double-click **`Start PPWR Platform.command`** — it installs dependencies, starts the server on
<http://127.0.0.1:8130> and opens the browser. Or:

```bash
python3 -m pip install --user -r requirements.txt
python3 -m uvicorn app.main:app --port 8130
```

Demo accounts (password `demo`, shown on the login page): **expert** (HDL reviewer, sees all
clients), **lumen** and **aurora** (client users, each sees only its own projects and suppliers).
The demo seed runs once into `data/`; *reset demo data* in the footer (expert) restores it.

Tests: `python3 -m pytest tests -q` — 27 tests covering the catalogue, applicability matrix,
workflow, AI pre-review rules, change impact, TD/DoC generation, BOM import and access scoping.

## What the service does

| Step | Who | Where in the app |
|---|---|---|
| Register packaging units (PU) and their BOM components — by hand or by dropping a filled **PPWR_BOM_V1.xlsx** | Client | Project → Packaging & BOM |
| Collect data and evidence for **16 categories · 69 items** (Checklist V1.5 / V3.1 prototype), per unit | Client | Project → Data collection → item |
| **AI pre-review** of each submission: completeness, Art 5(4) limit, applicability consistency, BOM mass cross-check, evidence age (< 24 months), supplier certificates — each check cites its source | Platform (Layer-3) | Review queue / item page |
| **Expert decision**: approve, reject with comment, confirm N/A | TÜV SÜD expert | Review queue / item page |
| Generate **TD** (TD V1.5: T00, T01, §1–§21, App. A/B = Annex VII Module A point 2 a–f) and **EU DoC** (Annex VIII points 1–8) as Word, versioned; DRAFT + OPEN markers until 100 % | Anyone; issue = expert | Project → TD & DoC |
| One-click **authority dossier** (Art 15(10), 10 days) — TD, DoC and every evidence file in the Appendix A folders | Anyone | Project → TD & DoC |
| Supplier library: materials with trace codes and certificates; expiry watch (≤ 30 days) | Client | Suppliers |
| **Change impact**: a renewal, expiry or material change is walked material → components → units → projects → items → documents; applying it re-opens items and flags documents “update required” (Art 39(2)) | Client / expert | Change impact |

### Scenarios (from the V3.1 prototype)

- **A — per-unit technical file**: each packaging unit gets its own TD + DoC; a document-package
  overview indexes them for the final packaging user.
- **B — consolidated technical file**: producer = packaging manufacturer; one TD (§2 lists every
  unit) and one DoC.

### Identifiers (manual-collection kit)

`PS-001` packaging system → `PU-001` packaging unit → `PU-001-C001` component →
`PU-001-C001-TST-001` evidence (type codes DRW, TST, DCL, MSD, PHO, BOM, CAL, REC, CRT, RPT).

### Applicability matrix

Derived from the project profile (food contact, reusable, Art 9 type, biobased claim) and the BOM
material groups. Items for an article that is not applicable are closed automatically with the
rationale that TD §5 / §19 quote; if the profile changes, they re-open.

## Code map

```
app/
  main.py            app, sign-in, mounts (/ds design system, /kb-files knowledge base, /kit templates)
  db.py              SQLAlchemy models (Client, User, Supplier, SupplierMaterial, Certificate, Project,
                     PackagingUnit, Component, Submission, Evidence, Document, ChangeEvent, AuditEvent)
  catalogue.py       69-item catalogue (seeds/catalogue.json, built by tools/build_catalogue.py)
  applicability.py   PPWR applicability matrix (TD §5)
  workflow.py        submission states, auto-N/A, progress, TD readiness, ID generation
  ai_review.py       AI pre-review rule engine (Layer-3 interface; LLM + RAG in production)
  changes.py         change-impact engine and certificate expiry watch
  generator.py       TD / DoC / document package (python-docx) and the authority dossier zip
  excel_io.py        BOM import, BOM + Evidence List export in the client templates' layout
  seed.py            two fictitious demo clients
  routers/           dashboard, projects, review (collection + queue), evidence, documents,
                     suppliers (+ changes), catalogue_views (knowledge base)
  templates/, static/  CPS CoE shell + app styles
tools/build_catalogue.py   regenerates the catalogue from the V3.1 prototype data
tests/                     pytest suite
```

## Pilot boundaries → production

- **AI pre-review** is a deterministic rule engine over the PPWR knowledge base, behind the same
  interface (`ai_review.review`) that an LLM + RAG service over `PPWR Knowledgebase/` would use.
  It is advisory; the expert decides.
- **Storage** is local disk (`data/uploads`) and SQLite; production → object storage + a server DB.
- **Auth** is local PBKDF2 accounts; production → corporate SSO.
- **Signature** of the DoC stays with the manufacturer (Art 39(4)); the platform issues the
  reviewed documents, it does not sign them.
- The manual-collection guide images cite the draft numbering (Annex II / Art 45); the platform
  follows the adopted Regulation — TD per **Annex VII**, DoC per **Art 39 / Annex VIII**,
  recyclability **Annex II**, minimisation **Annex IV**.

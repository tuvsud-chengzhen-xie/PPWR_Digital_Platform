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

Tests: `python3 -m pytest tests -q` — 46 tests covering the catalogue, applicability matrix,
workflow, AI pre-review rules, change impact, TD/DoC generation, BOM import, access scoping, and the
guidance / RAG / smart-import / regulatory-monitoring features (`tests/test_guidance.py`). Tests skip
the full-text index (`PPWR_RAG_CORPUS=0`); the curated knowledge pool is always searched.

## Bilingual, guided, knowledge-based (v2)

| Feature | Where | How it works |
|---|---|---|
| **中文 / English** interface, regulatory content, guidance and AI output | top-bar toggle `Bilingual · English` (the navigation bar itself is always English) | `app/i18n.py` (`t()`, `tt()`, `tf()` helpers); catalogue, knowledge pool, guidance and AI checks carry `*_zh` text |
| **Dynamic evidence guidance** | item page → *Evidence requirements*; project → *Compliance guide* | `app/guidance.py`: legal level per item (`seeds/guidance/levels.json` — *required* by the PPWR text / *recommended evidence* / *good practice*, each citing its provision) × applicability matrix × application date → “legally required now / from <date> / recommended / not required”; due date, minimum evidence evaluated live, gaps, recommendations |
| **Interactive client guidance** | item page → five folds + *Check my entry* | regulation, key terms & logic · information, document types, formats & acceptance criteria · steps with acceptable / rejected examples · samples, Word template (`template.docx`) & validation rules · sources. Field formats validated as you type; a dry-run pre-check lists omissions before submission; uploads are checked for format and for looking like another item |
| **RAG pipeline** | item rail *Ask about this item*; *Knowledge & AI* page | `app/rag.py`: curated, bilingual knowledge pool (`seeds/knowledge_pool.json` — regulation articles, harmonised standards, implementing / delegated acts, official interpretations, good practice; each with source file + page) **plus** the full text of every PDF/HTML in `PPWR Knowledgebase/` (pypdf, page-level chunks, BM25 with Chinese bigrams and a 中→EN glossary; cached in `data/kb_index.json`, rebuilt when the folder changes). `app/assistant.py` answers only from retrieved sources with `[S#]` citations, separating binding from non-binding sources, or says the knowledge base does not cover the question |
| **Optional LLM** | ⚙ *AI settings* (expert) | `app/llm.py`: Azure OpenAI or OpenAI-compatible endpoint (or env `PPWR_LLM_PROVIDER / _ENDPOINT / _API_KEY / _MODEL / _API_VERSION`). The model only sees retrieved sources; on any error the local answer is used. The key is stored in `data/ai_settings.json` (git-ignored) |
| **Regulatory monitoring** | *Reg. updates* (nav badge), dashboard, project overview / guide, item hints | `app/monitor.py`: curated updates (`seeds/reg_updates.json`, each traced to a knowledge-base document); scanner that turns new / changed files in `PPWR Knowledgebase/` into updates mapped to articles and items (expert review pending); optional web watch (`PPWR_MONITOR_URLS`). Impact per project (open items to collect, approved items to re-check, issued documents); expert can re-open affected items (Art 15(4)) |
| **Smart import** (V4.2 one-click upload + AI identification) | project → *Smart import* | `app/importer.py`: files, folders or ZIPs identified by item code, number, the V4.2 bilingual keyword library (`seeds/import_rules.json`), Appendix-A folder, content (PDF / DOCX / XLSX / text) with the V4.2 lock rules, and learned corrections; unit from `PU-xxx` / `PKG-xx` / UPI; staged for review, then imported with evidence IDs, auto-submit and AI pre-review. Tables (paste / XLSX / CSV) map to units, BOM lines and item fields |
| **Art 5 evidence items** (V4.2) | category 4 | C04-70 heavy-metal CoC / report, C04-71 PFAS report, C04-72 food-contact declaration, C04-73 Art 5 statement (good practice) — 73 items in total |

Accuracy rules: every “required” statement cites the provision it rests on (checked against the
adopted text, OJ L 22.1.2025, and the Commission FAQ 2026); anything else is labelled recommended or
good practice; the assistant never answers beyond its sources. Copyrighted standards (DIN EN) are
indexed by title only.

The first start builds the full-text index in the background (≈ 1–2 min for the current knowledge
base); until then the assistant uses the curated pool.

## What the service does

| Step | Who | Where in the app |
|---|---|---|
| Register packaging units (PU) and their BOM components — by hand or by dropping a filled **PPWR_BOM_V1.xlsx** | Client | Project → Packaging & BOM |
| Collect data and evidence for **16 categories · 73 items** (Checklist V1.5 / V3.1 prototype + V4.2 Art 5 evidence items), per unit | Client | Project → Data collection → item |
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
  catalogue.py       73-item catalogue (seeds/catalogue.json, built by tools/build_catalogue.py)
  applicability.py   PPWR applicability matrix (TD §5)
  workflow.py        submission states, auto-N/A, progress, TD readiness, ID generation
  ai_review.py       AI pre-review rule engine (bilingual checks; Layer-3 interface)
  guidance.py        dynamic evidence guidance: legal level × timeline, minimum evidence, gaps, hints, templates
  rag.py             knowledge pool + full-text corpus index (BM25, 中/EN), search with citations
  assistant.py       grounded, cited, bilingual answers (local or via llm.py)
  llm.py             optional Azure OpenAI / OpenAI-compatible connector
  monitor.py         regulatory updates: seed, knowledge-base scanner, impact, notifications
  importer.py        smart import (V4.2 identification engine, staging, table mapping, one-click import)
  i18n.py            bilingual presentation helpers and language modes
  changes.py         change-impact engine and certificate expiry watch
  generator.py       TD / DoC / document package (python-docx) and the authority dossier zip
  excel_io.py        BOM import, BOM + Evidence List export in the client templates' layout
  seed.py            two fictitious demo clients
  routers/           dashboard, projects, review (collection + queue), evidence, documents,
                     suppliers (+ changes), catalogue_views (knowledge base), guide (compliance guide,
                     pre-check, templates, assistant, language), imports (smart import),
                     monitoring (regulatory updates), settings (AI / index)
  seeds/             catalogue, knowledge_pool, guidance/*, reg_updates, import_rules (all bilingual)
  templates/, static/  CPS CoE shell + app styles
tools/build_catalogue.py   regenerates the catalogue from the V3.1 prototype data
tests/                     pytest suite
```

## Pilot boundaries → production

- **AI pre-review** is a deterministic, bilingual rule engine; the guidance, assistant and update
  summaries use RAG over `PPWR Knowledgebase/` and, when configured, an LLM that may only use the
  retrieved sources. All AI output is advisory; the expert decides.
- **OCR** is not included: scanned PDFs and images are identified by file name only.
- **Storage** is local disk (`data/uploads`) and SQLite; production → object storage + a server DB.
- **Auth** is local PBKDF2 accounts; production → corporate SSO.
- **Signature** of the DoC stays with the manufacturer (Art 39(4)); the platform issues the
  reviewed documents, it does not sign them.
- The manual-collection guide images cite the draft numbering (Annex II / Art 45); the platform
  follows the adopted Regulation — TD per **Annex VII**, DoC per **Art 39 / Annex VIII**,
  recyclability **Annex II**, minimisation **Annex IV**.

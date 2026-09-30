"""Paths and constants for the PPWR Digital Platform."""
from __future__ import annotations

import os
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
ROOT = APP_DIR.parent

APP_NAME = "PPWR Digital Platform"
APP_SUB = "by CPS Center of Excellence"
APP_VERSION = "0.1.0"
SERVICE_LINE = "PPWR Technical Documentation & EU DoC service"
DISCLAIMER = ("Pilot build. Platform outputs are drafts for expert review; the manufacturer "
              "remains responsible for the EU declaration of conformity (Art 39(4)).")

DESIGN_SYSTEM_DIR = ROOT / "cps-coe-design-system_v1.1"
STATIC_DIR = APP_DIR / "static"
TEMPLATES_DIR = APP_DIR / "templates"
SEEDS_DIR = APP_DIR / "seeds"

DATA_DIR = Path(os.getenv("PPWR_DATA_DIR", ROOT / "data"))
DB_PATH = DATA_DIR / "ppwr.db"
UPLOAD_DIR = DATA_DIR / "uploads"
GENERATED_DIR = DATA_DIR / "generated"

KNOWLEDGE_DIR = ROOT / "PPWR Knowledgebase"
TEMPLATE_KIT_DIR = ROOT / "manual collection"

MAX_UPLOAD_MB = 25

# Certificates this close to expiry are flagged on the dashboard and supplier library.
EXPIRY_WINDOW_DAYS = 30
# Test reports older than this are flagged at AI pre-review (Checklist V1.5: "< 24 months").
REPORT_MAX_AGE_MONTHS = 24

for d in (DATA_DIR, UPLOAD_DIR, GENERATED_DIR):
    d.mkdir(parents=True, exist_ok=True)

"""SQLite data layer.

The model mirrors how PPWR itself thinks (AI 数据库宣讲 deck, slide 9):

    Supplier → SupplierMaterial (+ Certificates)          the supplier library
        ↓ used by
    Project (one packaging system PS-xxx, one TD/DoC case)
        → PackagingUnit (PU-xxx: sales / grouped / transport)
            → Component (PU-xxx-Cxxx: carton, bag, label, …)
        → Submission (one per catalogue item × unit, the collection + review state)
        → Evidence (PU-xxx-Cxxx-TST-001 …, files in the vault)
        → Document (generated TD / DoC, versioned)
    ChangeEvent — a supplier-side change and the ripple it causes.
"""
from __future__ import annotations

import datetime as dt
import json

from sqlalchemy import (Boolean, Column, Date, DateTime, Float, ForeignKey, Integer,
                        String, Text, create_engine, event)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

from . import config

engine = create_engine(f"sqlite:///{config.DB_PATH}", connect_args={"check_same_thread": False})


@event.listens_for(engine, "connect")
def _sqlite_pragmas(dbapi_conn, _):
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA foreign_keys=ON")
    cur.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
Base = declarative_base()


def now() -> dt.datetime:
    return dt.datetime.now().replace(microsecond=0)


class JsonField:
    """Descriptor: a Text column holding JSON, read/written as Python values."""

    def __init__(self, column: str, default=None):
        self.column = column
        self.default = default

    def __get__(self, obj, owner):
        if obj is None:
            return self
        raw = getattr(obj, self.column)
        if not raw:
            return json.loads(json.dumps(self.default))
        return json.loads(raw)

    def __set__(self, obj, value):
        setattr(obj, self.column, json.dumps(value, ensure_ascii=False) if value is not None else None)


# ---------------------------------------------------------------------------
# Accounts
# ---------------------------------------------------------------------------

class Client(Base):
    __tablename__ = "clients"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False, unique=True)
    address = Column(Text, default="")
    country = Column(String, default="")
    contact_name = Column(String, default="")
    contact_email = Column(String, default="")
    eu_representative = Column(Text, default="")
    created_at = Column(DateTime, default=now)

    projects = relationship("Project", back_populates="client")
    suppliers = relationship("Supplier", back_populates="client")


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, nullable=False)
    display_name = Column(String, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, nullable=False, default="client")  # expert | client
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=True)
    last_login = Column(String, nullable=True)

    client = relationship("Client")

    @property
    def is_expert(self) -> bool:
        return self.role == "expert"


# ---------------------------------------------------------------------------
# Supplier library
# ---------------------------------------------------------------------------

class Supplier(Base):
    __tablename__ = "suppliers"
    id = Column(Integer, primary_key=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    code = Column(String, nullable=False)            # SUP-001
    name = Column(String, nullable=False)
    address = Column(Text, default="")
    country = Column(String, default="")
    contact = Column(String, default="")
    status = Column(String, default="active")        # active | audit | inactive

    client = relationship("Client", back_populates="suppliers")
    materials = relationship("SupplierMaterial", back_populates="supplier",
                             cascade="all, delete-orphan", order_by="SupplierMaterial.code")


class SupplierMaterial(Base):
    """What a supplier delivers — a packaging material / packaging type with its own
    trace code (V3.1 'supplier packaging type', e.g. PAP20-300GSM-2024A)."""
    __tablename__ = "supplier_materials"
    id = Column(Integer, primary_key=True)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=False)
    code = Column(String, nullable=False)            # SPT-001
    trace_code = Column(String, default="")
    name = Column(String, nullable=False)
    material = Column(String, default="")
    material_group = Column(String, default="other")  # paper | plastic | glass | metal | wood | other
    status = Column(String, default="active")

    supplier = relationship("Supplier", back_populates="materials")
    certificates = relationship("Certificate", back_populates="material",
                                cascade="all, delete-orphan", order_by="Certificate.doc_type")
    components = relationship("Component", back_populates="supplier_material")


class Certificate(Base):
    __tablename__ = "certificates"
    id = Column(Integer, primary_key=True)
    supplier_material_id = Column(Integer, ForeignKey("supplier_materials.id"), nullable=False)
    doc_type = Column(String, nullable=False)        # hm | pf | rc | doc | td | comp | iso | fsc | oth
    number = Column(String, default="")
    issuer = Column(String, default="")
    issued = Column(Date, nullable=True)
    expires = Column(Date, nullable=True)
    value = Column(String, default="")               # e.g. "38 mg/kg" for heavy metals
    conclusion = Column(String, default="conform")   # conform | non-conform
    filename = Column(String, nullable=True)
    stored_path = Column(String, nullable=True)
    status = Column(String, default="valid")         # valid | superseded
    created_at = Column(DateTime, default=now)

    material = relationship("SupplierMaterial", back_populates="certificates")


# ---------------------------------------------------------------------------
# Projects — one TD / DoC service case
# ---------------------------------------------------------------------------

class Project(Base):
    __tablename__ = "projects"
    id = Column(Integer, primary_key=True)
    code = Column(String, unique=True, nullable=False)   # PRJ-2026-001
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    title = Column(String, nullable=False)
    product_description = Column(Text, default="")
    ps_code = Column(String, default="PS-001")           # packaging system (one per SKU family)
    scenario = Column(String, default="B")               # A per-unit TD package | B consolidated TD
    food_contact = Column(Boolean, default=False)
    reusable = Column(Boolean, default=False)
    compostable_type = Column(Boolean, default=False)    # Art 9 packaging (pods, stickers, …)
    biobased_claim = Column(Boolean, default=False)
    markets = Column(String, default="EU")
    target_date = Column(Date, nullable=True)
    stage = Column(String, default="collecting")         # collecting | review | issued
    created_at = Column(DateTime, default=now)
    created_by = Column(String, default="")

    client = relationship("Client", back_populates="projects")
    units = relationship("PackagingUnit", back_populates="project",
                         cascade="all, delete-orphan", order_by="PackagingUnit.code")
    submissions = relationship("Submission", back_populates="project", cascade="all, delete-orphan")
    evidence = relationship("Evidence", back_populates="project", cascade="all, delete-orphan",
                            order_by="Evidence.code")
    documents = relationship("Document", back_populates="project", cascade="all, delete-orphan",
                             order_by="Document.generated_at.desc()")


class PackagingUnit(Base):
    __tablename__ = "packaging_units"
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    code = Column(String, nullable=False)                # PU-001
    name = Column(String, nullable=False)
    level = Column(String, default="Sales")              # Sales | Grouped | Transport | E-commerce
    pack_type = Column(String, default="")               # Carton, Pouch, Card …
    upi = Column(String, default="")
    skus = Column(String, default="")
    mass_g = Column(Float, nullable=True)
    dims = Column(String, default="")
    supplier_name = Column(String, default="")
    site = Column(String, default="")
    country = Column(String, default="")
    artwork_ref = Column(String, default="")

    project = relationship("Project", back_populates="units")
    components = relationship("Component", back_populates="unit", cascade="all, delete-orphan",
                              order_by="Component.code")


class Component(Base):
    __tablename__ = "components"
    id = Column(Integer, primary_key=True)
    unit_id = Column(Integer, ForeignKey("packaging_units.id"), nullable=False)
    code = Column(String, nullable=False)                # PU-001-C001
    pack_type = Column(String, default="")
    description = Column(String, default="")
    structure = Column(String, default="Mono-material")  # Mono-material | Multi-layer | Composite | Other
    material = Column(String, default="")
    material_group = Column(String, default="other")
    mass_g = Column(Float, nullable=True)
    dims = Column(String, default="")
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=True)
    supplier_material_id = Column(Integer, ForeignKey("supplier_materials.id"), nullable=True)
    recycled_pct = Column(Float, nullable=True)
    biobased_pct = Column(Float, nullable=True)
    remarks = Column(Text, default="")

    unit = relationship("PackagingUnit", back_populates="components")
    supplier = relationship("Supplier")
    supplier_material = relationship("SupplierMaterial", back_populates="components")


class Submission(Base):
    """Collection + review state of one catalogue item for one packaging unit
    (unit_id NULL for project-level items)."""
    __tablename__ = "submissions"
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    unit_id = Column(Integer, ForeignKey("packaging_units.id"), nullable=True)
    item_id = Column(String, nullable=False)
    # pending → submitted → ai_reviewed → approved | rejected ;  na (with reason)
    status = Column(String, default="pending")
    data_json = Column(Text, nullable=True)
    table_json = Column(Text, nullable=True)
    na_requested = Column(Boolean, default=False)
    na_reason = Column(Text, default="")
    na_auto = Column(Boolean, default=False)
    ai_verdict = Column(String, nullable=True)           # pass | warn | fail
    ai_checks_json = Column(Text, nullable=True)
    ai_at = Column(DateTime, nullable=True)
    review_comment = Column(Text, default="")
    reviewed_by = Column(String, default="")
    reviewed_at = Column(DateTime, nullable=True)
    submitted_by = Column(String, default="")
    submitted_at = Column(DateTime, nullable=True)
    reopened_reason = Column(Text, default="")
    updated_at = Column(DateTime, default=now, onupdate=now)

    project = relationship("Project", back_populates="submissions")
    unit = relationship("PackagingUnit")

    data = JsonField("data_json", {})
    table = JsonField("table_json", [])
    ai_checks = JsonField("ai_checks_json", [])

    @property
    def is_done(self) -> bool:
        return self.status in ("approved", "na")


class Evidence(Base):
    __tablename__ = "evidence"
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    unit_id = Column(Integer, ForeignKey("packaging_units.id"), nullable=True)
    component_id = Column(Integer, ForeignKey("components.id"), nullable=True)
    item_id = Column(String, nullable=True)
    certificate_id = Column(Integer, ForeignKey("certificates.id"), nullable=True)
    code = Column(String, nullable=False)                # PU-001-C001-TST-001
    title = Column(String, nullable=False)
    type_code = Column(String, default="DOC")
    file_no = Column(String, default="")
    issuer = Column(String, default="")
    issued_date = Column(Date, nullable=True)
    responsible = Column(String, default="")
    conformity = Column(String, default="Conform")
    supplier_name = Column(String, default="")
    filename = Column(String, nullable=True)
    stored_path = Column(String, nullable=True)
    size = Column(Integer, default=0)
    uploaded_by = Column(String, default="")
    uploaded_at = Column(DateTime, default=now)

    project = relationship("Project", back_populates="evidence")
    unit = relationship("PackagingUnit")
    component = relationship("Component")
    certificate = relationship("Certificate")


class Document(Base):
    __tablename__ = "documents"
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    unit_id = Column(Integer, ForeignKey("packaging_units.id"), nullable=True)
    kind = Column(String, nullable=False)                # TD | DOC | PACKAGE | DOSSIER
    number = Column(String, nullable=False)
    version = Column(Integer, default=1)
    status = Column(String, default="draft")             # draft | issued | outdated | superseded
    path = Column(String, nullable=False)
    readiness = Column(Float, default=0)
    trigger = Column(String, default="")
    outdated_reason = Column(Text, default="")
    generated_at = Column(DateTime, default=now)
    generated_by = Column(String, default="")
    issued_at = Column(DateTime, nullable=True)
    issued_by = Column(String, default="")

    project = relationship("Project", back_populates="documents")
    unit = relationship("PackagingUnit")


class ChangeEvent(Base):
    """A supplier-side change and its ripple (deck slide 10)."""
    __tablename__ = "change_events"
    id = Column(Integer, primary_key=True)
    code = Column(String, nullable=False)                # CHG-0001
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    supplier_material_id = Column(Integer, ForeignKey("supplier_materials.id"), nullable=True)
    certificate_id = Column(Integer, ForeignKey("certificates.id"), nullable=True)
    kind = Column(String, nullable=False)                # certificate_update | material_change | certificate_expiry
    title = Column(String, nullable=False)
    description = Column(Text, default="")
    doc_types_json = Column(Text, nullable=True)
    status = Column(String, default="open")              # open | applied | dismissed
    created_at = Column(DateTime, default=now)
    created_by = Column(String, default="")
    applied_at = Column(DateTime, nullable=True)
    applied_by = Column(String, default="")
    impact_json = Column(Text, nullable=True)

    client = relationship("Client")
    supplier_material = relationship("SupplierMaterial")
    certificate = relationship("Certificate")

    doc_types = JsonField("doc_types_json", [])
    impact = JsonField("impact_json", {})


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True)
    unit_id = Column(Integer, nullable=True)
    item_id = Column(String, nullable=True)
    actor = Column(String, default="")
    action = Column(String, nullable=False)
    comment = Column(Text, default="")
    at = Column(DateTime, default=now)


# ---------------------------------------------------------------------------

def init_db() -> None:
    Base.metadata.create_all(engine)


def get_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def log(session, action: str, actor: str = "", project_id=None, unit_id=None,
        item_id=None, comment: str = "") -> None:
    session.add(AuditEvent(project_id=project_id, unit_id=unit_id, item_id=item_id,
                           actor=actor, action=action, comment=comment or ""))

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
# Regulatory monitoring — implementing acts, standards, guidance and their impact
# ---------------------------------------------------------------------------

class RegUpdate(Base):
    __tablename__ = "reg_updates"
    id = Column(Integer, primary_key=True)
    code = Column(String, unique=True, nullable=False)    # REG-2026-001
    kind = Column(String, default="interpretation")       # regulation | implementing | standard | interpretation | consultation
    status = Column(String, default="published")          # adopted | published | corrigendum | draft | consultation | guidance
    binding = Column(Boolean, default=False)
    title = Column(String, nullable=False)
    title_zh = Column(String, default="")
    reference = Column(String, default="")
    published = Column(Date, nullable=True)
    date_label = Column(String, default="")
    effective = Column(Date, nullable=True)
    summary = Column(Text, default="")
    summary_zh = Column(Text, default="")
    impact = Column(Text, default="")
    impact_zh = Column(Text, default="")
    evidence_change = Column(Text, default="")
    evidence_change_zh = Column(Text, default="")
    severity = Column(String, default="info")             # high | medium | info
    source_path = Column(String, default="")
    origin = Column(String, default="seed")               # seed | scan | manual
    reviewed = Column(Boolean, default=True)              # auto-detected updates need expert review
    articles_json = Column(Text, nullable=True)
    items_json = Column(Text, nullable=True)
    detected_at = Column(DateTime, default=now)
    created_by = Column(String, default="")

    articles = JsonField("articles_json", [])
    items = JsonField("items_json", [])


class RegAck(Base):
    __tablename__ = "reg_acks"
    id = Column(Integer, primary_key=True)
    update_id = Column(Integer, ForeignKey("reg_updates.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    at = Column(DateTime, default=now)


# ---------------------------------------------------------------------------
# Smart import (V4.2 one-click upload + AI identification), staged before it lands
# ---------------------------------------------------------------------------

class ImportBatch(Base):
    __tablename__ = "import_batches"
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    status = Column(String, default="staged")             # staged | imported | discarded
    created_by = Column(String, default="")
    created_at = Column(DateTime, default=now)
    imported_at = Column(DateTime, nullable=True)
    table_json = Column(Text, nullable=True)
    stats_json = Column(Text, nullable=True)

    project = relationship("Project")
    files = relationship("ImportFile", back_populates="batch", cascade="all, delete-orphan",
                         order_by="ImportFile.id")
    table = JsonField("table_json", {})
    stats = JsonField("stats_json", {})


class ImportFile(Base):
    __tablename__ = "import_files"
    id = Column(Integer, primary_key=True)
    batch_id = Column(Integer, ForeignKey("import_batches.id"), nullable=False)
    filename = Column(String, nullable=False)
    folder = Column(String, default="")
    stored_path = Column(String, nullable=True)
    size = Column(Integer, default=0)
    item_id = Column(String, nullable=True)               # proposed / corrected catalogue item (None = skip)
    proposed_item = Column(String, nullable=True)         # what the AI proposed — a difference is a correction
    unit_id = Column(Integer, nullable=True)
    unit_ref = Column(String, default="")                 # PU-002 / PKG-02 / UPI found in the name
    type_code = Column(String, default="DOC")
    confidence = Column(Float, default=0)
    rule = Column(Text, default="")
    method = Column(String, default="")                   # filename | pdf-text | docx | xlsx | text | none
    snippet = Column(Text, default="")
    version = Column(String, default="")
    found_date = Column(String, default="")
    status = Column(String, default="staged")             # staged | imported | skipped
    evidence_id = Column(Integer, nullable=True)
    candidates_json = Column(Text, nullable=True)

    batch = relationship("ImportBatch", back_populates="files")
    candidates = JsonField("candidates_json", [])


class ImportFeedback(Base):
    """A human correction of the AI identification — weighted into the next identification."""
    __tablename__ = "import_feedback"
    id = Column(Integer, primary_key=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=True)
    stem = Column(String, nullable=False)
    item_id = Column(String, nullable=False)
    count = Column(Integer, default=1)
    updated_at = Column(DateTime, default=now, onupdate=now)


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

"""Regulatory monitoring — track implementing / delegated acts, harmonised standards, guidance.

Sources of updates
* seeds/reg_updates.json — curated, reviewed updates (each traced to a knowledge-base document);
* the knowledge-base scanner — every new or changed document dropped into `PPWR Knowledgebase/`
  becomes an update automatically: its first page is read, it is classified by folder
  (regulation / standard / implementing / interpretation), and mapped to the PPWR articles and
  catalogue items it mentions. Auto-detected updates are marked "to be reviewed by the expert";
  with an LLM configured a bilingual summary is drafted from the document text only;
* optional online watch (env PPWR_MONITOR_URLS, comma-separated): a page whose content changes
  raises an update pointing at the URL.

Impact = for every visible project, the items the update touches that apply to it (not N/A),
split into approved items to re-check and open items to collect against the new rule, plus
issued documents that may need an update (Art 39(2): the DoC is continuously updated).
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
import urllib.request

from sqlalchemy.orm import Session

from . import applicability, catalogue, config, llm, rag
from .db import Project, RegAck, RegUpdate, SessionLocal, Submission, User, log, now

MANIFEST_PATH = config.DATA_DIR / "kb_manifest.json"
WATCH_PATH = config.DATA_DIR / "kb_watch.json"

KIND_LABEL = {"regulation": ("Regulation", "法规"), "implementing": ("Implementing / delegated act", "实施 / 授权法案"),
              "standard": ("Harmonised standard", "协调标准"), "interpretation": ("Interpretation / guidance", "解释 / 指南"),
              "consultation": ("Draft / consultation", "草案 / 征询意见")}
STATUS_LABEL = {"adopted": ("Adopted", "已通过"), "published": ("Published in OJ", "已在官方公报公布"),
                "corrigendum": ("Corrigendum", "勘误"), "draft": ("Draft", "草案"),
                "consultation": ("Consultation", "征询意见"), "guidance": ("Guidance (non-binding)", "指南（无约束力）"),
                "detected": ("Detected — to be reviewed", "已检测——待审核")}
SEVERITY_BADGE = {"high": "badge-high", "medium": "badge-warn", "info": "badge-info"}

# Text signals → PPWR article keys (used to map auto-detected documents to items).
ARTICLE_SIGNALS = {
    "a5": r"heavy metal|lead, cadmium|substances? of concern|article 5\b|art\.? 5\b",
    "a5pfas": r"\bpfas\b|perfluoro|polyfluoro|food[- ]contact",
    "a6": r"recyclab|design for recycling|recycled at scale|article 6\b",
    "a7": r"recycled content|post-consumer|recyclate|article 7\b",
    "a8": r"bio-?based",
    "a9": r"compostab|biodegradab|article 9\b",
    "a10": r"minimi[sz]ation|empty space|article 10\b|article 24\b",
    "a11": r"re-?us(e|able)|refill|article 11\b",
    "a12": r"label(l)?ing|harmoni[sz]ed label|data carrier|qr code|article 12\b",
    "core": r"technical documentation|declaration of conformity|conformity assessment|annex vii\b|annex viii\b",
}


def _date(s):
    return dt.date.fromisoformat(s) if s else None


def seed_updates(session: Session) -> int:
    if session.query(RegUpdate).count():
        return 0
    data = json.loads((config.SEEDS_DIR / "reg_updates.json").read_text(encoding="utf-8"))
    for u in data["updates"]:
        session.add(RegUpdate(code=u["code"], kind=u["kind"], status=u["status"], binding=u["binding"],
                              severity=u["severity"], reference=u["reference"], published=_date(u.get("published")),
                              date_label=u.get("date_label", ""), title=u["title"], title_zh=u["title_zh"],
                              summary=u["summary"], summary_zh=u["summary_zh"], impact=u["impact"],
                              impact_zh=u["impact_zh"], evidence_change=u.get("evidence_change", ""),
                              evidence_change_zh=u.get("evidence_change_zh", ""), source_path=u.get("source", ""),
                              articles=u.get("articles", []), items=u.get("items", []), origin="seed",
                              reviewed=True, created_by="TÜV SÜD regulatory desk"))
    return len(data["updates"])


def next_code(session: Session) -> str:
    year = dt.date.today().year
    n = session.query(RegUpdate).filter(RegUpdate.code.like(f"REG-{year}-%")).count() + 1
    while session.query(RegUpdate).filter_by(code=f"REG-{year}-{n:03d}").first():
        n += 1
    return f"REG-{year}-{n:03d}"


def detect_articles(text: str) -> list[str]:
    low = (text or "").lower()
    return [k for k, rx in ARTICLE_SIGNALS.items() if re.search(rx, low)]


def items_for_articles(articles: list[str], limit: int = 12) -> list[str]:
    ids = [i["id"] for i in catalogue.items() if i["article"] in articles and i["article"] != "core"]
    if "core" in articles:
        ids += ["C14-54", "C16-66"]
    return ids[:limit]


# ---------------------------------------------------------------------------
# Scanner
# ---------------------------------------------------------------------------

def _first_text(path) -> str:
    pages = rag._pages(path)
    return re.sub(r"\s+", " ", " ".join(pages[:2]))[:4000]


def _summarise(title: str, text: str) -> tuple[str, str, str, str]:
    """Bilingual summary + impact. LLM if configured (grounded in the text only), else extractive."""
    extract = text[:600].strip()
    if llm.configured() and extract:
        try:
            out = llm.chat([
                {"role": "system", "content": "You summarise EU packaging regulatory documents for compliance staff. "
                 "Use ONLY the text provided. Do not add requirements or dates that are not in the text. "
                 "Return JSON with keys summary_en, summary_zh, impact_en, impact_zh (each ≤ 60 words). "
                 "impact = what may change for packaging technical documentation / evidence; say 'unclear from the "
                 "text' if the text does not say."},
                {"role": "user", "content": f"Title: {title}\n\nText:\n{text[:3500]}"}], max_tokens=600)
            m = re.search(r"\{.*\}", out, re.S)
            j = json.loads(m.group(0)) if m else {}
            return (j.get("summary_en", extract), j.get("summary_zh", ""), j.get("impact_en", ""), j.get("impact_zh", ""))
        except (llm.LLMError, ValueError):
            pass
    return (extract + (" …" if len(text) > 600 else ""), "",
            "Auto-detected document — impact to be assessed by the TÜV SÜD expert. Mapped articles are based on "
            "keywords in the text.",
            "自动检测到的文件——影响待 TÜV SÜD 专家评估。条款映射基于文中关键词。")


def scan(session: Session, actor: str = "Platform monitor") -> dict:
    """Compare the knowledge-base folder with the last manifest; raise updates for new/changed files."""
    current = rag.manifest()
    try:
        previous = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        previous = None
    created = []
    if previous is not None:
        known = {u.source_path for u in session.query(RegUpdate)}
        for rel, meta in current.items():
            if previous.get(rel) == meta:
                continue
            changed = rel in previous
            if not changed and rel in known:
                continue
            path = config.KNOWLEDGE_DIR / rel
            text = _first_text(path)
            title = path.stem.replace("_", " ")
            kind = {"01": "implementing", "02": "standard", "03": "consultation", "05": "interpretation"}.get(rel[:2], "interpretation")
            if rel[:2] == "01" and re.search(r"regulation \(eu\)|^ppwr regulation", title.lower()):
                kind = "regulation"
            arts = detect_articles(text) or ["core"]
            s_en, s_zh, i_en, i_zh = _summarise(title, text)
            u = RegUpdate(code=next_code(session), kind=kind, status="detected", binding=False,
                          severity="medium" if kind in ("implementing", "regulation", "standard") else "info",
                          reference=title, published=dt.date.today(), date_label=f"detected {dt.date.today():%d %b %Y}",
                          title=("Changed: " if changed else "New: ") + title,
                          title_zh=("已变更：" if changed else "新增：") + title,
                          summary=s_en, summary_zh=s_zh, impact=i_en, impact_zh=i_zh, source_path=rel,
                          articles=arts, items=items_for_articles(arts), origin="scan", reviewed=False,
                          created_by=actor)
            session.add(u)
            created.append(u)
        for rel in set(previous) - set(current):
            log(session, "knowledge-base document removed", actor, comment=rel)
    MANIFEST_PATH.write_text(json.dumps(current, indent=0), encoding="utf-8")
    watched = watch_online(session, actor)
    if created or watched:
        rag.CORPUS.start_background()
        log(session, "regulatory scan", actor, comment=f"{len(created)} document(s), {len(watched)} online source(s) changed")
    return {"baseline": previous is None, "created": [u.code for u in created + watched], "files": len(current)}


def watch_online(session: Session, actor: str) -> list[RegUpdate]:
    urls = [u.strip() for u in os.getenv("PPWR_MONITOR_URLS", "").split(",") if u.strip()]
    if not urls:
        return []
    try:
        state = json.loads(WATCH_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        state = {}
    out = []
    for url in urls:
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "PPWR-monitor"}), timeout=15) as r:
                body = r.read()
        except Exception as exc:  # network is optional
            state.setdefault("_errors", {})[url] = str(exc)[:200]
            continue
        text = re.sub(r"<[^>]+>", " ", body.decode("utf-8", "ignore"))
        digest = hashlib.sha1(re.sub(r"\s+", " ", text).encode()).hexdigest()
        if url in state and state[url] != digest:
            u = RegUpdate(code=next_code(session), kind="interpretation", status="detected", severity="info",
                          title=f"Online source changed: {url}", title_zh=f"在线来源已变更：{url}", reference=url,
                          published=dt.date.today(), date_label=f"detected {dt.date.today():%d %b %Y}",
                          summary="The monitored page changed. Review what is new.", summary_zh="所监控页面已变更，请查看新增内容。",
                          impact="To be assessed by the expert.", impact_zh="待专家评估。", source_path=url,
                          articles=["core"], items=[], origin="scan", reviewed=False, created_by=actor)
            session.add(u)
            out.append(u)
        state[url] = digest
    WATCH_PATH.write_text(json.dumps(state, indent=0), encoding="utf-8")
    return out


# ---------------------------------------------------------------------------
# Impact & notifications
# ---------------------------------------------------------------------------

def impact(update: RegUpdate, projects: list[Project]) -> list[dict]:
    rows = []
    items = set(update.items or [])
    for p in projects:
        approved, open_, docs = [], [], []
        for s in p.submissions:
            if s.item_id not in items:
                continue
            it = catalogue.item(s.item_id)
            if it is None or applicability.is_na(p, it["article"]) or s.status == "na":
                continue
            (approved if s.status == "approved" else open_).append(s)
        if approved and update.binding:
            docs = [d for d in p.documents if d.status == "issued"]
        if approved or open_:
            rows.append({"project": p, "approved": approved, "open": open_, "documents": docs})
    return rows


def visible_updates(session: Session):
    return session.query(RegUpdate).order_by(RegUpdate.reviewed.asc(), RegUpdate.published.desc().nulls_last(),
                                             RegUpdate.code.desc())


def acked_ids(session: Session, user: User) -> set[int]:
    return {a.update_id for a in session.query(RegAck).filter_by(user_id=user.id)}


def unread_count(session: Session, user: User) -> int:
    seen = acked_ids(session, user)
    return sum(1 for u in session.query(RegUpdate.id) if u.id not in seen)


def acknowledge(session: Session, update: RegUpdate, user: User) -> None:
    if not session.query(RegAck).filter_by(update_id=update.id, user_id=user.id).first():
        session.add(RegAck(update_id=update.id, user_id=user.id))


def recheck(session: Session, update: RegUpdate, project: Project, actor: str) -> int:
    """Expert action: send approved items touched by the update back for re-assessment (Art 15(4))."""
    reason = f"{update.code}: {update.title} — re-assess against the update."
    n = 0
    for row in impact(update, [project]):
        for s in row["approved"]:
            s.status, s.reopened_reason = "submitted", reason
            s.ai_verdict, s.ai_checks = None, []
            log(session, "reopened by regulatory update", actor, s.project_id, s.unit_id, s.item_id, reason)
            n += 1
        for d in row["documents"]:
            d.status, d.outdated_reason = "outdated", f"Update required — {reason}"
    return n


def updates_for_item(item_id: str, days: int = 400) -> list[dict]:
    """Recent updates touching an item — shown as hints on the item page."""
    cutoff = now() - dt.timedelta(days=days)
    with SessionLocal() as s:
        rows = s.query(RegUpdate).filter(RegUpdate.detected_at >= cutoff).all()
        return [{"code": u.code, "title": u.title, "title_zh": u.title_zh,
                 "impact": u.evidence_change or u.impact, "impact_zh": u.evidence_change_zh or u.impact_zh,
                 "id": u.id} for u in rows if item_id in (u.items or [])][:3]


def project_alerts(session: Session, project: Project) -> list[dict]:
    out = []
    for u in session.query(RegUpdate).order_by(RegUpdate.detected_at.desc()).limit(40):
        rows = impact(u, [project])
        if rows:
            out.append({"u": u, "approved": len(rows[0]["approved"]), "open": len(rows[0]["open"])})
    return out

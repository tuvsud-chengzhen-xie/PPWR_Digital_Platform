"""Retrieval-augmented generation (RAG) over the PPWR knowledge base.

Two retrieval sources, searched together:

1. The structured knowledge pool (seeds/knowledge_pool.json) — curated, bilingual entries for
   regulation articles, harmonised standards, implementing / delegated acts, official
   interpretations and good practice, each tagged with the articles and catalogue items it
   concerns and pointing at the source document + page.
2. The document corpus — the full text of every PDF / HTML in `PPWR Knowledgebase/`, extracted
   page by page (pypdf), chunked and indexed. Chunks keep file + page so every answer can link
   to the exact page of the source.

Ranking is BM25 (English word tokens + Chinese character bigrams). Chinese questions are
expanded with an English glossary so they also hit the English-only corpus. The corpus index
is cached in DATA_DIR/kb_index.json and rebuilt when the knowledge-base folder changes.
"""
from __future__ import annotations

import hashlib
import html.parser
import json
import logging
import math
import os
import re
import threading
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote

from . import config

logging.getLogger("pypdf").setLevel(logging.ERROR)

INDEX_PATH = config.DATA_DIR / "kb_index.json"
INDEX_VERSION = 3
CHUNK_CHARS = 900
CHUNK_OVERLAP = 150
MAX_PAGES = 480

FOLDER_KIND = {"01": "regulation", "02": "standard", "03": "implementing", "04": "standard", "05": "interpretation"}
KIND_LABEL = {
    "regulation": ("Regulation & acts", "法规与法案"), "standard": ("Harmonised standard", "协调标准"),
    "implementing": ("Implementing / delegated act", "实施 / 授权法案"),
    "interpretation": ("Interpretation & guidance", "解释与指南"),
    "practice": ("Good practice", "良好实践"),
}

STOP = set("""a an the of and or to in on for by with as at from is are be been was were this that these those it its
which shall may can not no any all such other than into within under per their there where when also only each
has have had will would should than then if so out up about over more most some same both between
how what why who whom must do does did need needs my our we you your i me tell explain please""".split())

# Chinese → English expansion so Chinese questions retrieve passages from English sources.
GLOSSARY = {
    "重金属": "heavy metal lead cadmium mercury chromium", "铅": "lead", "镉": "cadmium", "汞": "mercury",
    "六价铬": "hexavalent chromium", "全氟": "pfas perfluoro", "氟": "fluorine pfas", "食品接触": "food contact",
    "可回收": "recyclable recyclability recycling", "回收": "recycling recycled", "再生": "recycled content post-consumer",
    "再生料": "recycled content post-consumer", "最小化": "minimisation minimum weight volume", "减量": "minimisation reduction",
    "空隙": "empty space ratio", "标签": "label labelling", "标识": "marking label identification",
    "技术文档": "technical documentation annex vii", "技术文件": "technical documentation annex vii",
    "符合性声明": "declaration of conformity", "合格评定": "conformity assessment", "声明": "declaration",
    "图纸": "drawing drawings design", "设计": "design", "制造": "manufacturing manufacture", "生产": "production manufacturing",
    "供应商": "supplier suppliers", "检测": "test testing analysis", "报告": "report", "测试": "test",
    "堆肥": "compostable composting", "可降解": "biodegradable", "生物基": "biobased", "重复使用": "reusable reuse re-use",
    "押金": "deposit return", "豁免": "exemption derogation", "协调标准": "harmonised standard presumption",
    "推定": "presumption of conformity", "实施法案": "implementing act", "授权法案": "delegated act",
    "制造商": "manufacturer", "进口商": "importer", "经销商": "distributor", "运输包装": "transport packaging",
    "销售包装": "sales packaging", "组合包装": "grouped packaging", "电商": "e-commerce", "保存": "keep retain years",
    "期限": "date deadline", "日期": "date apply", "适用": "apply applicable", "风险": "risk analysis",
    "关注物质": "substances of concern", "物质": "substance", "塑料": "plastic", "纸": "paper board",
    "玻璃": "glass", "托盘": "pallet", "缠绕膜": "wrapping film", "二维码": "qr code data carrier",
    "批号": "batch serial number", "地址": "postal address", "认证": "certificate", "证书": "certificate",
    "等级": "grade grades", "包装": "packaging", "义务": "obligation", "要求": "requirement",
}

_WORD = re.compile(r"[a-z0-9]+")
_CJK = re.compile(r"[\u4e00-\u9fff]+")


def tokens(text: str) -> list[str]:
    low = (text or "").lower()
    out = []
    for w in _WORD.findall(low):
        if w in STOP or (len(w) == 1 and not w.isdigit()):
            continue
        if len(w) > 4 and w.endswith("ies"):
            w = w[:-3] + "y"
        elif len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
            w = w[:-1]
        out.append(w)
    for run in _CJK.findall(text or ""):
        if len(run) == 1:
            out.append(run)
        out.extend(run[i:i + 2] for i in range(len(run) - 1))
    return out


# English synonyms: everyday wording → the wording used in the legal texts.
SYNONYMS = {
    "kept": "keep retain retention years", "keep": "kept retain retention years", "long": "years",
    "retain": "kept keep years", "store": "kept keep", "archive": "kept keep", "limit": "limits exceed concentration",
    "drawing": "drawings design manufacturing", "drawings": "design manufacturing", "label": "labelling marked",
    "deadline": "apply from date", "when": "apply from date", "standard": "harmonised presumption",
    "standards": "harmonised presumption", "supplier": "suppliers information documentation",
    "recycle": "recyclable recycling", "reuse": "reusable re-use", "heavy": "lead cadmium mercury chromium",
    "doc": "declaration conformity", "td": "technical documentation", "evidence": "documentation test reports",
}


def expand_query(q: str) -> str:
    extra = [en for zh, en in GLOSSARY.items() if zh in (q or "")]
    extra += [SYNONYMS[w] for w in re.findall(r"[a-z]+", (q or "").lower()) if w in SYNONYMS]
    return q + (" " + " ".join(extra) if extra else "")


class BM25:
    def __init__(self, docs: list[list[str]], k1: float = 1.4, b: float = 0.72):
        self.k1, self.b = k1, b
        self.n = len(docs)
        self.len = [len(d) for d in docs]
        self.avg = (sum(self.len) / self.n) if self.n else 1.0
        self.post: dict[str, list[tuple[int, int]]] = defaultdict(list)
        for i, d in enumerate(docs):
            for term, tf in Counter(d).items():
                self.post[term].append((i, tf))

    def scores(self, query: list[str]) -> dict[int, float]:
        out: dict[int, float] = defaultdict(float)
        for term in set(query):
            plist = self.post.get(term)
            if not plist:
                continue
            idf = math.log(1 + (self.n - len(plist) + 0.5) / (len(plist) + 0.5))
            for i, tf in plist:
                denom = tf + self.k1 * (1 - self.b + self.b * self.len[i] / self.avg)
                out[i] += idf * tf * (self.k1 + 1) / denom
        return out


# ---------------------------------------------------------------------------
# Knowledge pool
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def pool() -> dict:
    return json.loads((config.SEEDS_DIR / "knowledge_pool.json").read_text(encoding="utf-8"))


def pool_entries() -> list[dict]:
    return pool()["entries"]


def pool_entry(eid: str) -> dict | None:
    return next((e for e in pool_entries() if e["id"] == eid), None)


def kb_url(rel: str, page: int = 0) -> str:
    if not rel:
        return ""
    return "/kb-files/" + "/".join(quote(p) for p in rel.split("/")) + (f"#page={page}" if page else "")


def entry_url(e: dict) -> str:
    rel = pool()["sources"].get(e.get("src", ""), "")
    return kb_url(rel, e.get("page") or 0)


@lru_cache(maxsize=1)
def _pool_index() -> BM25:
    docs = [tokens(" ".join([e["ref"], e["title"], e["title_zh"], e["text"], e["text_zh"]] * 1 + [e["title"]] * 2))
            for e in pool_entries()]
    return BM25(docs)


def for_item(item_id: str, article: str | None = None, limit: int = 8) -> list[dict]:
    """Pool entries tagged with this item (binding first), then entries for its article."""
    rank = {"regulation": 0, "implementing": 1, "interpretation": 2, "standard": 3, "practice": 4}
    tagged = [e for e in pool_entries() if item_id in e.get("items", [])]
    if article and len(tagged) < 3:
        tagged += [e for e in pool_entries() if article in e.get("articles", []) and e not in tagged][:3]
    tagged.sort(key=lambda e: (rank.get(e["kind"], 9), e["id"]))
    return tagged[:limit]


# ---------------------------------------------------------------------------
# Document corpus
# ---------------------------------------------------------------------------

class _HTMLText(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts, self._skip = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript", "svg"):
            self._skip += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript", "svg") and self._skip:
            self._skip -= 1

    def handle_data(self, data):
        if not self._skip and data.strip():
            self.parts.append(data.strip())


def _kb_files() -> list[Path]:
    root = config.KNOWLEDGE_DIR
    if not root.exists():
        return []
    out = []
    for p in sorted(root.rglob("*")):
        if not p.is_file() or "_files" in p.parent.name:
            continue
        if p.suffix.lower() in (".pdf", ".html", ".htm"):
            out.append(p)
    return out


def manifest() -> dict[str, list]:
    root = config.KNOWLEDGE_DIR
    return {p.relative_to(root).as_posix(): [p.stat().st_size, int(p.stat().st_mtime)] for p in _kb_files()}


def _pages(path: Path) -> list[str]:
    if path.suffix.lower() == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError:
            return []
        try:
            reader = PdfReader(str(path))
            pages = []
            for pg in reader.pages[:MAX_PAGES]:
                try:
                    pages.append(pg.extract_text() or "")
                except Exception:  # damaged page — keep numbering
                    pages.append("")
            return pages
        except Exception:
            return []
    parser = _HTMLText()
    try:
        parser.feed(path.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return []
    return ["\n".join(parser.parts)]


def _chunks(text: str) -> list[str]:
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n{2,}", "\n", text).strip()
    if len(text) < 60:
        return []
    out, start = [], 0
    while start < len(text):
        end = min(len(text), start + CHUNK_CHARS)
        if end < len(text):
            cut = max(text.rfind(". ", start + CHUNK_CHARS // 2, end), text.rfind("\n", start + CHUNK_CHARS // 2, end))
            if cut > start:
                end = cut + 1
        out.append(text[start:end].strip())
        if end >= len(text):
            break
        start = max(end - CHUNK_OVERLAP, start + 1)
    return out


def build_corpus() -> dict:
    root = config.KNOWLEDGE_DIR
    seen, docs, chunks = set(), [], []
    for path in _kb_files():
        rel = path.relative_to(root).as_posix()
        pages = _pages(path)
        full = "\n".join(pages)
        digest = hashlib.sha1(full.encode("utf-8", "ignore")).hexdigest()
        kind = FOLDER_KIND.get(rel[:2], "interpretation")
        title = path.stem.replace("_", " ")
        doc = {"path": rel, "title": title, "kind": kind, "pages": len(pages), "chars": len(full),
               "sha1": digest, "indexed": False}
        if len(full.strip()) < 200:
            doc["note"] = "no extractable text (scanned or protected) — metadata only"
        elif digest in seen:
            doc["note"] = "duplicate of another document — not indexed twice"
        else:
            seen.add(digest)
            doc["indexed"] = True
            for pno, ptext in enumerate(pages, 1):
                for c in _chunks(ptext):
                    chunks.append({"d": len(docs), "p": pno if path.suffix.lower() == ".pdf" else 0, "t": c})
        docs.append(doc)
    return {"version": INDEX_VERSION, "manifest": manifest(), "docs": docs, "chunks": chunks}


class _Corpus:
    def __init__(self):
        self.lock = threading.Lock()
        self.data: dict | None = None
        self.bm25: BM25 | None = None
        self.snapshot: tuple | None = None
        self.state = "idle"
        self.error = ""

    def enabled(self) -> bool:
        return os.getenv("PPWR_RAG_CORPUS", "1") != "0" and config.KNOWLEDGE_DIR.exists()

    def _load_cached(self) -> dict | None:
        try:
            data = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        if data.get("version") != INDEX_VERSION or data.get("manifest") != manifest():
            return None
        return data

    def ensure(self, rebuild: bool = False) -> None:
        if not self.enabled():
            self.state = "disabled"
            return
        with self.lock:
            if self.bm25 is not None and not rebuild:
                return
            self.state = "building"
            try:
                data = None if rebuild else self._load_cached()
                if data is None:
                    data = build_corpus()
                    try:
                        INDEX_PATH.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
                    except OSError:
                        pass
                bm25 = BM25([tokens(c["t"]) for c in data["chunks"]])
                self.snapshot = (data, bm25)   # swapped atomically: readers never mix old index and new chunks
                self.data, self.bm25 = data, bm25
                self.state = "ready"
            except Exception as exc:  # never break the app because of the index
                self.state, self.error = "error", str(exc)

    def start_background(self) -> None:
        if self.enabled() and self.bm25 is None and self.state != "building":
            threading.Thread(target=self.ensure, name="kb-index", daemon=True).start()


CORPUS = _Corpus()


def status() -> dict:
    d = CORPUS.data or {}
    try:
        import pypdf  # noqa: F401
        pdf_ok = True
    except ImportError:
        pdf_ok = False
    return {"state": CORPUS.state, "error": CORPUS.error, "pool": len(pool_entries()),
            "docs": len(d.get("docs", [])), "indexed": sum(1 for x in d.get("docs", []) if x.get("indexed")),
            "chunks": len(d.get("chunks", [])), "pdf_support": pdf_ok, "doc_list": d.get("docs", [])}


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

@dataclass
class Hit:
    source: str            # pool | corpus
    id: str
    kind: str
    title: str
    title_zh: str = ""
    ref: str = ""
    text: str = ""
    text_zh: str = ""
    url: str = ""
    page: int = 0
    binding: bool = False
    score: float = 0.0
    items: list = field(default_factory=list)

    def as_dict(self) -> dict:
        return asdict(self)


def _is_binding(rel: str) -> bool:
    """Legal acts (regulations, directives, decisions) vs. guidance, FAQs, studies and consultations."""
    name = rel.rsplit("/", 1)[-1].lower()
    if rel[:2] in ("03", "05"):
        return False
    return name.startswith(("ppwr regulation", "decision", "implementingdecision", "reg_eu", "supd_directive",
                            "94 62 ec"))


def _snippet(text: str, q_terms: list[str], width: int = 420) -> str:
    low = text.lower()
    pos = [low.find(t) for t in q_terms if len(t) > 3 and low.find(t) >= 0]
    start = max(0, min(pos) - 120) if pos else 0
    s = text[start:start + width].strip()
    return ("… " if start else "") + s + (" …" if start + width < len(text) else "")


def search(query: str, k: int = 6, item_id: str | None = None, articles: list[str] | None = None,
           corpus: bool = True, wait: bool = False) -> list[Hit]:
    q = expand_query(query or "")
    qt = tokens(q)
    if item_id:
        qt += [item_id.lower().replace("-", "")]
    hits: list[Hit] = []
    entries = pool_entries()
    ps = _pool_index().scores(qt) if qt else {}
    top_p = max(ps.values()) if ps else 0.0
    for i, e in enumerate(entries):
        s = (ps.get(i, 0.0) / top_p) if top_p else 0.0
        if item_id and item_id in e.get("items", []):
            s += 0.45
        if articles and set(articles) & set(e.get("articles", [])):
            s += 0.15
        if s >= 0.25:
            hits.append(Hit("pool", e["id"], e["kind"], e["title"], e["title_zh"], e["ref"], e["text"], e["text_zh"],
                            entry_url(e), e.get("page") or 0, bool(e.get("binding")), round(s, 3), e.get("items", [])))
    if corpus and CORPUS.enabled():
        if wait:
            CORPUS.ensure()
        else:
            CORPUS.start_background()
        snap = CORPUS.snapshot
        if snap is not None and qt:
            data, bm25 = snap
            cs = bm25.scores(qt)
            if cs:
                top_c = max(cs.values())
                best = sorted(cs.items(), key=lambda x: -x[1])[: k * 3]
                seen_pages = set()
                for idx, sc in best:
                    c = data["chunks"][idx]
                    doc = data["docs"][c["d"]]
                    key = (c["d"], c["p"])
                    if key in seen_pages:
                        continue
                    seen_pages.add(key)
                    norm = 0.85 * sc / top_c
                    if norm < 0.3:
                        continue
                    hits.append(Hit("corpus", f"{doc['path']}#{c['p']}", doc["kind"], doc["title"], "",
                                    doc["kind"], _snippet(c["t"], [t for t in qt if t.isascii()]), "",
                                    kb_url(doc["path"], c["p"]), c["p"], _is_binding(doc["path"]),
                                    round(norm, 3)))
    hits.sort(key=lambda h: -h.score)
    pool_hits = [h for h in hits if h.source == "pool"][: max(1, k - 2)]
    corpus_hits = [h for h in hits if h.source == "corpus"][: max(2, k - len(pool_hits))]
    out = sorted(pool_hits + corpus_hits, key=lambda h: -h.score)[:k]
    return out

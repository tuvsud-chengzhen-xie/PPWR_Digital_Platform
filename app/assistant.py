"""The PPWR assistant: retrieval-augmented, bilingual, citation-first answers.

answer() retrieves from the structured knowledge pool and the document corpus (rag.search),
then either
  * asks the configured LLM to answer **only** from the numbered sources, in English and
    Chinese, separating legal requirements from recommendations; or
  * composes a deterministic answer from the same sources (no model needed).
If nothing relevant is retrieved the assistant says so and points to the expert — it never
invents a requirement. Context (project, unit, item) narrows retrieval and adds the item's
obligation status and open gaps to the answer.
"""
from __future__ import annotations

import re

from . import guidance, llm, rag

SYSTEM = (
    "You are the PPWR compliance assistant of TÜV SÜD for Regulation (EU) 2025/40 (packaging and packaging waste). "
    "Answer ONLY with information contained in the numbered SOURCES. Cite every statement with [S#]. "
    "Clearly separate (1) what the regulation legally requires — only from sources marked BINDING — from "
    "(2) recommendations, interpretations or good practice. If the sources do not answer the question, say "
    "'The knowledge base does not cover this — please ask the TÜV SÜD expert.' Never invent articles, dates, "
    "limits or document requirements. Use plain language for non-experts. "
    "Write the answer first in English under the heading 'EN', then the same content in Simplified Chinese under "
    "the heading '中文'. Keep each language under 220 words."
)

NO_ANSWER = ("The knowledge base does not cover this question. Please ask the TÜV SÜD expert (Review queue → comment).",
             "知识库未涵盖该问题。请咨询 TÜV SÜD 专家（审核队列 → 留言）。")


def _sources_block(hits: list[rag.Hit]) -> str:
    lines = []
    for i, h in enumerate(hits, 1):
        tag = "BINDING" if h.binding else "NON-BINDING"
        head = f"[S{i}] ({tag}; {h.kind}) {h.ref or h.title}" + (f", p. {h.page}" if h.page else "")
        body = h.text if h.source == "pool" else h.text
        lines.append(f"{head}\n{h.title}: {body}")
    return "\n\n".join(lines)


def _context_lines(ctx: dict | None) -> tuple[list[str], list[str]]:
    if not ctx or not ctx.get("eval"):
        return [], []
    ev = ctx["eval"]
    ob, it = ev["ob"], ev["item"]
    en = [f"Item {it['id']} {it['name']}: {_ob_text(ob)[0]}"]
    zh = [f"条目 {it['id']} {it['name_zh']}：{_ob_text(ob)[1]}"]
    if ev["gaps"]:
        en.append("Still missing: " + "; ".join(g["en"] for g in ev["gaps"][:4]))
        zh.append("仍缺少：" + "；".join((g["zh"] or g["en"]) for g in ev["gaps"][:4]))
    return en, zh


def _ob_text(ob) -> tuple[str, str]:
    if ob.code == "mandatory_now":
        return ("legally required now (" + ob.why + ")", "现行法定必需（" + ob.why_zh + "）")
    if ob.code == "mandatory_from":
        return (f"legally required from {ob.applies_from:%d %b %Y} ({ob.why})",
                f"自 {ob.applies_from:%Y-%m-%d} 起法定必需（{ob.why_zh}）")
    if ob.code == "supporting":
        return ("recommended evidence for a legal requirement (" + ob.why + ")", "用于证明法定要求的建议证据（" + ob.why_zh + "）")
    if ob.code == "practice":
        return ("good practice, not legally required (" + ob.why + ")", "良好实践，非法定要求（" + ob.why_zh + "）")
    return ("not required for this packaging (" + ob.art_basis + ")", "本包装不适用")


def _local(question: str, hits: list[rag.Hit], ctx: dict | None) -> tuple[str, str]:
    legal = [(i, h) for i, h in enumerate(hits, 1) if h.binding]
    other = [(i, h) for i, h in enumerate(hits, 1) if not h.binding]
    en, zh = [], []
    c_en, c_zh = _context_lines(ctx)
    if c_en:
        en += c_en + [""]
        zh += c_zh + [""]
    if legal:
        en.append("What the regulation requires:")
        zh.append("法规要求：")
        for i, h in legal[:3]:
            if h.source == "pool":
                en.append(f"• {h.title} — {h.text} [S{i}]")
                zh.append(f"• {h.title_zh or h.title} —— {h.text_zh or h.text} [S{i}]")
            else:
                en.append(f"• Source text ({h.title}, p. {h.page}): “{h.text.strip()}” [S{i}]")
                zh.append(f"• 原文摘录（{h.title}，第 {h.page} 页，英文）：“{h.text.strip()}” [S{i}]")
    if other:
        en.append("Interpretation, guidance and good practice (not legally binding):")
        zh.append("解释、指南与良好实践（无法律约束力）：")
        for i, h in other[:3]:
            if h.source == "pool":
                en.append(f"• {h.title} — {h.text} [S{i}]")
                zh.append(f"• {h.title_zh or h.title} —— {h.text_zh or h.text} [S{i}]")
            else:
                en.append(f"• {h.title}{', p. ' + str(h.page) if h.page else ''}: “{h.text.strip()}” [S{i}]")
                zh.append(f"• {h.title}{'，第 ' + str(h.page) + ' 页' if h.page else ''}（英文原文）：“{h.text.strip()}” [S{i}]")
    return "\n".join(en), "\n".join(zh)


def answer(question: str, ctx: dict | None = None, k: int = 6) -> dict:
    question = (question or "").strip()[:800]
    item_id = ctx["eval"]["item"]["id"] if ctx and ctx.get("eval") else None
    articles = [ctx["eval"]["ob"].article] if ctx and ctx.get("eval") else None
    hits = rag.search(question, k=k, item_id=item_id, articles=articles) if question else []
    status = rag.status()
    out = {"question": question, "sources": [h.as_dict() for h in hits], "mode": "local", "notice": "",
           "corpus_state": status["state"]}
    if not hits or max(h.score for h in hits) < 0.3:
        out["en"], out["zh"] = NO_ANSWER
        out["sources"] = []
        return out
    if llm.configured():
        c_en, _ = _context_lines(ctx)
        prompt = (("CONTEXT (from the platform, not a source):\n" + "\n".join(c_en) + "\n\n") if c_en else "") + \
            f"QUESTION: {question}\n\nSOURCES:\n{_sources_block(hits)}"
        try:
            text = llm.chat([{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}])
            parts = re.split(r"^\s*#*\s*中文\s*:?\s*$", text, maxsplit=1, flags=re.M)
            en = re.sub(r"^\s*#*\s*EN\s*:?\s*$", "", parts[0], flags=re.M).strip()
            zh = parts[1].strip() if len(parts) > 1 else ""
            cited = {int(n) for n in re.findall(r"\[S(\d+)\]", text)}
            if not cited:
                raise llm.LLMError("answer without citations")
            out.update(en=en, zh=zh, mode="llm")
            return out
        except llm.LLMError as exc:
            out["notice"] = f"LLM unavailable ({str(exc)[:80]}) — answered from the knowledge base directly."
    out["en"], out["zh"] = _local(question, hits, ctx)
    return out


SUGGESTIONS = {
    "default": [("Which evidence must be in the technical documentation?", "技术文档必须包含哪些证据？"),
                ("Do EN 13430 and EN 13432 still give presumption of conformity?", "EN 13430 和 EN 13432 还能产生符合性推定吗？"),
                ("What are the PFAS limits for food-contact packaging?", "食品接触包装的 PFAS 限值是多少？"),
                ("How long must the TD and DoC be kept?", "技术文档和 DoC 须保存多久？")],
}


def suggestions_for(item_id: str | None) -> list[tuple[str, str]]:
    if not item_id:
        return SUGGESTIONS["default"]
    it = guidance.catalogue.item(item_id)
    return [(f"What exactly do I need to provide for {it['name']}?", f"“{it['name_zh']}”具体需要提供什么？"),
            (f"Is {it['name']} legally required or only recommended?", f"“{it['name_zh']}”是法定要求还是建议？"),
            ("What does the regulation say about this?", "法规对此有何规定？")]

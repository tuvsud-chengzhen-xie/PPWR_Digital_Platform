"""Bilingual (English / 简体中文) presentation.

Three display modes, chosen per browser session from the top bar:
    bi  – English with Chinese alongside (default; the service is used by EU experts and Chinese clients)
    en  – English only
    zh  – Chinese only (English shown where no translation exists)

Templates call `t(en, zh)` for markup and `tt(en, zh)` for plain text (attributes,
placeholders). Catalogue / knowledge objects carry `x` and `x_zh` pairs; `tf(obj, "name")`
picks them. AI outputs are produced in both languages and rendered through the same helpers.
"""
from __future__ import annotations

import markupsafe
from jinja2 import pass_context

LANGS = {"bi": "中 / EN", "en": "EN", "zh": "中文"}
DEFAULT = "bi"


def lang_of(request) -> str:
    try:
        v = request.session.get("lang", DEFAULT)
    except (AssertionError, AttributeError):
        v = DEFAULT
    return v if v in LANGS else DEFAULT


def _ctx_lang(ctx) -> str:
    req = ctx.get("request")
    return lang_of(req) if req is not None else DEFAULT


def render_pair(lang: str, en, zh) -> markupsafe.Markup:
    en = "" if en is None else str(en)
    zh = "" if zh is None else str(zh)
    if not zh or zh == en:
        return markupsafe.escape(en)
    if lang == "en":
        return markupsafe.escape(en)
    if lang == "zh":
        return markupsafe.Markup('<span lang="zh">{}</span>').format(zh)
    return markupsafe.Markup('{} <span class="zh" lang="zh">{}</span>').format(en, zh)


def text_pair(lang: str, en, zh, sep: str = " / ") -> str:
    en = "" if en is None else str(en)
    zh = "" if zh is None else str(zh)
    if not zh or zh == en or lang == "en":
        return en
    if lang == "zh":
        return zh
    return f"{en}{sep}{zh}"


def block_pair(lang: str, en, zh) -> markupsafe.Markup:
    """Longer text: in bilingual mode Chinese goes on its own line."""
    en = "" if en is None else str(en)
    zh = "" if zh is None else str(zh)
    if not zh or lang == "en":
        return markupsafe.escape(en)
    if lang == "zh":
        return markupsafe.Markup('<span lang="zh">{}</span>').format(zh)
    return markupsafe.Markup('{}<span class="zh-block" lang="zh">{}</span>').format(en, zh)


@pass_context
def t(ctx, en, zh=None):
    return render_pair(_ctx_lang(ctx), en, zh)


@pass_context
def tt(ctx, en, zh=None):
    return text_pair(_ctx_lang(ctx), en, zh)


@pass_context
def tb(ctx, en, zh=None):
    return block_pair(_ctx_lang(ctx), en, zh)


@pass_context
def tp(ctx, pair):
    """A [en, zh] list from the guidance / knowledge seeds."""
    if not pair:
        return ""
    if isinstance(pair, str):
        return markupsafe.escape(pair)
    return block_pair(_ctx_lang(ctx), pair[0], pair[1] if len(pair) > 1 else "")


@pass_context
def tf(ctx, obj, field: str, block: bool = False):
    """obj[field] with obj[field + '_zh'] — catalogue items, categories, knowledge entries."""
    if obj is None:
        return ""
    get = obj.get if isinstance(obj, dict) else (lambda k, d=None: getattr(obj, k, d))
    fn = block_pair if block else render_pair
    return fn(_ctx_lang(ctx), get(field, ""), get(field + "_zh", ""))


@pass_context
def cur_lang(ctx):
    return _ctx_lang(ctx)


# Status / verdict / stage labels used across templates.
STATUS_ZH = {"pending": "未收集", "submitted": "待 AI 初审", "ai_reviewed": "待专家复审",
             "approved": "已批准", "rejected": "已退回 — 需返工", "na": "不适用"}
VERDICT_ZH = {"pass": "AI：未发现问题", "warn": "AI：需核查", "fail": "AI：发现问题"}
STAGE_ZH = {"collecting": "资料收集中", "review": "审核中", "ready": "可签发", "issued": "TD 与 DoC 已签发"}
LEVEL = {
    "mandatory_now": ("Legally required now", "法定 · 现行必需", "badge-high"),
    "mandatory_from": ("Legally required from", "法定 · 将于以下日期起必需", "badge-warn"),
    "supporting": ("Recommended evidence", "建议证据（用于证明法定要求）", "badge-info"),
    "practice": ("Good practice (optional)", "良好实践（可选）", "badge-outline"),
    "not_required": ("Not required for this packaging", "本包装不适用", "badge-muted"),
}


def install(env) -> None:
    env.globals.update(t=t, tt=tt, tb=tb, tp=tp, tf=tf, cur_lang=cur_lang, LANGS=LANGS,
                       STATUS_ZH=STATUS_ZH, VERDICT_ZH=VERDICT_ZH, STAGE_ZH=STAGE_ZH, LEVEL=LEVEL)

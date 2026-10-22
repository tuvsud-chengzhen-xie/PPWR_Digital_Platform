"""Optional LLM connector for the AI layer (Azure OpenAI or any OpenAI-compatible endpoint).

Without configuration every AI feature runs on the local, deterministic RAG pipeline. With an
endpoint configured (Settings page, or environment variables) answers are *generated* by the
model — but only from the retrieved, numbered sources, and the local answer is used as a
fallback on any error. The API key is stored in DATA_DIR (git-ignored), never in the repo.

Environment variables override the settings file:
    PPWR_LLM_PROVIDER   azure | openai
    PPWR_LLM_ENDPOINT   https://<resource>.openai.azure.com   |  https://api.openai.com/v1
    PPWR_LLM_API_KEY
    PPWR_LLM_MODEL      deployment name (Azure) or model name
    PPWR_LLM_API_VERSION  (Azure, default 2024-06-01)
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from . import config

SETTINGS_PATH = config.DATA_DIR / "ai_settings.json"
TIMEOUT = 45


class LLMError(RuntimeError):
    pass


def settings() -> dict:
    s = {"provider": "azure", "endpoint": "", "api_key": "", "model": "", "api_version": "2024-06-01",
         "enabled": False}
    try:
        s.update(json.loads(SETTINGS_PATH.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        pass
    env = {"provider": "PPWR_LLM_PROVIDER", "endpoint": "PPWR_LLM_ENDPOINT", "api_key": "PPWR_LLM_API_KEY",
           "model": "PPWR_LLM_MODEL", "api_version": "PPWR_LLM_API_VERSION"}
    from_env = False
    for k, var in env.items():
        if os.getenv(var):
            s[k], from_env = os.getenv(var), True
    if from_env:
        s["enabled"], s["source"] = True, "environment"
    else:
        s.setdefault("source", "settings")
    return s


def save_settings(provider: str, endpoint: str, api_key: str | None, model: str, api_version: str,
                  enabled: bool) -> None:
    current = settings()
    data = {"provider": provider if provider in ("azure", "openai") else "azure",
            "endpoint": endpoint.strip().rstrip("/"), "model": model.strip(),
            "api_version": api_version.strip() or "2024-06-01", "enabled": bool(enabled),
            "api_key": api_key.strip() if api_key else current.get("api_key", "")}
    SETTINGS_PATH.write_text(json.dumps(data, indent=1), encoding="utf-8")


def configured() -> bool:
    s = settings()
    return bool(s.get("enabled") and s.get("endpoint") and s.get("api_key") and s.get("model"))


def masked_key() -> str:
    k = settings().get("api_key", "")
    return (k[:3] + "…" + k[-4:]) if len(k) > 8 else ("set" if k else "")


def chat(messages: list[dict], max_tokens: int = 1100, temperature: float = 0.1) -> str:
    s = settings()
    if not configured():
        raise LLMError("No LLM endpoint configured")
    if s["provider"] == "azure":
        url = (f"{s['endpoint']}/openai/deployments/{s['model']}/chat/completions"
               f"?api-version={s.get('api_version') or '2024-06-01'}")
        headers = {"api-key": s["api_key"]}
        body = {"messages": messages, "max_tokens": max_tokens, "temperature": temperature}
    else:
        url = f"{s['endpoint']}/chat/completions"
        headers = {"Authorization": f"Bearer {s['api_key']}"}
        body = {"model": s["model"], "messages": messages, "max_tokens": max_tokens, "temperature": temperature}
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), method="POST",
                                 headers={"Content-Type": "application/json", **headers})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "ignore")[:300]
        raise LLMError(f"HTTP {exc.code}: {detail}") from exc
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        raise LLMError(str(exc)) from exc
    try:
        return data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError) as exc:
        raise LLMError("Unexpected response format") from exc


def test_connection() -> tuple[bool, str]:
    try:
        out = chat([{"role": "user", "content": "Reply with the single word OK."}], max_tokens=5)
        return True, out[:40]
    except LLMError as exc:
        return False, str(exc)

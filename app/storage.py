"""File vault on local disk (data/uploads). Production: object storage."""
from __future__ import annotations

import re
from pathlib import Path

from . import config


def safe_name(name: str) -> str:
    name = Path(name or "file").name
    return re.sub(r"[^A-Za-z0-9._\- ]+", "_", name).strip() or "file"


def save(folder: str, stem: str, filename: str, data: bytes) -> Path:
    d = config.UPLOAD_DIR / safe_name(folder)
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{safe_name(stem)}__{safe_name(filename)}"
    path.write_bytes(data)
    return path

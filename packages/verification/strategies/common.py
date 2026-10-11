"""Shared deterministic artifact inspection helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Optional
from urllib.parse import unquote, urlparse
import os


def local_path(uri: str) -> Optional[Path]:
    if not uri or uri.startswith(("http://", "https://")):
        return None
    if uri.startswith("file://"):
        parsed = urlparse(uri)
        path = unquote(parsed.path)
        if os.name == "nt" and path.startswith("/") and len(path) > 2 and path[2] == ":":
            path = path[1:]
        return Path(path)
    return Path(uri)


def normalize_format(value: str) -> str:
    value = value.lower().strip().lstrip(".")
    return {"jpeg": "jpg", "quicktime": "mov"}.get(value, value)

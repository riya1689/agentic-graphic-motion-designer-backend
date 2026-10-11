"""Runtime URL configuration shared by backend adapters.

This module owns public URL construction only. It does not contain
orchestration, agent, provider, or rendering logic.
"""

from __future__ import annotations

import os


DEFAULT_PUBLIC_API_BASE_URL = "http://127.0.0.1:8000"


def public_api_base_url() -> str:
    """Return the externally reachable base URL for this backend instance."""

    configured_url = os.getenv(
        "PUBLIC_API_BASE_URL",
        "",
    ).strip()

    return (
        configured_url or DEFAULT_PUBLIC_API_BASE_URL
    ).rstrip("/")


def public_api_url(path: str) -> str:
    """Build a public API URL without leaking deployment details to callers."""

    return f"{public_api_base_url()}/{path.lstrip('/')}"

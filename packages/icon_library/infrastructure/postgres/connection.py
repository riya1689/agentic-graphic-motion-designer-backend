"""Lazy PostgreSQL connection boundary.

The driver is imported only when this adapter is explicitly used. Existing
application startup therefore does not require PostgreSQL to be running.
"""

from __future__ import annotations

from typing import Any

from packages.icon_library.infrastructure.postgres.config import PostgresSettings


def connect(settings: PostgresSettings | None = None) -> Any:
    settings = settings or PostgresSettings.from_environment()
    try:
        import psycopg
    except ImportError as exc:  # pragma: no cover - depends on deployment environment
        raise RuntimeError(
            "PostgreSQL support requires the 'psycopg[binary]' package."
        ) from exc
    return psycopg.connect(
        settings.database_url,
        connect_timeout=settings.connect_timeout_seconds,
    )

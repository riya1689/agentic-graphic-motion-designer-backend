"""Lazy PostgreSQL connection adapter for authentication storage."""

from __future__ import annotations

from typing import Any

from packages.auth.infrastructure.postgres.config import AuthPostgresSettings


def connect(settings: AuthPostgresSettings) -> Any:
    try:
        import psycopg
    except ImportError as exc:
        raise RuntimeError(
            "Authentication PostgreSQL support requires psycopg[binary]."
        ) from exc

    return psycopg.connect(
        settings.database_url,
        connect_timeout=settings.connect_timeout_seconds,
    )

"""Lazy PostgreSQL connection adapter for provider secrets."""

from __future__ import annotations

from typing import Any

from packages.provider_secrets.infrastructure.postgres.config import (
    ProviderSecretsPostgresSettings,
)


def connect(settings: ProviderSecretsPostgresSettings) -> Any:
    try:
        import psycopg
    except ImportError as exc:
        raise RuntimeError(
            "Provider secret storage requires psycopg[binary]."
        ) from exc
    return psycopg.connect(
        settings.database_url,
        connect_timeout=settings.connect_timeout_seconds,
    )

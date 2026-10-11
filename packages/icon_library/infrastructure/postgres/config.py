"""Environment-backed PostgreSQL configuration for the Icon Library."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[4]
load_dotenv(PROJECT_ROOT / ".env", override=False)


@dataclass(frozen=True)
class PostgresSettings:
    """Connection settings shared by desktop and future server deployments."""

    database_url: str
    connect_timeout_seconds: int = 10
    auto_migrate: bool = False

    @classmethod
    def from_environment(cls) -> "PostgresSettings":
        configured_url = os.getenv("ICON_LIBRARY_DATABASE_URL", "").strip()
        shared_url = os.getenv("DATABASE_URL", "").strip()
        return cls(
            database_url=(
                configured_url
                or shared_url
                or "postgresql://localhost:5432/agentic_graphic_motion_designer"
            ),
            connect_timeout_seconds=_positive_int(
                os.getenv("ICON_LIBRARY_DB_CONNECT_TIMEOUT", "10"), default=10
            ),
            auto_migrate=_truthy(os.getenv("ICON_LIBRARY_AUTO_MIGRATE", "false")),
        )

    def redacted_database_url(self) -> str:
        """Return a log-safe DSN without exposing a password."""
        value = self.database_url
        if "://" not in value or "@" not in value:
            return value
        scheme, remainder = value.split("://", 1)
        credentials, host = remainder.rsplit("@", 1)
        if ":" not in credentials:
            return value
        username = credentials.split(":", 1)[0]
        return f"{scheme}://{username}:***@{host}"


def _truthy(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _positive_int(value: str, *, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default

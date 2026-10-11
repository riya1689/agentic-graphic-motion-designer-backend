"""Environment-backed PostgreSQL settings for authentication."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[4]
load_dotenv(PROJECT_ROOT / ".env", override=False)


@dataclass(frozen=True)
class AuthPostgresSettings:
    database_url: str
    connect_timeout_seconds: int = 10
    jwt_secret: str = ""
    access_token_minutes: int = 15
    refresh_token_days: int = 30
    allowed_email_domains: tuple[str, ...] = ()

    @classmethod
    def from_environment(cls) -> "AuthPostgresSettings":
        configured_url = os.getenv("AUTH_DATABASE_URL", "").strip()
        fallback_url = os.getenv(
            "ICON_LIBRARY_DATABASE_URL",
            "",
        ).strip()
        allowed_domains = tuple(
            domain.strip().lower().lstrip("@")
            for domain in os.getenv(
                "AUTH_ALLOWED_EMAIL_DOMAINS",
                "",
            ).split(",")
            if domain.strip()
        )
        return cls(
            database_url=configured_url or fallback_url,
            connect_timeout_seconds=_positive_int(
                os.getenv("AUTH_DB_CONNECT_TIMEOUT", "10"),
            ),
            jwt_secret=os.getenv("AUTH_JWT_SECRET", "").strip(),
            access_token_minutes=_positive_int(
                os.getenv("AUTH_ACCESS_TOKEN_MINUTES", "15"),
            ),
            refresh_token_days=_positive_int(
                os.getenv("AUTH_REFRESH_TOKEN_DAYS", "30"),
            ),
            allowed_email_domains=allowed_domains,
        )


def _positive_int(value: str, default: int = 10) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default

"""Environment-backed database settings for provider secrets."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[4]
load_dotenv(PROJECT_ROOT / ".env", override=False)


@dataclass(frozen=True)
class ProviderSecretsPostgresSettings:
    database_url: str
    connect_timeout_seconds: int = 10
    encryption_key: str = ""
    allowed_providers: tuple[str, ...] = (
        "openai",
        "gemini",
        "higgsfield",
    )

    @classmethod
    def from_environment(cls) -> "ProviderSecretsPostgresSettings":
        configured_url = os.getenv("AUTH_DATABASE_URL", "").strip()
        fallback_url = os.getenv(
            "ICON_LIBRARY_DATABASE_URL",
            "",
        ).strip()
        shared_url = os.getenv("DATABASE_URL", "").strip()
        providers = tuple(
            item.strip().lower()
            for item in os.getenv(
                "PROVIDER_SECRET_ALLOWED_PROVIDERS",
                "openai,gemini,higgsfield",
            ).split(",")
            if item.strip()
        )
        return cls(
            database_url=configured_url or fallback_url or shared_url,
            connect_timeout_seconds=_positive_int(
                os.getenv("AUTH_DB_CONNECT_TIMEOUT", "10")
            ),
            encryption_key=os.getenv(
                "PROVIDER_SECRETS_ENCRYPTION_KEY",
                "",
            ).strip(),
            allowed_providers=providers,
        )


def _positive_int(value: str, default: int = 10) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default

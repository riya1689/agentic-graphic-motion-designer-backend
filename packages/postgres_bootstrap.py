"""Application PostgreSQL bootstrap shared by the HTTP server and scripts.

The auth and icon-library adapters intentionally keep their migrations in
their own packages.  This module is the composition boundary that applies
both sets of migrations to the configured database after PostgreSQL has been
reinstalled or a new database has been created.
"""

from __future__ import annotations

import os

from packages.auth.infrastructure.postgres.bootstrap import initialize_auth_database
from packages.auth.infrastructure.postgres.config import AuthPostgresSettings
from packages.icon_library.infrastructure.postgres.bootstrap import (
    initialize_icon_library_database,
    seed_default_builtin_icons,
)
from packages.icon_library.infrastructure.postgres.config import PostgresSettings


def initialize_application_database(
    *,
    auth_settings: AuthPostgresSettings | None = None,
    icon_library_settings: PostgresSettings | None = None,
) -> dict[str, list[str]]:
    """Apply all application PostgreSQL migrations in dependency order."""

    resolved_auth = auth_settings or AuthPostgresSettings.from_environment()
    resolved_icons = icon_library_settings or PostgresSettings.from_environment()

    # Provider-secret migration 0002 references auth.users, so auth must be
    # migrated before the icon library and before any provider-secret access.
    return {
        "auth": initialize_auth_database(resolved_auth),
        "icon_library": initialize_icon_library_database(resolved_icons),
    }


def seed_application_catalog(
    *,
    icon_library_settings: PostgresSettings | None = None,
) -> tuple[str, ...]:
    """Restore packaged built-in icons without replacing user-created icons."""

    return seed_default_builtin_icons(
        icon_library_settings or PostgresSettings.from_environment(),
    )


def should_auto_migrate() -> bool:
    """Return whether the server should repair schemas during startup.

    Automatic migration is enabled by default because the desktop deployment
    owns its local PostgreSQL database.  Set POSTGRES_AUTO_MIGRATE=false for
    environments where migrations are managed by a separate release step.
    """

    value = os.getenv("POSTGRES_AUTO_MIGRATE", "true")
    return value.strip().lower() in {"1", "true", "yes", "on"}


def format_migration_result(result: dict[str, list[str]]) -> str:
    """Create a concise, non-sensitive startup log message."""

    return "; ".join(
        f"{name}: {', '.join(versions) if versions else 'already up to date'}"
        for name, versions in result.items()
    )

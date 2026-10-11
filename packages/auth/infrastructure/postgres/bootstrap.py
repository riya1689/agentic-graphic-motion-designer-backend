"""Explicit authentication database bootstrap command."""

from __future__ import annotations

from packages.auth.infrastructure.postgres.config import AuthPostgresSettings
from packages.auth.infrastructure.postgres.connection import connect
from packages.auth.infrastructure.postgres.migrator import AuthMigrationRunner


def initialize_auth_database(
    settings: AuthPostgresSettings | None = None,
) -> list[str]:
    resolved = settings or AuthPostgresSettings.from_environment()
    return AuthMigrationRunner(
        lambda: connect(resolved),
    ).apply()


def main() -> None:
    applied = initialize_auth_database()
    if applied:
        print(f"Authentication migrations applied: {', '.join(applied)}")
    else:
        print("Authentication database is already up to date.")


if __name__ == "__main__":
    main()

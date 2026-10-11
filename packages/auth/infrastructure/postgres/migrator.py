"""Small additive migration runner for the authentication schema."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable


class AuthMigrationRunner:
    def __init__(
        self,
        connection_factory: Callable[[], Any],
        *,
        migrations_dir: Path | None = None,
    ) -> None:
        self._connection_factory = connection_factory
        self._migrations_dir = migrations_dir or Path(__file__).parent / "migrations"

    def apply(self) -> list[str]:
        applied: list[str] = []
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute("CREATE SCHEMA IF NOT EXISTS auth")
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS auth.schema_migrations (
                        version TEXT PRIMARY KEY,
                        applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                    """
                )
                cursor.execute("SELECT version FROM auth.schema_migrations")
                existing = {str(row[0]) for row in cursor.fetchall()}

                for path in sorted(self._migrations_dir.glob("*.sql")):
                    version = path.stem.split("_", 1)[0]
                    if not version.isdigit() or version in existing:
                        continue
                    cursor.execute(path.read_text(encoding="utf-8"))
                    cursor.execute(
                        "INSERT INTO auth.schema_migrations (version) VALUES (%s)",
                        (version,),
                    )
                    applied.append(version)
        return applied

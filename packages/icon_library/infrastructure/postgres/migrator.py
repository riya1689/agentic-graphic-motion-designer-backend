"""Small additive migration runner for the Icon Library PostgreSQL schema."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


@dataclass(frozen=True)
class Migration:
    version: str
    path: Path


class MigrationRunner:
    """Apply ordered SQL files and record completed versions."""

    def __init__(
        self,
        connection_factory: Callable[[], Any],
        *,
        migrations_dir: Path | None = None,
    ) -> None:
        self._connection_factory = connection_factory
        self._migrations_dir = migrations_dir or Path(__file__).parent / "migrations"

    def discover(self) -> list[Migration]:
        migrations = []
        for path in sorted(self._migrations_dir.glob("*.sql")):
            version = path.stem.split("_", 1)[0]
            if not version.isdigit():
                raise ValueError(f"Migration filename must start with a numeric version: {path.name}")
            migrations.append(Migration(version=version, path=path))
        return migrations

    def apply(self) -> list[str]:
        migrations = self.discover()
        applied: list[str] = []
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "CREATE SCHEMA IF NOT EXISTS icon_library"
                )
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS icon_library.schema_migrations (
                        version TEXT PRIMARY KEY,
                        applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                    """
                )
                cursor.execute("SELECT version FROM icon_library.schema_migrations")
                existing = {str(row[0]) for row in cursor.fetchall()}
                for migration in migrations:
                    if migration.version in existing:
                        continue
                    cursor.execute(migration.path.read_text(encoding="utf-8"))
                    cursor.execute(
                        "INSERT INTO icon_library.schema_migrations (version) VALUES (%s)",
                        (migration.version,),
                    )
                    applied.append(migration.version)
        return applied

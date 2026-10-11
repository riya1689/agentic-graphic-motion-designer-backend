"""Explicit desktop/server database bootstrap for the Icon Library."""

from __future__ import annotations

from pathlib import Path

from packages.icon_library.application.catalog import seed_builtin_icons
from packages.icon_library.infrastructure.postgres.factory import build_postgres_icon_library_service
from packages.icon_library.infrastructure.postgres.config import PostgresSettings
from packages.icon_library.infrastructure.postgres.connection import connect
from packages.icon_library.infrastructure.postgres.migrator import MigrationRunner


def initialize_icon_library_database(settings: PostgresSettings | None = None) -> list[str]:
    """Connect explicitly and apply pending Icon Library migrations."""
    resolved = settings or PostgresSettings.from_environment()
    runner = MigrationRunner(lambda: connect(resolved))
    return runner.apply()


def seed_default_builtin_icons(settings: PostgresSettings | None = None) -> tuple[str, ...]:
    """Register the versioned built-in SVG catalog after migrations."""
    resolved = settings or PostgresSettings.from_environment()
    package_root = Path(__file__).resolve().parents[2]
    asset_directory = package_root / "assets" / "builtin"
    return seed_builtin_icons(
        build_postgres_icon_library_service(resolved),
        manifest_path=asset_directory / "manifest.json",
        asset_directory=asset_directory,
    )


def main() -> None:
    settings = PostgresSettings.from_environment()
    applied = initialize_icon_library_database(settings)
    seeded = seed_default_builtin_icons(settings)
    if applied:
        print(f"Icon Library migrations applied: {', '.join(applied)}")
    else:
        print("Icon Library database is already up to date.")
    if seeded:
        print(f"Built-in icons seeded: {', '.join(seeded)}")
    else:
        print("Built-in icon catalog is already up to date.")


if __name__ == "__main__":
    main()

"""One-time interactive bootstrap for the first administrator account."""

from __future__ import annotations

from getpass import getpass

import os

from packages.auth.infrastructure.postgres.bootstrap import initialize_auth_database
from packages.auth.infrastructure.postgres.config import AuthPostgresSettings
from packages.auth.infrastructure.postgres.factory import build_postgres_auth_service


def main() -> None:
    if os.getenv("STORAGE_BACKEND", "postgres").strip().lower() == "sqlite":
        from packages.sqlite_storage.bootstrap import initialize_database
        from packages.auth.infrastructure.sqlite.factory import build_sqlite_auth_service

        initialize_database()
        settings = AuthPostgresSettings.from_environment()
        service_factory = lambda: build_sqlite_auth_service(settings)
    else:
        service_factory = lambda: build_postgres_auth_service(settings)

    settings = AuthPostgresSettings.from_environment()
    if os.getenv("STORAGE_BACKEND", "postgres").strip().lower() != "sqlite":
        initialize_auth_database(settings)

    email = input("Admin email: ").strip()
    display_name = input("Admin display name: ").strip()
    password = getpass("Temporary password (min 10 characters): ")
    confirmation = getpass("Confirm password: ")

    if password != confirmation:
        raise SystemExit("Passwords do not match.")

    service = service_factory()
    user = service.create_user(
        email=email,
        display_name=display_name,
        temporary_password=password,
        roles=("admin",),
    )
    print(f"Administrator created: {user.email}")


if __name__ == "__main__":
    main()

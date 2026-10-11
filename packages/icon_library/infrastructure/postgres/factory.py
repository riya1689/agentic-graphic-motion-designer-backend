"""Composition boundary for the PostgreSQL-backed Icon Library."""

from __future__ import annotations

from typing import Any, Callable

from packages.icon_library.application.service import IconLibraryService
from packages.icon_library.infrastructure.postgres.config import PostgresSettings
from packages.icon_library.infrastructure.postgres.connection import connect
from packages.icon_library.infrastructure.postgres.repository import (
    PostgresIconAssetStore,
    PostgresIconRepository,
)


ConnectionFactory = Callable[[], Any]


def build_postgres_icon_library_service(
    settings: PostgresSettings | None = None,
    *,
    connection_factory: ConnectionFactory | None = None,
) -> IconLibraryService:
    """Compose the application service with PostgreSQL adapters.

    The connection factory is injectable for tests and future connection-pool
    implementations. No connection is opened while this function builds the
    service; the database is contacted only when a use case is executed.
    """
    resolved_settings = settings or PostgresSettings.from_environment()
    factory = connection_factory or (lambda: connect(resolved_settings))
    return IconLibraryService(
        repository=PostgresIconRepository(factory),
        asset_store=PostgresIconAssetStore(factory),
    )


def check_postgres_connection(
    settings: PostgresSettings | None = None,
    *,
    connection_factory: ConnectionFactory | None = None,
) -> bool:
    """Perform an explicit lightweight database health check."""
    resolved_settings = settings or PostgresSettings.from_environment()
    factory = connection_factory or (lambda: connect(resolved_settings))
    with factory() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            return cursor.fetchone()[0] == 1

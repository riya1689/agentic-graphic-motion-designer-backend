"""Factories for the PostgreSQL authentication adapter."""

from packages.auth.application.service_impl import PostgresAuthService
from packages.auth.infrastructure.postgres.config import AuthPostgresSettings
from packages.auth.infrastructure.postgres.connection import connect
from packages.auth.infrastructure.postgres.repository import PostgresAuthRepository


def build_postgres_auth_service(
    settings: AuthPostgresSettings | None = None,
) -> PostgresAuthService:
    resolved = settings or AuthPostgresSettings.from_environment()
    repository = PostgresAuthRepository(
        lambda: connect(resolved),
    )
    return PostgresAuthService(
        repository=repository,
        settings=resolved,
    )

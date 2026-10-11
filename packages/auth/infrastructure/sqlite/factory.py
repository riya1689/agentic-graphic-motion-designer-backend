from packages.auth.application.service_impl import PostgresAuthService
from packages.auth.infrastructure.postgres.config import AuthPostgresSettings
from packages.auth.infrastructure.sqlite.repository import SQLiteAuthRepository
from packages.sqlite_storage.connection import connect


def build_sqlite_auth_service(settings=None):
    resolved = settings or AuthPostgresSettings.from_environment()
    return PostgresAuthService(repository=SQLiteAuthRepository(connect), settings=resolved)


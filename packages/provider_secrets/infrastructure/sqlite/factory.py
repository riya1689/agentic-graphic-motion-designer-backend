from packages.provider_secrets.application.service_impl import EncryptedProviderSecretService
from packages.provider_secrets.infrastructure.postgres.config import ProviderSecretsPostgresSettings
from packages.provider_secrets.infrastructure.sqlite.repository import SQLiteProviderSecretRepository
from packages.sqlite_storage.connection import connect


def build_sqlite_provider_secret_service(settings=None):
    resolved = settings or ProviderSecretsPostgresSettings.from_environment()
    return EncryptedProviderSecretService(repository=SQLiteProviderSecretRepository(connect), settings=resolved)


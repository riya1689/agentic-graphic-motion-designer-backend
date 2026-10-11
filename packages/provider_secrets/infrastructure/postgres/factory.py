"""Factories for provider-secret persistence."""

from packages.provider_secrets.application.service_impl import (
    EncryptedProviderSecretService,
)
from packages.provider_secrets.infrastructure.postgres.config import (
    ProviderSecretsPostgresSettings,
)
from packages.provider_secrets.infrastructure.postgres.connection import connect
from packages.provider_secrets.infrastructure.postgres.repository import (
    ProviderSecretRepository,
)


def build_provider_secret_service(
    settings: ProviderSecretsPostgresSettings | None = None,
) -> EncryptedProviderSecretService:
    resolved = settings or ProviderSecretsPostgresSettings.from_environment()
    repository = ProviderSecretRepository(lambda: connect(resolved))
    return EncryptedProviderSecretService(
        repository=repository,
        settings=resolved,
    )

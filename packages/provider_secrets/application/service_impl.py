"""Encrypted PostgreSQL-backed provider-secret service."""

from __future__ import annotations

from packages.provider_secrets.domain.models import ProviderSecretSummary
from packages.provider_secrets.infrastructure.crypto import SecretCipher
from packages.provider_secrets.infrastructure.postgres.config import (
    ProviderSecretsPostgresSettings,
)
from packages.provider_secrets.infrastructure.postgres.repository import (
    ProviderSecretRepository,
)


class EncryptedProviderSecretService:
    def __init__(
        self,
        *,
        repository: ProviderSecretRepository,
        settings: ProviderSecretsPostgresSettings,
    ) -> None:
        self._repository = repository
        self._settings = settings
        self._cipher = SecretCipher(settings.encryption_key)

    def list_secrets(self) -> list[ProviderSecretSummary]:
        return self._repository.list()

    def set_secret(
        self,
        *,
        provider: str,
        secret_name: str,
        value: str,
        updated_by: str,
    ) -> ProviderSecretSummary:
        provider_name = self._validate_provider(provider)
        name = _validate_name(secret_name)
        clean_value = value.strip()
        if not clean_value:
            raise ValueError("Provider secret must not be empty")
        if len(clean_value) > 4096:
            raise ValueError("Provider secret is too large")
        return self._repository.upsert(
            provider=provider_name,
            secret_name=name,
            ciphertext=self._cipher.encrypt(clean_value),
            masked_value=self._cipher.mask(clean_value),
            updated_by=updated_by,
        )

    def get_secret(self, *, provider: str, secret_name: str = "api_key") -> str | None:
        provider_name = self._validate_provider(provider)
        ciphertext = self._repository.get_active_ciphertext(
            provider=provider_name,
            secret_name=_validate_name(secret_name),
        )
        return self._cipher.decrypt(ciphertext) if ciphertext else None

    def revoke_secret(
        self,
        *,
        provider: str,
        secret_name: str,
        updated_by: str,
    ) -> None:
        self._repository.revoke(
            provider=self._validate_provider(provider),
            secret_name=_validate_name(secret_name),
            updated_by=updated_by,
        )

    def _validate_provider(self, provider: str) -> str:
        normalized = provider.strip().lower()
        if normalized not in self._settings.allowed_providers:
            raise ValueError("Provider is not enabled for secret management")
        return normalized


def _validate_name(value: str) -> str:
    normalized = value.strip().lower()
    if not normalized or len(normalized) > 100:
        raise ValueError("Secret name is invalid")
    return normalized

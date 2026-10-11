"""Provider-neutral secret-management interface."""

from __future__ import annotations

from typing import Protocol

from packages.provider_secrets.domain.models import ProviderSecretSummary


class ProviderSecretService(Protocol):
    def list_secrets(self) -> list[ProviderSecretSummary]:
        """List masked provider secrets only."""

    def set_secret(
        self,
        *,
        provider: str,
        secret_name: str,
        value: str,
        updated_by: str,
    ) -> ProviderSecretSummary:
        """Encrypt and store one provider secret."""

    def get_secret(self, *, provider: str, secret_name: str = "api_key") -> str | None:
        """Resolve one secret for trusted backend provider adapters."""

    def revoke_secret(
        self,
        *,
        provider: str,
        secret_name: str,
        updated_by: str,
    ) -> None:
        """Disable a provider secret without returning its value."""

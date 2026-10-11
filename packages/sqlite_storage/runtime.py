"""Desktop-only runtime secret bootstrap for the encrypted local store."""

from __future__ import annotations

import os
import secrets

from packages.sqlite_storage.credentials import CredentialManagerSecretStore


def ensure_desktop_runtime_secrets() -> None:
    """Populate authentication/encryption secrets before app composition."""
    if os.name != "nt":
        raise RuntimeError(
            "Desktop SQLite mode requires Windows Credential Manager on Windows."
        )

    jwt_secret = _ensure_secret(
        target="Runtime/AuthJwtSecret",
        environment_name="AUTH_JWT_SECRET",
        factory=lambda: secrets.token_urlsafe(48),
        comment="Agentic Graphic Motion Designer authentication signing secret",
    )
    provider_key = _ensure_secret(
        target="Runtime/ProviderSecretsEncryptionKey",
        environment_name="PROVIDER_SECRETS_ENCRYPTION_KEY",
        factory=_generate_fernet_key,
        comment="Agentic Graphic Motion Designer provider-secret encryption key",
        validator=_is_valid_fernet_key,
    )

    os.environ["AUTH_JWT_SECRET"] = jwt_secret
    os.environ["PROVIDER_SECRETS_ENCRYPTION_KEY"] = provider_key


def _ensure_secret(*, target, environment_name, factory, comment, validator=None) -> str:
    store = CredentialManagerSecretStore(target)
    stored = store.read()
    if stored:
        if validator is None or validator(stored):
            return stored
        # A malformed legacy value must not prevent desktop startup. It
        # cannot decrypt provider secrets, so replace it with a valid key.
        store.delete()

    configured = os.getenv(environment_name, "").strip()
    if configured and (validator is None or validator(configured)):
        store.write(configured, comment=comment)
        return configured

    return store.get_or_create(factory, comment=comment)


def _generate_fernet_key() -> str:
    try:
        from cryptography.fernet import Fernet
    except ImportError as exc:
        raise RuntimeError(
            "cryptography is required to initialize desktop provider-secret storage."
        ) from exc
    return Fernet.generate_key().decode("ascii")


def _is_valid_fernet_key(value: str) -> bool:
    try:
        from cryptography.fernet import Fernet

        Fernet(value.encode("ascii"))
        return True
    except (ImportError, UnicodeEncodeError, ValueError, TypeError):
        return False

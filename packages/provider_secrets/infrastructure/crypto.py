"""Application-level encryption for provider secrets.

The encryption key is never stored in PostgreSQL. It must be supplied through
the server secret environment or an external secret manager.
"""

from __future__ import annotations


class SecretCipher:
    def __init__(self, encryption_key: str) -> None:
        self._encryption_key = encryption_key.strip()
        self._fernet = None

    def encrypt(self, value: str) -> str:
        return self._get_fernet().encrypt(value.encode("utf-8")).decode("utf-8")

    def decrypt(self, value: str) -> str:
        try:
            return self._get_fernet().decrypt(value.encode("utf-8")).decode("utf-8")
        except Exception as exc:
            raise RuntimeError("Provider secret could not be decrypted") from exc

    @staticmethod
    def mask(value: str) -> str:
        if len(value) <= 4:
            return "••••"
        return f"••••••••{value[-4:]}"

    def _get_fernet(self):
        if self._fernet is not None:
            return self._fernet
        if not self._encryption_key:
            raise RuntimeError(
                "PROVIDER_SECRETS_ENCRYPTION_KEY is required for provider secrets"
            )
        try:
            from cryptography.fernet import Fernet
        except ImportError as exc:
            raise RuntimeError(
                "cryptography is required for provider secret management"
            ) from exc
        try:
            self._fernet = Fernet(self._encryption_key.encode("utf-8"))
        except Exception as exc:
            raise RuntimeError(
                "PROVIDER_SECRETS_ENCRYPTION_KEY is not a valid Fernet key"
            ) from exc
        return self._fernet

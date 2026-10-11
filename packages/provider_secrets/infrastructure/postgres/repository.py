"""Persistence operations for encrypted provider secrets."""

from __future__ import annotations

import json
from typing import Any, Callable
from uuid import UUID

from packages.provider_secrets.domain.models import ProviderSecretSummary


class ProviderSecretRepository:
    def __init__(self, connection_factory: Callable[[], Any]) -> None:
        self._connection_factory = connection_factory

    def list(self) -> list[ProviderSecretSummary]:
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT provider, secret_name, masked_value, is_active,
                           version, created_at, updated_at
                    FROM auth.provider_secrets
                    ORDER BY provider, secret_name
                    """
                )
                rows = cursor.fetchall()
        return [_summary(row) for row in rows]

    def get_active_ciphertext(
        self,
        *,
        provider: str,
        secret_name: str,
    ) -> str | None:
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT ciphertext
                    FROM auth.provider_secrets
                    WHERE provider = %s
                      AND secret_name = %s
                      AND is_active = TRUE
                    """,
                    (provider, secret_name),
                )
                row = cursor.fetchone()
        return str(row[0]) if row else None

    def upsert(
        self,
        *,
        provider: str,
        secret_name: str,
        ciphertext: str,
        masked_value: str,
        updated_by: str,
    ) -> ProviderSecretSummary:
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO auth.provider_secrets
                        (provider, secret_name, ciphertext, masked_value,
                         is_active, version, updated_by)
                    VALUES (%s, %s, %s, %s, TRUE, 1, %s)
                    ON CONFLICT (provider, secret_name) DO UPDATE SET
                        ciphertext = EXCLUDED.ciphertext,
                        masked_value = EXCLUDED.masked_value,
                        is_active = TRUE,
                        version = auth.provider_secrets.version + 1,
                        updated_at = NOW(),
                        updated_by = EXCLUDED.updated_by
                    RETURNING provider, secret_name, masked_value, is_active,
                              version, created_at, updated_at
                    """,
                    (
                        provider,
                        secret_name,
                        ciphertext,
                        masked_value,
                        UUID(updated_by),
                    ),
                )
                row = cursor.fetchone()
                cursor.execute(
                    """
                    INSERT INTO auth.audit_log
                        (user_id, event, metadata)
                    VALUES (%s, %s, %s::jsonb)
                    """,
                    (
                        UUID(updated_by),
                        "provider_secret_upserted",
                        json.dumps({
                            "provider": provider,
                            "secret_name": secret_name,
                        }),
                    ),
                )
        return _summary(row)

    def revoke(
        self,
        *,
        provider: str,
        secret_name: str,
        updated_by: str,
    ) -> None:
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE auth.provider_secrets
                    SET is_active = FALSE,
                        version = version + 1,
                        updated_at = NOW(),
                        updated_by = %s
                    WHERE provider = %s AND secret_name = %s
                    """,
                    (UUID(updated_by), provider, secret_name),
                )
                cursor.execute(
                    """
                    INSERT INTO auth.audit_log
                        (user_id, event, metadata)
                    VALUES (%s, %s, %s::jsonb)
                    """,
                    (
                        UUID(updated_by),
                        "provider_secret_revoked",
                        json.dumps({
                            "provider": provider,
                            "secret_name": secret_name,
                        }),
                    ),
                )


def _summary(row: Any) -> ProviderSecretSummary:
    return ProviderSecretSummary(
        provider=str(row[0]),
        secret_name=str(row[1]),
        masked_value=str(row[2]),
        is_active=bool(row[3]),
        version=int(row[4]),
        created_at=row[5],
        updated_at=row[6],
    )

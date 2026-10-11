"""PostgreSQL repository for users, roles, sessions, and audit events."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Callable
from uuid import UUID, uuid4

from packages.auth.domain.models import AuthenticatedUser, AuthSession, UserAccount


class PostgresAuthRepository:
    def __init__(self, connection_factory: Callable[[], Any]) -> None:
        self._connection_factory = connection_factory

    def create_user(
        self,
        *,
        email: str,
        display_name: str,
        password_hash: str,
        roles: tuple[str, ...],
    ) -> UserAccount:
        user_id = uuid4()
        normalized_email = _normalize_email(email)
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO auth.users
                        (id, email, display_name, password_hash)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id, email, display_name, status,
                              created_at, last_login_at,
                              must_change_password
                    """,
                    (user_id, normalized_email, display_name.strip(), password_hash),
                )
                row = cursor.fetchone()
                for role in roles:
                    cursor.execute(
                        """
                        INSERT INTO auth.user_roles (user_id, role_id)
                        VALUES (%s, %s)
                        """,
                        (user_id, role),
                    )
        return _user_from_row(row)

    def find_by_email(self, email: str) -> tuple[UserAccount, str, tuple[str, ...]] | None:
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT u.id, u.email, u.display_name, u.status,
                           u.created_at, u.last_login_at,
                           u.must_change_password, u.password_hash,
                           COALESCE(
                               ARRAY_AGG(ur.role_id)
                               FILTER (WHERE ur.role_id IS NOT NULL),
                               ARRAY[]::TEXT[]
                           ) AS roles
                    FROM auth.users AS u
                    LEFT JOIN auth.user_roles AS ur ON ur.user_id = u.id
                    WHERE LOWER(u.email) = LOWER(%s)
                    GROUP BY u.id
                    """,
                    (email.strip(),),
                )
                row = cursor.fetchone()
        if row is None:
            return None
        return _user_from_row(row[:7]), str(row[7]), tuple(row[8] or ())

    def list_users(self) -> list[tuple[UserAccount, tuple[str, ...]]]:
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT u.id, u.email, u.display_name, u.status,
                           u.created_at, u.last_login_at,
                           u.must_change_password,
                           COALESCE(
                               ARRAY_AGG(ur.role_id)
                               FILTER (WHERE ur.role_id IS NOT NULL),
                               ARRAY[]::TEXT[]
                           ) AS roles
                    FROM auth.users AS u
                    LEFT JOIN auth.user_roles AS ur ON ur.user_id = u.id
                    GROUP BY u.id
                    ORDER BY u.created_at ASC, u.email ASC
                    """
                )
                rows = cursor.fetchall()
        return [
            (_user_from_row(row[:7]), tuple(row[7] or ()))
            for row in rows
        ]

    def update_status(self, *, user_id: str, status: str) -> UserAccount:
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE auth.users
                    SET status = %s, updated_at = NOW()
                    WHERE id = %s
                    RETURNING id, email, display_name, status,
                              created_at, last_login_at,
                              must_change_password
                    """,
                    (status, UUID(user_id)),
                )
                row = cursor.fetchone()
        if row is None:
            raise ValueError("User was not found")
        return _user_from_row(row)

    def update_password(
        self,
        *,
        user_id: str,
        password_hash: str,
    ) -> UserAccount:
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE auth.users
                    SET password_hash = %s,
                        must_change_password = TRUE,
                        updated_at = NOW()
                    WHERE id = %s
                    RETURNING id, email, display_name, status,
                              created_at, last_login_at,
                              must_change_password
                    """,
                    (password_hash, UUID(user_id)),
                )
                row = cursor.fetchone()
        if row is None:
            raise ValueError("User was not found")
        return _user_from_row(row)

    def find_active_user(
        self,
        user_id: str,
    ) -> AuthenticatedUser | None:
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT u.id, u.email, u.display_name, u.status,
                           u.created_at, u.last_login_at,
                           u.must_change_password,
                           COALESCE(
                               ARRAY_AGG(ur.role_id)
                               FILTER (WHERE ur.role_id IS NOT NULL),
                               ARRAY[]::TEXT[]
                           ) AS roles
                    FROM auth.users AS u
                    LEFT JOIN auth.user_roles AS ur ON ur.user_id = u.id
                    WHERE u.id = %s AND u.status = 'active'
                    GROUP BY u.id
                    """,
                    (UUID(user_id),),
                )
                row = cursor.fetchone()
        if row is None:
            return None
        return AuthenticatedUser(
            user=_user_from_row(row[:7]),
            roles=tuple(row[7] or ()),
        )

    def mark_login(self, *, user_id: str) -> None:
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE auth.users SET last_login_at = NOW(), updated_at = NOW() WHERE id = %s",
                    (UUID(user_id),),
                )

    def create_session(
        self,
        *,
        user_id: str,
        refresh_token_hash: str,
        expires_at: datetime,
        device_label: str | None,
        ip_address: str | None,
        user_agent: str | None,
    ) -> str:
        session_id = uuid4()
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO auth.sessions
                        (id, user_id, refresh_token_hash, expires_at,
                         device_label, ip_address, user_agent)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        session_id,
                        UUID(user_id),
                        refresh_token_hash,
                        expires_at,
                        device_label,
                        ip_address,
                        user_agent,
                    ),
                )
        return str(session_id)

    def find_session(self, *, refresh_token_hash: str) -> tuple[str, str] | None:
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id, user_id
                    FROM auth.sessions
                    WHERE refresh_token_hash = %s
                      AND revoked_at IS NULL
                      AND expires_at > NOW()
                    """,
                    (refresh_token_hash,),
                )
                row = cursor.fetchone()
        if row is None:
            return None
        return str(row[0]), str(row[1])

    def touch_session(self, *, session_id: str) -> None:
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE auth.sessions SET last_seen_at = NOW() WHERE id = %s",
                    (UUID(session_id),),
                )

    def revoke_session(self, *, session_id: str) -> None:
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE auth.sessions SET revoked_at = NOW() WHERE id = %s",
                    (UUID(session_id),),
                )

    def audit(
        self,
        *,
        user_id: str | None,
        event: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO auth.audit_log
                        (user_id, event, ip_address, user_agent, metadata)
                    VALUES (%s, %s, %s, %s, %s::jsonb)
                    """,
                    (
                        UUID(user_id) if user_id else None,
                        event,
                        ip_address,
                        user_agent,
                        json.dumps(metadata or {}),
                    ),
                )


def hash_refresh_token(refresh_token: str) -> str:
    return hashlib.sha256(refresh_token.encode("utf-8")).hexdigest()


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _user_from_row(row: Any) -> UserAccount:
    return UserAccount(
        user_id=str(row[0]),
        email=str(row[1]),
        display_name=str(row[2]),
        status=str(row[3]),
        created_at=row[4],
        last_login_at=row[5],
        must_change_password=bool(row[6]),
    )

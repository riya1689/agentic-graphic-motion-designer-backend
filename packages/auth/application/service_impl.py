"""PostgreSQL-backed implementation of the provider-neutral AuthService."""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

from packages.auth.application.service import AuthService
from packages.auth.domain.models import (
    AuthenticatedUser,
    AuthSession,
    AuthTokens,
    UserAccount,
)
from packages.auth.infrastructure.passwords import BcryptPasswordHasher
from packages.auth.infrastructure.postgres.config import AuthPostgresSettings
from packages.auth.infrastructure.postgres.repository import (
    PostgresAuthRepository,
    hash_refresh_token,
)


class PostgresAuthService(AuthService):
    def __init__(
        self,
        *,
        repository: PostgresAuthRepository,
        settings: AuthPostgresSettings,
        password_hasher: BcryptPasswordHasher | None = None,
    ) -> None:
        self._repository = repository
        self._settings = settings
        self._password_hasher = password_hasher or BcryptPasswordHasher()

    def create_user(
        self,
        *,
        email: str,
        display_name: str,
        temporary_password: str,
        roles: tuple[str, ...] = ("viewer",),
    ) -> UserAccount:
        normalized_email = _validate_email(email, self._settings.allowed_email_domains)
        normalized_roles = tuple(sorted(set(role.strip().lower() for role in roles if role.strip())))
        if not normalized_roles:
            raise ValueError("At least one role is required")
        unsupported_roles = set(normalized_roles) - {"admin", "designer", "viewer"}
        if unsupported_roles:
            raise ValueError(
                "Unsupported role(s): " + ", ".join(sorted(unsupported_roles))
            )
        if not display_name.strip():
            raise ValueError("Display name is required")
        if self._repository.find_by_email(normalized_email) is not None:
            raise ValueError("A user with this email already exists")
        return self._repository.create_user(
            email=normalized_email,
            display_name=display_name,
            password_hash=self._password_hasher.hash(temporary_password),
            roles=normalized_roles,
        )

    def authenticate(
        self,
        *,
        email: str,
        password: str,
    ) -> AuthenticatedUser | None:
        record = self._repository.find_by_email(email)
        if record is None:
            return None
        user, password_hash, roles = record
        if user.status != "active" or not self._password_hasher.verify(password, password_hash):
            return None
        self._repository.mark_login(user_id=user.user_id)
        self._repository.audit(user_id=user.user_id, event="login_success")
        return AuthenticatedUser(user=user, roles=roles)

    def list_users(self) -> list[AuthenticatedUser]:
        return [
            AuthenticatedUser(user=user, roles=roles)
            for user, roles in self._repository.list_users()
        ]

    def set_user_status(self, *, user_id: str, status: str) -> UserAccount:
        normalized = status.strip().lower()
        if normalized not in {"active", "disabled", "pending"}:
            raise ValueError("Status must be active, disabled, or pending")
        return self._repository.update_status(user_id=user_id, status=normalized)

    def reset_user_password(
        self,
        *,
        user_id: str,
        temporary_password: str,
    ) -> UserAccount:
        return self._repository.update_password(
            user_id=user_id,
            password_hash=self._password_hasher.hash(temporary_password),
        )

    def issue_tokens(
        self,
        *,
        authenticated_user: AuthenticatedUser,
        device_label: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> AuthTokens:
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(days=self._settings.refresh_token_days)
        refresh_token = secrets.token_urlsafe(48)
        session_id = self._repository.create_session(
            user_id=authenticated_user.user.user_id,
            refresh_token_hash=hash_refresh_token(refresh_token),
            expires_at=expires_at,
            device_label=device_label,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        access_token = self._encode_access_token(authenticated_user)
        self._repository.audit(
            user_id=authenticated_user.user.user_id,
            event="session_created",
            ip_address=ip_address,
            user_agent=user_agent,
            metadata={"session_id": session_id},
        )
        return AuthTokens(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="Bearer",
            expires_in=self._settings.access_token_minutes * 60,
        )

    def authenticate_access_token(self, token: str) -> AuthenticatedUser | None:
        jwt = _load_jwt()
        try:
            payload = jwt.decode(
                token,
                self._settings.jwt_secret,
                algorithms=["HS256"],
                options={"require": ["sub", "exp", "iat", "type"]},
            )
        except jwt.InvalidTokenError:
            return None
        if payload.get("type") != "access":
            return None
        return self._repository.find_active_user(str(payload["sub"]))

    def refresh_tokens(
        self,
        *,
        refresh_token: str,
        device_label: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> AuthTokens | None:
        session = self._repository.find_session(
            refresh_token_hash=hash_refresh_token(refresh_token),
        )
        if session is None:
            return None
        session_id, user_id = session
        user = self._repository.find_active_user(user_id)
        if user is None:
            return None
        self._require_jwt_secret()
        self._repository.revoke_session(session_id=session_id)
        return self.issue_tokens(
            authenticated_user=user,
            device_label=device_label,
            ip_address=ip_address,
            user_agent=user_agent,
        )

    def revoke_refresh_token(self, *, refresh_token: str) -> None:
        session = self._repository.find_session(
            refresh_token_hash=hash_refresh_token(refresh_token),
        )
        if session is not None:
            session_id, user_id = session
            self._repository.revoke_session(session_id=session_id)
            self._repository.audit(user_id=user_id, event="logout")

    def _encode_access_token(self, user: AuthenticatedUser) -> str:
        jwt = _load_jwt()
        jwt_secret = self._require_jwt_secret()
        now = datetime.now(timezone.utc)
        return jwt.encode(
            {
                "sub": user.user.user_id,
                "roles": list(user.roles),
                "type": "access",
                "iat": now,
                "exp": now + timedelta(minutes=self._settings.access_token_minutes),
            },
            jwt_secret,
            algorithm="HS256",
        )

    def _require_jwt_secret(self) -> str:
        if not self._settings.jwt_secret:
            raise RuntimeError("AUTH_JWT_SECRET is required for authentication")
        return self._settings.jwt_secret


def _validate_email(email: str, allowed_domains: tuple[str, ...]) -> str:
    normalized = email.strip().lower()
    if "@" not in normalized or normalized.startswith("@") or normalized.endswith("@"):
        raise ValueError("A valid email address is required")
    if allowed_domains and normalized.rsplit("@", 1)[1] not in allowed_domains:
        raise ValueError("This email domain is not allowed")
    return normalized


def _load_jwt():
    try:
        import jwt
    except ImportError as exc:
        raise RuntimeError(
            "PyJWT is required for authentication. Install the project requirements."
        ) from exc
    return jwt

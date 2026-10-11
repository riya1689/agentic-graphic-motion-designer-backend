"""Authentication domain models independent of HTTP and PostgreSQL."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class UserAccount:
    user_id: str
    email: str
    display_name: str
    status: str
    created_at: datetime
    last_login_at: datetime | None
    must_change_password: bool


@dataclass(frozen=True)
class AuthenticatedUser:
    user: UserAccount
    roles: tuple[str, ...]


@dataclass(frozen=True)
class AuthSession:
    session_id: str
    user_id: str
    refresh_token: str
    expires_at: datetime


@dataclass(frozen=True)
class AuthTokens:
    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int

"""Provider-neutral authentication service interfaces.

HTTP routes and provider adapters depend on these contracts rather than on
PostgreSQL or a particular identity provider.
"""

from __future__ import annotations

from typing import Protocol

from packages.auth.domain.models import (
    AuthenticatedUser,
    AuthTokens,
    UserAccount,
)


class PasswordHasher(Protocol):
    def hash(self, password: str) -> str:
        """Create a one-way password hash."""

    def verify(self, password: str, password_hash: str) -> bool:
        """Verify a password against a stored hash."""


class AuthService(Protocol):
    """Application contract used by future login and admin routes."""

    def create_user(
        self,
        *,
        email: str,
        display_name: str,
        temporary_password: str,
        roles: tuple[str, ...] = ("viewer",),
    ) -> UserAccount:
        """Create an admin-provisioned account."""

    def authenticate(
        self,
        *,
        email: str,
        password: str,
    ) -> AuthenticatedUser | None:
        """Authenticate a user without exposing password details."""

    def issue_tokens(
        self,
        *,
        authenticated_user: AuthenticatedUser,
        device_label: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> AuthTokens:
        """Issue an access token and refresh session."""

    def authenticate_access_token(
        self,
        token: str,
    ) -> AuthenticatedUser | None:
        """Resolve a valid access token to the current user."""

    def refresh_tokens(
        self,
        *,
        refresh_token: str,
        device_label: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> AuthTokens | None:
        """Rotate a refresh session and issue fresh tokens."""

    def revoke_refresh_token(self, *, refresh_token: str) -> None:
        """Revoke a refresh token session."""

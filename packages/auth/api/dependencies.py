"""Reusable FastAPI authentication dependencies."""

from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from packages.auth.application.service_impl import PostgresAuthService
from packages.auth.domain.models import AuthenticatedUser


class AuthDependencies:
    def __init__(self, service: PostgresAuthService) -> None:
        self._service = service
        self._bearer = HTTPBearer(auto_error=False)

    def require_auth(
        self,
        credentials: HTTPAuthorizationCredentials | None = Depends(
            HTTPBearer(auto_error=False)
        ),
    ) -> AuthenticatedUser:
        if credentials is None or credentials.scheme.lower() != "bearer":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required",
                headers={"WWW-Authenticate": "Bearer"},
            )
        try:
            user = self._service.authenticate_access_token(credentials.credentials)
        except RuntimeError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=str(exc),
            ) from exc
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired access token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return user

    def require_role(self, role: str):
        def dependency(
            user: AuthenticatedUser = Depends(self.require_auth),
        ) -> AuthenticatedUser:
            if role not in user.roles:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Role required: {role}",
                )
            return user

        return dependency


def build_auth_dependencies(service: PostgresAuthService) -> AuthDependencies:
    return AuthDependencies(service)

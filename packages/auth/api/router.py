"""Login, session, and admin user-management endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from packages.auth.application.service_impl import PostgresAuthService
from packages.auth.domain.models import AuthenticatedUser, AuthTokens, UserAccount


class LoginRequest(BaseModel):
    email: str
    password: str
    device_label: str | None = Field(default=None, max_length=120)


class RefreshRequest(BaseModel):
    refresh_token: str
    device_label: str | None = Field(default=None, max_length=120)


class LogoutRequest(BaseModel):
    refresh_token: str


class CreateUserRequest(BaseModel):
    email: str
    display_name: str = Field(min_length=1, max_length=160)
    temporary_password: str = Field(min_length=10, max_length=72)
    roles: tuple[str, ...] = ("viewer",)


class UpdateUserStatusRequest(BaseModel):
    status: str


class ResetUserPasswordRequest(BaseModel):
    temporary_password: str = Field(min_length=10, max_length=72)


class UserResponse(BaseModel):
    id: str
    email: str
    display_name: str
    status: str
    roles: tuple[str, ...]
    must_change_password: bool
    created_at: str
    last_login_at: str | None


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int
    user: UserResponse


def create_auth_router(service: PostgresAuthService) -> APIRouter:
    router = APIRouter(prefix="/auth", tags=["Authentication"])
    bearer = HTTPBearer(auto_error=False)

    def current_user_dependency(
        credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    ) -> AuthenticatedUser:
        if credentials is None or credentials.scheme.lower() != "bearer":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required",
                headers={"WWW-Authenticate": "Bearer"},
            )
        try:
            user = service.authenticate_access_token(credentials.credentials)
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

    def admin_dependency(
        user: AuthenticatedUser = Depends(current_user_dependency),
    ) -> AuthenticatedUser:
        if "admin" not in user.roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Administrator role required",
            )
        return user

    @router.post("/login", response_model=TokenResponse)
    async def login(
        payload: LoginRequest,
        request: Request,
    ) -> TokenResponse:
        user = service.authenticate(
            email=payload.email,
            password=payload.password,
        )
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )
        try:
            tokens = service.issue_tokens(
                authenticated_user=user,
                device_label=payload.device_label,
                ip_address=request.client.host if request.client else None,
                user_agent=request.headers.get("user-agent"),
            )
        except RuntimeError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=str(exc),
            ) from exc
        return _token_response(tokens, user)

    @router.post("/refresh", response_model=TokenResponse)
    async def refresh(
        payload: RefreshRequest,
        request: Request,
    ) -> TokenResponse:
        tokens = service.refresh_tokens(
            refresh_token=payload.refresh_token,
            device_label=payload.device_label,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
        if tokens is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired refresh session",
            )
        user = service.authenticate_access_token(tokens.access_token)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Could not create an authenticated session",
            )
        return _token_response(tokens, user)

    @router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
    async def logout(payload: LogoutRequest) -> None:
        service.revoke_refresh_token(refresh_token=payload.refresh_token)

    @router.get("/me", response_model=UserResponse)
    async def me(
        user: AuthenticatedUser = Depends(current_user_dependency),
    ) -> UserResponse:
        return _user_response(user)

    @router.post(
        "/admin/users",
        response_model=UserResponse,
        status_code=status.HTTP_201_CREATED,
    )
    async def create_user(
        payload: CreateUserRequest,
        _: AuthenticatedUser = Depends(admin_dependency),
    ) -> UserResponse:
        try:
            user = service.create_user(
                email=payload.email,
                display_name=payload.display_name,
                temporary_password=payload.temporary_password,
                roles=payload.roles,
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc
        return _user_response(
            AuthenticatedUser(user=user, roles=payload.roles),
        )

    @router.get(
        "/admin/users",
        response_model=list[UserResponse],
    )
    async def list_users(
        _: AuthenticatedUser = Depends(admin_dependency),
    ) -> list[UserResponse]:
        return [
            _user_response(user)
            for user in service.list_users()
        ]

    @router.patch(
        "/admin/users/{user_id}/status",
        response_model=UserResponse,
    )
    async def update_user_status(
        user_id: str,
        payload: UpdateUserStatusRequest,
        _: AuthenticatedUser = Depends(admin_dependency),
    ) -> UserResponse:
        try:
            existing = next(
                (item for item in service.list_users() if item.user.user_id == user_id),
                None,
            )
            user = service.set_user_status(
                user_id=user_id,
                status=payload.status,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return _user_response(
            AuthenticatedUser(user=user, roles=existing.roles if existing else ()),
        )

    @router.post(
        "/admin/users/{user_id}/reset-password",
        response_model=UserResponse,
    )
    async def reset_user_password(
        user_id: str,
        payload: ResetUserPasswordRequest,
        _: AuthenticatedUser = Depends(admin_dependency),
    ) -> UserResponse:
        try:
            existing = next(
                (item for item in service.list_users() if item.user.user_id == user_id),
                None,
            )
            user = service.reset_user_password(
                user_id=user_id,
                temporary_password=payload.temporary_password,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return _user_response(
            AuthenticatedUser(user=user, roles=existing.roles if existing else ()),
        )

    return router


def _token_response(tokens: AuthTokens, user: AuthenticatedUser) -> TokenResponse:
    return TokenResponse(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        token_type=tokens.token_type,
        expires_in=tokens.expires_in,
        user=_user_response(user),
    )


def _user_response(user: AuthenticatedUser) -> UserResponse:
    account: UserAccount = user.user
    return UserResponse(
        id=account.user_id,
        email=account.email,
        display_name=account.display_name,
        status=account.status,
        roles=user.roles,
        must_change_password=account.must_change_password,
        created_at=account.created_at.isoformat(),
        last_login_at=account.last_login_at.isoformat()
        if account.last_login_at
        else None,
    )

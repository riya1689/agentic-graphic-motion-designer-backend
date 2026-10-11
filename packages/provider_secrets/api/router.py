"""Admin-only provider-secret management API."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, SecretStr

from packages.auth.domain.models import AuthenticatedUser
from packages.provider_secrets.application.service_impl import (
    EncryptedProviderSecretService,
)
from packages.provider_secrets.domain.models import ProviderSecretSummary
from packages.provider_secrets.application.runtime import (
    invalidate_runtime_provider_secret,
)


class ProviderSecretResponse(BaseModel):
    provider: str
    secret_name: str
    masked_value: str
    is_active: bool
    version: int
    created_at: str
    updated_at: str


class ProviderSecretUpsertRequest(BaseModel):
    secret_name: str = Field(default="api_key", max_length=100)
    value: SecretStr = Field(min_length=1, max_length=4096)


def create_provider_secrets_router(
    service: EncryptedProviderSecretService,
    *,
    require_admin,
) -> APIRouter:
    router = APIRouter(
        prefix="/admin/provider-secrets",
        tags=["Provider Secrets"],
    )
    admin_dependency = [Depends(require_admin)]

    @router.get(
        "",
        response_model=list[ProviderSecretResponse],
        dependencies=admin_dependency,
    )
    async def list_provider_secrets() -> list[ProviderSecretResponse]:
        return [_response(item) for item in service.list_secrets()]

    @router.put(
        "/{provider}",
        response_model=ProviderSecretResponse,
    )
    async def upsert_provider_secret(
        provider: str,
        payload: ProviderSecretUpsertRequest,
        user: AuthenticatedUser = Depends(require_admin),
    ) -> ProviderSecretResponse:
        try:
            result = service.set_secret(
                provider=provider,
                secret_name=payload.secret_name,
                value=payload.value.get_secret_value(),
                updated_by=user.user.user_id,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=str(exc),
            ) from exc
        invalidate_runtime_provider_secret(provider, payload.secret_name)
        return _response(result)

    @router.delete(
        "/{provider}/{secret_name}",
        status_code=status.HTTP_204_NO_CONTENT,
    )
    async def revoke_provider_secret(
        provider: str,
        secret_name: str,
        user: AuthenticatedUser = Depends(require_admin),
    ) -> None:
        try:
            service.revoke_secret(
                provider=provider,
                secret_name=secret_name,
                updated_by=user.user.user_id,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        invalidate_runtime_provider_secret(provider, secret_name)

    return router


def _response(value: ProviderSecretSummary) -> ProviderSecretResponse:
    return ProviderSecretResponse(
        provider=value.provider,
        secret_name=value.secret_name,
        masked_value=value.masked_value,
        is_active=value.is_active,
        version=value.version,
        created_at=value.created_at.isoformat(),
        updated_at=value.updated_at.isoformat(),
    )

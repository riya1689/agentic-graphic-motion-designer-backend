"""Provider-neutral, read-only model catalog API."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from packages.model_catalog.domain.model import MediaType
from packages.model_catalog.application.runtime import (
    get_catalog_service,
)
from packages.model_catalog.service.catalog import ModelCatalogService

from .schemas import CatalogModelResponse, CatalogModelsResponse


router = APIRouter(
    prefix="/models",
    tags=["Model Catalog"],
)

def _serialize(model) -> CatalogModelResponse:
    return CatalogModelResponse(
        model_id=model.model_id,
        model_name=model.model_name,
        provider=model.provider,
        media_type=model.media_type.value,
        supported_operations=list(model.supported_operations),
        supported_input_types=list(model.supported_input_types),
        supported_output_formats=list(model.supported_output_formats),
        capabilities=list(model.capabilities),
        editable_output_support=model.editable_output_support,
        native_editable_support=model.native_editable_support,
        capability_metadata=dict(model.capability_metadata),
        availability=model.availability.value,
    )


def _api_error(code: str, message: str, status_code: int) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"error": {"code": code, "message": message}},
    )


@router.get("", response_model=CatalogModelsResponse)
def list_catalog_models(
    media_type: Optional[str] = Query(default=None),
    capability: Optional[str] = Query(default=None),
    provider: Optional[str] = Query(default=None),
    service: ModelCatalogService = Depends(get_catalog_service),
) -> CatalogModelsResponse:
    if media_type is not None:
        try:
            MediaType(media_type.strip().lower())
        except ValueError as exc:
            raise _api_error(
                "INVALID_MEDIA_TYPE",
                "media_type must be 'image' or 'video'.",
                400,
            ) from exc

    if capability is not None and not capability.strip():
        raise _api_error(
            "INVALID_CAPABILITY",
            "capability must not be blank.",
            400,
        )

    if provider is not None and not provider.strip():
        raise _api_error(
            "INVALID_PROVIDER",
            "provider must not be blank.",
            400,
        )

    try:
        models = service.list_models(
            media_type=media_type.strip().lower() if media_type else None,
            capability=capability.strip() if capability else None,
            provider=provider.strip() if provider else None,
        )
    except ValueError as exc:
        raise _api_error("INVALID_QUERY", str(exc), 400) from exc
    except Exception as exc:
        raise _api_error(
            "CATALOG_UNAVAILABLE",
            "The model catalog is currently unavailable.",
            503,
        ) from exc

    serialized = [_serialize(model) for model in models]
    return CatalogModelsResponse(models=serialized, count=len(serialized))


@router.get("/{model_id}", response_model=CatalogModelResponse)
def get_catalog_model(
    model_id: str,
    provider: Optional[str] = Query(default=None),
    service: ModelCatalogService = Depends(get_catalog_service),
) -> CatalogModelResponse:
    if not model_id.strip():
        raise _api_error(
            "INVALID_MODEL_ID",
            "model_id must not be blank.",
            400,
        )
    if provider is not None and not provider.strip():
        raise _api_error(
            "INVALID_PROVIDER",
            "provider must not be blank.",
            400,
        )

    try:
        model = service.get_model(
            model_id.strip(),
            provider=provider.strip() if provider else None,
        )
    except Exception as exc:
        raise _api_error(
            "CATALOG_UNAVAILABLE",
            "The model catalog is currently unavailable.",
            503,
        ) from exc

    if model is None:
        raise _api_error(
            "MODEL_NOT_FOUND",
            "The requested model was not found.",
            404,
        )

    return _serialize(model)

"""Read-only model catalog service with lightweight in-memory caching."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, List, Optional

from packages.model_catalog.domain.model import (
    CatalogModel,
    MediaType,
)
from packages.model_catalog.ports import ModelDiscoveryAdapter


@dataclass(frozen=True)
class CatalogRefreshResult:
    accepted_count: int
    rejected_count: int
    duplicate_count: int
    errors: List[str] = field(default_factory=list)
    used_cached_catalog: bool = False


class ModelCatalogService:
    """Expose catalog facts; it never ranks or selects models."""

    def __init__(
        self,
        adapter: Optional[ModelDiscoveryAdapter] = None,
        initial_models: Optional[Iterable[CatalogModel]] = None,
    ) -> None:
        self._adapter = adapter
        self._models: List[CatalogModel] = list(initial_models or [])
        self.last_refresh: Optional[CatalogRefreshResult] = None

    def list_models(
        self,
        *,
        media_type: MediaType | str | None = None,
        capability: str | None = None,
        provider: str | None = None,
    ) -> List[CatalogModel]:
        models = list(self._models)
        if media_type is not None:
            models = [
                model
                for model in models
                if model.media_type == MediaType(media_type)
            ]
        if capability is not None:
            normalized = capability.strip().lower()
            models = [
                model
                for model in models
                if normalized in model.capabilities
                or normalized in model.supported_operations
                or normalized in model.supported_input_types
                or normalized in model.supported_output_formats
            ]
        if provider is not None:
            normalized_provider = provider.strip().lower()
            models = [
                model
                for model in models
                if model.provider.lower() == normalized_provider
            ]
        return models

    def set_adapter(self, adapter: ModelDiscoveryAdapter) -> None:
        """Attach a discovery adapter during application composition."""
        self._adapter = adapter

    def get_model(
        self,
        model_id: str,
        *,
        provider: str | None = None,
    ) -> Optional[CatalogModel]:
        return next(
            (
                model
                for model in self._models
                if model.model_id == model_id
                and (
                    provider is None
                    or model.provider.lower() == provider.strip().lower()
                )
            ),
            None,
        )

    def list_by_media_type(self, media_type: MediaType | str) -> List[CatalogModel]:
        return self.list_models(media_type=media_type)

    def list_by_capability(self, capability: str) -> List[CatalogModel]:
        return self.list_models(capability=capability)

    def refresh(self) -> CatalogRefreshResult:
        if self._adapter is None:
            result = CatalogRefreshResult(
                accepted_count=len(self._models),
                rejected_count=0,
                duplicate_count=0,
                errors=["No discovery adapter configured."],
                used_cached_catalog=bool(self._models),
            )
            self.last_refresh = result
            return result

        try:
            raw_models = self._adapter.discover()
        except Exception as exc:
            result = CatalogRefreshResult(
                accepted_count=len(self._models),
                rejected_count=0,
                duplicate_count=0,
                errors=[f"Provider discovery failed: {exc}"],
                used_cached_catalog=bool(self._models),
            )
            self.last_refresh = result
            return result

        normalized: List[CatalogModel] = []
        errors: List[str] = []
        seen = set()
        duplicates = 0

        for index, raw in enumerate(raw_models or []):
            try:
                model = (
                    raw
                    if isinstance(raw, CatalogModel)
                    else CatalogModel.model_validate(raw)
                )
            except Exception as exc:
                errors.append(f"Model {index} rejected: {exc}")
                continue

            key = (model.provider, model.model_id)
            if key in seen:
                duplicates += 1
                continue
            seen.add(key)
            normalized.append(model)

        # An empty successful discovery is a valid empty catalog. A failed
        # discovery is handled above and preserves the previous cache.
        self._models = normalized
        result = CatalogRefreshResult(
            accepted_count=len(normalized),
            rejected_count=len(errors),
            duplicate_count=duplicates,
            errors=errors,
            used_cached_catalog=False,
        )
        self.last_refresh = result
        return result

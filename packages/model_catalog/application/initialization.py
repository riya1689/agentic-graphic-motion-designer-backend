"""Controlled provider discovery during application composition/startup."""

from __future__ import annotations

import logging
from typing import Optional

from packages.model_catalog.ports import ModelDiscoveryAdapter
from packages.model_catalog.service.catalog import (
    CatalogRefreshResult,
    ModelCatalogService,
)


logger = logging.getLogger(__name__)


class CatalogInitializationService:
    """Attach a provider adapter and perform one controlled refresh."""

    def __init__(
        self,
        catalog_service: ModelCatalogService,
        adapter: Optional[ModelDiscoveryAdapter] = None,
    ) -> None:
        self._catalog_service = catalog_service
        self._adapter = adapter

    def initialize(self) -> CatalogRefreshResult:
        self._catalog_service.set_adapter(self._adapter)
        result = self._catalog_service.refresh()

        if result.errors:
            logger.warning(
                "Model catalog initialization completed with %d accepted, %d rejected, and %d error(s).",
                result.accepted_count,
                result.rejected_count,
                len(result.errors),
            )
        else:
            logger.info(
                "Model catalog initialized with %d models.",
                result.accepted_count,
            )

        return result


def initialize_model_catalog(
    catalog_service: ModelCatalogService,
    adapter: Optional[ModelDiscoveryAdapter] = None,
) -> CatalogRefreshResult:
    """Composition-root helper used by application startup and tests."""
    return CatalogInitializationService(
        catalog_service=catalog_service,
        adapter=adapter,
    ).initialize()

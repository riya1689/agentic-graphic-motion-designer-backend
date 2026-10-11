"""Provider-neutral runtime service instance used by API dependency injection."""

from packages.model_catalog.service.catalog import ModelCatalogService


catalog_service = ModelCatalogService()


def get_catalog_service() -> ModelCatalogService:
    return catalog_service

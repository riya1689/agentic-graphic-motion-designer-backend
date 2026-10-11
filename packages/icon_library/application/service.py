"""Use cases for the Icon Library, independent of persistence and transport."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from typing import Sequence

from packages.icon_library.domain.models import IconRecord, IconSearchQuery
from packages.icon_library.ports import IconAssetStore, IconNotFoundError, IconRepository


class IconLibraryService:
    """Application boundary used later by API routes and design capabilities."""

    def __init__(self, repository: IconRepository, asset_store: IconAssetStore) -> None:
        self._repository = repository
        self._asset_store = asset_store

    def add(self, icon: IconRecord, *, svg_content: bytes) -> IconRecord:
        if icon.mime_type != "image/svg+xml":
            raise ValueError("Icon Library accepts SVG assets only.")
        if not svg_content:
            raise ValueError("SVG content cannot be empty.")
        asset_ref = self._asset_store.put_svg(icon_id=icon.icon_id, content=svg_content)
        return self._repository.create(replace(icon, asset_ref=asset_ref))

    def get(self, icon_id: str) -> IconRecord:
        icon = self._repository.get(icon_id)
        if icon is None:
            raise IconNotFoundError(f"Icon not found: {icon_id}")
        return icon

    def search(self, query: IconSearchQuery | None = None) -> Sequence[IconRecord]:
        return self._repository.search(query or IconSearchQuery())

    def update(self, icon: IconRecord) -> IconRecord:
        existing = self.get(icon.icon_id)
        return self._repository.update(
            replace(icon, created_at=existing.created_at, updated_at=datetime.now(timezone.utc))
        )

    def delete(self, icon_id: str) -> None:
        self.get(icon_id)
        self._repository.soft_delete(icon_id)

    def download_svg(self, icon_id: str) -> bytes:
        icon = self.get(icon_id)
        return self._asset_store.get(icon.asset_ref)

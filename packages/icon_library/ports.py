"""Ports for Icon Library adapters.

Concrete PostgreSQL, local-cache, HTTP, and test adapters will implement these
protocols in later phases. The application layer depends only on these ports.
"""

from __future__ import annotations

from typing import Protocol, Sequence

from packages.icon_library.domain.models import IconRecord, IconSearchQuery


class IconRepository(Protocol):
    """Persistence boundary for icon metadata and SVG asset references."""

    def create(self, icon: IconRecord) -> IconRecord:
        ...

    def get(self, icon_id: str, *, include_deleted: bool = False) -> IconRecord | None:
        ...

    def search(self, query: IconSearchQuery) -> Sequence[IconRecord]:
        ...

    def update(self, icon: IconRecord) -> IconRecord:
        ...

    def soft_delete(self, icon_id: str) -> None:
        ...


class IconAssetStore(Protocol):
    """Boundary for retrieving and storing validated SVG content."""

    def put_svg(self, *, icon_id: str, content: bytes) -> str:
        """
        Persist SVG bytes and return an opaque asset reference.

        The reference may point to PostgreSQL BYTEA-backed content or a local
        content-addressed cache. Callers must not interpret its format.
        """
        ...

    def get(self, asset_ref: str) -> bytes:
        ...


class IconLibraryError(Exception):
    """Base error for application-level Icon Library failures."""


class IconNotFoundError(IconLibraryError):
    """Raised when a requested icon does not exist."""

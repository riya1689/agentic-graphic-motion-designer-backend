"""Provider-independent Icon Library domain models.

These models deliberately do not know about PostgreSQL, HTTP, the frontend,
or any AI provider. They are the stable boundary shared by future adapters.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any


class IconSource(StrEnum):
    BUILT_IN = "built_in"
    USER_UPLOADED = "user_uploaded"
    AI_GENERATED = "ai_generated"


@dataclass(frozen=True)
class IconRecord:
    """Metadata for one library icon.

    ``asset_ref`` is intentionally opaque. A PostgreSQL adapter may resolve it
    to BYTEA content, while another adapter may resolve it to content-addressed
    local storage without changing this domain model.
    """

    icon_id: str
    name: str
    source: IconSource
    asset_ref: str
    category: str | None = None
    tags: tuple[str, ...] = ()
    style: str | None = None
    description: str | None = None
    mime_type: str = "image/svg+xml"
    version: int = 1
    is_deleted: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class IconSearchQuery:
    """Provider-neutral search criteria for library lookup."""

    text: str = ""
    category: str | None = None
    source: IconSource | None = None
    style: str | None = None
    tags: tuple[str, ...] = ()
    include_deleted: bool = False
    limit: int = 50
    offset: int = 0

    def __post_init__(self) -> None:
        if self.limit < 1 or self.limit > 200:
            raise ValueError("Icon search limit must be between 1 and 200.")
        if self.offset < 0:
            raise ValueError("Icon search offset cannot be negative.")

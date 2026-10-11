"""Provider-neutral results returned by the model router."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from packages.model_catalog.domain.model import CatalogModel


class RoutingSource(str, Enum):
    USER_SELECTED = "user_selected"
    CAPABILITY_MATCH = "capability_match"
    SYSTEM_DEFAULT = "system_default"


@dataclass(frozen=True)
class RoutingError:
    code: str
    message: str


@dataclass(frozen=True)
class RoutingResult:
    request_id: str
    selected_model: Optional[CatalogModel] = None
    routing_reason: Optional[str] = None
    routing_source: Optional[RoutingSource] = None
    error: Optional[RoutingError] = None

    @property
    def success(self) -> bool:
        return self.selected_model is not None and self.error is None

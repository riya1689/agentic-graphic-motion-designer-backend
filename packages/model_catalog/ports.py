"""Ports used by the catalog service."""

from __future__ import annotations

from typing import Any, Dict, List, Protocol


class ModelDiscoveryAdapter(Protocol):
    """Provider boundary returning normalized model records."""

    provider_id: str

    def discover(self) -> List[Any]:
        ...

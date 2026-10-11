"""Typed provider-neutral execution contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from packages.model_catalog.domain.model import CatalogModel, MediaType
from packages.request_contract.domain.schema import AssetReference, NormalizedRequest


class ExecutionStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"


@dataclass(frozen=True)
class ExecutionError:
    code: str
    message: str


@dataclass(frozen=True)
class OutputAsset:
    uri: str
    format: str
    editable: bool = False
    native_editable: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ExecutionRequest:
    request_id: str
    normalized_request: NormalizedRequest
    selected_model: CatalogModel
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProviderExecutionRequest:
    """Minimal provider-neutral input accepted by provider adapters."""

    request_id: str
    model_id: str
    media_type: MediaType
    prompt: str
    output_format: str
    input_assets: List[AssetReference] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProviderExecutionResponse:
    """Provider adapter output after translating provider-specific data."""

    provider: str
    model_id: str
    output_assets: List[OutputAsset]
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ExecutionResult:
    request_id: str
    status: ExecutionStatus
    provider: Optional[str] = None
    model_id: Optional[str] = None
    output_assets: List[OutputAsset] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    error: Optional[ExecutionError] = None

    @property
    def success(self) -> bool:
        return self.status == ExecutionStatus.SUCCESS and self.error is None

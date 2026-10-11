"""Provider-neutral normalized model representation."""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List

from pydantic import BaseModel, ConfigDict, Field, field_validator


class MediaType(str, Enum):
    IMAGE = "image"
    VIDEO = "video"


class ModelAvailability(str, Enum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"


class CatalogModel(BaseModel):
    """Capabilities reported by a provider, without routing policy."""

    model_config = ConfigDict(extra="forbid")

    model_id: str = Field(min_length=1)
    model_name: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    media_type: MediaType
    supported_operations: List[str] = Field(default_factory=list)
    supported_input_types: List[str] = Field(default_factory=list)
    supported_output_formats: List[str] = Field(default_factory=list)
    capabilities: List[str] = Field(default_factory=list)

    # These are explicit provider/catalog claims only. They are not inferred
    # from conversion utilities or from a file extension.
    editable_output_support: bool = False
    native_editable_support: bool = False

    capability_metadata: Dict[str, Any] = Field(default_factory=dict)
    availability: ModelAvailability = ModelAvailability.UNKNOWN

    @field_validator(
        "model_id",
        "model_name",
        "provider",
        mode="before",
    )
    @classmethod
    def normalize_required_text(cls, value: Any) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("required model text must be non-empty")
        return value.strip()

    @field_validator(
        "supported_operations",
        "supported_input_types",
        "supported_output_formats",
        "capabilities",
        mode="before",
    )
    @classmethod
    def normalize_string_lists(cls, value: Any) -> List[str]:
        if value is None:
            return []
        if isinstance(value, str):
            value = [value]
        if not isinstance(value, (list, tuple, set)):
            raise ValueError("model capability fields must be lists")
        return sorted({str(item).strip().lower() for item in value if str(item).strip()})

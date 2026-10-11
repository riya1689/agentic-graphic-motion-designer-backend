"""Stable domain contract between understanding and validation.

This module contains no provider, model-catalog, routing, or executor logic.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CreativeType(str, Enum):
    IMAGE = "image"
    MOTION = "motion"


class SizeSpec(BaseModel):
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    unit: str = "px"

    @field_validator("unit")
    @classmethod
    def normalize_unit(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not normalized:
            raise ValueError("size unit must not be empty")
        return normalized


class OutputRequirement(BaseModel):
    """Requested media plus the capability implied by that output."""

    media_type: CreativeType
    format: str
    editable_required: bool = False
    native_editable_required: bool = False

    @field_validator("format")
    @classmethod
    def normalize_format(cls, value: str) -> str:
        normalized = value.strip().lower().lstrip(".")
        if not normalized:
            raise ValueError("output format must not be empty")
        return normalized


class AssetReference(BaseModel):
    kind: str = "reference"
    uri: Optional[str] = None
    description: Optional[str] = None
    required: bool = True


class NormalizedRequest(BaseModel):
    """Provider-neutral request consumed by future workflow components."""

    model_config = ConfigDict(extra="forbid")

    request_id: str = Field(min_length=1)
    creative_type: CreativeType
    context_prompt: str = Field(min_length=1)
    output: OutputRequirement

    # User/domain fields. They are optional because the understanding step may
    # not be able to infer them from every request.
    design_type: Optional[str] = None
    purpose: Optional[str] = None
    size: Optional[SizeSpec] = None
    brand: Optional[str] = None
    colors: List[str] = Field(default_factory=list)
    text: List[str] = Field(default_factory=list)
    style: Optional[str] = None
    audience: Optional[str] = None
    reference_assets: List[AssetReference] = Field(default_factory=list)
    input_assets: List[AssetReference] = Field(default_factory=list)
    quality_preferences: Dict[str, Any] = Field(default_factory=dict)
    additional_requirements: Dict[str, Any] = Field(default_factory=dict)

    # Explicit user selection is preserved. None means no explicit selection;
    # an invalid provider/model identifier is intentionally not resolved here.
    selected_model: Optional[str] = None

    @field_validator("request_id", "context_prompt")
    @classmethod
    def reject_blank_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("value must not be blank")
        return normalized

    @field_validator("selected_model")
    @classmethod
    def normalize_selected_model(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("selected_model must be null or a non-empty identifier")
        return normalized

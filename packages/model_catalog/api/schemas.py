"""Stable API representations for normalized catalog data."""

from __future__ import annotations

from typing import Any, Dict, List

from pydantic import BaseModel


class CatalogModelResponse(BaseModel):
    model_id: str
    model_name: str
    provider: str
    media_type: str
    supported_operations: List[str]
    supported_input_types: List[str]
    supported_output_formats: List[str]
    capabilities: List[str]
    editable_output_support: bool
    native_editable_support: bool
    capability_metadata: Dict[str, Any]
    availability: str


class CatalogModelsResponse(BaseModel):
    models: List[CatalogModelResponse]
    count: int

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, model_validator


# ============================================================
# DOCUMENT
# ============================================================
# Generic canvas/document definition.
# No Illustrator / Photoshop dependency.
# ============================================================

class PlannerGraphicDocumentSpec(BaseModel):

    width: int

    height: int

    unit: str = "px"

    color_mode: str = "RGB"

    background_color: Optional[str] = None


# ============================================================
# COLOR
# ============================================================
# Named palette color.
# List-based structure avoids arbitrary Dict schema issues.
# ============================================================

class PlannerGraphicColorSpec(BaseModel):

    name: str

    value: str


# ============================================================
# TRANSFORM / PLACEMENT
# ============================================================
# Generic spatial information.
# Supports semantic anchor and exact coordinates.
# ============================================================

class PlannerGraphicPlacementSpec(BaseModel):

    anchor: Optional[str] = None

    x: Optional[float] = None

    y: Optional[float] = None

    width: Optional[float] = None

    height: Optional[float] = None

    rotation: float = 0.0

    scale_x: float = 1.0

    scale_y: float = 1.0


# ============================================================
# TYPOGRAPHY
# ============================================================
# Text-specific styling kept separate from generic appearance.
# ============================================================

class PlannerGraphicTypographySpec(BaseModel):

    font_family: Optional[str] = None

    font_size: Optional[float] = None

    font_weight: Optional[str] = None

    text_align: Optional[str] = None

    line_height: Optional[float] = None

    letter_spacing: Optional[float] = None


# ============================================================
# APPEARANCE
# ============================================================
# Generic visual appearance.
# No renderer-specific commands.
# ============================================================

class PlannerGraphicStyleSpec(BaseModel):

    # A gradient remains renderer-independent: the SVG renderer owns the
    # serialization, while the plan owns only semantic stops.
    fill: Optional[str | Dict[str, Any]] = None

    stroke: Optional[str] = None

    stroke_width: Optional[float] = None

    opacity: float = 1.0

    effects: List[str] = Field(
        default_factory=list
    )


# ============================================================
# GEOMETRY
# ============================================================
# Optional generic geometric information.
# ============================================================

class PlannerGraphicGeometrySpec(BaseModel):

    shape: Optional[str] = None

    points: List[float] = Field(
        default_factory=list
    )

    corner_radius: Optional[float] = None


# ============================================================
# ELEMENT
# ============================================================
# Generic scene element.
#
# Examples:
# text
# rectangle
# ellipse
# line
# polygon
# path
# image
# group
# symbol
# custom
#
# Complex designs should be decomposed into multiple elements.
# ============================================================

class PlannerGraphicElementSpec(BaseModel):

    id: str

    type: str

    name: Optional[str] = None

    content: Optional[str] = None

    asset_id: Optional[str] = None

    placement: PlannerGraphicPlacementSpec = Field(
        default_factory=PlannerGraphicPlacementSpec
    )

    style: PlannerGraphicStyleSpec = Field(
        default_factory=PlannerGraphicStyleSpec
    )

    typography: PlannerGraphicTypographySpec = Field(
        default_factory=PlannerGraphicTypographySpec
    )

    geometry: PlannerGraphicGeometrySpec = Field(
        default_factory=PlannerGraphicGeometrySpec
    )

    children: List[
        "PlannerGraphicElementSpec"
    ] = Field(
        default_factory=list
    )

    @model_validator(mode="before")
    @classmethod
    def replace_null_nested_objects(cls, value):
        """Turn LLM nulls into the declared empty-object defaults."""
        if not isinstance(value, dict):
            return value
        normalized = dict(value)
        for field_name in ("placement", "style", "typography", "geometry"):
            if normalized.get(field_name) is None:
                normalized[field_name] = {}
        if normalized.get("children") is None:
            normalized["children"] = []
        return normalized


# ============================================================
# LAYER
# ============================================================
# Generic layer/group container.
# ============================================================

class PlannerGraphicLayerSpec(BaseModel):

    id: str

    name: str

    visible: bool = True

    locked: bool = False

    elements: List[
        PlannerGraphicElementSpec
    ] = Field(
        default_factory=list
    )

    @model_validator(mode="before")
    @classmethod
    def replace_null_elements(cls, value):
        if not isinstance(value, dict):
            return value
        normalized = dict(value)
        if normalized.get("elements") is None:
            normalized["elements"] = []
        return normalized


# ============================================================
# ASSET
# ============================================================
# Generic external/local asset reference.
# ============================================================

class PlannerGraphicAssetSpec(BaseModel):

    id: str

    type: str

    name: Optional[str] = None

    path: Optional[str] = None

    description: Optional[str] = None

    required: bool = True

    @model_validator(mode="before")
    @classmethod
    def normalize_request_asset_shape(cls, value):
        """Accept request-asset aliases while preserving renderer contract."""
        if not isinstance(value, dict):
            return value
        normalized = dict(value)
        normalized.setdefault("type", normalized.get("kind") or "image")
        normalized.setdefault("id", normalized.get("name") or "uploaded-asset")
        normalized.setdefault("description", normalized.get("description") or normalized.get("uri"))
        normalized.setdefault("path", normalized.get("uri"))
        return normalized


# ============================================================
# GRAPHIC EXECUTION SPEC
# ============================================================
# Planner-side structured graphic plan.
#
# IMPORTANT:
# - Tool-neutral
# - No Illustrator commands
# - No Photoshop commands
# - No Manager dependency
# - No Graphic Agent dependency
# - No hardcoded poster/image template
# ============================================================

class PlannerGraphicExecutionSpec(BaseModel):

    version: str = "1.0"

    document: PlannerGraphicDocumentSpec

    palette: List[
        PlannerGraphicColorSpec
    ] = Field(
        default_factory=list
    )

    assets: List[
        PlannerGraphicAssetSpec
    ] = Field(
        default_factory=list
    )

    layers: List[
        PlannerGraphicLayerSpec
    ] = Field(
        default_factory=list
    )

    @model_validator(mode="before")
    @classmethod
    def replace_null_collections(cls, value):
        if not isinstance(value, dict):
            return value
        normalized = dict(value)
        for field_name in ("palette", "assets", "layers"):
            if normalized.get(field_name) is None:
                normalized[field_name] = []
        if normalized.get("document") is None:
            normalized["document"] = {}
        return normalized


PlannerGraphicElementSpec.model_rebuild()

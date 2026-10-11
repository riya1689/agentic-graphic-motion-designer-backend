"""Renderer-independent spatial layout contracts."""

from __future__ import annotations

from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field, model_validator


class LayoutPoint(BaseModel):
    x: float = Field(ge=0.0, le=1.0)
    y: float = Field(ge=0.0, le=1.0)


class NormalizedBounds(BaseModel):
    x: float = Field(ge=0.0, le=1.0)
    y: float = Field(ge=0.0, le=1.0)
    width: float = Field(gt=0.0, le=1.0)
    height: float = Field(gt=0.0, le=1.0)

    @model_validator(mode="after")
    def stay_on_canvas(self):
        if self.x + self.width > 1.0 or self.y + self.height > 1.0:
            raise ValueError("normalized bounds must stay within the canvas")
        return self


class LayoutInsets(BaseModel):
    top: float = Field(ge=0.0, le=0.5)
    right: float = Field(ge=0.0, le=0.5)
    bottom: float = Field(ge=0.0, le=0.5)
    left: float = Field(ge=0.0, le=0.5)


class LayoutCanvas(BaseModel):
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    aspect_ratio: float = Field(gt=0.0)
    orientation: str
    margins: LayoutInsets
    safe_area: NormalizedBounds
    background: Optional[str] = None


class LayoutGrid(BaseModel):
    columns: Optional[int] = Field(default=None, gt=0)
    rows: Optional[int] = Field(default=None, gt=0)
    gutters: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    outer_margin: Optional[float] = Field(default=None, ge=0.0, le=0.5)
    inner_padding: Optional[float] = Field(default=None, ge=0.0, le=0.5)
    baseline_alignment: Optional[str] = None


class LayoutRegion(BaseModel):
    id: str = Field(min_length=1)
    purpose: str = Field(min_length=1)
    bounds: NormalizedBounds
    priority: int = Field(default=3, ge=1, le=5)
    alignment: Optional[str] = None
    spacing: Optional[str] = None
    parent_id: Optional[str] = None
    children: List[str] = Field(default_factory=list)
    allow_overlap: bool = False


class LayoutElementType(str, Enum):
    TEXT = "text"
    IMAGE = "image"
    LOGO = "logo"
    ICON = "icon"
    SHAPE = "shape"
    ILLUSTRATION = "illustration"
    GROUP = "group"
    DIVIDER = "divider"
    BADGE = "badge"
    CHART = "chart"
    DIAGRAM = "diagram"
    DECORATIVE = "decorative"


class SizingStrategy(str, Enum):
    FIXED = "fixed"
    RELATIVE = "relative"
    FILL = "fill"
    HUG_CONTENT = "hug_content"
    MIN_MAX = "min_max"
    ASPECT_LOCKED = "aspect_locked"
    PRIORITY_BASED = "priority_based"


class LayoutElement(BaseModel):
    id: str = Field(min_length=1)
    type: LayoutElementType
    role: str = Field(min_length=1)
    content_reference: Optional[str] = None
    region_reference: str = Field(min_length=1)
    bounds: NormalizedBounds
    alignment: Optional[str] = None
    alignment_reference: Optional[str] = None
    z_index: int = 0
    visibility: bool = True
    constraints: List[str] = Field(default_factory=list)
    sizing: SizingStrategy = SizingStrategy.RELATIVE
    fit: Optional[str] = None
    allow_overlap: bool = False


class LayoutRelationship(BaseModel):
    source_id: str = Field(min_length=1)
    relationship: str = Field(min_length=1)
    target_id: str = Field(min_length=1)
    required: bool = True


class LayoutSpecification(BaseModel):
    """Spatial intent independent from SVG, providers, and file storage."""

    canvas: LayoutCanvas
    composition_strategy: Optional[str] = None
    grid: LayoutGrid = Field(default_factory=LayoutGrid)
    regions: List[LayoutRegion] = Field(default_factory=list)
    elements: List[LayoutElement] = Field(default_factory=list)
    relationships: List[LayoutRelationship] = Field(default_factory=list)
    focal_region: Optional[str] = None
    reading_path: Optional[str] = None
    spacing_tokens: Dict[str, str] = Field(default_factory=dict)
    constraints: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_references(self):
        region_ids = {region.id for region in self.regions}
        element_ids = {element.id for element in self.elements}
        if self.focal_region and self.focal_region not in region_ids:
            raise ValueError("focal_region must reference an existing region")
        for element in self.elements:
            if element.region_reference not in region_ids:
                raise ValueError(f"element references unknown region: {element.region_reference}")
        for relationship in self.relationships:
            if relationship.source_id not in element_ids or relationship.target_id not in element_ids:
                raise ValueError("layout relationship references an unknown element")
        return self


class LayoutValidationIssue(BaseModel):
    code: str
    message: str
    severity: str = "error"

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


# ============================================================
# DOCUMENT SPEC
# ============================================================

class GraphicDocumentSpec(BaseModel):
    """
    Tool-neutral document/canvas definition.
    """

    width: int = Field(
        ...,
        gt=0,
    )

    height: int = Field(
        ...,
        gt=0,
    )

    unit: Literal[
        "px",
        "pt",
        "mm",
        "cm",
        "in",
    ] = "px"

    color_mode: Literal[
        "RGB",
        "CMYK",
    ] = "RGB"

    background_color: Optional[str] = None


# ============================================================
# PLACEMENT
# ============================================================

class GraphicPlacementSpec(BaseModel):
    """
    Element placement.

    We support both:
        semantic placement
        exact coordinates

    Semantic placement:
        top_center
        center
        bottom_left

    Exact:
        x / y
    """

    anchor: Optional[Literal[
        "top_left",
        "top_center",
        "top_right",
        "center_left",
        "center",
        "center_right",
        "bottom_left",
        "bottom_center",
        "bottom_right",
    ]] = None

    x: Optional[float] = None

    y: Optional[float] = None

    width: Optional[float] = None

    height: Optional[float] = None

    rotation: float = 0.0


# ============================================================
# STYLE
# ============================================================

class GraphicStyleSpec(BaseModel):
    """
    Generic visual styling.

    Illustrator/Photoshop-specific implementation
    এখানে থাকবে না।
    """

    fill: Optional[str] = None

    stroke: Optional[str] = None

    stroke_width: Optional[float] = None

    opacity: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
    )

    font_family: Optional[str] = None

    font_size: Optional[float] = None

    font_weight: Optional[Literal[
        "light",
        "regular",
        "medium",
        "semibold",
        "bold",
        "black",
    ]] = None

    text_align: Optional[Literal[
        "left",
        "center",
        "right",
    ]] = None

    gradient: Optional[Dict[str, Any]] = None

    effects: List[str] = Field(
        default_factory=list
    )


# ============================================================
# GRAPHIC ELEMENT
# ============================================================

class GraphicElementSpec(BaseModel):
    """
    One logical design element.

    IMPORTANT:
    এটি Illustrator object নয়।
    এটি Photoshop layer-ও নয়।

    এটি generic visual intent.
    """

    id: str

    type: Literal[
        "background",
        "text",
        "rectangle",
        "ellipse",
        "line",
        "polygon",
        "path",
        "image",
        "logo",
        "icon",
        "group",
        "decorative_vector",
        "product_illustration",
        "custom",
    ]

    name: Optional[str] = None

    content: Optional[str] = None

    subject: Optional[str] = None

    placement: GraphicPlacementSpec = Field(
        default_factory=GraphicPlacementSpec
    )

    style: GraphicStyleSpec = Field(
        default_factory=GraphicStyleSpec
    )

    children: List["GraphicElementSpec"] = Field(
        default_factory=list
    )

    metadata: Dict[str, Any] = Field(
        default_factory=dict
    )


# ============================================================
# LAYER
# ============================================================

class GraphicLayerSpec(BaseModel):
    """
    Tool-neutral design layer.
    """

    id: str

    name: str

    visible: bool = True

    locked: bool = False

    elements: List[GraphicElementSpec] = Field(
        default_factory=list
    )


# ============================================================
# PALETTE
# ============================================================

class GraphicPaletteSpec(BaseModel):
    """
    Optional named color palette.
    """

    colors: Dict[str, str] = Field(
        default_factory=dict
    )


# ============================================================
# ASSET REFERENCE
# ============================================================

class GraphicAssetSpec(BaseModel):
    """
    Asset that renderer may need.

    Example:
        logo
        product image
        reference image
        icon
    """

    id: str

    type: Literal[
        "image",
        "logo",
        "icon",
        "reference",
        "other",
    ]

    name: Optional[str] = None

    path: Optional[str] = None

    description: Optional[str] = None

    required: bool = True


# ============================================================
# GRAPHIC EXECUTION SPEC
# ============================================================

class GraphicExecutionSpec(BaseModel):
    """
    Normalized tool-neutral design execution contract.

    Planner intent
        ↓
    GraphicExecutionSpec
        ↓
    Illustrator / Photoshop / Canva adapter
    """

    version: str = "1.0"

    document: GraphicDocumentSpec

    palette: GraphicPaletteSpec = Field(
        default_factory=GraphicPaletteSpec
    )

    assets: List[GraphicAssetSpec] = Field(
        default_factory=list
    )

    layers: List[GraphicLayerSpec] = Field(
        default_factory=list
    )

    global_style: GraphicStyleSpec = Field(
        default_factory=GraphicStyleSpec
    )

    metadata: Dict[str, Any] = Field(
        default_factory=dict
    )


GraphicElementSpec.model_rebuild()
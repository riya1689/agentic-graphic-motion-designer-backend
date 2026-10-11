"""Design-intelligence domain models."""

from .specification import (
    ArtDirection,
    ColorSystem,
    CompositionIntent,
    ContentPriority,
    DesignBrief,
    DesignContent,
    DesignSpecification,
    HierarchyItem,
    RequirementCoverage,
    TypographyIntent,
)
from .layout import (
    LayoutCanvas,
    LayoutElement,
    LayoutElementType,
    LayoutGrid,
    LayoutRegion,
    LayoutRelationship,
    LayoutSpecification,
    NormalizedBounds,
)

__all__ = [
    "ArtDirection",
    "ColorSystem",
    "CompositionIntent",
    "ContentPriority",
    "DesignBrief",
    "DesignContent",
    "DesignSpecification",
    "HierarchyItem",
    "RequirementCoverage",
    "TypographyIntent",
    "LayoutCanvas",
    "LayoutElement",
    "LayoutElementType",
    "LayoutGrid",
    "LayoutRegion",
    "LayoutRelationship",
    "LayoutSpecification",
    "NormalizedBounds",
]

"""Provider-neutral visual inspection contracts."""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class InspectionSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class InspectionConfidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class RequirementInspectionStatus(str, Enum):
    SATISFIED = "satisfied"
    NOT_SATISFIED = "not_satisfied"
    UNCERTAIN = "uncertain"


class InspectionCategory(str, Enum):
    GEOMETRY = "geometry"
    COMPOSITION = "composition"
    HIERARCHY = "hierarchy"
    READABILITY = "readability"
    SPACING = "spacing"
    COLOR = "color"
    ASSET_VISIBILITY = "asset_visibility"
    REQUIREMENT_VISIBILITY = "requirement_visibility"
    RENDERING = "rendering"


class VisualInspectionIssue(BaseModel):
    id: Optional[str] = None
    severity: InspectionSeverity
    category: InspectionCategory
    message: str = Field(min_length=1)
    affected_element: Optional[str] = None
    affected_region: Optional[str] = None
    evidence: Optional[str] = None
    requirement_reference: Optional[str] = None
    confidence: InspectionConfidence = InspectionConfidence.HIGH
    source: str = "deterministic"


class RequirementInspection(BaseModel):
    requirement_reference: str = Field(min_length=1)
    status: RequirementInspectionStatus
    evidence: str = Field(min_length=1)
    confidence: InspectionConfidence = InspectionConfidence.HIGH
    source: str = "deterministic"


class VisualCritiqueRequest(BaseModel):
    """Provider-neutral input to a visual critique adapter."""

    preview: "PreviewArtifact"
    design_brief: Dict[str, Any] = Field(default_factory=dict)
    design_specification: Dict[str, Any] = Field(default_factory=dict)
    layout_specification: Dict[str, Any] = Field(default_factory=dict)
    user_requirements: List[str] = Field(default_factory=list)
    inspection_criteria: List[str] = Field(default_factory=list)


class InspectionCategoryResult(BaseModel):
    passed: bool = True
    issues: List[VisualInspectionIssue] = Field(default_factory=list)


class PreviewArtifact(BaseModel):
    source_artifact: str
    preview_format: str = "png"
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    reference: Optional[str] = None
    render_status: str
    error: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


VisualCritiqueRequest.model_rebuild()


class VisualInspectionResult(BaseModel):
    render_success: bool
    geometry: InspectionCategoryResult = Field(default_factory=InspectionCategoryResult)
    composition: InspectionCategoryResult = Field(default_factory=InspectionCategoryResult)
    hierarchy: InspectionCategoryResult = Field(default_factory=InspectionCategoryResult)
    readability: InspectionCategoryResult = Field(default_factory=InspectionCategoryResult)
    spacing: InspectionCategoryResult = Field(default_factory=InspectionCategoryResult)
    color: InspectionCategoryResult = Field(default_factory=InspectionCategoryResult)
    asset_visibility: InspectionCategoryResult = Field(default_factory=InspectionCategoryResult)
    requirement_visibility: InspectionCategoryResult = Field(default_factory=InspectionCategoryResult)
    issues: List[VisualInspectionIssue] = Field(default_factory=list)
    requirements: List[RequirementInspection] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    source: str = "deterministic"

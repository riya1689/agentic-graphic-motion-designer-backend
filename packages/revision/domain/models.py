"""Typed design-revision contracts. No provider or renderer types live here."""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, model_validator

from packages.design_intelligence.domain.layout import LayoutSpecification
from packages.design_intelligence.domain.specification import DesignBrief, DesignSpecification
from packages.verification.domain.visual import VisualInspectionResult


class RevisionPriority(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class RevisionChangeType(str, Enum):
    INCREASE_FONT_SIZE = "increase_font_size"
    DECREASE_FONT_SIZE = "decrease_font_size"
    INCREASE_FONT_WEIGHT = "increase_font_weight"
    DECREASE_FONT_WEIGHT = "decrease_font_weight"
    ADJUST_LETTER_SPACING = "adjust_letter_spacing"
    ADJUST_LINE_HEIGHT = "adjust_line_height"
    CHANGE_TEXT_ALIGNMENT = "change_text_alignment"
    MOVE_REGION = "move_region"
    RESIZE_REGION = "resize_region"
    INCREASE_SPACING = "increase_spacing"
    DECREASE_SPACING = "decrease_spacing"
    ADJUST_ALIGNMENT = "adjust_alignment"
    INCREASE_VISUAL_WEIGHT = "increase_visual_weight"
    DECREASE_VISUAL_WEIGHT = "decrease_visual_weight"
    PROMOTE_ELEMENT = "promote_element"
    DEMOTE_ELEMENT = "demote_element"
    CHANGE_SEMANTIC_COLOR_ROLE = "change_semantic_color_role"
    INCREASE_CONTRAST = "increase_contrast"
    DECREASE_CONTRAST = "decrease_contrast"
    INCREASE_ASSET_SIZE = "increase_asset_size"
    DECREASE_ASSET_SIZE = "decrease_asset_size"
    MOVE_ASSET = "move_asset"
    ADJUST_ASSET_FIT = "adjust_asset_fit"


class RevisionRequest(BaseModel):
    inspection: VisualInspectionResult
    design_brief: DesignBrief
    design_specification: DesignSpecification
    layout_specification: LayoutSpecification
    iteration: int = Field(ge=1)
    maximum_iterations: int = Field(ge=1)
    constraints: List[str] = Field(default_factory=list)


class RevisionDecision(BaseModel):
    should_revise: bool
    priority: RevisionPriority = RevisionPriority.MEDIUM
    reason: str = Field(min_length=1, max_length=1000)
    target: Optional[str] = None
    change_type: Optional[RevisionChangeType] = None
    value: Any = None
    finding_reference: Optional[str] = None

    @model_validator(mode="after")
    def decision_has_patch_when_needed(self):
        if self.should_revise and (not self.target or not self.change_type):
            raise ValueError("a revision decision must identify a target and change_type")
        return self


class RevisionPatch(BaseModel):
    target: str = Field(min_length=1, max_length=160)
    operation: RevisionChangeType
    value: Any = None
    finding_reference: Optional[str] = None

    @model_validator(mode="after")
    def validate_value_bounds(self):
        numeric = self.value
        bounds = {
            RevisionChangeType.INCREASE_FONT_SIZE: (0.75, 1.50),
            RevisionChangeType.DECREASE_FONT_SIZE: (0.75, 1.50),
            RevisionChangeType.ADJUST_LETTER_SPACING: (-20.0, 50.0),
            RevisionChangeType.ADJUST_LINE_HEIGHT: (0.5, 3.0),
            RevisionChangeType.MOVE_REGION: (-0.15, 0.15),
            RevisionChangeType.RESIZE_REGION: (0.75, 1.25),
            RevisionChangeType.INCREASE_SPACING: (0.5, 2.0),
            RevisionChangeType.DECREASE_SPACING: (0.5, 2.0),
            RevisionChangeType.INCREASE_ASSET_SIZE: (0.70, 1.40),
            RevisionChangeType.DECREASE_ASSET_SIZE: (0.70, 1.40),
        }
        if self.operation in bounds:
            if not isinstance(numeric, (int, float)):
                raise ValueError(f"{self.operation.value} requires a numeric value")
            low, high = bounds[self.operation]
            if not low <= float(numeric) <= high:
                raise ValueError(f"{self.operation.value} value must be between {low} and {high}")
        elif self.operation in {RevisionChangeType.INCREASE_FONT_WEIGHT, RevisionChangeType.DECREASE_FONT_WEIGHT,
                                RevisionChangeType.CHANGE_TEXT_ALIGNMENT, RevisionChangeType.ADJUST_ALIGNMENT,
                                RevisionChangeType.CHANGE_SEMANTIC_COLOR_ROLE, RevisionChangeType.ADJUST_ASSET_FIT}:
            if not isinstance(numeric, str) or not numeric.strip():
                raise ValueError(f"{self.operation.value} requires a non-empty string value")
        return self


class RevisionStatus(str, Enum):
    PROPOSED = "proposed"
    APPLIED = "applied"
    REJECTED = "rejected"
    FAILED = "failed"


class RevisionRecord(BaseModel):
    iteration: int = Field(ge=1)
    finding_reference: Optional[str] = None
    decision: RevisionDecision
    patch: Optional[RevisionPatch] = None
    status: RevisionStatus
    reason: Optional[str] = None


class RevisionResult(BaseModel):
    status: RevisionStatus
    iteration: int = Field(ge=1)
    previous_specification: DesignSpecification
    revised_specification: DesignSpecification
    decision: Optional[RevisionDecision] = None
    patch: Optional[RevisionPatch] = None
    inspection_before: VisualInspectionResult
    inspection_after: Optional[VisualInspectionResult] = None
    accepted: bool = False
    rollback_reason: Optional[str] = None
    history: List[RevisionRecord] = Field(default_factory=list)

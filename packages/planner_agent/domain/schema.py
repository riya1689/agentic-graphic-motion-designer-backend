from __future__ import annotations
from typing import Any, Dict, List, Literal, Optional
# from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field
from packages.planner_agent.domain.graphic_execution_schema import (
    PlannerGraphicExecutionSpec,
)
from packages.design_intelligence.domain.specification import DesignSpecification


# ============================================================
# Previous Asset Requirement
# ============================================================

class TimeReference(BaseModel):
    """
    Relative time reference for an existing/previous asset.

    Example:
        offset_months = -2
        means two months before the current request.
    """

    offset_days: Optional[int] = None
    offset_weeks: Optional[int] = None
    offset_months: Optional[int] = None
    offset_years: Optional[int] = None


class AssetRequest(BaseModel):
    """
    Planner describes WHAT previous asset/context is required.

    IMPORTANT:
    Planner does NOT retrieve the asset.
    Planner does NOT choose the storage/RAG tool.
    """

    type: str = Field(
        ...,
        description="Asset type such as brand_logo, image, video, font, previous_design, ui_reference."
    )

    name: Optional[str] = Field(
        default=None,
        description="Specific asset name if known."
    )

    description: Optional[str] = Field(
        default=None,
        description="Natural-language description of the required previous asset."
    )

    time_reference: Optional[TimeReference] = None

    required: bool = True


# ============================================================
# Task Planning
# ============================================================

class PlannerTask(BaseModel):
    """
    One executable work unit created by the Planner.
    """

    task_id: str

    title: str

    description: str

    job_type: Literal[
        "graphic_design",
        "motion_design",
        "ui_ux_design",
        "unknown"
    ]

    required_capabilities: List[str] = Field(default_factory=list)

    depends_on: List[str] = Field(default_factory=list)

    can_run_parallel: bool = False

    inputs: List[str] = Field(default_factory=list)

    expected_outputs: List[str] = Field(default_factory=list)

    constraints: List[str] = Field(default_factory=list)

    acceptance_criteria: List[str] = Field(default_factory=list)


# ============================================================
# Verification Planning
# ============================================================

class VerificationPlan(BaseModel):
    required: bool = True

    checks: List[str] = Field(default_factory=list)

    retry_on_failure: bool = True

    max_repair_attempts: int = Field(
        default=2,
        ge=0,
        le=5
    )


# ============================================================
# Planner Final Output
# ============================================================

class PlannerOutput(BaseModel):
    """
    Final structured output returned by planner_agent to Manager.
    """

    planner_status: Literal[
        "completed",
        "failed"
    ] = "completed"

    job_summary: str

    primary_job_type: Literal[
        "graphic_design",
        "motion_design",
        "ui_ux_design",
        "mixed",
        "unknown"
    ]

    target_software: Literal[
        "adobe_illustrator",
        "adobe_photoshop",
        "video_generation",
    ]

    target_output_format: Literal[
        "psd",
        "ai",
        "svg",
        "jpg",
    ] = None

    graphic_execution_spec: Optional[Dict[str, Any]] = None

    # --------------------------------------------------------
    # Previous asset/context requirement
    # --------------------------------------------------------

    previous_asset_required: bool = False

    asset_requests: List[AssetRequest] = Field(
        default_factory=list
    )

    # --------------------------------------------------------
    # Execution planning
    # --------------------------------------------------------

    tasks: List[PlannerTask] = Field(
        default_factory=list
    )

    # ============================================================
# GENERIC GRAPHIC EXECUTION SPEC
# ============================================================
# Used for graphic-design jobs.
# Tool-neutral structured visual plan.
# ============================================================

    graphic_execution_spec: Optional[
        PlannerGraphicExecutionSpec
    ] = None

    # Design intent is kept separate from renderer execution details.  The
    # field is optional for backward compatibility with older Planner output.
    design_specification: Optional[DesignSpecification] = None

    # graphic_execution_spec: Optional[
    #     Dict[str, Any]
    # ] = None

    execution_order: List[str] = Field(
        default_factory=list
    )

    global_constraints: List[str] = Field(
        default_factory=list
    )

    final_deliverables: List[str] = Field(
        default_factory=list
    )

    verification: VerificationPlan = Field(
        default_factory=VerificationPlan
    )

    # Future-safe metadata.
    # Do not use this for tool selection.
    # metadata: Dict[str, Any] = Field(
    #     default_factory=dict
    # )

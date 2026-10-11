"""
Motion Agent Workflow State

IMPORTANT ARCHITECTURE RULE:

ManagerWorkflowState
        !=
MotionAgentState

Manager পুরো multi-agent workflow track করে।

MotionAgentState শুধুমাত্র Motion Agent-এর internal
execution lifecycle track করবে।

PHASE-1:

    RECEIVE
        ↓
    VALIDATE
        ↓
    ACK / FAIL
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field
from packages.motion_agent.compiler.schema import (
    MotionExecutionSpec,
)


# ============================================================
# MOTION WORKFLOW STATUS
# ============================================================

class MotionWorkflowStatus(str, Enum):

    RECEIVED = "received"

    VALIDATING = "validating"

    COMPLETED = "completed"

    FAILED = "failed"


# ============================================================
# MOTION AGENT STATE
# ============================================================

class MotionAgentState(BaseModel):
    """
    Motion Agent-এর complete internal workflow state.

    Phase-1 intentionally contains no video-generation
    implementation logic.
    """

    # ========================================================
    # INPUT
    # ========================================================

    job_id: str

    original_user_request: str = ""

    planner_plan: Dict[str, Any] = Field(
        default_factory=dict
    )


    # ========================================================
    # WORKFLOW TRACKING
    # ========================================================

    current_stage: str = "received"

    status: MotionWorkflowStatus = (
        MotionWorkflowStatus.RECEIVED
    )


    # ========================================================
    # LOOP ENGINEERING STATE
    # ========================================================

    validation_attempt: int = 0

    max_validation_attempts: int = 2

    validation_errors: List[str] = Field(
        default_factory=list
    )


    # ========================================================
    # VERIFICATION GATE
    # ========================================================

    plan_verified: bool = False


    # ========================================================
    # OUTPUT
    # ========================================================

    output: Optional[Dict[str, Any]] = None

    error: Optional[str] = None

    # ========================================================
# PHASE-2A — MOTION EXECUTION COMPILATION
# ========================================================
#
# Planner output থেকে model-neutral execution contract.
#
# No Wan/LTX specific data belongs here.
# ========================================================

    motion_execution_spec: Optional[
        MotionExecutionSpec
    ] = None

    motion_llm_provider: Optional[str] = None

    motion_llm_model: Optional[str] = None

    execution_spec_verified: bool = False

    execution_spec_errors: List[str] = Field(
        default_factory=list
 )

 # ========================================================
    # PHASE-2B — VIDEO GENERATION
    # ========================================================

    selected_video_tool: Optional[str] = None

    current_shot_index: int = 0

    generated_shots: List[
        Dict[str, Any]
    ] = Field(
        default_factory=list
    )

    video_generation_attempt: int = 0

    max_video_generation_attempts: int = 2

    generated_video: Optional[str] = None

    video_verification_errors: List[str] = Field(
        default_factory=list
    )

    video_verified: bool = False

        # ========================================================
    # PHASE-2B — VIDEO EXECUTION METADATA
    # ========================================================
    #
    # These are runtime values.
    #
    # They are NOT Planner business requirements.
    # ========================================================

    selected_video_tool: Optional[str] = None

    selected_video_gateway: Optional[str] = None

    selected_video_provider: Optional[str] = None

    selected_video_model: Optional[str] = None


    # ========================================================
    # PHASE-2B — GENERATION LOOP
    # ========================================================

    video_generation_attempt: int = 0

    max_video_generation_attempts: int = 2


    # ========================================================
    # PHASE-2B — GENERATED ARTIFACTS
    # ========================================================

    generated_shots: List[
        Dict[str, Any]
    ] = Field(
        default_factory=list
    )

    generated_video: Optional[str] = None


    # ========================================================
    # PHASE-2B — VIDEO VERIFICATION
    # ========================================================

    video_verified: bool = False

    video_verification_errors: List[str] = Field(
        default_factory=list
    )
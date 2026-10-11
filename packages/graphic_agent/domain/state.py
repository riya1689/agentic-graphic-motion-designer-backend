"""
Graphic Agent Workflow State

এই state শুধুমাত্র Graphic Agent-এর internal execution track করবে।

Manager-এর ManagerWorkflowState এবং GraphicState আলাদা।

Manager State:
    পুরো multi-agent workflow track করে।

Graphic State:
    Graphic Agent-এর ভিতরের workflow track করে।
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from packages.graphic_agent.compiler.execution_spec import (
    GraphicExecutionSpec,
)


# ============================================================
# GRAPHIC WORKFLOW STATUS
# ============================================================

class GraphicWorkflowStatus(str, Enum):

    RECEIVED = "received"

    VALIDATING = "validating"

    COMPLETED = "completed"

    FAILED = "failed"


# ============================================================
# GRAPHIC AGENT STATE
# ============================================================

class GraphicAgentState(BaseModel):
    """
    Graphic Agent-এর complete internal state.

    Phase-1:
        receive
        validate
        acknowledge

    Future:
        plan interpretation
        tool selection
        design generation
        verification
        repair
    """

    # Manager job ID
    job_id: str

    # Original prompt
    original_user_request: str = ""

    # Planner Agent-এর final plan
    planner_plan: Dict[str, Any] = Field(
        default_factory=dict
    )

    # Current Graphic Agent stage
    current_stage: str = "received"

    # Workflow status
    status: GraphicWorkflowStatus = (
        GraphicWorkflowStatus.RECEIVED
    )

    # ========================================================
    # LOOP ENGINEERING STATE
    # ========================================================

    validation_attempt: int = 0

    max_validation_attempts: int = 2

    validation_errors: List[str] = Field(
        default_factory=list
    )

    # Verification gate
    plan_verified: bool = False

    # Final Phase-1 response
    output: Optional[Dict[str, Any]] = None

    # Fatal error
    error: Optional[str] = None

   # ========================================================
   # PHASE-2 — DESIGN EXECUTION STATE
   # ========================================================

    selected_tool: Optional[str] = None

    generation_prompt: str = ""

    generation_attempt: int = 0

    selected_image_model: Optional[str] = None

    selected_image_provider: Optional[str] = None

    selected_image_job_type: Optional[str] = None

    max_generation_attempts: int = 2

    generated_file: Optional[str] = None

    tool_result: Optional[Dict[str, Any]] = None
    # ========================================================
    # PHASE-3 — JSX FALLBACK STATE
    # ========================================================
    #
    # Primary image tool fail করলে fallback execution
    # information এখানে track হবে।
    # ========================================================

    # NORMALIZED GRAPHIC EXECUTION SPEC

    execution_spec: Optional[GraphicExecutionSpec] = None
    primary_generation_error: Optional[str] = None

    fallback_used: bool = False

    fallback_tool: Optional[str] = None

    fallback_file: Optional[str] = None

    fallback_verified: bool = False
"""
Motion Agent Domain Schemas

PHASE-1 PURPOSE:

Manager থেকে আসা Planner plan-কে Motion Agent-এর
internal structured task হিসেবে represent করা।

IMPORTANT:

এই phase-এ:

- video generate হবে না
- Wan/LTX select হবে না
- prompt compile হবে না
- FFmpeg run হবে না
- Motion Agent Planner plan modify করবে না

Motion Agent শুধু:

    receive
        ↓
    validate
        ↓
    acknowledge / fail

করবে।
"""

from __future__ import annotations

from typing import Any, Dict

from pydantic import BaseModel, Field


# ============================================================
# MOTION TASK
# ============================================================

class MotionTask(BaseModel):
    """
    Motion Agent-এর internal task representation.

    Manager API payload directly agent workflow-এর everywhere
    pass না করে domain model দিয়ে normalize করা হচ্ছে.

    This keeps API contract and internal execution state separate.
    """

    # Manager workflow job ID.
    job_id: str

    # Planner Agent-এর final verified execution plan.
    planner_plan: Dict[str, Any] = Field(
        default_factory=dict
    )

    # Original user prompt.
    #
    # Phase-1 validation-এর জন্য mandatory নয়।
    # Future prompt compiler / verification-এ useful হবে।
    original_user_request: str = ""

    # ========================================================
    # LOOP ENGINEERING
    # ========================================================
    #
    # Infinite validation retry prevent করার জন্য bounded limit.
    # ========================================================

    max_validation_attempts: int = 2
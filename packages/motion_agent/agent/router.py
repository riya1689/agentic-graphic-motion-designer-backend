"""
Motion Agent Workflow Router

এই router validation-এর পরে workflow কোথায় যাবে
সেটা deterministicভাবে decide করবে।

IMPORTANT:

এটি LLM router নয়।

No business-generation logic belongs here.
"""

from __future__ import annotations

from typing import Literal

from packages.motion_agent.domain.state import (
    MotionAgentState,
)


MotionRoute = Literal[
    "success",
    "retry",
    "failure",
]


# ============================================================
# ROUTE AFTER VALIDATION
# ============================================================

def route_after_validation(
    state: MotionAgentState,
) -> MotionRoute:
    """
    PASS:
        acknowledgement

    FAIL + attempts remaining:
        retry validation

    FAIL + attempts exhausted:
        failure
    """

    if state.plan_verified:

        return "success"

    if (
        state.validation_attempt
        <
        state.max_validation_attempts
    ):

        return "retry"

    return "failure"
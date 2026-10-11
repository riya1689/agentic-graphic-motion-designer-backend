"""
Graphic Agent Workflow Router

এই router সিদ্ধান্ত নেয় validation-এর পরে
workflow কোথায় যাবে।

IMPORTANT:

এটি LLM router নয়।

Phase-1 এ routing deterministic.
"""

from __future__ import annotations

from typing import Literal

from packages.graphic_agent.domain.state import (
    GraphicAgentState,
)


GraphicRoute = Literal[
    "success",
    "retry",
    "failure",
]


# ============================================================
# ROUTE AFTER VALIDATION
# ============================================================

def route_after_validation(
    state: GraphicAgentState,
) -> GraphicRoute:
    """
    Verification gate.

    PASS:
        acknowledgement

    FAIL + attempts left:
        validation loop

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
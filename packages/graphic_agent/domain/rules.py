"""
Graphic Agent Deterministic Rules

Phase-1 এ আমরা শুধু communication contract verify করছি।

IMPORTANT:

Planner-এর design quality এখানে verify করছি না।

Planner already নিজে:
    planning
    validation
    verification
    repair

করেছে।

Graphic Agent শুধু নিশ্চিত করবে usable plan পেয়েছে।
"""

from __future__ import annotations

from typing import Any, Dict, List


# ============================================================
# PLAN VALIDATION RULE
# ============================================================

def validate_received_plan(
    planner_plan: Dict[str, Any],
) -> List[str]:
    """
    Planner plan Graphic Agent-এর জন্য usable কিনা check করে।

    Return:
        []      -> PASS
        errors  -> FAIL
    """

    errors: List[str] = []

    # --------------------------------------------------------
    # Rule 1:
    # Planner output dictionary হতে হবে।
    # --------------------------------------------------------

    if not isinstance(planner_plan, dict):

        errors.append(
            "planner_plan must be a dictionary."
        )

        return errors

    # --------------------------------------------------------
    # Rule 2:
    # Empty plan accept করা হবে না।
    # --------------------------------------------------------

    if not planner_plan:

        errors.append(
            "planner_plan cannot be empty."
        )

    return errors
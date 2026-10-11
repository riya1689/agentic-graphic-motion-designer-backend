"""
Motion Agent Domain Validation Rules

এই file-এর কাজ:

Planner থেকে Motion Agent যে plan পেয়েছে
তার basic communication / contract integrity verify করা।

IMPORTANT:

এই validator video quality verify করে না।

এই validator:

- Wan compatibility check করে না
- LTX compatibility check করে না
- cinematic quality check করে না
- prompt quality check করে না
- FFmpeg requirements check করে না

Those belong to later phases.
"""

from __future__ import annotations

from typing import Any, Dict, List


# ============================================================
# VALIDATE RECEIVED PLANNER PLAN
# ============================================================

def validate_received_plan(
    planner_plan: Dict[str, Any],
) -> List[str]:
    """
    Validate basic Planner -> Motion Agent contract.

    Returns:

        []          -> PASS

        ["error"]   -> FAIL
    """

    errors: List[str] = []


    # ========================================================
    # RULE 1 — PLAN MUST BE DICTIONARY
    # ========================================================

    if not isinstance(
        planner_plan,
        dict,
    ):

        errors.append(
            "Planner plan must be a dictionary."
        )

        return errors


    # ========================================================
    # RULE 2 — PLAN MUST NOT BE EMPTY
    # ========================================================

    if not planner_plan:

        errors.append(
            "Planner plan is empty."
        )

        return errors


    # ========================================================
    # RULE 3 — PLANNER STATUS
    # ========================================================
    #
    # Motion Agent should not execute a failed Planner output.
    # ========================================================

    planner_status = planner_plan.get(
        "planner_status"
    )

    if planner_status != "completed":

        errors.append(
            "Planner plan is not marked as completed."
        )


    # ========================================================
    # RULE 4 — JOB TYPE
    # ========================================================
    #
    # Motion Agent accepts:
    #
    # motion_design
    # mixed
    #
    # mixed is allowed because future workflows may contain
    # both graphic and motion tasks.
    # ========================================================

    primary_job_type = planner_plan.get(
        "primary_job_type"
    )

    if primary_job_type not in {
        "motion_design",
        "mixed",
    }:

        errors.append(
            "Planner plan is not a motion-design job."
        )


    # ========================================================
    # RULE 5 — TASKS MUST EXIST
    # ========================================================

    tasks = planner_plan.get(
        "tasks"
    )

    if not isinstance(
        tasks,
        list,
    ) or not tasks:

        errors.append(
            "Planner plan contains no executable tasks."
        )


    # ========================================================
    # RULE 6 — EXECUTION ORDER
    # ========================================================
    #
    # We do NOT deeply revalidate Planner planning.
    #
    # Planner already has its own validation + verification.
    #
    # We only ensure contract shape is usable.
    # ========================================================

    execution_order = planner_plan.get(
        "execution_order"
    )

    if not isinstance(
        execution_order,
        list,
    ):

        errors.append(
            "Planner plan execution_order must be a list."
        )


    return errors
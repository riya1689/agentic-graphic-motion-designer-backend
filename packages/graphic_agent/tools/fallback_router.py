"""
Graphic Agent Fallback Router

Purpose:

    Planner JSON
        ↓
    target software detection
        ↓
    appropriate JSX generator

IMPORTANT:

No Manager business logic.
No HTTP logic.
No LLM call.
"""

from __future__ import annotations

from typing import Any, Dict


# ============================================================
# TARGET SOFTWARE FINDER
# ============================================================

def find_target_software(
    planner_plan: Dict[str, Any],
) -> str:
    """
    Planner plan-এর ভিতরে target software খুঁজে বের করে।

    Supported:
        adobe_illustrator
        adobe_photoshop
    """

    # --------------------------------------------------------
    # Direct field
    # --------------------------------------------------------

    direct_target = planner_plan.get(
        "target_software"
    )

    if isinstance(
        direct_target,
        str,
    ):

        return direct_target.lower()


    # --------------------------------------------------------
    # Check common nested structures
    # --------------------------------------------------------

    for key in (
        "design_spec",
        "execution_plan",
        "output",
        "requirements",
        "metadata",
    ):

        nested = planner_plan.get(
            key
        )

        if isinstance(
            nested,
            dict,
        ):

            nested_target = nested.get(
                "target_software"
            )

            if isinstance(
                nested_target,
                str,
            ):

                return nested_target.lower()


    # --------------------------------------------------------
    # Conservative fallback.
    #
    # We do NOT guess Illustrator or Photoshop.
    # --------------------------------------------------------

    return ""


# ============================================================
# SELECT JSX FALLBACK TOOL
# ============================================================

def select_jsx_fallback_tool(
    planner_plan: Dict[str, Any],
) -> str:

    target = find_target_software(
        planner_plan
    )


    if target in (
        "adobe_illustrator",
        "illustrator",
    ):

        return "illustrator_jsx"


    if target in (
        "adobe_photoshop",
        "photoshop",
    ):

        return "photoshop_jsx"


    raise ValueError(
        "Planner plan does not contain a supported "
        "target_software for JSX fallback."
    )
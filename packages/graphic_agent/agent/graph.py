"""
Graphic Agent Workflow Graph

PHASE-1:

    RECEIVE
       ↓
    VALIDATE
       ↓
    ┌──────────── Verification Gate ────────────┐
    │                                           │
   PASS                                        FAIL
    │                                           │
    ↓                                           ↓
   ACK                               attempts remaining?
                                                │
                                     ┌──────────┴─────────┐
                                    YES                  NO
                                     │                    │
                                     └──→ VALIDATE       FAIL


IMPORTANT:

এই phase-এ retry loop intentionally simple।

Future phase-এ:

    FAIL
      ↓
    Repair Node
      ↓
    Re-generate
      ↓
    Verify

যোগ হবে।
"""

from __future__ import annotations

import os
from pathlib import Path

from packages.graphic_agent.agent.node import (
    # ========================================================
    # NEW: JSX FALLBACK NODES
    # ========================================================
    build_generation_prompt_node,
    execute_tool_node,
    generate_jsx_fallback_node,
    select_jsx_fallback_node,
    select_tool_node,
    validate_image_model_node,
    verify_generated_file_node,
    verify_jsx_fallback_node,
)
from packages.graphic_agent.agent.registry import (
    get_node,
)
from packages.graphic_agent.agent.router import (
    route_after_validation,
)
from packages.graphic_agent.domain.schema import (
    GraphicTask,
)
from packages.graphic_agent.domain.state import (
    GraphicAgentState,
    GraphicWorkflowStatus,
)

# ============================================================
# NEW: PHASE-2 GENERATION NODES
# ============================================================
#
# এই nodes agent registry-এর মাধ্যমে না নিয়ে direct import
# করা হচ্ছে।
#
# কারণ Phase-2 tool execution path এখনো small এবং explicit।
#
# Future-এ চাইলে এগুলোকেও dedicated workflow/node registry
# pattern-এ migrate করা যাবে।
# ============================================================


# ============================================================
# RUN GRAPHIC WORKFLOW
# ============================================================

def run_graphic_workflow(
    task: GraphicTask,
) -> GraphicAgentState:
    """
    Graphic Agent Phase-1 deterministic workflow.

    কোনো LLM call নেই।
    কোনো graphic generation নেই।
    কোনো external tool call নেই।

    Phase-2 extension:

    Planner plan validation PASS করার পরে
    deterministic prompt builder + Nano Banana tool
    ব্যবহার করে image generation test করা হচ্ছে।
    """

    # ========================================================
    # INITIAL STATE
    # ========================================================

    state = GraphicAgentState(
        job_id=task.job_id,
        original_user_request=(
            task.original_user_request
        ),
        planner_plan=task.planner_plan,
        selected_image_model=(
            task.selected_image_model
        ),
        max_validation_attempts=(
            task.max_validation_attempts
        ),
    )

    # ========================================================
    # NODE 1 — RECEIVE
    # ========================================================

    receive_node = get_node(
        "receive_plan"
    )

    state = receive_node(
        state
    )

    # ========================================================
    # LOOP ENGINEERING
    # ========================================================
    #
    # Bounded loop.
    #
    # Infinite retry allowed নয়।
    # ========================================================

    while True:

        # ----------------------------------------------------
        # NODE 2 — VALIDATE
        # ----------------------------------------------------

        validate_node = get_node(
            "validate_plan"
        )

        state = validate_node(
            state
        )

        # ----------------------------------------------------
        # VERIFICATION / ROUTING GATE
        # ----------------------------------------------------

        route = route_after_validation(
            state
        )

        # ----------------------------------------------------
        # PASS
        # ----------------------------------------------------

        if route == "success":

            acknowledge_node = get_node(
                "acknowledge_plan"
            )

            state = acknowledge_node(
                state
            )

            break

        # ----------------------------------------------------
        # RETRY
        # ----------------------------------------------------

        if route == "retry":

            print(
                "[GRAPHIC AGENT] "
                "Retrying validation..."
            )

            continue

        # ----------------------------------------------------
        # FAILED
        # ----------------------------------------------------

        fail_node = get_node(
            "fail_plan"
        )

        state = fail_node(
            state
        )

        break

    # ========================================================
    # PHASE-1 FAILURE GATE
    # ========================================================
    #
    # Planner plan validation fail করলে Phase-2 tool execution
    # start হবে না।
    # ========================================================

    if not state.plan_verified:

        return state

    # The current Higgsfield image path produces raster output. Do not enter
    # generation when the plan requires native editable output; tracing or
    # embedding that raster would falsely claim SVG/PSD/AI capability.
    requested_format = str(
        (state.planner_plan or {}).get("target_output_format") or ""
    ).strip().lower()
    if requested_format in {"svg", "psd", "ai"}:
        state.status = GraphicWorkflowStatus.FAILED
        state.current_stage = "native_output_capability_unavailable"
        state.error = (
            f"Native {requested_format.upper()} output is not supported by the "
            "selected raster execution path. No raster-to-editable conversion was performed."
        )
        state.output = None
        print(f"[GRAPHIC AGENT] Native {requested_format.upper()} output capability = FAIL")
        return state

    # ========================================================
    # NEW: PHASE-2 — BUILD TOOL-SPECIFIC GENERATION PROMPT
    # ========================================================

    state = build_generation_prompt_node(
        state
    )

    # ========================================================
    # FIX 1: Indentation error corrected here.
    # Previously 'try:' was placed outside the function body.
    # ========================================================

    try:

        state = validate_image_model_node(
            state
        )

    except Exception as exc:

        state.status = (
            GraphicWorkflowStatus.FAILED
        )

        state.current_stage = (
            "image_model_validation_failed"
        )

        state.error = str(exc)

        state.output = None

        print()

        print(
            "[GRAPHIC AGENT] "
            "Image model validation = FAIL"
        )

        print(
            "[GRAPHIC AGENT] "
            f"Error: {state.error}"
        )

        # ========================================================
        # FIX 2: Fixed bad indentation space before 'return state'
        # ========================================================
        return state

    # ========================================================
    # NEW: PHASE-2 — SELECT TOOL
    # ========================================================

    state = select_tool_node(
        state
    )

    # ========================================================
    # NEW: PHASE-2 GENERATION LOOP
    # ========================================================

    while True:

        try:

            # ------------------------------------------------
            # EXECUTE GRAPHIC TOOL
            # ------------------------------------------------

            state = execute_tool_node(
                state
            )

            # ------------------------------------------------
            # VERIFY GENERATED FILE
            # ------------------------------------------------

            state = verify_generated_file_node(
                state
            )

            # ------------------------------------------------
            # SUCCESS GATE
            # ------------------------------------------------

            if state.error is None:

                break

        except Exception as exc:

            state.error = str(
                exc
            )

            print(
                "[GRAPHIC AGENT] "
                f"Generation error: {state.error}"
            )

        # ----------------------------------------------------
        # PRIMARY IMAGE TOOL EXHAUSTED
        # ----------------------------------------------------

        if (
            state.generation_attempt
            >=
            state.max_generation_attempts
        ):

            print(
                "[GRAPHIC AGENT] "
                "Primary image generation retry limit reached."
            )

            # Preserve provider error.
            state.primary_generation_error = (
                state.error
            )

            break

        print(
            "[GRAPHIC AGENT] "
            "Generation failed. Retrying..."
        )

    # ========================================================
    # NEW: JSX FALLBACK GATE
    # ========================================================

    if state.error is not None:

        try:

            # ------------------------------------------------
            # SELECT FALLBACK
            # ------------------------------------------------

            state = select_jsx_fallback_node(
                state
            )

            # ------------------------------------------------
            # GENERATE JSX
            # ------------------------------------------------

            state = generate_jsx_fallback_node(
                state
            )

            # ------------------------------------------------
            # VERIFY JSX
            # ------------------------------------------------

            state = verify_jsx_fallback_node(
                state
            )

        except Exception as exc:

            state.status = (
                GraphicWorkflowStatus.FAILED
            )

            state.current_stage = (
                "jsx_fallback_failed"
            )

            state.error = str(
                exc
            )

            state.output = None

            print(
                "[GRAPHIC AGENT] "
                f"JSX fallback failed: {state.error}"
            )

            return state

        # ----------------------------------------------------
        # FALLBACK SUCCESS
        # ----------------------------------------------------

        if state.fallback_verified:

            state.status = (
                GraphicWorkflowStatus.COMPLETED
            )

            state.current_stage = (
                "completed"
            )

            state.error = None

            state.output = {

                "status":
                    "FALLBACK_GENERATED",

                "primary_tool":
                    state.selected_tool,

                "primary_error":
                    state.primary_generation_error,

                "fallback_used":
                    True,

                "fallback_tool":
                    state.fallback_tool,

                "fallback_file":
                    state.fallback_file,

                "message": (
                    "Primary image generation failed. "
                    "An Adobe JSX fallback script was "
                    "generated successfully."
                ),
            }

            print()

            print(
                "[GRAPHIC AGENT] JSX fallback = SUCCESS"
            )

            print(
                "[GRAPHIC AGENT] JSX file: "
                f"{state.fallback_file}"
            )

            return state

    # ========================================================
    # NEW: PHASE-2 SUCCESS
    # ========================================================

    state.status = (
        GraphicWorkflowStatus.COMPLETED
    )

    state.current_stage = (
        "image_generated"
    )

    state.error = None

    state.output = {

        "status":
            "GENERATED",

        "tool":
            state.selected_tool,

        "generated_file":
            state.generated_file,

        "generation_attempt":
            state.generation_attempt,

        "plan_verified":
            state.plan_verified,
    }

    print()

    print(
        "[GRAPHIC AGENT] Image generation = SUCCESS"
    )

    print(
        "[GRAPHIC AGENT] Generated image: "
        f"{state.generated_file}"
    )

    # ========================================================
    # NEW: AUTO OPEN GENERATED IMAGE
    # ========================================================

    if state.generated_file:

        generated_path = Path(
            state.generated_file
        ).resolve()

        # ========================================================
        # FIX 3: Fixed indentation of 'if generated_path.exists():'
        # ========================================================
        if generated_path.exists():

            print(
                "[GRAPHIC AGENT] Opening generated image..."
            )

            # os.startfile(
            #     str(generated_path)
            # )

    print("=" * 70)

    return state

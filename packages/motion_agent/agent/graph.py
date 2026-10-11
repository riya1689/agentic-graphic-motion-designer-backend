"""
Motion Agent Workflow Graph

CURRENT FLOW:

    RECEIVE
       ↓
    VALIDATE PLAN
       ↓
    PLAN ACCEPTED
       ↓
    COMPILE MotionExecutionSpec
       ↓
    VERIFY MotionExecutionSpec
       ↓
    SELECT VIDEO TOOL
       ↓
    GENERATE VIDEO
       ↓
    VERIFY VIDEO
       ↓
    FINALIZE
       ↓
    RETURN TO MANAGER


IMPORTANT:

Manager orchestration এখানে নেই.

Provider-specific API logic এখানে নেই.

Hugging Face logic bridge layer-এ থাকবে.
"""

from __future__ import annotations

from packages.motion_agent.agent.registry import (
    get_node,
)

from packages.motion_agent.agent.router import (
    route_after_validation,
)

from packages.motion_agent.domain.schema import (
    MotionTask,
)

from packages.motion_agent.domain.state import (
    MotionAgentState,
    MotionWorkflowStatus,
)


# ============================================================
# RUN MOTION WORKFLOW
# ============================================================

def run_motion_workflow(
    task: MotionTask,
) -> MotionAgentState:


    # ========================================================
    # INITIAL STATE
    # ========================================================

    state = MotionAgentState(

        job_id=
            task.job_id,

        original_user_request=
            task.original_user_request,

        planner_plan=
            task.planner_plan,

        max_validation_attempts=
            task.max_validation_attempts,

    )


    # ========================================================
    # PHASE-1 — RECEIVE
    # ========================================================

    receive_node = get_node(
        "receive_plan"
    )

    state = receive_node(
        state
    )


    # ========================================================
    # PHASE-1 — BOUNDED PLAN VALIDATION
    # ========================================================

    while True:


        validate_node = get_node(
            "validate_plan"
        )

        state = validate_node(
            state
        )


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
                "[MOTION AGENT] "
                "Retrying validation..."
            )

            continue


        # ----------------------------------------------------
        # FAILURE
        # ----------------------------------------------------

        fail_node = get_node(
            "fail_plan"
        )

        state = fail_node(
            state
        )

        return state


    # ========================================================
    # SAFETY GATE
    # ========================================================

    if not state.plan_verified:

        return state


    # ========================================================
    # PHASE-2A — COMPILE MOTION EXECUTION SPEC
    # ========================================================

    try:

        compile_spec_node = get_node(
            "compile_execution_spec"
        )

        state = compile_spec_node(
            state
        )


    except Exception as exc:

        state.status = (
            MotionWorkflowStatus.FAILED
        )

        state.current_stage = (
            "motion_execution_spec_failed"
        )

        state.error = str(exc)

        state.output = None


        print()

        print(
            "[MOTION AGENT] "
            "MotionExecutionSpec compilation = FAIL"
        )

        print(
            f"[MOTION AGENT] Error: {exc}"
        )


        return state


    # ========================================================
    # PHASE-2A — VERIFY EXECUTION SPEC
    # ========================================================

    verify_spec_node = get_node(
        "verify_execution_spec"
    )

    state = verify_spec_node(
        state
    )


    if not state.execution_spec_verified:

        state.status = (
            MotionWorkflowStatus.FAILED
        )

        state.current_stage = (
            "motion_execution_spec_invalid"
        )

        state.error = (
            "; ".join(
                state.execution_spec_errors
            )
        )

        state.output = None


        return state


    # ========================================================
    # PHASE-2B — SELECT VIDEO TOOL
    # ========================================================

    try:

        select_tool_node = get_node(
            "select_video_tool"
        )

        state = select_tool_node(
            state
        )


    except Exception as exc:

        state.status = (
            MotionWorkflowStatus.FAILED
        )

        state.current_stage = (
            "video_tool_selection_failed"
        )

        state.error = str(exc)

        state.output = None


        print(
            "[MOTION AGENT] "
            f"Video tool selection failed: {exc}"
        )


        return state


    # ========================================================
    # PHASE-2B — BOUNDED VIDEO GENERATION LOOP
    # ========================================================

    while True:

        try:


            # ------------------------------------------------
            # GENERATE
            # ------------------------------------------------

            generate_node = get_node(
                "generate_video"
            )

            state = generate_node(
                state
            )


            # ------------------------------------------------
            # VERIFY
            # ------------------------------------------------

            verify_video_node = get_node(
                "verify_generated_video"
            )

            state = verify_video_node(
                state
            )


            # ------------------------------------------------
            # SUCCESS
            # ------------------------------------------------

            if state.video_verified:

                break


        except Exception as exc:

            state.error = str(
                exc
            )


            print()

            print(
                "[MOTION AGENT] "
                "Video generation error:"
            )

            print(
                f"[MOTION AGENT] "
                f"{state.error}"
            )


        # ====================================================
        # RETRY LIMIT
        # ====================================================

        if (
            state.video_generation_attempt
            >=
            state.max_video_generation_attempts
        ):

            state.status = (
                MotionWorkflowStatus.FAILED
            )

            state.current_stage = (
                "video_generation_failed"
            )

            state.output = None


            print(
                "[MOTION AGENT] "
                "Video generation retry limit reached."
            )


            return state


        print(
            "[MOTION AGENT] "
            "Retrying video generation..."
        )


    # ========================================================
    # PHASE-2B — FINALIZE
    # ========================================================

    finalize_node = get_node(
        "finalize_video"
    )


    state = finalize_node(
        state
    )


    return state
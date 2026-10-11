"""
Motion Agent Nodes

PHASE-1 WORKFLOW:

    Receive Planner Plan
            ↓
    Validate Planner Plan
            ↓
       Verification Gate
        /             \\
      PASS            FAIL
       ↓                ↓
      ACK             Retry
                         ↓
                    Retry limit
                         ↓
                        FAIL


IMPORTANT:

Each node has ONE responsibility.

No:

- video generation
- prompt compilation
- video-model selection
- FFmpeg execution
- Manager orchestration

inside this file during Phase-1.
"""

from __future__ import annotations

import json

from packages.motion_agent.domain.rules import (
    validate_received_plan,
)

from packages.motion_agent.domain.state import (
    MotionAgentState,
    MotionWorkflowStatus,
)

from packages.motion_agent.compiler.compiler import (
    MotionExecutionCompiler,
)

from packages.motion_agent.llm.gemini import (
    GeminiMotionLLM,
)

from packages.motion_agent.tools.registry import (
    get_video_tool,
)

from packages.motion_agent.verification.execution_spec import (
    verify_motion_execution_spec,
)

from packages.motion_agent.verification.video_file import (
    verify_generated_video,
)

from packages.motion_agent.providers.config import (
    get_motion_video_runtime_config,
)

from packages.motion_agent.artifacts.video_store import (
    save_video_artifact,
)


# ============================================================
# NODE 1 — RECEIVE PLANNER PLAN
# ============================================================

def receive_plan_node(
    state: MotionAgentState,
) -> MotionAgentState:
    """
    Manager থেকে Planner-এর verified final plan receive করে।

    No validation happens here.
    No planning happens here.
    """

    state.current_stage = "plan_received"

    state.status = MotionWorkflowStatus.RECEIVED

    print()

    print("=" * 70)

    print(
        "[MOTION AGENT] Planner plan received from Manager"
    )

    print(
        f"[MOTION AGENT] Job ID: {state.job_id}"
    )

    print()

    print(
        "[MOTION AGENT] Received Planner Plan:"
    )

    print(
        json.dumps(
            state.planner_plan,
            indent=2,
            ensure_ascii=False,
        )
    )

    print("=" * 70)

    return state


# ============================================================
# NODE 2 — VALIDATE RECEIVED PLAN
# ============================================================

def validate_plan_node(
    state: MotionAgentState,
) -> MotionAgentState:
    """
    Basic Planner -> Motion Agent communication validation.

    IMPORTANT:

    This is NOT video-quality verification.

    This only checks whether Motion Agent received a usable
    Planner contract.
    """

    state.current_stage = "validating_plan"

    state.status = MotionWorkflowStatus.VALIDATING

    state.validation_attempt += 1

    print()

    print(
        "[MOTION AGENT] Validation attempt "
        f"{state.validation_attempt}/"
        f"{state.max_validation_attempts}"
    )

    errors = validate_received_plan(
        state.planner_plan
    )

    state.validation_errors = errors

    state.plan_verified = not bool(
        errors
    )

    if state.plan_verified:

        print(
            "[MOTION AGENT] Planner plan validation = PASS"
        )

    else:

        print(
            "[MOTION AGENT] Planner plan validation = FAIL"
        )

        for error in errors:

            print(
                f"[MOTION AGENT] Validation error: {error}"
            )

    return state


# ============================================================
# NODE 3 — PLAN ACCEPTED
# ============================================================

def acknowledge_plan_node(
    state: MotionAgentState,
) -> MotionAgentState:

    state.current_stage = "plan_accepted"

    # ========================================================
    # CHANGED:
    # Workflow এখনো complete নয়।
    # ========================================================

    state.status = MotionWorkflowStatus.VALIDATING

    state.error = None

    # ========================================================
    # CHANGED:
    # Manager-কে এখনই final output দেওয়া হবে না।
    # ========================================================

    state.output = None


    print()

    print(
        "[MOTION AGENT] Planner plan accepted."
    )

    print(
        "[MOTION AGENT] "
        "Proceeding to motion execution."
    )

    return state

# ============================================================
# PHASE-2A NODE — COMPILE MOTION EXECUTION SPEC
# ============================================================
#
# Responsibility:
#
# Planner verified plan
#      ↓
# Motion LLM Compiler
#      ↓
# model-neutral MotionExecutionSpec
#
# IMPORTANT:
#
# No Hugging Face logic here.
# No video generation here.
# ============================================================

def compile_execution_spec_node(
    state: MotionAgentState,
) -> MotionAgentState:

    state.current_stage = (
        "compiling_motion_execution_spec"
    )


    print()

    print(
        "[MOTION AGENT] "
        "Compiling MotionExecutionSpec..."
    )


    provider = GeminiMotionLLM()


    compiler = MotionExecutionCompiler(
        provider=provider
    )


    spec = compiler.compile(

        job_id=state.job_id,

        planner_plan=state.planner_plan,

        original_user_request=(
            state.original_user_request
        ),

    )


    state.motion_execution_spec = spec

    state.motion_llm_provider = (
        provider.provider_id
    )

    state.motion_llm_model = (
        provider.model
    )


    print(
        "[MOTION AGENT] "
        "MotionExecutionSpec generated."
    )

    print(
        "[MOTION AGENT] "
        f"Shots = {len(spec.shots)}"
    )


    return state


# ============================================================
# PHASE-2A NODE — VERIFY MOTION EXECUTION SPEC
# ============================================================

def verify_execution_spec_node(
    state: MotionAgentState,
) -> MotionAgentState:

    state.current_stage = (
        "verifying_motion_execution_spec"
    )


    if state.motion_execution_spec is None:

        state.execution_spec_errors = [
            "MotionExecutionSpec is missing."
        ]

        state.execution_spec_verified = False

        return state


    errors = verify_motion_execution_spec(
        state.motion_execution_spec
    )


    state.execution_spec_errors = errors


    state.execution_spec_verified = (
        not bool(errors)
    )


    if state.execution_spec_verified:

        print(
            "[MOTION AGENT] "
            "MotionExecutionSpec verification = PASS"
        )


    else:

        print(
            "[MOTION AGENT] "
            "MotionExecutionSpec verification = FAIL"
        )

        for error in errors:

            print(
                "[MOTION AGENT] "
                f"Execution spec error: {error}"
            )


    return state



# ============================================================
# NODE 4 — FAILURE
# ============================================================

def fail_plan_node(
    state: MotionAgentState,
) -> MotionAgentState:
    """
    Validation retry limit reached.

    Fail explicitly instead of silently continuing.
    """

    state.current_stage = (
        "plan_validation_failed"
    )

    state.status = (
        MotionWorkflowStatus.FAILED
    )

    state.plan_verified = False

    state.error = (
        "; ".join(
            state.validation_errors
        )
        or
        "Planner plan validation failed."
    )

    state.output = None

    print()

    print(
        "[MOTION AGENT] Validation retry limit reached."
    )

    print(
        f"[MOTION AGENT] ERROR: {state.error}"
    )

    return state

    # ============================================================
# PHASE-2B NODE — SELECT VIDEO TOOL
# ============================================================
#
# IMPORTANT:
#
# No provider/model is hardcoded here.
#
# Configuration:
#     ↓
# Tool Registry:
#     ↓
# actual provider adapter
#
# This node only records runtime selection.
# ============================================================

def select_video_tool_node(
    state: MotionAgentState,
) -> MotionAgentState:

    state.current_stage = (
        "selecting_video_tool"
    )


    config = (
        get_motion_video_runtime_config()
    )


    tool = get_video_tool()


    state.selected_video_tool = (
        tool.tool_id
    )

    state.selected_video_gateway = (
        config.gateway
    )

    state.selected_video_provider = (
        config.provider
    )

    state.selected_video_model = (
        config.model
    )


    print()

    print(
        "[MOTION AGENT] "
        f"Video gateway = "
        f"{state.selected_video_gateway}"
    )

    print(
        "[MOTION AGENT] "
        f"Provider routing = "
        f"{state.selected_video_provider}"
    )

    print(
        "[MOTION AGENT] "
        f"Video model = "
        f"{state.selected_video_model}"
    )


    return state

    # ============================================================
# PHASE-2B NODE — GENERATE VIDEO
# ============================================================
#
# Trial Phase:
#
# Generate the first shot only.
#
# Multi-shot sequencing/merge belongs to Phase-2C.
#
# IMPORTANT:
#
# This node:
#
# - does NOT know Hugging Face SDK
# - does NOT know Fal
# - does NOT know Replicate
# - does NOT know model API details
# ============================================================

def generate_video_node(
    state: MotionAgentState,
) -> MotionAgentState:

    state.current_stage = (
        "generating_video"
    )


    # ========================================================
    # REQUIRE EXECUTION SPEC
    # ========================================================

    if state.motion_execution_spec is None:

        raise RuntimeError(
            "MotionExecutionSpec is missing."
        )


    if not state.motion_execution_spec.shots:

        raise RuntimeError(
            "MotionExecutionSpec contains no shots."
        )


    # ========================================================
    # BOUNDED ATTEMPT COUNT
    # ========================================================

    state.video_generation_attempt += 1


    print()

    print(
        "[MOTION AGENT] "
        "Video generation attempt "
        f"{state.video_generation_attempt}/"
        f"{state.max_video_generation_attempts}"
    )


    # ========================================================
    # GET TOOL THROUGH DEPENDENCY REGISTRY
    # ========================================================

    tool = get_video_tool()


    # ========================================================
    # TRIAL PHASE — FIRST SHOT
    # ========================================================

    shot = (
        state.motion_execution_spec.shots[0]
    )


    print(
        "[MOTION AGENT] "
        f"Generating shot = {shot.shot_id}"
    )


    # ========================================================
    # CLOUD GENERATION
    # ========================================================

    tool_result = tool.generate(

        job_id=state.job_id,

        shot=shot,

    )


    # ========================================================
    # SAVE GENERATED BYTES
    # ========================================================
    #
    # Provider bridge does NOT control filesystem storage.
    # ========================================================

    output_path = save_video_artifact(

        job_id=state.job_id,

        shot_id=shot.shot_id,

        video_bytes=tool_result.video_bytes,

    )


    # ========================================================
    # SAVE SERIALIZABLE METADATA ONLY
    # ========================================================
    #
    # Never store video_bytes inside Pydantic workflow state.
    # ========================================================

    shot_result = {

        "shot_id":
            tool_result.shot_id,

        "tool_id":
            tool_result.tool_id,

        "provider":
            tool_result.provider,

        "model":
            tool_result.model,

        "prompt":
            tool_result.prompt,

        "output_path":
            output_path,

    }


    state.generated_shots = [
        shot_result
    ]


    state.generated_video = (
        output_path
    )


    print(
        "[MOTION AGENT] "
        f"Video artifact saved = {output_path}"
    )


    return state

    # ============================================================
# PHASE-2B NODE — VERIFY VIDEO
# ============================================================

def verify_generated_video_node(
    state: MotionAgentState,
) -> MotionAgentState:

    state.current_stage = (
        "verifying_generated_video"
    )


    errors = verify_generated_video(

        state.generated_video
        or ""

    )


    state.video_verification_errors = (
        errors
    )


    state.video_verified = (
        not bool(errors)
    )


    if state.video_verified:

        state.error = None

        print(
            "[MOTION AGENT] "
            "Generated video verification = PASS"
        )


    else:

        state.error = "; ".join(
            errors
        )

        print(
            "[MOTION AGENT] "
            "Generated video verification = FAIL"
        )


        for error in errors:

            print(
                "[MOTION AGENT] "
                f"Video error: {error}"
            )


    return state

    # ============================================================
# PHASE-2B NODE — FINALIZE VIDEO RESULT
# ============================================================

def finalize_video_node(
    state: MotionAgentState,
) -> MotionAgentState:

    state.current_stage = (
        "video_generated"
    )


    state.status = (
        MotionWorkflowStatus.COMPLETED
    )


    state.error = None


    # ========================================================
    # MANAGER-SAFE SERIALIZABLE OUTPUT
    # ========================================================

    state.output = {

        "status":
            "VIDEO_GENERATED",

        "job_id":
            state.job_id,

        "plan_verified":
            state.plan_verified,

        "execution_spec_verified":
            state.execution_spec_verified,

        "motion_llm_provider":
            state.motion_llm_provider,

        "motion_llm_model":
            state.motion_llm_model,

        "video_gateway":
            state.selected_video_gateway,

        "video_provider":
            state.selected_video_provider,

        "video_model":
            state.selected_video_model,

        "video_tool":
            state.selected_video_tool,

        "generated_video":
            state.generated_video,

        "generated_shots":
            state.generated_shots,

        "video_verified":
            state.video_verified,

        "generation_attempt":
            state.video_generation_attempt,

    }


    print()

    print(
        "[MOTION AGENT] "
        "Cloud video generation = SUCCESS"
    )

    print(
        "[MOTION AGENT] "
        f"Generated video = "
        f"{state.generated_video}"
    )


    return state
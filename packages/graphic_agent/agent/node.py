"""
Graphic Agent Nodes

Loop Engineering principle:

একটি giant function-এর ভিতরে সব logic না রেখে
workflow-কে ছোট deterministic nodes-এ ভাগ করা হচ্ছে।

Phase-1 Nodes:

    Receive Node
        ↓
    Validate Node
        ↓
    ACK Node

Future:

    Interpret Plan
        ↓
    Select Tool
        ↓
    Execute
        ↓
    Verify
        ↓
    Repair
"""

from __future__ import annotations

import json
from pathlib import Path

# ============================================================
# IMPORTS & RULES
# ============================================================

from packages.graphic_agent.compiler.normalize_plan import (
    normalize_planner_plan,
)
from packages.graphic_agent.domain.rules import (
    validate_received_plan,
)
from packages.graphic_agent.domain.state import (
    GraphicAgentState,
    GraphicWorkflowStatus,
)
from packages.graphic_agent.providers.higgsfield_models import (
    resolve_higgsfield_image_model,
)
from packages.graphic_agent.tools.fallback_router import (
    select_jsx_fallback_tool,
)
from packages.graphic_agent.tools.jsx.illustrator_jsx import (
    IllustratorJSXGenerator,
)
from packages.graphic_agent.tools.jsx.photoshop_jsx import (
    PhotoshopJSXGenerator,
)
from packages.graphic_agent.tools.registry import (
    get_tool,
)
from packages.graphic_agent.verifier.fallback_file_verifier import (
    verify_jsx_file,
)

from packages.graphic_agent.artifacts.format_router import (
    build_graphic_artifact,
)


# ============================================================
# NODE 1 — RECEIVE PLANNER PLAN
# ============================================================

def receive_plan_node(
    state: GraphicAgentState,
) -> GraphicAgentState:
    """
    Manager থেকে আসা Planner output receive করে।
    """

    state.current_stage = "plan_received"
    state.status = GraphicWorkflowStatus.RECEIVED

    print()
    print("=" * 70)
    print(
        "[GRAPHIC AGENT] Planner plan received from Manager"
    )
    print(
        f"[GRAPHIC AGENT] Job ID: {state.job_id}"
    )
    print()
    print(
        "[GRAPHIC AGENT] Received Planner Plan:"
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
    state: GraphicAgentState,
) -> GraphicAgentState:
    """
    Communication integrity validation.
    """

    state.current_stage = "validating_plan"
    state.status = GraphicWorkflowStatus.VALIDATING
    state.validation_attempt += 1

    print()
    print(
        "[GRAPHIC AGENT] Validation attempt "
        f"{state.validation_attempt}/"
        f"{state.max_validation_attempts}"
    )

    errors = validate_received_plan(
        state.planner_plan
    )

    state.validation_errors = errors
    state.plan_verified = not bool(errors)

    if state.plan_verified:
        print(
            "[GRAPHIC AGENT] Planner plan validation = PASS"
        )
    else:
        print(
            "[GRAPHIC AGENT] Planner plan validation = FAIL"
        )
        for error in errors:
            print(
                f"[GRAPHIC AGENT] Validation error: {error}"
            )

    return state


# ============================================================
# NODE 3 — SUCCESS ACKNOWLEDGEMENT
# ============================================================

def acknowledge_plan_node(
    state: GraphicAgentState,
) -> GraphicAgentState:
    """
    Manager-কে Phase-1 acknowledgement তৈরি করে।
    """

    state.current_stage = "plan_accepted"
    state.status = GraphicWorkflowStatus.COMPLETED
    state.error = None

    state.output = {
        "status": "RECEIVED",
        "message": (
            "Graphic Agent successfully received "
            "and validated the Planner plan."
        ),
        "job_id": state.job_id,
        "plan_verified": True,
        "validation_attempt": (
            state.validation_attempt
        ),
    }

    print()
    print(
        "[GRAPHIC AGENT] Planner plan accepted."
    )
    print(
        "[GRAPHIC AGENT] Phase-1 communication = SUCCESS"
    )

    return state


# ============================================================
# NODE — BUILD IMAGE GENERATION PROMPT
# ============================================================

def build_generation_prompt_node(
    state: GraphicAgentState,
) -> GraphicAgentState:

    state.current_stage = (
        "building_generation_prompt"
    )

    print(
        "[GRAPHIC AGENT] "
        "Building image prompt from Planner plan"
    )

    state.generation_prompt = (
        "Create the following graphic design "
        "according to this structured execution plan.\n\n"
        + json.dumps(
            state.planner_plan,
            indent=2,
            ensure_ascii=False,
        )
        + "\n\n"
        "Generate one polished final image. "
        "Follow the supplied composition, style, "
        "content, colors, typography and requirements."
    )

    return state


# ============================================================
# NODE — VALIDATE / RESOLVE IMAGE MODEL
# ============================================================

def validate_image_model_node(
    state: GraphicAgentState,
) -> GraphicAgentState:
    """
    Validate frontend-selected image-generation model.
    """

    print()
    print(
        "[GRAPHIC AGENT] "
        "Validating selected image model..."
    )

    model = resolve_higgsfield_image_model(
        state.selected_image_model
    )

    state.selected_image_model = (
        model.model_id
    )

    state.selected_image_provider = (
        "higgsfield"
    )

    state.selected_image_job_type = (
        model.job_type
    )

    print(
        "[GRAPHIC AGENT] "
        f"Image model = {model.display_name}"
    )

    print(
        "[GRAPHIC AGENT] "
        f"Image job type = {model.job_type}"
    )

    print(
        "[GRAPHIC AGENT] "
        "Image model validation = PASS"
    )

    return state


# ============================================================
# NODE — SELECT GRAPHIC TOOL
# ============================================================

def select_tool_node(
    state: GraphicAgentState,
) -> GraphicAgentState:

    state.current_stage = (
        "selecting_tool"
    )

    if (
        state.selected_image_provider
        ==
        "higgsfield"
    ):
        state.selected_tool = (
            "higgsfield_image"
        )
    else:
        raise ValueError(
            "Unsupported image generation provider: "
            f"{state.selected_image_provider!r}"
        )

    print(
        "[GRAPHIC AGENT] "
        f"Selected tool = {state.selected_tool}"
    )

    return state


# ============================================================
# NODE — EXECUTE GRAPHIC TOOL
# ============================================================

def execute_tool_node(
    state: GraphicAgentState,
) -> GraphicAgentState:

    state.current_stage = "generating_image"
    state.generation_attempt += 1

    print(
        "[GRAPHIC AGENT] Generation attempt "
        f"{state.generation_attempt}/"
        f"{state.max_generation_attempts}"
    )

    tool = get_tool(
        state.selected_tool
    )

    result = tool.execute({
        "job_id": state.job_id,
        "prompt": state.generation_prompt,
        "image_model": state.selected_image_model,
        "image_job_type": state.selected_image_job_type,
    })

    state.tool_result = result

    state.generated_file = (
        (result.get("output_path") or result.get("result_url")) if result else None
    )

    target_output_format = "jpg"
    if (
        state.execution_spec is not None
        and getattr(state.execution_spec, "target_output_format", None)
    ):
        target_output_format = state.execution_spec.target_output_format
    elif isinstance(state.planner_plan, dict):
        target_output_format = (
            state.planner_plan.get("target_output_format")
            or state.planner_plan.get("output_format")
            or target_output_format
        )

    req_lower = (state.original_user_request or "").lower()
    if ".psd" in req_lower or " psd" in req_lower or "psd format" in req_lower or "photoshop" in req_lower:
        target_output_format = "psd"
    elif ".ai" in req_lower or " illustrator" in req_lower or " ai format" in req_lower:
        target_output_format = "ai"
    elif ".svg" in req_lower or " svg" in req_lower or "svg format" in req_lower or "vector" in req_lower:
        target_output_format = "svg"

    artifact = build_graphic_artifact(
        job_id=state.job_id,
        source_path=state.generated_file,
        target_output_format=target_output_format,
        allow_raster_conversion=False,
    )

    # ============================================================
    # NEW:
    # FINAL OUTPUT CONTRACT
    # ============================================================

    state.output = {
        "message": (
            "Graphic artifact generated successfully."
        ),
    "artifact": artifact,
}


    print(
        "[GRAPHIC AGENT] Tool execution completed"
    )

    print(
        f"[GRAPHIC AGENT] Generated file: "
        f"{state.generated_file}"
    )

    return state


# ============================================================
# NODE — VERIFY GENERATED FILE
# ============================================================

def verify_generated_file_node(
    state: GraphicAgentState,
) -> GraphicAgentState:

    state.current_stage = "verifying_generated_file"

    if not state.generated_file:
        state.error = (
            "Graphic tool returned no output file."
        )
        print(
            "[GRAPHIC AGENT] Generated image file = FAIL"
        )
        print(
            f"[GRAPHIC AGENT] ERROR: {state.error}"
        )
        return state

    if state.generated_file and str(state.generated_file).startswith(("http://", "https://")):
        print(
            "[GRAPHIC AGENT] Generated image web URL = PASS"
        )
        state.error = None
        return state

    path = Path(
        state.generated_file
    )

    if (
        not path.exists()
        or path.stat().st_size <= 0
    ):
        state.error = (
            "Generated image file does not exist "
            "or is empty."
        )
        print(
            "[GRAPHIC AGENT] Generated image file = FAIL"
        )
        print(
            f"[GRAPHIC AGENT] ERROR: {state.error}"
        )
        return state

    state.error = None

    print(
        "[GRAPHIC AGENT] Generated image file = PASS"
    )

    return state


# ============================================================
# NODE — SELECT JSX FALLBACK
# ============================================================

def select_jsx_fallback_node(
    state: GraphicAgentState,
) -> GraphicAgentState:

    state.current_stage = "selecting_jsx_fallback"

    state.fallback_tool = (
        select_jsx_fallback_tool(
            state.planner_plan
        )
    )

    state.fallback_used = True

    print(
        "[GRAPHIC AGENT] JSX fallback selected: "
        f"{state.fallback_tool}"
    )

    return state


# ============================================================
# NODE — GENERATE JSX FALLBACK FILE
# ============================================================

def generate_jsx_fallback_node(
    state: GraphicAgentState,
) -> GraphicAgentState:

    state.current_stage = "generating_jsx_fallback"

    # 1. Normalize Planner Plan
    state.execution_spec = normalize_planner_plan(
        state.planner_plan
    )

    print(
        "[GRAPHIC AGENT] "
        "Planner plan normalized into GraphicExecutionSpec"
    )

    print(
        "[GRAPHIC AGENT] "
        f"Document = "
        f"{state.execution_spec.document.width}x"
        f"{state.execution_spec.document.height}"
    )

    print(
        "[GRAPHIC AGENT] "
        f"Layers = "
        f"{len(state.execution_spec.layers)}"
    )

    # 2. Fallback Output Directory
    fallback_dir = (
        Path("runtime-data")
        / "graphic_agent"
        / state.job_id
        / "fallback"
    )

    # 3. Select Software-Specific Generator
    if state.fallback_tool == "illustrator_jsx":
        generator = IllustratorJSXGenerator()
        output_path = (
            fallback_dir
            / "illustrator_design.jsx"
        )
    elif state.fallback_tool == "photoshop_jsx":
        generator = PhotoshopJSXGenerator()
        output_path = (
            fallback_dir
            / "photoshop_design.jsx"
        )
    else:
        raise RuntimeError(
            "No valid JSX fallback tool selected."
        )

    # 4. Generate JSX
    result = generator.generate(
        job_id=state.job_id,
        planner_plan=state.planner_plan,
        execution_spec=state.execution_spec,
        output_path=output_path,
    )

    # 5. Save Result
    state.fallback_file = result.get(
        "output_path"
    )

    if not state.fallback_file:
        raise RuntimeError(
            "JSX generator returned no output path."
        )

    print(
        "[GRAPHIC AGENT] "
        f"JSX fallback generated: "
        f"{state.fallback_file}"
    )

    return state


# ============================================================
# NODE — VERIFY JSX FALLBACK FILE
# ============================================================

def verify_jsx_fallback_node(
    state: GraphicAgentState,
) -> GraphicAgentState:
    """
    Verify generated JSX fallback file.

    IMPORTANT:

    This node does NOT:
    - generate JSX
    - modify Planner plan
    - select fallback tool
    - execute Higgsfield

    It only verifies the already-generated fallback file.
    """

    state.current_stage = (
        "verifying_jsx_fallback"
    )


    # ========================================================
    # VERIFY FALLBACK FILE
    # ========================================================

    state.fallback_verified = (
        verify_jsx_file(
            state.fallback_file or ""
        )
    )


    # ========================================================
    # FAILED
    # ========================================================

    if not state.fallback_verified:

        state.error = (
            "Generated JSX fallback file "
            "verification failed."
        )


        print(
            "[GRAPHIC AGENT] "
            "JSX fallback verification = FAIL"
        )


        return state


    # ========================================================
    # SUCCESS
    # ========================================================

    state.error = None


    print(
        "[GRAPHIC AGENT] "
        "JSX fallback verification = PASS"
    )


    return state    

# ============================================================
# NODE 4 — FAILURE
# ============================================================

def fail_plan_node(
    state: GraphicAgentState,
) -> GraphicAgentState:
    """
    Retry limit শেষ হলে workflow fail করে।
    """

    state.current_stage = "plan_validation_failed"

    state.status = GraphicWorkflowStatus.FAILED

    state.plan_verified = False

    state.error = (
        "; ".join(state.validation_errors)
        or
        "Planner plan validation failed."
    )

    state.output = None

    print()

    print(
        "[GRAPHIC AGENT] Validation retry limit reached."
    )

    print(
        f"[GRAPHIC AGENT] ERROR: {state.error}"
    )

    return state    



# """
# Graphic Agent Nodes

# Loop Engineering principle:

# একটি giant function-এর ভিতরে সব logic না রেখে
# workflow-কে ছোট deterministic nodes-এ ভাগ করা হচ্ছে।

# Phase-1 Nodes:

#     Receive Node
#         ↓
#     Validate Node
#         ↓
#     ACK Node

# Future:

#     Interpret Plan
#         ↓
#     Select Tool
#         ↓
#     Execute
#         ↓
#     Verify
#         ↓
#     Repair
# """

# from __future__ import annotations

# import json

# from packages.graphic_agent.domain.rules import (
#     validate_received_plan,
# )

# from packages.graphic_agent.domain.state import (
#     GraphicAgentState,
#     GraphicWorkflowStatus,
# )

# from packages.graphic_agent.agent.registry import (
#     get_tool,
# )


# # ============================================================
# # NODE 1 — RECEIVE PLANNER PLAN
# # ============================================================

# def receive_plan_node(
#     state: GraphicAgentState,
# ) -> GraphicAgentState:
#     """
#     Manager থেকে আসা Planner output receive করে।

#     Phase-1 debugging-এর জন্য complete plan terminal-এ print হবে.
#     """

#     state.current_stage = "plan_received"

#     state.status = GraphicWorkflowStatus.RECEIVED

#     print()

#     print("=" * 70)

#     print(
#         "[GRAPHIC AGENT] Planner plan received from Manager"
#     )

#     print(
#         f"[GRAPHIC AGENT] Job ID: {state.job_id}"
#     )

#     print()

#     print(
#         "[GRAPHIC AGENT] Received Planner Plan:"
#     )

#     print(
#         json.dumps(
#             state.planner_plan,
#             indent=2,
#             ensure_ascii=False,
#         )
#     )

#     print("=" * 70)

#     return state


# # ============================================================
# # NODE 2 — VALIDATE RECEIVED PLAN
# # ============================================================

# def validate_plan_node(
#     state: GraphicAgentState,
# ) -> GraphicAgentState:
#     """
#     Communication integrity validation.

#     IMPORTANT:
#     Design quality verify করছে না।
#     শুধু usable planner payload পেয়েছে কিনা check করছে।
#     """

#     state.current_stage = "validating_plan"

#     state.status = GraphicWorkflowStatus.VALIDATING

#     state.validation_attempt += 1

#     print()

#     print(
#         "[GRAPHIC AGENT] Validation attempt "
#         f"{state.validation_attempt}/"
#         f"{state.max_validation_attempts}"
#     )

#     errors = validate_received_plan(
#         state.planner_plan
#     )

#     state.validation_errors = errors

#     state.plan_verified = not bool(errors)

#     if state.plan_verified:

#         print(
#             "[GRAPHIC AGENT] Planner plan validation = PASS"
#         )

#     else:

#         print(
#             "[GRAPHIC AGENT] Planner plan validation = FAIL"
#         )

#         for error in errors:

#             print(
#                 f"[GRAPHIC AGENT] Validation error: {error}"
#             )

#     return state


# # ============================================================
# # NODE 3 — SUCCESS ACKNOWLEDGEMENT
# # ============================================================

# def acknowledge_plan_node(
#     state: GraphicAgentState,
# ) -> GraphicAgentState:
#     """
#     Manager-কে Phase-1 acknowledgement তৈরি করে।
#     """

#     state.current_stage = "plan_accepted"

#     state.status = GraphicWorkflowStatus.COMPLETED

#     state.error = None

#     state.output = {
#         "status": "RECEIVED",
#         "message": (
#             "Graphic Agent successfully received "
#             "and validated the Planner plan."
#         ),
#         "job_id": state.job_id,
#         "plan_verified": True,
#         "validation_attempt": (
#             state.validation_attempt
#         ),
#     }

#     print()

#     print(
#         "[GRAPHIC AGENT] Planner plan accepted."
#     )

#     print(
#         "[GRAPHIC AGENT] Phase-1 communication = SUCCESS"
#     )

#     return state


# # ============================================================
# # NODE — BUILD IMAGE GENERATION PROMPT
# # ============================================================

# def build_generation_prompt_node(
#     state: GraphicAgentState,
# ) -> GraphicAgentState:

#     state.current_stage = (
#         "building_generation_prompt"
#     )

#     print(
#         "[GRAPHIC AGENT] "
#         "Building image prompt from Planner plan"
#     )

#     # Phase-2 deterministic conversion.
#     #
#     # Future phase:
#     # Graphic Agent LLM এই plan interpret করে
#     # better tool-specific prompt তৈরি করবে.

#     state.generation_prompt = (
#         "Create the following graphic design "
#         "according to this structured execution plan.\n\n"
#         + json.dumps(
#             state.planner_plan,
#             indent=2,
#             ensure_ascii=False,
#         )
#         + "\n\n"
#         "Generate one polished final image. "
#         "Follow the supplied composition, style, "
#         "content, colors, typography and requirements."
#     )

#     return state


#     # ============================================================
# # NODE — SELECT TOOL
# # ============================================================

# def select_tool_node(
#     state: GraphicAgentState,
# ) -> GraphicAgentState:

#     state.current_stage = "selecting_tool"

#     # --------------------------------------------------------
#     # PHASE-2 TEST:
#     #
#     # Only one registered generation tool exists.
#     #
#     # Future:
#     # Graphic Agent LLM / routing logic will choose:
#     #
#     # nano_banana
#     # photoshop
#     # illustrator
#     # canva
#     # stitch
#     # --------------------------------------------------------

#     state.selected_tool = "nano_banana"

#     print(
#         "[GRAPHIC AGENT] "
#         "Selected tool = nano_banana"
#     )

#     return state


# # ============================================================
# # NODE — EXECUTE GRAPHIC TOOL
# # ============================================================

# def execute_tool_node(
#     state: GraphicAgentState,
# ) -> GraphicAgentState:

#     state.current_stage = "generating_image"

#     state.generation_attempt += 1

#     print(
#         "[GRAPHIC AGENT] Generation attempt "
#         f"{state.generation_attempt}/"
#         f"{state.max_generation_attempts}"
#     )

#     tool = get_tool(
#         state.selected_tool
#     )

#     result = tool.execute({

#         "job_id":
#             state.job_id,

#         "prompt":
#             state.generation_prompt,
#     })

#     state.tool_result = result

#     state.generated_file = (
#         result.get("output_path")
#     )

#     print(
#         "[GRAPHIC AGENT] Tool execution completed"
#     )

#     print(
#         f"[GRAPHIC AGENT] Generated file: "
#         f"{state.generated_file}"
#     )

#     return state


# # ============================================================
# # NODE 4 — FAILURE
# # ============================================================

# def fail_plan_node(
#     state: GraphicAgentState,
# ) -> GraphicAgentState:
#     """
#     Retry limit শেষ হলে workflow fail করে।
#     """

#     state.current_stage = "plan_validation_failed"

#     state.status = GraphicWorkflowStatus.FAILED

#     state.plan_verified = False

#     state.error = (
#         "; ".join(state.validation_errors)
#         or
#         "Planner plan validation failed."
#     )

#     state.output = None

#     print()

#     print(
#         "[GRAPHIC AGENT] Validation retry limit reached."
#     )

#     print(
#         f"[GRAPHIC AGENT] ERROR: {state.error}"
#     )

#     return state

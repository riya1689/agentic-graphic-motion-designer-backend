# packages/prompt_to_json_agent/api/router.py
#
# Purpose:
# Prompt-to-JSON Agent-কে দুইভাবে expose করা:
#
# 1. /prompt-to-json/convert
#    → Standalone / direct testing
#
# 2. /prompt-to-json/execute
#    → Manager Agent থেকে task receive করার জন্য
#
# IMPORTANT:
# JSON extraction business logic এক জায়গায় থাকবে।
# /convert এবং /execute দুটো endpoint একই internal function ব্যবহার করবে.


from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional

from ..agent.graph import (
    extraction_graph,
    autofill_loop_graph,
)


# ============================================================
# ROUTER
# ============================================================

router = APIRouter(
    prefix="/prompt-to-json",
    tags=["Prompt To JSON Agent"],
)


# ============================================================
# STANDALONE REQUEST MODEL
# ============================================================

class PromptConversionRequest(BaseModel):
    """
    Existing standalone API request.

    Example:
    POST /prompt-to-json/convert
    """

    asset_type: str = Field(
        ...,
        example="image",
    )

    prompt: str = Field(
        ...,
        example="Brand: Apex, Cyberpunk style",
    )

    auto_complete_missing: bool = Field(
        default=True,
    )


# ============================================================
# STANDALONE RESPONSE MODEL
# ============================================================

class PromptConversionResponse(BaseModel):

    success: bool

    is_complete: bool

    spec: Optional[Dict[str, Any]] = None

    missing_fields: Optional[list] = None


# ============================================================
# MANAGER REQUEST MODEL
# ============================================================

class ManagerPromptRequest(BaseModel):
    """
    Manager Agent থেকে আসা request.

    job_id:
        Manager-created workflow/job ID

    prompt:
        Original user prompt

    asset_type:
        Phase-1 default = image

        পরে Manager অথবা previous routing logic
        এটা dynamically দিতে পারবে.

    auto_complete_missing:
        Existing JSON Agent behaviour preserve করা হয়েছে.
    """

    job_id: str

    prompt: str

    asset_type: str = "image"

    auto_complete_missing: bool = True


# ============================================================
# SHARED CONVERSION FUNCTION
# ============================================================

def run_prompt_conversion(
    asset_type: str,
    prompt: str,
    auto_complete_missing: bool = True,
) -> Dict[str, Any]:
    """
    Prompt-to-JSON Agent-এর actual business logic.

    IMPORTANT:
    /convert এবং /execute উভয় endpoint এই function ব্যবহার করবে।

    তাই:
        - extraction logic duplicate হবে না
        - existing behaviour preserve হবে
        - Manager integration clean থাকবে
    """

    # --------------------------------------------------------
    # Existing prompt format preserve করা হচ্ছে
    # --------------------------------------------------------

    full_prompt = (
        f"type: {asset_type}\n"
        f"{prompt}"
    )

    # --------------------------------------------------------
    # Initial LangGraph state
    # --------------------------------------------------------

    state = {
        "raw_prompt": full_prompt,

        "max_retries": 4,

        "extraction_attempt_count": 0,

        "coverage_complete": False,

        "coverage_missing_requirements": [],

        "coverage_notes": [],

        "extracted_spec": None,

        "missing_fields": [],

        "user_wants_ai_autofill": auto_complete_missing,

        "autofill_attempt_count": 0,

        "validation_errors": [],

        "is_complete": False,

        "final_output": None,
    }

    # ========================================================
    # STEP 1
    # EXTRACTION + COVERAGE
    # ========================================================

    extraction_result = extraction_graph.invoke(state)

    state.update(extraction_result)

    # --------------------------------------------------------
    # Coverage check
    # --------------------------------------------------------

    if not state.get("coverage_complete", False):

        raise ValueError(
            "Coverage verification failed to capture "
            "all prompt requirements."
        )

    # ========================================================
    # STEP 2
    # OPTIONAL AUTOFILL
    # ========================================================

    if (
        state.get("missing_fields")
        and auto_complete_missing
    ):

        autofill_result = autofill_loop_graph.invoke(state)

        state.update(autofill_result)

    # ========================================================
    # STEP 3
    # GET FINAL SPEC
    # ========================================================

    final_spec = (
        state.get("final_output")
        or state.get("extracted_spec")
    )

    # --------------------------------------------------------
    # Pydantic model হলে dict-এ convert করো
    # --------------------------------------------------------

    if hasattr(final_spec, "model_dump"):
        final_spec = final_spec.model_dump()

    # ========================================================
    # NORMALIZED RESULT
    # ========================================================

    return {
        "is_complete": state.get(
            "is_complete",
            False,
        ),

        "spec": final_spec,

        "missing_fields": state.get(
            "missing_fields",
            [],
        ),
    }


# ============================================================
# EXISTING STANDALONE ENDPOINT
# ============================================================

@router.post(
    "/convert",
    response_model=PromptConversionResponse,
)
async def convert_prompt(
    req: PromptConversionRequest,
):
    """
    Existing standalone Prompt-to-JSON endpoint.

    এই endpoint আগের মতোই ব্যবহার করা যাবে.
    """

    print("\n" + "=" * 60)
    print("[JSON AGENT] Standalone request received")
    print(f"[JSON AGENT] Asset type: {req.asset_type}")
    print(f"[JSON AGENT] Prompt: {req.prompt}")
    print("[JSON AGENT] Running conversion...")

    try:

        result = run_prompt_conversion(
            asset_type=req.asset_type,
            prompt=req.prompt,
            auto_complete_missing=req.auto_complete_missing,
        )

        print("[JSON AGENT] Conversion completed successfully")
        print("=" * 60 + "\n")

        return PromptConversionResponse(
            success=True,

            is_complete=result["is_complete"],

            spec=result["spec"],

            missing_fields=result["missing_fields"],
        )

    except ValueError as exc:

        print(
            f"[JSON AGENT] Conversion failed: {exc}"
        )

        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )

    except Exception as exc:

        print(
            f"[JSON AGENT] Unexpected error: {exc}"
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )


# ============================================================
# MANAGER AGENT ENDPOINT
# ============================================================

@router.post("/execute")
async def execute_prompt_to_json(
    request: ManagerPromptRequest,
):
    """
    Manager Agent এই endpoint call করবে.

    Flow:

    Manager
       ↓
    /execute
       ↓
    Prompt-to-JSON Graph
       ↓
    JSON Result
       ↓
    Manager
    """

    print("\n" + "=" * 60)
    print("[JSON AGENT] Task received from Manager")
    print(f"[JSON AGENT] Job ID: {request.job_id}")
    print(f"[JSON AGENT] Prompt: {request.prompt}")
    print(
        f"[JSON AGENT] Asset type: "
        f"{request.asset_type}"
    )

    try:

        # ====================================================
        # JSON AGENT STARTED
        # ====================================================

        print(
            "[JSON AGENT] Status = RUNNING"
        )

        print(
            "[JSON AGENT] Running prompt conversion..."
        )

        # ====================================================
        # CALL SAME EXISTING BUSINESS LOGIC
        # ====================================================

        result = run_prompt_conversion(
            asset_type=request.asset_type,
            prompt=request.prompt,
            auto_complete_missing=(
                request.auto_complete_missing
            ),
        )

        # ====================================================
        # COMPLETED
        # ====================================================

        print(
            "[JSON AGENT] Conversion completed"
        )

        print(
            "[JSON AGENT] Status = COMPLETED"
        )

        print(
            "[JSON AGENT] Sending result back to Manager"
        )

        print("=" * 60 + "\n")

        # ====================================================
        # STANDARD MANAGER RESPONSE CONTRACT
        # ====================================================

        return {
            "success": True,

            "agent_id": "prompt_to_json_agent",

            "job_id": request.job_id,

            "output": {
                "is_complete": result[
                    "is_complete"
                ],

                "spec": result[
                    "spec"
                ],

                "missing_fields": result[
                    "missing_fields"
                ],
            },
        }

    except Exception as exc:

        # ====================================================
        # FAILURE RESPONSE
        # ====================================================

        print(
            f"[JSON AGENT] FAILED: {exc}"
        )

        print(
            "[JSON AGENT] Sending failure "
            "response back to Manager"
        )

        print("=" * 60 + "\n")

        return {
            "success": False,

            "agent_id": "prompt_to_json_agent",

            "job_id": request.job_id,

            "output": None,

            "error": str(exc),
        }
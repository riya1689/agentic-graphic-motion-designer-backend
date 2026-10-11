from __future__ import annotations

# ============================================================
# Planner Agent - FastAPI Router
# ============================================================
#
# FILE:
# packages/planner_agent/api/router.py
#
#
# PURPOSE:
#
# This file is ONLY the HTTP/API boundary for Planner Agent.
#
# Responsibilities:
#
#   HTTP Request
#       ↓
#   Build initial PlannerState
#       ↓
#   run_planner()
#       ↓
#   Planner LangGraph runs
#       ↓
#   Return HTTP response
#
#
# IMPORTANT:
#
# This file DOES NOT contain:
#
#   - Gemini prompt logic
#   - planning logic
#   - verification logic
#   - hill-climbing logic
#   - graph edges
#   - asset retrieval
#   - graphic-agent logic
#   - manager-agent logic
#
# Those responsibilities remain isolated in their own layers.
#
# ============================================================


from typing import Any, Dict, Optional
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from packages.planner_agent.agent.graph import run_planner


# ============================================================
# FastAPI Router
# ============================================================

router = APIRouter(
    prefix="/api/planner",
    tags=["Planner Agent"],
)


# ============================================================
# API Request Schema
# ============================================================
#
# This schema represents what an external caller,
# Manager Agent, or standalone API client sends
# to Planner Agent.
#
# IMPORTANT:
#
# This is an API transport schema.
#
# It is NOT Planner's business-domain schema.
#
# Planner's actual final output schema remains:
#
# packages/planner_agent/domain/schema.py
# ============================================================


class PlannerRequest(BaseModel):
    """
    Input accepted by Planner Agent API.
    """

    # --------------------------------------------------------
    # Optional Job ID
    # --------------------------------------------------------
    #
    # Manager can provide its own job ID.
    #
    # If omitted, Planner API creates one automatically.
    # --------------------------------------------------------

    job_id: Optional[str] = None

    # --------------------------------------------------------
    # JSON Agent Output
    # --------------------------------------------------------
    #
    # This is the PRIMARY input for Planner Agent.
    #
    # Example:
    #
    # {
    #     "job_type": "graphic_design",
    #     "requirements": [...],
    #     ...
    # }
    # --------------------------------------------------------

    json_agent_output: Dict[str, Any] = Field(
        ...,
        description=(
            "Structured requirement JSON produced "
            "by prompt_to_json_agent."
        ),
    )

    # --------------------------------------------------------
    # Original User Request
    # --------------------------------------------------------
    #
    # Optional.
    #
    # Planner primarily uses json_agent_output.
    #
    # Original user prompt may help if structured
    # requirements contain ambiguity.
    # --------------------------------------------------------

    original_user_request: Optional[str] = None

    # --------------------------------------------------------
    # Repair Limit
    # --------------------------------------------------------
    #
    # Controls Planner's bounded verification / repair loop.
    #
    # This prevents infinite loops.
    # --------------------------------------------------------

    max_repair_attempts: int = Field(
        default=3,
        ge=0,
        le=10,
    )


# ============================================================
# API Response Schema
# ============================================================


class PlannerResponse(BaseModel):
    """
    Stable response contract exposed by Planner API.
    """

    success: bool

    job_id: str

    status: str

    final_output: Optional[Dict[str, Any]] = None

    error: Optional[str] = None

    # Useful observability information.
    planning_iteration: int = 0

    repair_attempt: int = 0

    verification_score: float = 0.0

    best_score: float = 0.0


# ============================================================
# Health Endpoint
# ============================================================


@router.get("/health")
def planner_health() -> Dict[str, Any]:
    """
    Lightweight health endpoint.

    IMPORTANT:
    This does NOT call Gemini.

    Therefore checking Planner API health does not consume
    LLM tokens.
    """

    return {
        "success": True,
        "agent": "planner_agent",
        "status": "ready",
    }


# ============================================================
# Planner Execution Endpoint
# ============================================================


@router.post(
    "/execute",
    response_model=PlannerResponse,
)
def create_plan(
    request: PlannerRequest,
) -> PlannerResponse:
    """
    Run Planner Agent.

    FLOW:

        HTTP / Manager request
              ↓
        create initial state
              ↓
        run_planner()
              ↓
        LangGraph execution
              ↓
        validation
              ↓
        semantic verification
              ↓
        repair / hill-climbing if needed
              ↓
        final result
              ↓
        HTTP response


    IMPORTANT:

    The API layer does not control the internal loop.

    graph.py controls the loop.

    This keeps HTTP transport logic separate from
    Planner Agent workflow logic.
    """

    # --------------------------------------------------------
    # Generate Job ID if Manager did not provide one.
    # --------------------------------------------------------

    job_id = (
        request.job_id
        or f"planner_{uuid4().hex}"
    )

    print()
    print("=" * 70)
    print(
        f"[PLANNER API] Request received: {job_id}"
    )
    print("=" * 70)

    # ========================================================
    # Build Initial Planner State
    # ========================================================
    #
    # This is the starting state consumed by graph.py.
    #
    # We initialize loop/verification fields here so every
    # Planner execution begins from a predictable state.
    # ========================================================

    initial_state = {

        # Request tracking
        "job_id": job_id,

        # Simulated Manager payload / source context
        "manager_input": {
            "source": "planner_api",
            "job_id": job_id,
            "json_agent_output": (
                request.json_agent_output
            ),
        },

        # Primary Planner input
        "json_agent_output": (
            request.json_agent_output
        ),

        # Optional original user prompt
        "original_user_request": (
            request.original_user_request
        ),

        # ----------------------------------------------------
        # Loop Engineering State
        # ----------------------------------------------------

        "repair_attempt": 0,

        "max_repair_attempts": (
            request.max_repair_attempts
        ),

        "planning_iteration": 0,

        # ----------------------------------------------------
        # Verification / Hill-Climbing State
        # ----------------------------------------------------

        "verification_score": 0.0,

        "verification_feedback": [],

        "best_plan": None,

        "best_score": 0.0,

        # ----------------------------------------------------
        # Validation State
        # ----------------------------------------------------

        "validation_passed": False,

        "validation_errors": [],

        # ----------------------------------------------------
        # Runtime Status
        # ----------------------------------------------------

        "status": "received",

        "current_step": "received",

        "error": None,

        # Debug / observability
        "debug_messages": [],
    }

    # ========================================================
    # Execute Planner Graph
    # ========================================================

    try:

        result = run_planner(
            initial_state
        )

    except Exception as exc:

        print(
            "[PLANNER API] Planner execution error:",
            str(exc),
        )

        # HTTP 500 is reserved for unexpected execution
        # failures at the API/system boundary.
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "job_id": job_id,
                "error": str(exc),
            },
        ) from exc

    # ========================================================
    # Read Final Planner Status
    # ========================================================

    status = result.get(
        "status",
        "failed",
    )

    success = (
        status == "completed"
        and result.get("final_output") is not None
    )

    # --------------------------------------------------------
    # Terminal visibility
    # --------------------------------------------------------

    if success:

        print(
            f"[PLANNER API] Planner completed: {job_id}"
        )

        print(
            "[PLANNER API] Verification score:",
            result.get(
                "verification_score",
                0.0,
            ),
        )

    else:

        print(
            f"[PLANNER API] Planner failed: {job_id}"
        )

        print(
            "[PLANNER API] Error:",
            result.get("error"),
        )

    print("=" * 70)

    # ========================================================
    # Return Stable API Response
    # ========================================================

    return PlannerResponse(

        success=success,

        job_id=job_id,

        status=status,

        final_output=result.get(
            "final_output"
        ),

        error=result.get(
            "error"
        ),

        planning_iteration=result.get(
            "planning_iteration",
            0,
        ),

        repair_attempt=result.get(
            "repair_attempt",
            0,
        ),

        verification_score=result.get(
            "verification_score",
            0.0,
        ),

        best_score=result.get(
            "best_score",
            0.0,
        ),
    )
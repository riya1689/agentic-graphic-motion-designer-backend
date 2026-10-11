"""
Manager Agent API

User সরাসরি worker agent-এর কাছে যাবে না।

User:
    ↓
Manager API:
    ↓
Manager Workflow
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from packages.manager_agent.orchestrator.workflow import (
    get_job,
    run_manager_workflow,
)


from packages.manager_agent.api.schemas import (
    ManagerPublicResponse,
)

from packages.manager_agent.api.presenter import (
    present_manager_response,
)


# ============================================================
# ROUTER
# ============================================================

router = APIRouter(
    prefix="/manager",
    tags=["Manager Agent"],
)


# ============================================================
# REQUEST MODEL
# ============================================================

class ManagerExecuteRequest(BaseModel):
    prompt: str
    selected_image_model: str | None = None
    selected_video_model: str | None = None


# ============================================================
# START MANAGER WORKFLOW
# ============================================================

# @router.post("/execute")
@router.post(
    "/execute",
    response_model=ManagerPublicResponse,
)
async def execute_manager(
    request: ManagerExecuteRequest,
):
    """
    User prompt গ্রহণ করে Manager workflow start করে।
    """

    state = await run_manager_workflow(
        user_prompt=request.prompt,
        selected_image_model=request.selected_image_model,
        selected_video_model=request.selected_video_model,
    )

# ============================================================
# PUBLIC API PRESENTATION
# ============================================================
#
# Manager workflow returns internal state.
#
# Frontend should NOT receive:
#   - planner_plan
#   - agent_tasks
#   - internal artifacts
#   - tool internals
#
# Presenter converts internal workflow state
# into a clean frontend-facing response.
# ============================================================

    return present_manager_response(
    state
)


# ============================================================
# GET JOB STATUS
# ============================================================

@router.get("/jobs/{job_id}")
async def get_manager_job(
    job_id: str,
):
    """
    Manager-এর tracked workflow inspect করার endpoint।
    """

    try:

        state = get_job(job_id)

        return {
            "success": True,
            "job": state.model_dump(),
        }

    except ValueError as exc:

        raise HTTPException(
            status_code=404,
            detail=str(exc),
        )
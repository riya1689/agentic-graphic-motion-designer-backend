"""
Motion Agent API Router

API layer responsibilities:

- HTTP request receive
- MotionTask create
- Motion Agent workflow call
- HTTP-safe response return

IMPORTANT:

No motion business logic belongs here.
"""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter
from pydantic import BaseModel, Field

from packages.motion_agent.agent.graph import (
    run_motion_workflow,
)

from packages.motion_agent.domain.schema import (
    MotionTask,
)


# ============================================================
# ROUTER
# ============================================================

router = APIRouter(
    prefix="/api/motion",
    tags=["motion-agent"],
)


# ============================================================
# API REQUEST CONTRACT
# ============================================================

class MotionExecuteRequest(BaseModel):

    job_id: str

    planner_plan: Dict[str, Any] = Field(
        default_factory=dict
    )

    original_user_request: str = ""

    max_validation_attempts: int = 2


# ============================================================
# EXECUTE
# ============================================================

@router.post("/execute")
async def execute_motion_agent(
    request: MotionExecuteRequest,
):

    try:

        task = MotionTask(

            job_id=
                request.job_id,

            planner_plan=
                request.planner_plan,

            original_user_request=
                request.original_user_request,

            max_validation_attempts=
                request.max_validation_attempts,

        )

        state = run_motion_workflow(
            task
        )

        if state.error:

            return {

                "success":
                    False,

                "job_id":
                    state.job_id,

                "status":
                    state.status.value,

                "error":
                    state.error,

                "output":
                    state.output,

            }

        return {

            "success":
                True,

            "job_id":
                state.job_id,

            "status":
                state.status.value,

            "output":
                state.output,

        }

    except Exception as exc:

        return {

            "success":
                False,

            "error":
                str(exc),

        }


from pathlib import Path
from fastapi.responses import FileResponse

# ============================================================
# SERVE GENERATED VIDEO ARTIFACT
# ============================================================

@router.get("/videos/{job_id}")
async def serve_generated_video(job_id: str):
    raw_dir = Path("runtime-data") / "motion_agent" / job_id / "raw"
    
    if raw_dir.exists():
        video_files = list(raw_dir.glob("*.mp4"))
        if video_files:
            return FileResponse(
                path=video_files[0],
                media_type="video/mp4",
                filename=video_files[0].name,
            )

    raise HTTPException(
        status_code=404,
        detail=f"Generated motion video not found for job_id={job_id}",
    )


# ============================================================
# HEALTH
# ============================================================

@router.get("/health")
async def motion_agent_health():

    return {

        "success": True,

        "service": "motion_agent",

        "status": "ok",

    }
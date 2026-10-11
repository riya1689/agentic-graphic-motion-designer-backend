"""
Graphic Agent API Router

Manager Agent এই endpoint call করবে:

    POST /api/graphic/execute

Phase-1:
    Planner plan receive
    -> internal workflow
    -> acknowledgement
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from fastapi import APIRouter

from packages.graphic_agent.api.schemas import (
    GraphicExecuteRequest,
    GraphicExecuteResponse,
)

from packages.graphic_agent.agent.graph import (
    run_graphic_workflow,
)

from packages.graphic_agent.artifacts.store import (
    load_artifact_record,
)

from packages.graphic_agent.domain.schema import (
    GraphicTask,
)

from packages.graphic_agent.domain.state import (
    GraphicWorkflowStatus,
)


# ============================================================
# ROUTER
# ============================================================

router = APIRouter(

    prefix="/api/graphic",

    tags=[
        "Graphic Agent"
    ],
)


# ============================================================
# EXECUTE
# ============================================================

@router.post(
    "/execute",
    response_model=GraphicExecuteResponse,
)
async def execute_graphic_agent(
    request: GraphicExecuteRequest,
):
    """
    Manager থেকে Planner plan receive করে
    Graphic Agent Phase-1 workflow execute করে।
    """

    print()

    print(
        "[GRAPHIC AGENT API] "
        "Request received from Manager"
    )

    # --------------------------------------------------------
    # API model -> Domain model
    # --------------------------------------------------------

    task = GraphicTask(

        job_id=request.job_id,

        planner_plan=request.planner_plan,

        original_user_request=(
            request.original_user_request
        ),
        selected_image_model=(
        request.selected_image_model
        ),
        max_validation_attempts=(
            request.max_validation_attempts
        ),
    )

    # --------------------------------------------------------
    # Run Graphic Agent workflow
    # --------------------------------------------------------

    state = run_graphic_workflow(
        task
    )

    success = (
        state.status
        ==
        GraphicWorkflowStatus.COMPLETED
    )

    artifact = None
    if state.output:
        artifact = state.output.get(
            "artifact"
        )

    return GraphicExecuteResponse(

        success=success,

        job_id=state.job_id,

        status=state.status.value,

        current_stage=state.current_stage,

        plan_verified=state.plan_verified,

        validation_attempt=(
            state.validation_attempt
        ),

        validation_errors=(
            state.validation_errors
        ),

        output=state.output,

        error=state.error,
    )

from pathlib import Path


def _resolve_graphic_artifact(job_id: str) -> tuple[Path, str, str]:
    try:
        record = load_artifact_record(job_id)
        path = Path(record.absolute_path)
        if path.exists():
            return path, record.mime_type, record.filename
    except Exception:
        pass

    job_dir = Path("runtime-data") / "graphic_agent" / job_id
    if job_dir.exists():
        for ext, mime in [
            (".png", "image/png"),
            (".jpg", "image/jpeg"),
            (".jpeg", "image/jpeg"),
            (".webp", "image/webp"),
            (".gif", "image/gif"),
            (".jsx", "text/plain"),
        ]:
            matches = list(job_dir.rglob(f"*{ext}"))
            if matches:
                target = matches[0]
                return target, mime, target.name

    raise HTTPException(
        status_code=404,
        detail=f"Image artifact not found for job_id={job_id}",
    )


# ============================================================
# PREVIEW ARTIFACT
# ============================================================

@router.get(
    "/artifacts/{job_id}/preview"
)
async def preview_artifact(
    job_id: str,
):
    path, mime_type, filename = _resolve_graphic_artifact(job_id)
    return FileResponse(
        path=str(path),
        media_type=mime_type,
        filename=filename,
    )


# ============================================================
# DOWNLOAD ARTIFACT
# ============================================================

@router.get(
    "/artifacts/{job_id}/download"
)
async def download_artifact(
    job_id: str,
):
    path, mime_type, filename = _resolve_graphic_artifact(job_id)
    return FileResponse(
        path=str(path),
        media_type=mime_type,
        filename=filename,
    )
"""Public API for the new provider-neutral workflow."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from fastapi import APIRouter
from pydantic import BaseModel, Field

from packages.orchestrator.application.orchestrator import Orchestrator


router = APIRouter(prefix="/orchestrator", tags=["Orchestrator"])


class OrchestratorExecuteRequest(BaseModel):
    prompt: str = Field(min_length=1)
    selected_image_model: str | None = None
    selected_video_model: str | None = None
    attachments: list[dict[str, Any]] = Field(default_factory=list)


def _state_response(state) -> dict[str, Any]:
    if state.current_stage.value != "completed":
        return {
            "success": False,
            "request_id": state.request_id,
            "status": "failed",
            "stage": state.current_stage.value,
            "error_code": state.error_code,
            "error": state.error_message,
        }

    outputs = (state.final_output or {}).get("outputs", [])
    first_output = outputs[0] if outputs else {}
    uri = first_output.get("uri")
    output_format = first_output.get("format")
    return {
        "success": True,
        "request_id": state.request_id,
        "status": "completed",
        "message": "Your design request has been completed.",
        "image_url": uri,
        "download_url": first_output.get("download_uri") or uri,
        "artifact_format": output_format,
        "artifact_filename": (
            f"design_{state.request_id}.{output_format}"
            if output_format
            else None
        ),
        "workflow": state.final_output,
    }


def create_router(orchestrator: Orchestrator) -> APIRouter:
    """Create a router bound to one application-composed orchestrator."""
    bound_router = APIRouter(prefix="/orchestrator", tags=["Orchestrator"])

    @bound_router.post("/execute")
    async def execute(request: OrchestratorExecuteRequest):
        request_id = str(uuid4())
        state = orchestrator.run(
            request.prompt,
            request_id=request_id,
            selected_image_model=request.selected_image_model,
            selected_video_model=request.selected_video_model,
            attachments=request.attachments,
        )
        return _state_response(state)

    return bound_router

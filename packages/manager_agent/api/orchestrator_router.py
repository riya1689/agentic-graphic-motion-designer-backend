"""Manager public API backed by the new provider-neutral orchestrator."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, field_validator

from packages.graphic_agent.native_svg import native_svg_path, native_svg_preview_path
from packages.graphic_agent.system_raster import system_raster_path
from packages.graphic_agent.code_svg import code_svg_path
from packages.graphic_agent.image_to_vector import vector_svg_path, vector_svg_preview_path
from packages.graphic_agent.hybrid_svg import hybrid_svg_path, hybrid_svg_preview_path
from packages.orchestrator.application.orchestrator import Orchestrator
from packages.orchestrator.api.router import _state_response


class ManagerExecuteRequest(BaseModel):
    prompt: str = Field(min_length=1)
    selected_image_model: str | None = None
    selected_video_model: str | None = None
    attachments: list[dict[str, Any]] = Field(default_factory=list)

    @field_validator("attachments")
    @classmethod
    def validate_image_attachments(cls, value: list[dict[str, Any]]) -> list[dict[str, Any]]:
        for item in value:
            if not isinstance(item, dict):
                raise ValueError("Each attachment must be an object.")
            mime_type = str(item.get("mime_type") or "")
            uri = str(item.get("uri") or "")
            if mime_type and mime_type not in {"image/png", "image/jpeg", "image/svg+xml"}:
                raise ValueError("Only PNG, JPG, and SVG image uploads are supported.")
            if uri and not uri.startswith("data:image/"):
                raise ValueError("Uploaded image data must use a data:image URI.")
            if len(uri) > 15_000_000:
                raise ValueError("Uploaded image is too large. Maximum size is 10 MB.")
        return value


def create_manager_router(
    orchestrator: Orchestrator,
    *,
    require_auth=None,
) -> APIRouter:
    router = APIRouter(prefix="/manager", tags=["Manager Agent"])

    execute_dependencies = [Depends(require_auth)] if require_auth else []
    @router.post("/execute", dependencies=execute_dependencies)
    async def execute_manager(request: ManagerExecuteRequest):
        state = orchestrator.run(
            request.prompt,
            request_id=str(uuid4()),
            selected_image_model=request.selected_image_model,
            selected_video_model=request.selected_video_model,
            attachments=request.attachments,
        )
        return _state_response(state)

    @router.get("/jobs/{job_id}/preview")
    async def preview_job(job_id: str):
        path = native_svg_path(job_id)
        if not path.exists():
            raise HTTPException(status_code=404, detail="Graphic artifact not found.")
        return FileResponse(path=str(path), media_type="image/svg+xml", filename=path.name)

    @router.get("/jobs/{job_id}/download")
    async def download_job(job_id: str):
        path = native_svg_path(job_id)
        if not path.exists():
            raise HTTPException(status_code=404, detail="Graphic artifact not found.")
        return FileResponse(path=str(path), media_type="image/svg+xml", filename=path.name)

    @router.get("/jobs/{job_id}/preview.png")
    async def preview_png(job_id: str):
        path = native_svg_preview_path(job_id)
        if not path.exists():
            raise HTTPException(status_code=404, detail="PNG preview not found.")
        return FileResponse(path=str(path), media_type="image/png", filename=path.name)

    @router.get("/jobs/{job_id}/system/preview")
    async def system_preview(job_id: str):
        for output_format in ("png", "jpg", "webp"):
            path = system_raster_path(job_id, output_format)
            if path.exists():
                media_type = {"png": "image/png", "jpg": "image/jpeg", "webp": "image/webp"}[output_format]
                return FileResponse(path=str(path), media_type=media_type, filename=path.name)
        raise HTTPException(status_code=404, detail="System raster artifact not found.")

    @router.get("/jobs/{job_id}/system/download")
    async def system_download(job_id: str):
        for output_format in ("png", "jpg", "webp"):
            path = system_raster_path(job_id, output_format)
            if path.exists():
                media_type = {"png": "image/png", "jpg": "image/jpeg", "webp": "image/webp"}[output_format]
                return FileResponse(path=str(path), media_type=media_type, filename=path.name, content_disposition_type="attachment")
        raise HTTPException(status_code=404, detail="System raster artifact not found.")

    @router.get("/jobs/{job_id}/code/preview")
    async def code_preview(job_id: str):
        path = code_svg_path(job_id)
        if not path.exists():
            raise HTTPException(status_code=404, detail="Code Image artifact not found.")
        return FileResponse(path=str(path), media_type="image/svg+xml", filename=path.name)

    @router.get("/jobs/{job_id}/code/download")
    async def code_download(job_id: str):
        path = code_svg_path(job_id)
        if not path.exists():
            raise HTTPException(status_code=404, detail="Code Image artifact not found.")
        return FileResponse(path=str(path), media_type="image/svg+xml", filename=path.name, content_disposition_type="attachment")

    @router.get("/jobs/{job_id}/vector/preview")
    async def vector_preview(job_id: str):
        path = vector_svg_path(job_id)
        if not path.exists():
            raise HTTPException(status_code=404, detail="Image-to-vector artifact not found.")
        return FileResponse(path=str(path), media_type="image/svg+xml", filename=path.name)

    @router.get("/jobs/{job_id}/vector/download")
    async def vector_download(job_id: str):
        path = vector_svg_path(job_id)
        if not path.exists():
            raise HTTPException(status_code=404, detail="Image-to-vector artifact not found.")
        return FileResponse(path=str(path), media_type="image/svg+xml", filename=path.name, content_disposition_type="attachment")

    @router.get("/jobs/{job_id}/vector/preview.png")
    async def vector_preview_png(job_id: str):
        path = vector_svg_preview_path(job_id)
        if not path.exists():
            raise HTTPException(status_code=404, detail="Image-to-vector preview not found.")
        return FileResponse(path=str(path), media_type="image/png", filename=path.name)

    @router.get("/jobs/{job_id}/hybrid/preview")
    async def hybrid_preview(job_id: str):
        path = hybrid_svg_path(job_id)
        if not path.exists():
            raise HTTPException(status_code=404, detail="Hybrid SVG artifact not found.")
        return FileResponse(path=str(path), media_type="image/svg+xml", filename=path.name)

    @router.get("/jobs/{job_id}/hybrid/download")
    async def hybrid_download(job_id: str):
        path = hybrid_svg_path(job_id)
        if not path.exists():
            raise HTTPException(status_code=404, detail="Hybrid SVG artifact not found.")
        return FileResponse(path=str(path), media_type="image/svg+xml", filename=path.name, content_disposition_type="attachment")

    @router.get("/jobs/{job_id}/hybrid/preview.png")
    async def hybrid_preview_png(job_id: str):
        path = hybrid_svg_preview_path(job_id)
        if not path.exists():
            raise HTTPException(status_code=404, detail="Hybrid SVG preview not found.")
        return FileResponse(path=str(path), media_type="image/png", filename=path.name)

    return router

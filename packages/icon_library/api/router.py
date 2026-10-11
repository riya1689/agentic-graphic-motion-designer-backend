"""Provider-neutral FastAPI routes for the Icon Library."""

from __future__ import annotations

import base64
import binascii
from typing import Any, Callable
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field, field_validator

from packages.icon_library.application.service import IconLibraryService
from packages.icon_library.domain.models import IconRecord, IconSearchQuery, IconSource
from packages.icon_library.ports import IconNotFoundError


MAX_SVG_BYTES = 10 * 1024 * 1024


class IconResponse(BaseModel):
    icon_id: str
    name: str
    source: IconSource
    category: str | None = None
    tags: list[str] = Field(default_factory=list)
    style: str | None = None
    description: str | None = None
    mime_type: str
    version: int
    is_deleted: bool
    created_at: str
    updated_at: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class IconCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    source: IconSource = IconSource.USER_UPLOADED
    category: str | None = Field(default=None, max_length=100)
    tags: list[str] = Field(default_factory=list, max_length=50)
    style: str | None = Field(default=None, max_length=100)
    description: str | None = Field(default=None, max_length=2000)
    icon_id: str | None = Field(default=None, min_length=1, max_length=200)
    svg_content_base64: str = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("svg_content_base64")
    @classmethod
    def validate_svg_payload(cls, value: str) -> str:
        _decode_svg(value)
        return value


class IconUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    category: str | None = Field(default=None, max_length=100)
    tags: list[str] | None = Field(default=None, max_length=50)
    style: str | None = Field(default=None, max_length=100)
    description: str | None = Field(default=None, max_length=2000)
    metadata: dict[str, Any] | None = None


def create_icon_library_router(
    service: IconLibraryService,
    *,
    health_check: Callable[[], bool] | None = None,
    require_auth=None,
    remote_sync=None,
    require_admin=None,
) -> APIRouter:
    router = APIRouter(prefix="/icon-library", tags=["Icon Library"])
    auth_dependencies = [Depends(require_auth)] if require_auth else []
    admin_dependencies = [Depends(require_admin)] if require_admin else auth_dependencies

    @router.get("/health")
    def health() -> dict[str, Any]:
        if health_check is None:
            return {"success": True, "service": "icon_library", "status": "configured"}
        try:
            healthy = bool(health_check())
        except Exception as exc:
            raise HTTPException(status_code=503, detail=f"Icon Library database unavailable: {exc}") from exc
        if not healthy:
            raise HTTPException(status_code=503, detail="Icon Library database health check failed.")
        return {
            "success": True,
            "service": "icon_library",
            "status": "ok",
            "shared_drive": bool(remote_sync and remote_sync.configured),
        }

    @router.get("/drive/status", dependencies=admin_dependencies)
    def drive_status() -> dict[str, Any]:
        if remote_sync is None:
            return {"enabled": False, "ready": False}
        return remote_sync.status()

    @router.post("/drive/connect", dependencies=admin_dependencies)
    def drive_connect() -> dict[str, str]:
        if remote_sync is None:
            raise HTTPException(status_code=503, detail="Google Drive integration is unavailable.")
        try:
            return {"authorization_url": remote_sync.start_authorization()}
        except RuntimeError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.get("/drive/callback")
    def drive_callback(code: str | None = None, state: str | None = None, error: str | None = None) -> Response:
        if error:
            return Response(
                content=f"<html><body><h2>Google Drive connection was cancelled</h2><p>{error}</p></body></html>",
                media_type="text/html",
                status_code=400,
            )
        if remote_sync is None or not code or not state:
            return Response(content="Invalid Google Drive callback.", media_type="text/plain", status_code=400)
        try:
            remote_sync.complete_authorization(state=state, code=code)
        except (RuntimeError, ValueError) as exc:
            return Response(content=f"<html><body><h2>Google Drive connection failed</h2><p>{exc}</p></body></html>", media_type="text/html", status_code=400)
        return Response(
            content="<html><body><h2>Google Drive connected</h2><p>You can close this window and return to the application.</p></body></html>",
            media_type="text/html",
        )

    @router.post("/drive/disconnect", status_code=status.HTTP_204_NO_CONTENT, dependencies=admin_dependencies)
    def drive_disconnect() -> Response:
        if remote_sync is not None:
            remote_sync.disconnect()
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @router.get(
        "/icons",
        response_model=list[IconResponse],
        dependencies=auth_dependencies,
    )
    def list_icons(
        text: str = Query(default=""),
        category: str | None = Query(default=None),
        source: IconSource | None = Query(default=None),
        style: str | None = Query(default=None),
        tags: list[str] = Query(default=[]),
        limit: int = Query(default=50, ge=1, le=200),
        offset: int = Query(default=0, ge=0),
    ) -> list[IconResponse]:
        if remote_sync is not None:
            try:
                remote_sync.pull_if_due()
            except Exception as exc:
                # The local encrypted cache remains usable while Drive is
                # temporarily offline or needs re-authentication.
                print(f"Google Drive icon sync skipped: {exc}")
        records = service.search(
            IconSearchQuery(
                text=text,
                category=category,
                source=source,
                style=style,
                tags=tuple(tags),
                limit=limit,
                offset=offset,
            )
        )
        return [_response(record) for record in records]

    @router.post(
        "/icons",
        response_model=IconResponse,
        status_code=status.HTTP_201_CREATED,
        dependencies=auth_dependencies,
    )
    def create_icon(request: IconCreateRequest) -> IconResponse:
        try:
            record = IconRecord(
                icon_id=request.icon_id or f"icon-{uuid4()}",
                name=request.name,
                source=request.source,
                asset_ref="pending",
                category=request.category,
                tags=tuple(_normalize_tags(request.tags)),
                style=request.style,
                description=request.description,
                metadata=request.metadata,
            )
            created = service.add(record, svg_content=_decode_svg(request.svg_content_base64))
            if remote_sync is not None:
                try:
                    remote = remote_sync.push(created, _decode_svg(request.svg_content_base64))
                    if remote:
                        created = service.update(replace_metadata(created, {
                            "shared_drive_file_id": remote["file_id"],
                            "shared_drive_modified_time": remote["modified_time"],
                            "shared_drive_sync": "synced",
                        }))
                    else:
                        created = service.update(replace_metadata(created, {
                            "shared_drive_sync": "local_only",
                        }))
                except Exception as exc:
                    created = service.update(replace_metadata(created, {
                        "shared_drive_sync": "pending",
                        "shared_drive_sync_error": str(exc)[:500],
                    }))
            return _response(created)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.get(
        "/icons/{icon_id}",
        response_model=IconResponse,
        dependencies=auth_dependencies,
    )
    def get_icon(icon_id: str) -> IconResponse:
        try:
            return _response(service.get(icon_id))
        except IconNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.get("/icons/{icon_id}/download", dependencies=auth_dependencies)
    def download_icon(icon_id: str) -> Response:
        try:
            content = service.download_svg(icon_id)
        except (IconNotFoundError, KeyError) as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return Response(
            content=content,
            media_type="image/svg+xml",
            headers={"Content-Disposition": f'attachment; filename="{icon_id}.svg"'},
        )

    @router.patch(
        "/icons/{icon_id}",
        response_model=IconResponse,
        dependencies=auth_dependencies,
    )
    def update_icon(icon_id: str, request: IconUpdateRequest) -> IconResponse:
        try:
            current = service.get(icon_id)
            changes = request.model_dump(exclude_unset=True)
            updated = current
            if "tags" in changes and changes["tags"] is not None:
                changes["tags"] = tuple(_normalize_tags(changes["tags"]))
            for field_name, value in changes.items():
                updated = updated.__class__(**{**updated.__dict__, field_name: value})
            return _response(service.update(updated))
        except IconNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.delete(
        "/icons/{icon_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        dependencies=auth_dependencies,
    )
    def delete_icon(icon_id: str) -> Response:
        try:
            service.delete(icon_id)
        except IconNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    return router


def _decode_svg(value: str) -> bytes:
    payload = value.strip()
    if payload.startswith("data:"):
        header, separator, payload = payload.partition(",")
        if not separator or ";base64" not in header.lower():
            raise ValueError("SVG payload must be base64-encoded.")
    try:
        decoded = base64.b64decode(payload, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("SVG payload is not valid base64.") from exc
    if not decoded or len(decoded) > MAX_SVG_BYTES:
        raise ValueError("SVG payload must be between 1 byte and 10 MB.")
    if b"<svg" not in decoded[:4096].lower():
        raise ValueError("Uploaded content is not an SVG document.")
    return decoded


def _normalize_tags(tags: list[str]) -> list[str]:
    normalized = []
    for tag in tags:
        clean = " ".join(str(tag).strip().lower().split())
        if clean and clean not in normalized:
            normalized.append(clean)
    return normalized


def _response(icon: IconRecord) -> IconResponse:
    return IconResponse(
        icon_id=icon.icon_id,
        name=icon.name,
        source=icon.source,
        category=icon.category,
        tags=list(icon.tags),
        style=icon.style,
        description=icon.description,
        mime_type=icon.mime_type,
        version=icon.version,
        is_deleted=icon.is_deleted,
        created_at=icon.created_at.isoformat(),
        updated_at=icon.updated_at.isoformat(),
        metadata=dict(icon.metadata),
    )


def replace_metadata(icon: IconRecord, extra: dict[str, Any]) -> IconRecord:
    from dataclasses import replace

    return replace(icon, metadata={**icon.metadata, **extra})

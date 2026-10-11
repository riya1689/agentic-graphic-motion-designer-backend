"""Small safe trace contract for inspecting autonomous decisions."""

from __future__ import annotations

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class DesignTrace(BaseModel):
    request: Dict[str, Any] = Field(default_factory=dict)
    brief: Dict[str, Any] = Field(default_factory=dict)
    design_type: Optional[str] = None
    brief_version: int = 1
    specification_version: int = 0
    layout_version: int = 0
    render_reference: Optional[str] = None
    preview_reference: Optional[str] = None
    inspection_summary: Dict[str, Any] = Field(default_factory=dict)
    revision_decision: Optional[Dict[str, Any]] = None
    patch: Optional[Dict[str, Any]] = None
    acceptance_result: Optional[str] = None
    final_artifact: Optional[str] = None
    iteration: int = 0

"""
Graphic Agent API Schemas

এই schemas Manager <-> Graphic Agent HTTP contract define করে।

domain/schema.py:
    Agent internal business/domain model.

api/schemas.py:
    Network request/response contract.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ============================================================
# MANAGER -> GRAPHIC AGENT REQUEST
# ============================================================

class GraphicExecuteRequest(BaseModel):

    job_id: str

    planner_plan: Dict[str, Any] = Field(
        default_factory=dict
    )

    original_user_request: str = ""

    selected_image_model: Optional[str] = None


    max_validation_attempts: int = 2


# ============================================================
# GRAPHIC AGENT -> MANAGER RESPONSE
# ============================================================

class GraphicExecuteResponse(BaseModel):

    success: bool

    job_id: str

    status: str

    current_stage: str

    plan_verified: bool

    validation_attempt: int

    validation_errors: List[str] = Field(
        default_factory=list
    )

    artifact: Optional[Dict[str, Any]] = None

    output: Optional[Dict[str, Any]] = None

    error: Optional[str] = None
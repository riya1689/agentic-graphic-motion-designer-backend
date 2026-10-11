"""
Manager Public API Schemas
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class ManagerPublicResponse(BaseModel):
    success: bool

    message: str

    status: Optional[str] = None

    job_id: Optional[str] = None

    result_type: Optional[str] = None

    image_url: Optional[str] = None

    download_url: Optional[str] = None

    artifact_format: Optional[str] = None

    artifact_filename: Optional[str] = None

    file_path: Optional[str] = None

    target_application: Optional[str] = None

    error: Optional[str] = None
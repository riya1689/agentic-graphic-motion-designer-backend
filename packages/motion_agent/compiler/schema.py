"""
Motion Execution Schema

Planner output এবং video-model-specific parameters-এর
মাঝের generic contract.

IMPORTANT:

This schema MUST NOT contain:

- Wan-specific parameters
- LTX-specific parameters
- ComfyUI node IDs
- API provider fields
- FFmpeg commands
"""

from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class MotionResolution(BaseModel):

    width: int = Field(
        ge=1,
    )

    height: int = Field(
        ge=1,
    )


class MotionCameraSpec(BaseModel):

    movement: Optional[str] = None

    angle: Optional[str] = None

    framing: Optional[str] = None


class MotionShotSpec(BaseModel):

    shot_id: str

    generation_type: Literal[
        "text_to_video",
        "image_to_video",
    ]

    duration_seconds: float = Field(
        ge=1.0,
    )

    subject: str

    action: str = ""

    environment: str = ""

    lighting: str = ""

    style: str = ""

    camera: MotionCameraSpec = Field(
        default_factory=MotionCameraSpec
    )

    reference_asset: Optional[str] = None

    negative_constraints: List[str] = Field(
        default_factory=list
    )


class MotionExecutionSpec(BaseModel):
    """
    Model-neutral Motion Agent execution contract.
    """

    job_id: str

    total_duration_seconds: float = Field(
        ge=1.0,
    )

    resolution: MotionResolution

    fps: int = Field(
        default=24,
        ge=1,
    )

    aspect_ratio: str = "16:9"

    shots: List[MotionShotSpec] = Field(
        default_factory=list
    )

    audio_required: bool = False
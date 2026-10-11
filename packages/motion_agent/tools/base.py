"""
Generic Motion Video Tool Contract

Motion Agent orchestrates this interface.

It does NOT directly orchestrate:

- Hugging Face
- Fal
- Replicate
- model APIs
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from packages.motion_agent.compiler.schema import (
    MotionShotSpec,
)


# ============================================================
# TOOL EXECUTION RESULT
# ============================================================

@dataclass
class VideoToolResult:

    job_id: str

    shot_id: str

    tool_id: str

    provider: str

    model: str

    prompt: str

    video_bytes: bytes


# ============================================================
# BASE TOOL
# ============================================================

class VideoGenerationTool(ABC):

    tool_id: str


    @abstractmethod
    def generate(
        self,
        *,
        job_id: str,
        shot: MotionShotSpec,
    ) -> VideoToolResult:

        raise NotImplementedError
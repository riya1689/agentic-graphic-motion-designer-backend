"""
Generic Cloud Video Generation Tool

Responsibilities:

MotionShotSpec
      ↓
Generic prompt
      ↓
Generic VideoProviderRequest
      ↓
VideoProviderBridge

No provider SDK exists in this file.
"""

from __future__ import annotations

from packages.motion_agent.bridges.base import (
    VideoProviderBridge,
    VideoProviderRequest,
)

from packages.motion_agent.compiler.schema import (
    MotionShotSpec,
)

from packages.motion_agent.prompt.video_prompt import (
    compile_video_prompt,
)

from packages.motion_agent.tools.base import (
    VideoGenerationTool,
    VideoToolResult,
)


# ============================================================
# CLOUD VIDEO TOOL
# ============================================================

class CloudVideoTool(
    VideoGenerationTool,
):

    tool_id = "cloud_video"


    def __init__(
        self,
        *,
        bridge: VideoProviderBridge,
        model: str,
    ):

        self.bridge = bridge

        self.model = model


    # ========================================================
    # GENERATE ONE SHOT
    # ========================================================

    def generate(
        self,
        *,
        job_id: str,
        shot: MotionShotSpec,
    ) -> VideoToolResult:

        # ====================================================
        # PHASE-2B TRIAL CAPABILITY
        # ====================================================
        #
        # Current trial supports text-to-video.
        #
        # image-to-video will get its own capability adapter
        # later instead of mixing it here.
        # ====================================================

        if (
            shot.generation_type
            != "text_to_video"
        ):

            raise ValueError(
                "Current Phase-2B cloud video tool "
                "supports text_to_video only."
            )


        # ====================================================
        # GENERIC PROMPT
        # ====================================================

        prompt = compile_video_prompt(
            shot
        )


        if not prompt:

            raise RuntimeError(
                "Generated video prompt is empty."
            )


        # ====================================================
        # GENERIC PROVIDER REQUEST
        # ====================================================

        request = VideoProviderRequest(

            prompt=prompt,

            model=self.model,

        )


        # ====================================================
        # PROVIDER EXECUTION
        # ====================================================

        result = self.bridge.generate(
            request
        )


        if not result.success:

            raise RuntimeError(
                "Video provider returned unsuccessful result."
            )


        # ====================================================
        # PROVIDER-NEUTRAL TOOL RESULT
        # ====================================================

        return VideoToolResult(

            job_id=job_id,

            shot_id=shot.shot_id,

            tool_id=self.tool_id,

            provider=result.provider,

            model=result.model,

            prompt=prompt,

            video_bytes=result.video_bytes,

        )
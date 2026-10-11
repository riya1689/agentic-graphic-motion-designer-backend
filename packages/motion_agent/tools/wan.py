"""
Wan Video Generation Tool Adapter

Motion Agent talks to VideoGenerationTool.

Wan-specific execution stays behind this adapter.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from packages.motion_agent.bridges.base import (
    VideoExecutionBridge,
)

from packages.motion_agent.compiler.schema import (
    MotionShotSpec,
)

from packages.motion_agent.prompt.wan_prompt import (
    compile_wan_prompt,
)

from packages.motion_agent.tools.base import (
    VideoGenerationTool,
)


class WanVideoTool(
    VideoGenerationTool,
):

    tool_id = "wan_2_1_t2v_1_3b"


    def __init__(
        self,
        bridge: VideoExecutionBridge,
    ):

        self.bridge = bridge


    def generate(
        self,
        *,
        shot: MotionShotSpec,
        job_id: str,
    ) -> Dict[str, Any]:

        if (
            shot.generation_type
            != "text_to_video"
        ):

            raise ValueError(
                "Wan2.1 T2V-1.3B trial adapter "
                "currently supports text_to_video only."
            )


        prompt = compile_wan_prompt(
            shot
        )


        output_path = (

            Path("runtime-data")
            / "motion_agent"
            / job_id
            / "raw"
            / f"{shot.shot_id}.mp4"

        )


        payload = {

            "job_id":
                job_id,

            "shot_id":
                shot.shot_id,

            "prompt":
                prompt,

            "width":
                832,

            "height":
                480,

            "output_path":
                str(output_path),

        }


        result = self.bridge.execute(
            payload
        )


        return {

            "tool_id":
                self.tool_id,

            "shot_id":
                shot.shot_id,

            "prompt":
                prompt,

            **result,

        }
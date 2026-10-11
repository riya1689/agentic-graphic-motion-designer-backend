"""
Nano Banana Graphic Tool

Graphic Agent-এর tool abstraction.

এই file:
    - Graphic Agent payload receive করে
    - API bridge call করে
    - standardized tool result return করে

API-specific code এখানে যত কম রাখা যায় তত ভালো।
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from packages.graphic_agent.tools.base import (
    GraphicTool,
)

from packages.graphic_agent.bridges.api_client import (
    GeminiImageAPIClient,
)


class NanoBananaTool(GraphicTool):

    tool_id = "nano_banana"

    def __init__(self):

        self.api = GeminiImageAPIClient()


    def execute(
        self,
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:

        prompt = payload.get(
            "prompt",
            "",
        ).strip()

        if not prompt:

            raise ValueError(
                "Nano Banana prompt is empty."
            )

        job_id = payload.get(
            "job_id",
            "unknown",
        )

        output_path = Path(
            "runtime-data"
        ) / "graphic_agent" / job_id / "generated.jpg"

        return self.api.generate_image(
            prompt=prompt,
            output_path=output_path,
        )
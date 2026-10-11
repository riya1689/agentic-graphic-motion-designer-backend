"""
Motion Tool Registry

IMPORTANT ARCHITECTURE RULE:

Agent nodes do NOT instantiate provider adapters.

All dependency construction happens here.

Future provider migration therefore remains isolated.
"""

from __future__ import annotations

from packages.motion_agent.bridges.huggingface import (
    HuggingFaceVideoBridge,
)

from packages.motion_agent.providers.config import (
    get_motion_video_runtime_config,
)

from packages.motion_agent.tools.higgsfield_video import (
    HiggsfieldVideoTool,
)
from packages.motion_agent.tools.cloud_video import (
    CloudVideoTool,
)
from packages.motion_agent.tools.base import (
    VideoGenerationTool,
)


# ============================================================
# BUILD VIDEO TOOL
# ============================================================

def get_video_tool(
) -> VideoGenerationTool:

    config = (
        get_motion_video_runtime_config()
    )


    # ========================================================
    # HIGGSFIELD GATEWAY
    # ========================================================

    if config.gateway in ("higgsfield", "higgsfield_cli", "higgsfield_video"):

        return HiggsfieldVideoTool(
            model=config.model,
        )


    # ========================================================
    # HUGGING FACE GATEWAY
    # ========================================================

    if config.gateway == "huggingface":

        bridge = HuggingFaceVideoBridge(

            provider=config.provider,

        )

        return CloudVideoTool(

            bridge=bridge,

            model=config.model,

        )


    # ========================================================
    # FUTURE PROVIDERS
    # ========================================================
    #
    # Example future additions:
    #
    # if config.gateway == "fal_direct":
    #     ...
    #
    # if config.gateway == "replicate_direct":
    #     ...
    #
    # No graph/node changes will be required.
    # ========================================================


    raise ValueError(
        "Unsupported motion video gateway: "
        f"{config.gateway}"
    )
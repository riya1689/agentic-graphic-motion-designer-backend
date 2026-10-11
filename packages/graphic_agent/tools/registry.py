"""
Graphic Agent Tool Registry

এই registry Graphic Agent-এর available design tools
centrally register করে।

Phase-2:

    nano_banana

Future:

    photoshop
    illustrator
    canva
    stitch

Graphic Agent core logic tool implementation জানবে না।

সে শুধু:

    get_tool(tool_name)

call করবে।
"""

from __future__ import annotations

from typing import Dict, Type

from packages.graphic_agent.tools.base import (
    GraphicTool,
)

from packages.graphic_agent.tools.nano_banana import (
    NanoBananaTool,
)

from packages.graphic_agent.tools.higgsfield_image import (
    HiggsfieldImageTool,
)


# ============================================================
# TOOL REGISTRY
# ============================================================

TOOL_REGISTRY: Dict[
    str,
    Type[GraphicTool],
] = {

    "nano_banana":
        NanoBananaTool,

    "higgsfield_image":
        HiggsfieldImageTool,    

}


# ============================================================
# GET TOOL
# ============================================================

def get_tool(
    tool_name: str,
) -> GraphicTool:

    tool_class = TOOL_REGISTRY.get(
        tool_name
    )

    if tool_class is None:

        raise ValueError(
            f"Graphic tool '{tool_name}' "
            "is not registered."
        )

    return tool_class()





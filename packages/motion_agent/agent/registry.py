"""
Motion Agent Internal Node Registry

PHASE-1:

Only workflow nodes are registered.

Future:

Tool registry MUST remain separate.

Reason:

agent.registry -> node
node -> tool.registry

এই ধরনের circular dependency avoid করতে tool registry
later packages/motion_agent/tools/registry.py-তে থাকবে.
"""

from __future__ import annotations

from typing import Callable, Dict

from packages.motion_agent.agent.node import (
    acknowledge_plan_node,
    fail_plan_node,
    receive_plan_node,
    validate_plan_node,
    compile_execution_spec_node,
    verify_execution_spec_node,
    select_video_tool_node,
    generate_video_node,
    verify_generated_video_node,
    finalize_video_node,
)


# ============================================================
# NODE REGISTRY
# ============================================================

NODE_REGISTRY: Dict[str, Callable] = {

    "receive_plan":
        receive_plan_node,

    "validate_plan":
        validate_plan_node,

    "acknowledge_plan":
        acknowledge_plan_node,

    "fail_plan":
        fail_plan_node,
    "compile_execution_spec":
        compile_execution_spec_node,

    "verify_execution_spec":
        verify_execution_spec_node,
    "select_video_tool":
        select_video_tool_node,

    "generate_video":
        generate_video_node,

    "verify_generated_video":
        verify_generated_video_node,

    "finalize_video":
        finalize_video_node,
}


# ============================================================
# GET NODE
# ============================================================

def get_node(
    node_name: str,
) -> Callable:

    node = NODE_REGISTRY.get(
        node_name
    )

    if node is None:

        raise ValueError(
            f"Motion Agent node "
            f"'{node_name}' is not registered."
        )

    return node
"""
Graphic Agent Internal Registry

Phase-1:

    workflow nodes register করা।

Future:

    tools / adapters / capabilities dynamically register করা যাবে।
"""

from __future__ import annotations

from typing import Callable, Dict

from packages.graphic_agent.agent.node import (

    acknowledge_plan_node,

    fail_plan_node,

    receive_plan_node,

    validate_plan_node,

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

            f"Graphic Agent node "

            f"'{node_name}' is not registered."

        )

    return node



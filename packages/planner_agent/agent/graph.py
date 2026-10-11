from __future__ import annotations

# ============================================================
# Planner Agent - LangGraph Workflow
# ============================================================
#
# PURPOSE OF THIS FILE:
#
# This file defines ONLY the Planner Agent workflow/graph.
#
# It connects nodes from nodes.py and controls:
#
#   - execution order
#   - conditional edges
#   - verification loop
#   - repair loop
#   - hill-climbing loop
#   - bounded retry
#   - success / failure termination
#
#
# IMPORTANT ARCHITECTURE RULE:
#
# graph.py = orchestration / graph topology
#
# graph.py MUST NOT contain:
#
#   - Gemini prompts
#   - planning business logic
#   - schema definitions
#   - asset retrieval
#   - graphic logic
#   - motion logic
#   - Manager logic
#   - tool selection
#
# This separation keeps the Planner Agent scalable
# and allows nodes to be added/removed later.
# ============================================================


from typing import Any, Dict

from langgraph.graph import END, START, StateGraph

from packages.planner_agent.agent.state import PlannerState

from packages.planner_agent.agent.nodes import (
    prepare_input_node,
    planning_node,
    validate_plan_node,
    verify_plan_node,
    hill_climb_node,
    restore_best_plan_node,
    finalize_node,
    fail_node,
    route_after_validation,
    route_after_verification,
)


# ============================================================
# Routing After Initial Planning
# ============================================================

def route_after_planning(
    state: PlannerState,
) -> str:
    """
    Decide what happens immediately after Gemini planning.

    Normally:
        planning -> validate

    But if the LLM/API call itself failed:
        planning -> fail

    IMPORTANT:
    This is deterministic routing.
    No LLM call is required.
    """

    if state.get("status") == "failed":
        return "fail"

    if state.get("error"):
        return "fail"

    return "validate"


# ============================================================
# Routing After Hill-Climbing / Repair
# ============================================================

def route_after_repair(
    state: PlannerState,
) -> str:
    """
    Decide what happens after a repair attempt.

    Successful repair candidate:
        repair -> validate

    Repair API / LLM failure:
        repair -> fail

    Every repaired plan MUST pass through validation again.
    """

    if state.get("status") == "failed":
        return "fail"

    if state.get("error"):
        return "fail"

    return "validate"


# ============================================================
# Routing After Restoring Best Candidate
# ============================================================

def route_after_restore(
    state: PlannerState,
) -> str:
    """
    If hill-climbing attempts are exhausted:

        restore best candidate

    If a best candidate exists:
        -> finalize

    Otherwise:
        -> fail
    """

    if state.get("status") == "failed":
        return "fail"

    if state.get("validated_plan") is None:
        return "fail"

    return "finalize"


# ============================================================
# Build Planner Graph
# ============================================================

def build_planner_graph():
    """
    Build and compile the Planner Agent LangGraph.

    High-level workflow:

        START
          |
          v
        prepare
          |
          v
        planning
          |
          v
        validate
          |
          +---- invalid -------------------+
          |                                |
          |                                v
          |                              repair
          |                                |
          |                                |
          +<---------- validate <----------+
          |
          | valid
          v
        verify
          |
          +---- complete ------> finalize ----> END
          |
          +---- incomplete
          |
          v
        repair
          |
          v
        validate
          |
          v
        verify
          |
         ...
          |
          | attempts exhausted
          v
        restore_best
          |
          v
        finalize
          |
          v
         END


    Important properties:

    1. Every LLM-generated candidate is validated.
    2. Every valid candidate is semantically verified.
    3. Failed verification enters repair/hill-climbing.
    4. Repair is bounded.
    5. Best candidate is preserved.
    6. Infinite loops are prevented.
    """

    # --------------------------------------------------------
    # Create graph using PlannerState as shared state contract.
    # --------------------------------------------------------

    workflow = StateGraph(PlannerState)

    # ========================================================
    # Register Nodes
    # ========================================================
    #
    # Node names are intentionally short and stable.
    #
    # Internal Python function names can later change
    # without requiring external systems to understand them.
    # ========================================================

    workflow.add_node(
        "prepare",
        prepare_input_node,
    )

    workflow.add_node(
        "planning",
        planning_node,
    )

    workflow.add_node(
        "validate",
        validate_plan_node,
    )

    workflow.add_node(
        "verify",
        verify_plan_node,
    )

    workflow.add_node(
        "repair",
        hill_climb_node,
    )

    workflow.add_node(
        "restore_best",
        restore_best_plan_node,
    )

    workflow.add_node(
        "finalize",
        finalize_node,
    )

    workflow.add_node(
        "fail",
        fail_node,
    )

    # ========================================================
    # START
    # ========================================================

    workflow.add_edge(
        START,
        "prepare",
    )

    # ========================================================
    # Prepare -> Planning
    # ========================================================

    workflow.add_edge(
        "prepare",
        "planning",
    )

    # ========================================================
    # Planning -> Validate / Fail
    # ========================================================
    #
    # Gemini planning failure should NOT be passed into
    # validation.
    #
    # This protects the graph from cascading errors.
    # ========================================================

    workflow.add_conditional_edges(
        "planning",
        route_after_planning,
        {
            "validate": "validate",
            "fail": "fail",
        },
    )

    # ========================================================
    # Validate -> Verify / Repair / Fail
    # ========================================================
    #
    # route_after_validation() comes from nodes.py.
    #
    # VALID:
    #     validate -> verify
    #
    # INVALID but attempts available:
    #     validate -> repair
    #
    # INVALID and attempts exhausted:
    #     validate -> fail
    # ========================================================

    workflow.add_conditional_edges(
        "validate",
        route_after_validation,
        {
            "verify": "verify",
            "repair": "repair",
            "fail": "fail",
        },
    )

    # ========================================================
    # Verify -> Finalize / Repair / Restore Best
    # ========================================================
    #
    # GOOD PLAN:
    #     verify -> finalize
    #
    # INCOMPLETE PLAN:
    #     verify -> repair
    #
    # RETRIES EXHAUSTED:
    #     verify -> restore_best
    #
    # This is the main Agent Verification Loop.
    # ========================================================

    workflow.add_conditional_edges(
        "verify",
        route_after_verification,
        {
            "finalize": "finalize",
            "repair": "repair",
            "restore_best": "restore_best",
        },
    )

    # ========================================================
    # Repair -> Validate Again
    # ========================================================
    #
    # CRITICAL:
    #
    # A repaired candidate NEVER goes directly to verifier.
    #
    # It must first pass deterministic validation again.
    #
    # repair
    #   ↓
    # validate
    #   ↓
    # verify
    #
    # This keeps the loop safe and predictable.
    # ========================================================

    workflow.add_conditional_edges(
        "repair",
        route_after_repair,
        {
            "validate": "validate",
            "fail": "fail",
        },
    )

    # ========================================================
    # Restore Best -> Finalize / Fail
    # ========================================================
    #
    # If hill-climbing reaches its retry limit,
    # restore the highest-scoring candidate.
    # ========================================================

    workflow.add_conditional_edges(
        "restore_best",
        route_after_restore,
        {
            "finalize": "finalize",
            "fail": "fail",
        },
    )

    # ========================================================
    # Terminal Nodes
    # ========================================================

    workflow.add_edge(
        "finalize",
        END,
    )

    workflow.add_edge(
        "fail",
        END,
    )

    # ========================================================
    # Compile Graph
    # ========================================================

    return workflow.compile()


# ============================================================
# Reusable Compiled Planner Graph
# ============================================================
#
# Other modules can simply import:
#
#     from packages.planner_agent.agent.graph import planner_graph
#
# and invoke:
#
#     result = planner_graph.invoke(initial_state)
#
# Manager integration comes later.
# ============================================================

planner_graph = build_planner_graph()


# ============================================================
# Public Invocation Helper
# ============================================================

def run_planner(
    initial_state: PlannerState,
) -> Dict[str, Any]:
    """
    Public helper for executing the Planner Agent.

    Why have this wrapper?

    Manager or test code should not need to know LangGraph
    implementation details.

    Today:
        LangGraph.invoke()

    Future:
        tracing
        persistence
        checkpoints
        distributed execution
        timeout
        telemetry

    can be added here without changing Manager code.
    """

    result = planner_graph.invoke(
        initial_state,
    )

    return dict(result)
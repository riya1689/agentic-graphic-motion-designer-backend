# packages/prompt_to_json_agent/agent/graph.py

# উদ্দেশ্য:
#
# LangGraph state machine
#
# দুটি আলাদা loop:
#
# LOOP 1:
# Prompt Extraction
#     ↓
# Prompt ↔ JSON Verification
#     ↓
# Missing user requirement?
#     ↓
# Repair Extraction
#
#
# LOOP 2:
# AI AutoFill
#     ↓
# Zero Null Validator
#     ↓
# Retry if required

from langgraph.graph import (
    StateGraph,
    END
)

from .state import AgentState

from .nodes import (
    strict_extractor_node,
    prompt_json_verifier_node,
    extraction_repair_node,
    gap_detector_node,
    ai_completion_node,
    null_validator_node
)


# ================================================================
# EXTRACTION COVERAGE ROUTER
# ================================================================

def route_extraction_coverage(
    state: AgentState
) -> str:

    """
    User prompt-এর সব explicit requirements
    JSON-এ capture হয়েছে কিনা check করে।

    PASS:
        gap_detector

    FAIL:
        extraction_repair

    Too many retries:
        circuit_break
    """

    if state.get(
        "coverage_complete",
        False
    ):
        return "approved"

    if (
        state.get(
            "extraction_attempt_count",
            0
        )
        >=
        state["max_retries"]
    ):
        return "circuit_break"

    return "retry"


# ================================================================
# AUTOFILL VALIDATION ROUTER
# ================================================================

def route_validation_loop(
    state: AgentState
) -> str:

    if state.get(
        "is_complete",
        False
    ):
        return "approved"

    if (
        state.get(
            "autofill_attempt_count",
            0
        )
        >=
        state["max_retries"]
    ):
        return "circuit_break"

    return "retry"


# ================================================================
# EXTRACTION GRAPH
# ================================================================

def build_extraction_graph():

    """
    User Prompt
       ↓
    Strict Extractor
       ↓
    Coverage Verifier
       ↓
    ┌─────────────┐
    │             │
    PASS          FAIL
    │             │
    ↓             ↓
    Gap         Repair
    Detector      │
                  │
                  └──→ Coverage Verifier
    """

    workflow = StateGraph(
        AgentState
    )

    workflow.add_node(
        "strict_extractor",
        strict_extractor_node
    )

    workflow.add_node(
        "coverage_verifier",
        prompt_json_verifier_node
    )

    workflow.add_node(
        "extraction_repair",
        extraction_repair_node
    )

    workflow.add_node(
        "gap_detector",
        gap_detector_node
    )

    workflow.set_entry_point(
        "strict_extractor"
    )

    workflow.add_edge(
        "strict_extractor",
        "coverage_verifier"
    )

    # ============================================================
    # NEW LOOP ENGINEERING:
    # Verify → Repair → Verify
    # ============================================================

    workflow.add_conditional_edges(

        "coverage_verifier",

        route_extraction_coverage,

        {
            "approved":
                "gap_detector",

            "retry":
                "extraction_repair",

            "circuit_break":
                END
        }
    )

    workflow.add_edge(
        "extraction_repair",
        "coverage_verifier"
    )

    workflow.add_edge(
        "gap_detector",
        END
    )

    return workflow.compile()


# ================================================================
# AI AUTOFILL GRAPH
# ================================================================

def build_autofill_loop_graph():

    workflow = StateGraph(
        AgentState
    )

    workflow.add_node(
        "ai_completion",
        ai_completion_node
    )

    workflow.add_node(
        "validator",
        null_validator_node
    )

    workflow.set_entry_point(
        "ai_completion"
    )

    workflow.add_edge(
        "ai_completion",
        "validator"
    )

    workflow.add_conditional_edges(

        "validator",

        route_validation_loop,

        {
            "approved":
                END,

            "retry":
                "ai_completion",

            "circuit_break":
                END
        }
    )

    return workflow.compile()


# ================================================================
# COMPILED GRAPHS
# ================================================================

extraction_graph = (
    build_extraction_graph()
)

autofill_loop_graph = (
    build_autofill_loop_graph()
)
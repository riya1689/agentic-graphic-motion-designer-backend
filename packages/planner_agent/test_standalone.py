from __future__ import annotations

# ============================================================
# Planner Agent - Standalone Test Runner
# ============================================================
#
# PURPOSE:
#
# Test planner_agent independently without Manager Agent.
#
# This script sends a fake JSON Agent output directly into
# planner_graph and prints the full Planner result.
#
# Run from project root:
#
#   python -m packages.planner_agent.test_standalone
#
# ============================================================

import json
from dotenv import load_dotenv

from packages.planner_agent.agent.graph import run_planner


# ============================================================
# Load Environment Variables
# ============================================================

load_dotenv()


# ============================================================
# Fake JSON Agent Output
# ============================================================
#
# This simulates the structured JSON that will later come
# from prompt_to_json_agent through Manager Agent.
# ============================================================

FAKE_JSON_AGENT_OUTPUT = {
    "job_type": "graphic_design",
    "user_goal": "Create a promotional brand poster",

    "requirements": [
        "Create a modern promotional poster",
        "Use the company brand logo from two months ago",
        "Use a clean premium visual style",
        "Keep the final design editable",
        "Include a clear headline and supporting text",
    ],

    "design_preferences": {
        "style": "modern premium",
        "layout": "clean",
        "editable_required": True,
    },

    "previous_reference": {
        "requested": True,
        "asset_type": "brand_logo",
        "time_reference": {
            "offset_months": -2,
        },
    },

    "deliverables": [
        "editable poster design",
        "final exported poster",
    ],
}


# ============================================================
# Fake Original User Prompt
# ============================================================

FAKE_USER_REQUEST = (
    "Create a modern promotional poster for our company. "
    "Use our brand logo from two months ago. "
    "Keep the design clean and premium and make sure "
    "the final output remains editable."
)


# ============================================================
# Build Initial Planner State
# ============================================================

INITIAL_STATE = {
    # Unique test job ID.
    "job_id": "planner_test_001",

    # Simulated Manager payload.
    "manager_input": {
        "source": "standalone_test",
        "json_agent_output": FAKE_JSON_AGENT_OUTPUT,
    },

    # Primary structured input for Planner.
    "json_agent_output": FAKE_JSON_AGENT_OUTPUT,

    # Optional original user prompt.
    "original_user_request": FAKE_USER_REQUEST,

    # Planner loop settings.
    "repair_attempt": 0,
    "max_repair_attempts": 3,

    # Hill-climbing state.
    "planning_iteration": 0,
    "verification_score": 0.0,
    "verification_feedback": [],
    "best_plan": None,
    "best_score": 0.0,

    # Runtime state.
    "status": "received",
    "current_step": "received",

    # Validation state.
    "validation_passed": False,
    "validation_errors": [],

    # Error state.
    "error": None,

    # Debugging.
    "debug_messages": [],
}


# ============================================================
# Main
# ============================================================

def main() -> None:
    print()
    print("=" * 80)
    print("PLANNER AGENT - STANDALONE TEST")
    print("=" * 80)

    try:
        result = run_planner(
            INITIAL_STATE
        )

    except Exception as exc:
        print()
        print("=" * 80)
        print("PLANNER AGENT TEST FAILED")
        print("=" * 80)
        print(str(exc))
        print("=" * 80)
        return

    print()
    print("=" * 80)
    print("PLANNER AGENT - FINAL STATE")
    print("=" * 80)

    print(
        json.dumps(
            result,
            indent=2,
            ensure_ascii=False,
            default=str,
        )
    )

    print()
    print("=" * 80)
    print("PLANNER AGENT - FINAL OUTPUT")
    print("=" * 80)

    final_output = result.get(
        "final_output"
    )

    if final_output is None:
        print("No final output returned.")
        print(
            "Status:",
            result.get("status"),
        )
        print(
            "Error:",
            result.get("error"),
        )

    else:
        print(
            json.dumps(
                final_output,
                indent=2,
                ensure_ascii=False,
            )
        )

    print()
    print("=" * 80)
    print("PLANNER TEST SUMMARY")
    print("=" * 80)

    print(
        "Status:",
        result.get("status"),
    )

    print(
        "Planning iterations:",
        result.get(
            "planning_iteration",
            0,
        ),
    )

    print(
        "Repair attempts:",
        result.get(
            "repair_attempt",
            0,
        ),
    )

    print(
        "Verification score:",
        result.get(
            "verification_score",
            0.0,
        ),
    )

    print(
        "Best score:",
        result.get(
            "best_score",
            0.0,
        ),
    )

    print(
        "Previous asset required:",
        result.get(
            "previous_asset_required",
            False,
        ),
    )

    print(
        "Asset requests:",
        json.dumps(
            result.get(
                "asset_requests",
                [],
            ),
            indent=2,
            ensure_ascii=False,
        ),
    )

    print("=" * 80)


# ============================================================
# Entry Point
# ============================================================

if __name__ == "__main__":
    main()
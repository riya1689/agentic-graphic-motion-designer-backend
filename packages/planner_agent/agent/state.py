from __future__ import annotations

# ============================================================
# Planner Agent State
# ============================================================
#
# এই file-এর কাজ:
#
# Manager -> Planner Agent
# Planner Agent internal processing
# Planner Agent -> Manager
#
# এই পুরো lifecycle-এর data/state track করা।
#
# IMPORTANT:
# এখানে কোনো LLM call হবে না।
# এখানে শুধু state structure define করা হবে।
#
# LLM call পরে nodes.py-তে থাকবে।
# ============================================================


from typing import Any, Dict, List, Optional, TypedDict

from packages.planner_agent.domain.schema import PlannerOutput


# ============================================================
# PlannerState
# ============================================================

class PlannerState(TypedDict, total=False):
    """
    LangGraph Planner Agent-এর shared state.

    LangGraph-এর প্রত্যেক node এই state receive করবে
    এবং প্রয়োজন অনুযায়ী কিছু field update করবে.

    Example flow:

        Manager
          ↓
        planner_input
          ↓
        prepare_input_node
          ↓
        planning_llm_node
          ↓
        validate_plan_node
          ↓
        final_output
          ↓
        Manager
    """

    # --------------------------------------------------------
    # 1. Request Tracking
    # --------------------------------------------------------

    # Manager থেকে আসা unique job/request ID.
    #
    # Example:
    # "job_20260922_001"
    #
    # Debugging, logging এবং future distributed system-এর জন্য
    # job_id খুব important.
    job_id: str


    # --------------------------------------------------------
    # 2. Raw Manager Input
    # --------------------------------------------------------

    # Manager Planner-কে যে complete payload পাঠাবে
    # সেটা এখানে রাখা হবে.
    #
    # এই input-এর ভিতরে থাকতে পারে:
    #
    # - JSON Agent output
    # - user request
    # - manager metadata
    #
    # Planner Manager-এর structure-এর উপর tightly coupled
    # না হওয়ার জন্য Dict[str, Any] রাখা হয়েছে.
    manager_input: Dict[str, Any]


    # --------------------------------------------------------
    # 3. JSON Agent Output
    # --------------------------------------------------------

    # Prompt-to-JSON Agent যে structured JSON তৈরি করেছে,
    # Planner primarily সেটাই analyze করবে.
    #
    # IMPORTANT:
    # Planner ideally raw user prompt-এর পরিবর্তে
    # structured requirement JSON-এর উপর plan করবে.
    #
    # এতে:
    #
    # - hallucination কমে
    # - requirement loss কমে
    # - planning consistent হয়
    json_agent_output: Dict[str, Any]


    # --------------------------------------------------------
    # 4. Optional Original User Request
    # --------------------------------------------------------

    # Original user prompt optionalভাবে রাখা হচ্ছে.
    #
    # Planner-এর primary source:
    # json_agent_output
    #
    # কিন্তু JSON-এর কোনো field ambiguous হলে
    # original request useful হতে পারে.
    original_user_request: Optional[str]


    # --------------------------------------------------------
    # 5. Prepared Planner Input
    # --------------------------------------------------------

    # LLM-কে raw Manager payload সরাসরি দেবো না.
    #
    # prepare_input node প্রয়োজনীয় data normalize করে
    # clean planner input তৈরি করবে.
    #
    # এতে token usage কমে এবং prompt stable থাকে.
    prepared_input: Dict[str, Any]


    # --------------------------------------------------------
    # 6. Previous Asset Requirement
    # --------------------------------------------------------

    # Planner decide করবে user কোনো previous asset/context
    # চেয়েছে কি না.
    #
    # Example:
    #
    # "Use our logo from two months ago"
    #
    # তখন:
    #
    # previous_asset_required = True
    #
    # NOTE:
    # Planner asset retrieve করবে না.
    previous_asset_required: bool


    # Planner কোন asset দরকার তার structured requests রাখবে.
    #
    # Example:
    #
    # [
    #   {
    #       "type": "brand_logo",
    #       "time_reference": {
    #           "offset_months": -2
    #       }
    #   }
    # ]
    #
    # Future Asset Resolver এই information ব্যবহার করবে.
    asset_requests: List[Dict[str, Any]]


    # --------------------------------------------------------
    # 7. LLM Planning Result
    # --------------------------------------------------------

    # Planner LLM-এর raw structured response.
    #
    # Validation-এর আগে এই field-এ রাখা হবে.
    #
    # IMPORTANT:
    # final Manager output হিসেবে এই raw value directly যাবে না.
    llm_plan_raw: Optional[Dict[str, Any]]


    # --------------------------------------------------------
    # 8. Validated Planner Output
    # --------------------------------------------------------

    # Pydantic schema validation pass করার পর
    # final PlannerOutput object এখানে থাকবে.
    #
    # এটা Planner Agent-এর trusted output.
    validated_plan: Optional[PlannerOutput]


    # --------------------------------------------------------
    # 9. Final Serializable Output
    # --------------------------------------------------------

    # Manager-কে পাঠানোর আগে PlannerOutput object-কে
    # normal JSON-compatible dictionary-তে convert করা হবে.
    #
    # Example:
    #
    # validated_plan.model_dump()
    #
    # তারপর এই value Manager receive করবে.
    final_output: Optional[Dict[str, Any]]


    # --------------------------------------------------------
    # 10. Validation State
    # --------------------------------------------------------

    # Planner output schema validation pass করেছে কি না.
    validation_passed: bool


    # Validation error থাকলে এখানে রাখা হবে.
    #
    # Example:
    #
    # [
    #   "tasks field missing",
    #   "primary_job_type invalid"
    # ]
    validation_errors: List[str]


    # --------------------------------------------------------
    # 11. Repair / Retry State
    # --------------------------------------------------------

    # LLM invalid plan দিলে কতবার repair attempt হয়েছে.
    repair_attempt: int


    # Planner Agent maximum কতবার repair করবে.
    #
    # আমরা bounded retry রাখবো যাতে infinite LLM loop না হয়.
    max_repair_attempts: int


    # --------------------------------------------------------
    # 12. Execution Status
    # --------------------------------------------------------

    # Planner lifecycle status.
    #
    # Expected values:
    #
    # received
    # preparing
    # planning
    # validating
    # repairing
    # completed
    # failed
    status: str


    # Human-readable current step.
    #
    # Terminal logging-এর জন্য useful.
    current_step: Optional[str]


    # --------------------------------------------------------
    # 13. Error Tracking
    # --------------------------------------------------------

    # Fatal error message.
    error: Optional[str]


    # --------------------------------------------------------
    # 14. Debug / Observability
    # --------------------------------------------------------

    # Internal notes/debug information.
    #
    # Production output-এর অংশ না হলেও
    # CLI/debugging-এর সময় useful.
    debug_messages: List[str]


    # LLM provider name track করা.
    #
    # Example:
    # "gemini"
    #
    # Provider swap করলে debugging সহজ হবে.
    llm_provider: Optional[str]


    # Actual model name.
    #
    # Example:
    # "gemini-3.5-flash-lite"
    llm_model: Optional[str]

        # ========================================================
    # Planner Verification / Hill-Climbing State
    # ========================================================

    # Current plan requirement coverage score.
    # Range: 0.0 - 100.0
    verification_score: float

    # Verifier যে missing / weak / conflicting বিষয় পাবে.
    verification_feedback: List[str]

    # এখন পর্যন্ত পাওয়া best valid plan.
    #
    # Hill-climbing-এর সময় নতুন candidate খারাপ হলে
    # previous best plan হারিয়ে যাবে না.
    best_plan: Optional[PlannerOutput]

    # best_plan-এর verification score.
    best_score: float

    # Initial generation + repair iterations track করার জন্য.
    planning_iteration: int
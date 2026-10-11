# packages/prompt_to_json_agent/agent/state.py
# উদ্দেশ্য: সম্পূর্ণ লুপ এবং ইন্টারঅ্যাকশন স্টেট ট্র্যাকিং

from typing import Dict, Any, List, Optional
from typing_extensions import TypedDict
from ..domain.schema import GraphicDesignSpec

class AgentState(TypedDict):

    # ============================================================
    # Original user prompt
    # ============================================================

    raw_prompt: str

    max_retries: int

    # ============================================================
    # NEW:
    # Extraction verification loop-এর জন্য আলাদা counter
    # ============================================================

    extraction_attempt_count: int

    coverage_complete: bool

    coverage_missing_requirements: List[str]

    coverage_notes: List[str]

    # ============================================================
    # Extracted JSON
    # ============================================================

    extracted_spec: Optional[GraphicDesignSpec]

    # ============================================================
    # Existing missing-field handling
    # ============================================================

    missing_fields: List[str]

    user_wants_ai_autofill: Optional[bool]

    # ============================================================
    # Auto-fill loop-এর জন্য আলাদা counter
    # ============================================================

    autofill_attempt_count: int

    validation_errors: List[str]

    is_complete: bool

    final_output: Optional[Dict[str, Any]]
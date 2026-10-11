# packages/prompt_to_json_agent/test_standalone.py
# উদ্দেশ্য: সম্পূর্ণ সিস্টেম ছাড়া শুধুমাত্র এই এজেন্টটি এককভাবে রান ও ভেরিফাই করা

import sys
from pathlib import Path

AGENT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))

from packages.prompt_to_json_agent.agent.graph import extraction_graph

if __name__ == "__main__":
    print("[TEST] Running Standalone Prompt-to-JSON Agent...")
    sample_prompt = "type: image\nBrand: TestBrand\nColors: Blue, White"
    state = {
        "raw_prompt": sample_prompt,
        "max_retries": 2,
        "extraction_attempt_count": 0,
        "coverage_complete": False,
        "coverage_missing_requirements": [],
        "coverage_notes": [],
        "extracted_spec": None,
        "missing_fields": [],
        "user_wants_ai_autofill": None,
        "autofill_attempt_count": 0,
        "validation_errors": [],
        "is_complete": False,
        "final_output": None
    }
    out = extraction_graph.invoke(state)
    print("[TEST SUCCESS] Extracted Spec:", out.get("extracted_spec"))
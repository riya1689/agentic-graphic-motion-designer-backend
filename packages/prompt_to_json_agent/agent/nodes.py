# packages/prompt_to_json_agent/agent/nodes.py

# উদ্দেশ্য:
#
# 1. Strict Prompt Extraction
# 2. Dynamic Requirement Extraction
# 3. Prompt ↔ JSON Coverage Verification
# 4. Missing User Requirement Repair
# 5. Gap Detection
# 6. AI Auto-Fill
# 7. Zero-Null Validation

import os
import json
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[3]

load_dotenv(
    PROJECT_ROOT / ".env",
    override=False,
)

from typing import Dict, Any, List

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import SystemMessage

from ..domain.schema import (
    GraphicDesignSpec,
    PromptCoverageResult
)

from .state import AgentState


import time

# ================================================================
# MODEL INITIALIZATION & FALLBACK ENGINE
# ================================================================

gemini_api_key = os.getenv("GEMINI_API_KEY")

primary_model = os.getenv(
    "GEMINI_MODEL",
    "gemini-flash-latest"
)

FALLBACK_MODELS = [
    primary_model,
    "gemini-flash-latest",
    "gemini-flash-lite-latest",
    "gemini-pro-latest",
    "gemini-2.0-flash",
]

def invoke_structured_with_fallback(
    prompt_template,
    output_schema: type,
    input_data: Dict[str, Any],
    max_retries: int = 3,
) -> Any:
    """
    Invoke LangChain ChatGoogleGenerativeAI with exponential backoff on 503/429
    and model fallback switching.
    """
    last_exception = None
    seen_models = set()

    for model_name in FALLBACK_MODELS:
        if not model_name or model_name in seen_models:
            continue
        seen_models.add(model_name)

        try:
            llm_instance = ChatGoogleGenerativeAI(
                model=model_name,
                temperature=0.0,
                google_api_key=gemini_api_key,
                max_retries=2,
            )
            chain = prompt_template | llm_instance.with_structured_output(output_schema)
        except Exception as exc:
            last_exception = exc
            continue

        for attempt in range(1, max_retries + 1):
            try:
                return chain.invoke(input_data)
            except Exception as exc:
                exc_str = str(exc)
                last_exception = exc
                is_transient = any(
                    err in exc_str
                    for err in [
                        "503",
                        "429",
                        "UNAVAILABLE",
                        "ResourceExhausted",
                        "high demand",
                        "Overloaded",
                        "ServiceUnavailable",
                    ]
                )

                if is_transient and attempt < max_retries:
                    wait_sec = attempt * 2
                    print(
                        f"[JSON AGENT RETRY] Model {model_name} temporary error ({exc_str[:80]}). "
                        f"Retrying attempt {attempt}/{max_retries} in {wait_sec}s..."
                    )
                    time.sleep(wait_sec)
                else:
                    print(
                        f"[JSON AGENT FALLBACK] Model {model_name} failed ({exc_str[:100]}). "
                        f"Trying next fallback model..."
                    )
                    break

    raise RuntimeError(
        f"All JSON Agent LLM attempts failed. Last error: {last_exception}"
    ) from last_exception


# ================================================================
# 1. STRICT EXTRACTION PROMPT
# ================================================================

STRICT_SYSTEM_PROMPT = """
You are a Strict Data Extraction Parser for a professional
Graphic Design Agent.

Your task is to convert the user's prompt into structured JSON.

IMPORTANT PRINCIPLE:

The predefined schema contains common/core graphic design fields.

However, users may provide additional graphic design specifications
that are NOT represented by predefined schema fields.

Examples:

- camera angle
- depth of field
- lighting direction
- atmosphere
- visual mood
- texture style
- composition rule
- focal length
- perspective
- negative space
- rendering style
- shadow direction
- glow strength
- animation easing
- transition style
- object positioning
- brand restrictions
- accessibility constraints

These are NOT missing fields.

They are:

DYNAMIC / ADDITIONAL USER REQUIREMENTS.

Store such information inside:

additional_requirements

Example:

{
    "additional_requirements": {
        "camera_angle": "low-angle",
        "lighting": "cinematic",
        "depth_of_field": "shallow"
    }
}


CRITICAL EXTRACTION RULES:

1. NEVER invent information during strict extraction.

2. Extract EVERY explicit meaningful requirement from the user.

3. Do NOT discard information only because no predefined schema
   field exists for it.

4. Unknown/new requirements MUST go into additional_requirements.

5. additional_requirements must contain ONLY information explicitly
   supplied by the user.

6. Do NOT use additional_requirements for fields already represented
   by the core schema.

7. If the user DID NOT explicitly provide:

target_software:
    "USER_NOT_PROVIDED"

canvas_dimensions:
    "USER_NOT_PROVIDED"

color_palette:
    ["USER_NOT_PROVIDED"]

primary_subject:
    "USER_NOT_PROVIDED"

editable_typography:
    ["USER_NOT_PROVIDED"]

layers:
    [
        {
            "layer_name": "USER_NOT_PROVIDED",
            "layer_type": "USER_NOT_PROVIDED",
            "visual_description": "USER_NOT_PROVIDED"
        }
    ]

8. If no dynamic requirement exists:

additional_requirements = {}

9. Do not summarize away important constraints.

10. Do not merge unrelated requirements if doing so loses meaning.

Your goal is LOSSLESS USER REQUIREMENT EXTRACTION.
"""


strict_prompt_template = ChatPromptTemplate.from_messages([
    SystemMessage(
        content=STRICT_SYSTEM_PROMPT
    ),

    (
        "human",
        "User Input:\n{user_input}"
    )
])


# ================================================================
# 2. PROMPT ↔ JSON COVERAGE VERIFIER
# ================================================================

COVERAGE_SYSTEM_PROMPT = """
You are a Requirement Coverage Verifier.

You receive:

1. Original user prompt
2. Extracted JSON specification

Your job is NOT to improve the design.

Your job is ONLY to check whether every explicit meaningful
requirement stated by the user appears somewhere in the JSON.

IMPORTANT:

A requirement may appear either:

- inside a predefined/core JSON field

OR

- inside additional_requirements

Do NOT treat information that the user never supplied as missing.

Do NOT ask whether the design specification is professionally complete.

Only verify USER PROVIDED INFORMATION.

Examples:

User says:

"low angle camera"

but JSON has no camera-angle information.

Result:

all_user_requirements_captured = false

missing_requirements = [
    "low angle camera"
]


User never specifies canvas dimensions.

JSON contains:

"canvas_dimensions": "USER_NOT_PROVIDED"

This is NOT a coverage failure because the user never supplied
canvas dimensions.

That will later be handled by the Gap Detection stage.


CRITICAL RULE:

USER_NOT_PROVIDED is acceptable during this verification stage
when the original prompt did not provide that information.

Return TRUE only when all explicitly supplied user requirements
are represented in JSON.
"""


coverage_prompt_template = ChatPromptTemplate.from_messages([
    (
        "system",
        COVERAGE_SYSTEM_PROMPT
    ),
    (
        "human",
        """
Original User Prompt:

{user_input}


Extracted JSON:

{current_spec}
"""
    )
])


# ================================================================
# 3. EXTRACTION REPAIR PROMPT
# ================================================================

REPAIR_EXTRACTION_SYSTEM_PROMPT = """
You are a Requirement Extraction Repair Agent.

A verifier discovered that some explicit requirements from the
original user prompt were missing from the generated JSON.

Your job is to repair the JSON.

RULES:

1. Preserve all correctly extracted existing information.

2. Add ONLY requirements explicitly stated by the user.

3. Do NOT invent professional design decisions.

4. If a missing requirement has no predefined core schema field,
   place it inside additional_requirements.

5. Never remove valid existing dynamic requirements.

6. USER_NOT_PROVIDED values must remain USER_NOT_PROVIDED when
   the user did not provide that information.

7. Your task is extraction repair, NOT AI autofill.

The final JSON must preserve every explicit user requirement.
"""


repair_extraction_prompt_template = ChatPromptTemplate.from_messages([
    SystemMessage(
        content=REPAIR_EXTRACTION_SYSTEM_PROMPT
    ),

    (
        "human",
        """
Original User Prompt:

{user_input}


Current JSON:

{current_spec}


Verifier says these user requirements are missing:

{missing_requirements}
"""
    )
])


# ================================================================
# 4. AUTOFILL PROMPT
# ================================================================

AUTOFILL_SYSTEM_PROMPT = """
You are an Enterprise Creative Director & Adobe Graphic Architect.

The user has authorized automatic completion for missing design details.

Analyze the partial specification and design context.

Replace EVERY required USER_NOT_PROVIDED core field with
professional production-ready design decisions.

IMPORTANT:

additional_requirements contains explicit requirements supplied
by the user.

These requirements MUST be preserved.

Do not remove, overwrite, or contradict them.


RULES:

1. No required core field may contain USER_NOT_PROVIDED,
   null or empty values after completion.

2. Infer professional canvas dimensions, layer hierarchy,
   color palette and typography when missing.

3. If asset_type == "motion":
   motion_duration_sec must be greater than 0.

4. Preserve every existing user-provided requirement.

5. additional_requirements must remain semantically consistent
   with the user's original prompt.
"""


autofill_prompt_template = ChatPromptTemplate.from_messages([
    SystemMessage(
        content=AUTOFILL_SYSTEM_PROMPT
    ),

    (
        "human",
        """
Current Partial Spec:

{current_spec}


Original User Context:

{user_input}


Validation Errors:

{error_context}
"""
    )
])


# ================================================================
# NODE 1
# STRICT EXTRACTOR
# ================================================================

def strict_extractor_node(
    state: AgentState
) -> Dict[str, Any]:

    """
    User-এর দেওয়া তথ্য strict ভাবে extract করবে।

    Schema-তে field না থাকলে information বাদ দেবে না।
    additional_requirements-এর মধ্যে রাখবে।
    """

    extracted: GraphicDesignSpec = invoke_structured_with_fallback(
        prompt_template=strict_prompt_template,
        output_schema=GraphicDesignSpec,
        input_data={"user_input": state["raw_prompt"]},
    )

    return {
        "extracted_spec": extracted,

        "extraction_attempt_count":
            state.get(
                "extraction_attempt_count",
                0
            ) + 1
    }


# ================================================================
# NODE 2
# PROMPT ↔ JSON COVERAGE VERIFIER
# ================================================================

def prompt_json_verifier_node(
    state: AgentState
) -> Dict[str, Any]:

    """
    Original prompt-এর প্রতিটি explicit requirement
    generated JSON-এ আছে কি না verify করবে।
    """

    spec = state["extracted_spec"]

    result: PromptCoverageResult = invoke_structured_with_fallback(
        prompt_template=coverage_prompt_template,
        output_schema=PromptCoverageResult,
        input_data={
            "user_input": state["raw_prompt"],
            "current_spec": spec.model_dump_json(indent=2),
        },
    )

    return {
        "coverage_complete":
            result.all_user_requirements_captured,

        "coverage_missing_requirements":
            result.missing_requirements,

        "coverage_notes":
            result.verification_notes
    }


# ================================================================
# NODE 3
# EXTRACTION REPAIR
# ================================================================

def extraction_repair_node(
    state: AgentState
) -> Dict[str, Any]:

    """
    Coverage verifier যদি বলে user-এর কোনো requirement
    JSON-এ missing, তাহলে JSON repair করবে।
    """

    missing = state.get(
        "coverage_missing_requirements",
        []
    )

    repaired: GraphicDesignSpec = invoke_structured_with_fallback(
        prompt_template=repair_extraction_prompt_template,
        output_schema=GraphicDesignSpec,
        input_data={
            "user_input": state["raw_prompt"],
            "current_spec": state["extracted_spec"].model_dump_json(indent=2),
            "missing_requirements": json.dumps(missing, indent=2),
        },
    )

    return {
        "extracted_spec": repaired,

        "extraction_attempt_count":
            state.get(
                "extraction_attempt_count",
                0
            ) + 1
    }


# ================================================================
# NODE 4
# GAP DETECTOR
# ================================================================

def gap_detector_node(
    state: AgentState
) -> Dict[str, Any]:

    """
    User যা দেয়নি এমন CORE requirements detect করবে।

    IMPORTANT:

    additional_requirements missing field নয়।

    কারণ additional_requirements শুধুমাত্র user explicitly
    যা extra দিয়েছে সেটি preserve করার জায়গা।
    """

    spec = state[
        "extracted_spec"
    ].model_dump()

    missing: List[str] = []

    if (
        spec.get("target_software")
        == "USER_NOT_PROVIDED"
    ):
        missing.append(
            "Target Software "
            "(Illustrator / Photoshop / After Effects)"
        )

    if (
        spec.get("canvas_dimensions")
        == "USER_NOT_PROVIDED"
    ):
        missing.append(
            "Canvas Dimensions"
        )

    if (
        "USER_NOT_PROVIDED"
        in spec.get(
            "color_palette",
            []
        )
    ):
        missing.append(
            "Color Palette"
        )

    if (
        spec.get("primary_subject")
        == "USER_NOT_PROVIDED"
    ):
        missing.append(
            "Primary Subject"
        )

    if (
        "USER_NOT_PROVIDED"
        in spec.get(
            "editable_typography",
            []
        )
    ):
        missing.append(
            "Exact Editable Typography / Copy Text"
        )

    layers = spec.get(
        "layers",
        []
    )

    if (
        len(layers) == 0
        or any(
            layer.get("layer_name")
            == "USER_NOT_PROVIDED"

            for layer in layers
        )
    ):
        missing.append(
            "Design Layer Breakdown & Visual Hierarchy"
        )

    # ============================================================
    # Motion হলে duration-ও required
    # ============================================================

    if (
        spec.get("asset_type") == "motion"
        and
        spec.get(
            "motion_duration_sec",
            0.0
        ) <= 0.0
    ):
        missing.append(
            "Motion Duration"
        )

    return {
        "missing_fields": missing
    }


# ================================================================
# NODE 5
# AI COMPLETION
# ================================================================

def ai_completion_node(
    state: AgentState
) -> Dict[str, Any]:

    """
    User অনুমতি দিলে missing CORE fields AI পূরণ করবে।
    """

    errors = state.get(
        "validation_errors",
        []
    )

    errors_str = (
        "\n".join(errors)
        if errors
        else "None"
    )

    completed: GraphicDesignSpec = invoke_structured_with_fallback(
        prompt_template=autofill_prompt_template,
        output_schema=GraphicDesignSpec,
        input_data={
            "current_spec": state["extracted_spec"].model_dump_json(indent=2),
            "user_input": state["raw_prompt"],
            "error_context": errors_str,
        },
    )

    return {
        "extracted_spec": completed,

        "autofill_attempt_count":
            state.get(
                "autofill_attempt_count",
                0
            ) + 1
    }


# ================================================================
# HELPER
# Recursive null / empty checker for dynamic requirements
# ================================================================

def validate_dynamic_value(
    value: Any,
    path: str,
    errors: List[str]
):

    if value is None:

        errors.append(
            f"Dynamic requirement '{path}' is null."
        )

        return

    if isinstance(value, str):

        if not value.strip():

            errors.append(
                f"Dynamic requirement '{path}' is empty."
            )

        return

    if isinstance(value, list):

        for index, item in enumerate(value):

            validate_dynamic_value(
                item,
                f"{path}[{index}]",
                errors
            )

        return

    if isinstance(value, dict):

        for key, item in value.items():

            validate_dynamic_value(
                item,
                f"{path}.{key}",
                errors
            )


# ================================================================
# NODE 6
# ZERO-NULL VALIDATOR
# ================================================================

def null_validator_node(
    state: AgentState
) -> Dict[str, Any]:

    """
    Final output-এর required fields valid কিনা verify করবে।
    """

    spec = state.get(
        "extracted_spec"
    )

    errors: List[str] = []

    if not spec:

        return {
            "validation_errors": [
                "Empty model output."
            ],

            "is_complete": False
        }

    spec_dict = spec.model_dump()

    # ============================================================
    # CORE FIELD VALIDATION
    # ============================================================

    for key, value in spec_dict.items():

        # Dynamic requirement আলাদাভাবে নিচে validate করবো
        if key == "additional_requirements":
            continue

        if value is None:

            errors.append(
                f"Field '{key}' is null."
            )

        elif isinstance(
            value,
            str
        ):

            if (
                not value.strip()
                or
                value == "USER_NOT_PROVIDED"
            ):

                errors.append(
                    f"Field '{key}' is missing "
                    "or USER_NOT_PROVIDED."
                )

        elif isinstance(
            value,
            list
        ):

            if len(value) == 0:

                errors.append(
                    f"List field '{key}' is empty."
                )

            elif (
                "USER_NOT_PROVIDED"
                in value
            ):

                errors.append(
                    f"List field '{key}' still "
                    "contains USER_NOT_PROVIDED."
                )

            elif key == "layers":

                for index, layer in enumerate(
                    value
                ):

                    if (
                        layer.get("layer_name")
                        == "USER_NOT_PROVIDED"
                        or
                        not layer.get(
                            "visual_description"
                        )
                    ):

                        errors.append(
                            f"Layer index {index} "
                            "has missing properties."
                        )

    # ============================================================
    # DYNAMIC REQUIREMENT VALIDATION
    # ============================================================

    dynamic_requirements = spec_dict.get(
        "additional_requirements",
        {}
    )

    for key, value in dynamic_requirements.items():

        validate_dynamic_value(
            value,
            f"additional_requirements.{key}",
            errors
        )

    # ============================================================
    # MOTION VALIDATION
    # ============================================================

    if (
        spec_dict.get("asset_type")
        == "motion"
        and
        spec_dict.get(
            "motion_duration_sec",
            0.0
        ) <= 0.0
    ):

        errors.append(
            "asset_type is motion but "
            "motion_duration_sec <= 0."
        )

    # ============================================================
    # SUCCESS
    # ============================================================

    if not errors:

        return {

            "validation_errors": [],

            "is_complete": True,

            "final_output":
                spec_dict
        }

    return {

        "validation_errors":
            errors,

        "is_complete":
            False
    }
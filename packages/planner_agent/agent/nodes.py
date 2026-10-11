from __future__ import annotations

# ============================================================

# Planner Agent - LangGraph Nodes

# ============================================================

#

# RESPONSIBILITY OF THIS FILE:

#

# 1. Prepare clean Planner input

# 2. Ask Gemini to generate a structured execution plan

# 3. Validate the generated plan

# 4. Verify requirement coverage

# 5. Repair / hill-climb weak plans

# 6. Keep the best plan

# 7. Finalize Planner output for Manager
# 8. Resolve and preserve requested graphic output format

#

#

# IMPORTANT ARCHITECTURE RULE:

#

# This file defines WHAT each node does.

#

# It DOES NOT define:

#

# - graph edges

# - workflow routing

# - Manager orchestration

# - asset retrieval

# - graphic generation

# - motion generation

# - tool selection

#

# Those responsibilities belong to their own modules.

#

#

# LOOP ENGINEERING:

#

# generate

#    ↓

# validate

#    ↓

# verify

#    ↓

# repair / hill-climb

#    ↓

# validate again

#

# The actual loop connections will be implemented

# later inside graph.py.

# ============================================================

import json

import os

import re

import time

from typing import Any, Dict, List, Optional

from google import genai

from google.genai import types

from pydantic import BaseModel, Field, ValidationError

from packages.planner_agent.agent.state import PlannerState

from packages.planner_agent.domain.schema import PlannerOutput
from packages.ai.provider import active_provider, openai_model, openai_structured
from packages.provider_secrets.application.runtime import resolve_provider_secret

# ============================================================

# Internal Verification Schema

# ============================================================

#

# This schema is INTERNAL to Planner verification.

#

# Manager does not need this structure.

#

# PlannerOutput = external Planner contract

#

# PlanVerificationResult = internal quality-control contract

# ============================================================

class PlanVerificationResult(BaseModel):

    """

    Structured output returned by Planner verifier.

    This verifier DOES NOT execute the plan.

    It only checks whether the generated plan adequately covers

    the requirements received by Planner.

    """

    complete: bool = False

    # 0 - 100 requirement coverage / planning quality score.

    score: float = Field(

        default=0.0,

        ge=0.0,

        le=100.0,

    )

    # Requirements that are missing from the generated plan.

    missing_requirements: List[str] = Field(default_factory=list)

    # Conflicting or logically inconsistent plan elements.

    contradictions: List[str] = Field(default_factory=list)

    # Weak planning decisions that should be improved.

    weaknesses: List[str] = Field(default_factory=list)

    # Precise instructions that the repair node can use.

    repair_instructions: List[str] = Field(default_factory=list)

# ============================================================

# Planner Configuration

# ============================================================

#

# Environment variables are used instead of hard-coding.

#

# Future:

#

# PLANNER_LLM_PROVIDER=openai

# PLANNER_LLM_PROVIDER=claude

# PLANNER_LLM_PROVIDER=gemini

#

# can later be handled through a provider adapter.

#

# For NOW this Planner uses Gemini only.

# ============================================================

DEFAULT_PLANNER_MODEL = "gemini-2.5-flash"

DEFAULT_MAX_REPAIR_ATTEMPTS = 3

# Score required before Planner considers a plan complete.

#

# IMPORTANT:

# score alone is not enough.

#

# complete must ALSO be True.

MIN_ACCEPTABLE_SCORE = 95.0

# ============================================================

# Planner System Instructions

# ============================================================

PLANNER_SYSTEM_INSTRUCTION = """

You are the Planning Agent inside a multi-agent graphic,

motion-design, and UI/UX production system.

Your responsibility is PLANNING ONLY.

You receive structured requirements that were already extracted

from the user's request.

Your job is to transform those requirements into a complete,

structured, executable plan.

============================================================

YOUR RESPONSIBILITIES

============================================================

You must determine:

1. What work must be done.

2. What tasks are required.

3. Correct task order.

4. Task dependencies.

5. Which tasks may run in parallel.

6. Required capabilities.

7. Inputs required by each task.

8. Expected outputs.

9. Global constraints.

10. Acceptance criteria.

11. Final deliverables.

12. Verification requirements.

13. Whether previous/existing assets are required.

14. What kind of previous assets are required.

15. Any relative time reference for those assets.

16. The most appropriate target production software.

You MUST always set:

target_software

Allowed values:

- adobe_illustrator

- adobe_photoshop

- video_generation

Choose based on the actual design requirements.

Use adobe_illustrator when the work is primarily:

- poster design

- banner design

- typography-heavy composition

- vector illustration

- logo or branding artwork

- scalable graphic layout

- shape/vector-heavy artwork

- print-style graphic composition

Use adobe_photoshop when the work is primarily:

- photo manipulation

- photographic compositing

- raster image editing

- realistic image treatment

- retouching

- pixel-based effects

- complex photographic blending

Use video_generation when the work is primarily:

- motion design

- generated video

- cinematic video

- text-to-video

- image-to-video

- animated visual sequence

- multi-shot motion content

- video-based creative production

IMPORTANT:

video_generation is a generic production target.

Do NOT select:

- Wan

- LTX

- ComfyUI

- FFmpeg

- Runway

- Kling

- Veo

- any API/provider/model

Those execution decisions belong to Motion Agent.

If the user does not explicitly specify software,

you MUST determine the appropriate target_software

from the design requirements.

Never omit target_software.

============================================================

GRAPHIC OUTPUT FORMAT DECISION

============================================================

For graphic_design jobs, you MUST set:

target_output_format

Allowed values:

- psd
- ai
- svg
- jpg

Rules:

- If the user explicitly requests PSD / Photoshop format:
  target_output_format = psd
  target_software = adobe_photoshop

- If the user explicitly requests Adobe Illustrator / AI format:
  target_output_format = ai
  target_software = adobe_illustrator

- If the user explicitly requests SVG:
  target_output_format = svg
  target_software = adobe_illustrator

- If the user explicitly requests JPG or JPEG:
  target_output_format = jpg

- If the user does not specify a graphic output format:
  target_output_format = jpg

- PNG is NOT supported.
  If the user requests PNG:
  target_output_format = jpg

IMPORTANT:

- target_output_format is a planning requirement.
- It does NOT select a provider, model, API, bridge, renderer,
  plugin, or implementation library.
- For motion_design jobs, this graphic artifact decision does not
  apply. Leave target_output_format null / omitted if the schema
  allows that.

============================================================

PREVIOUS ASSET DETECTION

============================================================

You MUST identify whether the request refers to existing or

previous materials.

Examples:

"Use our logo from two months ago"

previous_asset_required = true

asset_requests should contain a brand_logo request with:

time_reference.offset_months = -2

"Use the previous campaign image"

previous_asset_required = true

"Create a completely new logo"

previous_asset_required = false

asset_requests = []

============================================================

STRICT BOUNDARIES

============================================================

DO NOT:

- retrieve assets

- search RAG

- access files

- choose asset IDs

- invent asset paths

- select Canva

- select After Effects

- select Nano Banana

- select Stitch

- select rendering tools

- select implementation libraries

- select specific creative tools

- execute design work

- execute motion work

- generate final design assets

Execution-tool choice belongs to specialized execution agents.

You MAY choose only the required target production software

through the target_software field.

Do NOT choose the execution mechanism, API, model,

bridge, plugin, renderer, or implementation library.

You may describe REQUIRED CAPABILITIES.

Example:

GOOD:

"required_capabilities": [

    "vector_editing",

    "brand_consistency"

]

BAD:

"Use Adobe Illustrator"

============================================================

PLANNING QUALITY

============================================================

Every meaningful user requirement must appear somewhere in:

- tasks

- constraints

- expected outputs

- deliverables

- acceptance criteria

- asset requests

- verification checks

Before producing graphic_execution_spec, produce design_specification with:

- design_type and brief
- content_hierarchy with primary, secondary, supporting, CTA, and decorative priorities
- visual_hierarchy
- art_direction
- composition intent
- typography intent
- semantic color roles
- requirement_coverage for every explicit user text and color

Also make the design decisions explicit in design_specification:

- concept: the visual idea that communicates the purpose
- content_hierarchy: primary, secondary, supporting, CTA, metadata, decorative,
  with prominence, grouping, reading order, and emphasis
- visual_hierarchy: focal point, visual anchor, reading path, and whitespace intent
- composition: strategy, grid/alignment, balance, margins, safe area, density,
  focal placement, and semantic content regions
- typography: display/body roles, hierarchy levels, font personality, scale,
  weight, casing, wrapping, density, contrast, and readability
- color_system: semantic roles plus contrast, dominance, temperature, saturation,
  harmony, accent usage, and foreground/background relationship
- art_direction: mood, tone, visual language, imagery, shape language, texture,
  lighting, depth, abstraction level, and visual density
- asset_strategy: whether imagery is required and the role/treatment of assets
- design_tokens: implementation-neutral spacing, margin, radius, border, shadow,
  opacity, and density intent
- user_requirements and designer_decisions must remain separate

design_specification describes provider-neutral design decisions. It must not
contain SVG markup, renderer commands, provider names, model names, artifact
paths, or filesystem details. graphic_execution_spec remains the separate
renderer-facing execution representation derived from those decisions.

For every graphic_design job, populate graphic_execution_spec.

graphic_execution_spec must be a generic, tool-neutral,

structured scene plan.

Do NOT use Adobe Illustrator commands.

Do NOT use Photoshop commands.

Do NOT use software-specific object names.

Represent the design using generic:

- document

- palette

- assets

- layers

- elements

- placement

- geometry

- style

- typography

- children/groups

Use generic element types such as:

- text

- rectangle

- ellipse

- line

- polygon

- path

- image

- group

- symbol

- custom

Complex visual subjects should be decomposed into generic

primitive elements whenever reasonably possible.

Do not only describe visual intent in natural language.

Provide enough structured data for a deterministic renderer

to execute the composition.

Do not hardcode a poster, banner, logo, mobile phone,

or any other specific design pattern.

The same schema must work for arbitrary graphic-design jobs.

Do not silently remove requirements.

Do not invent major requirements that were not requested.

Keep tasks modular.

Avoid unnecessary task fragmentation.

Use dependencies only where logically required.

Use parallel execution where safe.

The final plan must be implementation-independent.

"""

# ============================================================

# Verification System Instruction

# ============================================================

VERIFIER_SYSTEM_INSTRUCTION = """

You are the verification component of a Planning Agent.

You are NOT verifying a finished graphic or motion artifact.

You are verifying whether a generated EXECUTION PLAN correctly

covers the structured user requirements.

Check:

1. Requirement coverage

2. Missing tasks

3. Missing deliverables

4. Missing constraints

5. Dependency correctness

6. Execution-order consistency

7. Previous-asset requirements

8. Acceptance criteria

9. Verification criteria

10. Contradictions

11. Unsupported assumptions

12. Whether the Planner incorrectly selected implementation tools
13. Graphic target_output_format correctness
14. PNG rejection / JPG fallback policy
15. Consistency between target_output_format and target_software

A plan is complete only when all meaningful requirements are

represented and the plan is internally consistent.

Scoring guidance:

100 = complete and internally consistent

95-99 = effectively complete, only negligible issues

85-94 = usable but important improvements remain

70-84 = multiple missing or weak requirements

below 70 = major planning problems

Do not give a high score when a meaningful requirement is missing.

Return actionable repair instructions.

"""

# ============================================================

# Hill-Climbing / Repair Instruction

# ============================================================

REPAIR_SYSTEM_INSTRUCTION = """

You are the repair component of a Planning Agent.

You receive:

1. Original structured requirements

2. Current execution plan

3. Verification feedback

Your responsibility is to produce an IMPROVED execution plan.

This is a hill-climbing step.

Preserve everything that is already correct.

Fix only what is missing, weak, contradictory, or incomplete.

Do not unnecessarily rewrite good parts.

Do not remove valid user requirements.

Do not select execution tools.

You MUST ensure target_software is present and appropriate.

For graphic_design jobs, preserve the resolved target_output_format.

Allowed target_output_format values:

- psd
- ai
- svg
- jpg

Rules:

- PSD -> psd and adobe_photoshop
- AI / Adobe Illustrator format -> ai and adobe_illustrator
- SVG -> svg and adobe_illustrator
- JPG / JPEG -> jpg
- PNG -> jpg
- no explicit graphic format -> jpg

Do NOT invent PNG as an output format.
Do NOT change the resolved output format during repair.

Allowed target_software values:

- adobe_illustrator

- adobe_photoshop

- video_generation

Selecting target_software is a planning decision.

Do NOT select the execution API, model, bridge,

plugin, renderer, or JSX implementation.

Do not retrieve assets.

Do not perform design work.

Return a complete PlannerOutput object, not a patch.

"""

# ============================================================

# Gemini Client Helper

# ============================================================

def _get_gemini_client() -> genai.Client:

    """

    Create Gemini client lazily.

    Why lazy initialization?

    - Importing nodes.py should not immediately call Gemini.

    - Tests can import this file without triggering an API request.

    - Future provider replacement becomes easier.

    """

    api_key = resolve_provider_secret(
        "gemini",
        environment_names=("PLANNER_GEMINI_API_KEY", "GEMINI_API_KEY"),
    )

    if not api_key:

        raise RuntimeError(

            "PLANNER_GEMINI_API_KEY is missing. "

            "Add PLANNER_GEMINI_API_KEY to your .env/environment."

        )

    return genai.Client(api_key=api_key)

def _get_planner_model() -> str:

    """

    Model can be changed without changing code.

    Example .env:

    PLANNER_MODEL=gemini-3.5-flash-lite

    """

    if active_provider() == "openai":
        return openai_model("OPENAI_PLANNER_MODEL")
    return os.getenv("PLANNER_MODEL", DEFAULT_PLANNER_MODEL)


def _gemini_response_schema(model_type: type[BaseModel]) -> dict:
    """Convert Pydantic schema to Gemini Developer API-compatible schema.

    The Developer API rejects ``additionalProperties`` and local ``$ref`` /
    nullable unions in structured-output schemas. The domain model remains the
    validation authority; this is only a transport-schema projection.
    """
    # PlannerOutput contains the complete generic scene graph. Gemini's
    # Developer API rejects that deeply nested transport schema. Keep the
    # provider schema shallow while retaining strict post-response validation.
    if model_type.__name__ == "PlannerOutput":
        return {
            "type": "object",
            "properties": {
                "planner_status": {"type": "string", "enum": ["completed", "failed"]},
                "job_summary": {"type": "string"},
                "primary_job_type": {"type": "string", "enum": ["graphic_design", "motion_design", "ui_ux_design", "mixed", "unknown"]},
                "target_software": {"type": "string", "enum": ["adobe_illustrator", "adobe_photoshop", "video_generation"]},
                "target_output_format": {"type": "string", "enum": ["psd", "ai", "svg", "jpg"]},
                "previous_asset_required": {"type": "boolean"},
                "asset_requests": {"type": "array", "items": {"type": "object"}},
                "tasks": {"type": "array", "items": {"type": "object"}},
                "graphic_execution_spec": {"type": "object"},
                "design_specification": {"type": "object"},
                "execution_order": {"type": "array", "items": {"type": "string"}},
                "global_constraints": {"type": "array", "items": {"type": "string"}},
                "final_deliverables": {"type": "array", "items": {"type": "string"}},
                "verification": {"type": "object"},
            },
            "required": [
                "job_summary", "primary_job_type", "target_software", "target_output_format",
                "previous_asset_required", "asset_requests", "tasks", "graphic_execution_spec",
                "design_specification", "execution_order", "global_constraints",
                "final_deliverables", "verification",
            ],
        }

    source = model_type.model_json_schema()
    definitions = source.get("$defs", {})

    def project(node, resolving=None):
        resolving = resolving or set()
        if not isinstance(node, dict):
            return node
        if "$ref" in node:
            name = str(node["$ref"]).rsplit("/", 1)[-1]
            if name in resolving:
                return {"type": "object", "properties": {}}
            return project(definitions.get(name, {"type": "object"}), resolving | {name})
        if "anyOf" in node:
            options = [item for item in node["anyOf"] if item.get("type") != "null"]
            return project(options[0] if options else {"type": "string"}, resolving)
        result = {}
        for key in ("type", "enum", "format", "properties", "required", "items"):
            if key in node:
                if key == "properties":
                    result[key] = {name: project(value, resolving) for name, value in node[key].items()}
                elif key == "items":
                    result[key] = project(node[key], resolving)
                else:
                    result[key] = node[key]
        # Gemini requires object properties to be closed in Developer API mode.
        if result.get("type") == "object":
            result.setdefault("properties", {})
            result.setdefault("required", list(result["properties"].keys()))
        return result

    return project(source)

# ============================================================

# Generic Structured Gemini Call

# ============================================================

def _generate_structured(
    *,
    system_instruction: str,
    prompt: str,
    response_schema: type[BaseModel],
) -> BaseModel:
    """
    Single reusable Gemini structured-output function.
    Includes automatic exponential backoff retries on 503/429 errors
    and fallback model switching.
    """
    if active_provider() == "openai":
        payload = openai_structured(
            model=_get_planner_model(),
            prompt=prompt,
            system_instruction=system_instruction,
            schema=response_schema.model_json_schema(),
            schema_name=response_schema.__name__,
        )
        return response_schema.model_validate(payload)

    client = _get_gemini_client()
    primary_model = _get_planner_model()

    candidate_models = [
        primary_model,
        "gemini-flash-latest",
        "gemini-flash-lite-latest",
        "gemini-pro-latest",
        "gemini-3.5-flash-lite",
    ]

    last_exception = None
    seen_models = set()

    for model in candidate_models:
        if not model or model in seen_models:
            continue
        seen_models.add(model)

        for attempt in range(1, 4):
            try:
                response = client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        **{
                            "system_instruction": system_instruction,
                            "response_mime_type": "application/json",
                            "response_schema": _gemini_response_schema(response_schema),
                        }
                    ),
                )

                if response.parsed is not None:
                    return response.parsed

                if not response.text:
                    raise RuntimeError(
                        "Gemini returned an empty response."
                    )

                return response_schema.model_validate_json(
                    response.text
                )

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

                if is_transient and attempt < 3:
                    wait_sec = attempt * 2
                    print(
                        f"[PLANNER GEMINI RETRY] Model {model} temporary error ({exc_str[:80]}). "
                        f"Retrying attempt {attempt}/3 in {wait_sec}s..."
                    )
                    time.sleep(wait_sec)
                else:
                    print(
                        f"[PLANNER GEMINI FALLBACK] Model {model} failed ({exc_str[:100]}). "
                        f"Trying next fallback model..."
                    )
                    break

    raise RuntimeError(
        f"All Planner LLM retries and fallback attempts failed. Last error: {last_exception}"
    ) from last_exception

# ============================================================

# Small State Helper

# ============================================================

def _append_debug(

    state: PlannerState,

    message: str,

) -> List[str]:

    """

    Return a NEW debug list.

    We avoid mutating the existing state list directly.

    This makes LangGraph state updates easier to reason about.

    """

    messages = list(

        state.get("debug_messages", [])

    )

    messages.append(message)

    return messages

# Output format resolver

def _resolve_target_output_format(
    original_user_request: str | None,
) -> str:
    """
    Resolve the requested GRAPHIC output format from the original
    user request.

    Product rules:

    - explicit PSD / Photoshop format -> "psd"
    - explicit AI / Adobe Illustrator format -> "ai"
    - explicit SVG -> "svg"
    - explicit JPG / JPEG -> "jpg"
    - explicit PNG -> "jpg" because PNG is unsupported
    - no explicit graphic format -> "jpg"

    IMPORTANT:

    Plain "AI" is NOT treated as Adobe Illustrator automatically,
    because the user may mean Artificial Intelligence.

    This helper decides only the requested artifact format.
    It does NOT choose provider/model/tool/bridge/renderer.
    """

    text = (
        original_user_request
        or ""
    ).strip().lower()

    # --------------------------------------------------------
    # Prefer explicit output/export/save format phrases.
    # --------------------------------------------------------

    explicit_patterns = [
        (
            "psd",
            r"(?:output|export|save|deliver|provide|give|create)"
            r"(?:\s+it|\s+this|\s+the\s+(?:design|file|image))?"
            r"\s+(?:as|in|to)?\s*(?:\.psd|psd)\b",
        ),
        (
            "ai",
            r"(?:output|export|save|deliver|provide|give|create)"
            r"(?:\s+it|\s+this|\s+the\s+(?:design|file|image))?"
            r"\s+(?:as|in|to)?\s*(?:\.ai|ai\s+(?:format|file)|adobe\s+illustrator)\b",
        ),
        (
            "svg",
            r"(?:output|export|save|deliver|provide|give|create)"
            r"(?:\s+it|\s+this|\s+the\s+(?:design|file|image))?"
            r"\s+(?:as|in|to)?\s*(?:\.svg|svg)\b",
        ),
        (
            "jpg",
            r"(?:output|export|save|deliver|provide|give|create)"
            r"(?:\s+it|\s+this|\s+the\s+(?:design|file|image))?"
            r"\s+(?:as|in|to)?\s*(?:\.jpe?g|jpe?g)\b",
        ),
        (
            "jpg",
            r"(?:output|export|save|deliver|provide|give|create)"
            r"(?:\s+it|\s+this|\s+the\s+(?:design|file|image))?"
            r"\s+(?:as|in|to)?\s*(?:\.png|png)\b",
        ),
    ]

    for resolved_format, pattern in explicit_patterns:
        if re.search(pattern, text):
            return resolved_format

    # --------------------------------------------------------
    # Direct explicit format mentions.
    # --------------------------------------------------------

    if re.search(
        r"\bpsd\s+(?:format|file)\b"
        r"|\bphotoshop\s+(?:format|file)\b"
        r"|\.psd\b",
        text,
    ):
        return "psd"

    if re.search(
        r"\bai\s+(?:format|file)\b"
        r"|\badobe\s+illustrator\b"
        r"|\billustrator\s+(?:format|file)\b"
        r"|\.ai\b",
        text,
    ):
        return "ai"

    if re.search(
        r"\bsvg\b|\.svg\b",
        text,
    ):
        return "svg"

    if re.search(
        r"\bjpg\b"
        r"|\bjpeg\b"
        r"|\.jpg\b"
        r"|\.jpeg\b",
        text,
    ):
        return "jpg"

    # PNG is intentionally unsupported.
    if re.search(
        r"\bpng\b|\.png\b",
        text,
    ):
        return "jpg"

    # Default graphic output.
    return "jpg"


def _apply_graphic_output_format_policy(
    plan: PlannerOutput,
    resolved_format: str,
) -> PlannerOutput:
    """
    Enforce the deterministic graphic-output decision on a
    generated/repaired PlannerOutput.

    Gemini performs the planning, but explicit format policy must
    not drift between initial planning and repair iterations.

    The policy applies only to graphic_design jobs.

    Software alignment:
    - PSD -> Photoshop
    - AI  -> Illustrator
    - SVG -> Illustrator
    - JPG -> keep Planner's design-driven software choice
    """

    if getattr(
        plan,
        "primary_job_type",
        None,
    ) != "graphic_design":
        return plan

    # PlannerOutput schema must define target_output_format.
    plan.target_output_format = resolved_format

    if resolved_format == "psd":
        plan.target_software = "adobe_photoshop"

    elif resolved_format in {
        "ai",
        "svg",
    }:
        plan.target_software = "adobe_illustrator"

    return plan


# ============================================================

# NODE 1

# Prepare Planner Input

# ============================================================

def prepare_input_node(

    state: PlannerState,

) -> Dict[str, Any]:

    """

    Normalize Manager input before sending anything to Gemini.

    This node does NOT plan.

    This node does NOT call an LLM.

    Its responsibility is input preparation only.

    """

    print()

    print("=" * 70)

    print("[PLANNER AGENT] Task received from Manager")

    print("=" * 70)

    manager_input = state.get(

        "manager_input",

        {},

    )

    json_agent_output = state.get(

        "json_agent_output",

        {},

    )

    original_user_request = state.get(

        "original_user_request",

    )

    # --------------------------------------------------------

    # Prefer explicitly supplied JSON Agent output.

    #

    # If Manager embeds it inside manager_input,

    # use that as a safe fallback.

    # --------------------------------------------------------

    if not json_agent_output:

        possible_json_output = manager_input.get(

            "json_agent_output"

        )

        if isinstance(

            possible_json_output,

            dict,

        ):

            json_agent_output = possible_json_output

    # --------------------------------------------------------

    # Planner should receive only relevant planning information.

    #

    # We do NOT send the whole Manager internal state to Gemini.

    #

    # Benefits:

    #

    # - lower token usage

    # - less accidental coupling

    # - better security boundary

    # - more stable prompts

    # --------------------------------------------------------

    prepared_input = {

        "structured_requirements": json_agent_output,

    }

    if original_user_request:

        prepared_input[

            "original_user_request"

        ] = original_user_request

    print(

        "[PLANNER AGENT] Input prepared."

    )

    return {

        "status": "preparing",

        "current_step": "prepare_input",

        "prepared_input": prepared_input,

        "json_agent_output": json_agent_output,

        "repair_attempt": state.get(

            "repair_attempt",

            0,

        ),

        "max_repair_attempts": state.get(

            "max_repair_attempts",

            DEFAULT_MAX_REPAIR_ATTEMPTS,

        ),

        "planning_iteration": state.get(

            "planning_iteration",

            0,

        ),

        "verification_score": 0.0,

        "verification_feedback": [],

        "best_score": state.get(

            "best_score",

            0.0,

        ),

        "validation_passed": False,

        "validation_errors": [],

        "error": None,

        "llm_provider": "gemini",

        "llm_model": _get_planner_model(),

        "debug_messages": _append_debug(

            state,

            "Planner input prepared.",

        ),

    }

# ============================================================

# NODE 2

# Initial Planning

# ============================================================

def planning_node(
    state: PlannerState,
) -> Dict[str, Any]:
    """
    Main Planner reasoning node.

    Gemini creates the FIRST candidate execution plan.

    This node does NOT decide whether the plan is good enough.
    Verification is intentionally separated.

    RECENT REQUIREMENT:

    For graphic_design jobs, Planner also decides the requested
    final artifact format from the original user request.

    Supported graphic formats:
    - psd
    - ai
    - svg
    - jpg

    PNG is intentionally unsupported and resolves to JPG.
    """

    prepared_input = state.get(
        "prepared_input",
        {},
    )

    original_user_request = (
        prepared_input.get(
            "original_user_request"
        )
        or state.get(
            "original_user_request"
        )
        or ""
    )

    # ========================================================
    # RESOLVE REQUESTED GRAPHIC OUTPUT FORMAT
    # ========================================================
    #
    # This is deterministic requirement policy.
    #
    # Gemini still performs the planning itself.
    # The resolver only prevents output-format drift.
    # ========================================================

    target_output_format = (
        _resolve_target_output_format(
            original_user_request
        )
    )

    print(
        "[PLANNER AGENT] "
        "Resolved graphic output format = "
        f"{target_output_format}"
    )

    print(
        "[PLANNER AGENT] Planning with "
        f"{_get_planner_model()}..."
    )

    prompt = f"""
Create a complete execution plan for the following request.

STRUCTURED INPUT:

{json.dumps(
    prepared_input,
    ensure_ascii=False,
    indent=2,
)}

Remember:

- cover every meaningful requirement
- identify previous asset requirements

- determine target_software
- target_software must be one of:
  adobe_illustrator,
  adobe_photoshop,
  video_generation

- use video_generation for motion/video generation jobs
- choose target_software based on the actual design requirement

GRAPHIC OUTPUT FORMAT POLICY:

- for graphic_design jobs, target_output_format must be exactly one of:
  psd
  ai
  svg
  jpg

- the deterministic resolver selected:
  {target_output_format}

- if this is a graphic_design job, use exactly that value

- PSD requires:
  target_output_format = psd
  target_software = adobe_photoshop

- Adobe Illustrator / AI format requires:
  target_output_format = ai
  target_software = adobe_illustrator

- SVG requires:
  target_output_format = svg
  target_software = adobe_illustrator

- JPG / JPEG requires:
  target_output_format = jpg

- PNG is unsupported and must become:
  target_output_format = jpg

- if the user did not specify a graphic format:
  target_output_format = jpg

- for motion_design jobs, do not treat this graphic-format
  decision as a motion/video output-format requirement

IMPORTANT BOUNDARIES:

- do not retrieve assets
- do not choose execution APIs, models, plugins, bridges,
  renderers, video models, or post-processing tools
- return only the structured PlannerOutput
"""

    try:
        plan = _generate_structured(
            system_instruction=PLANNER_SYSTEM_INSTRUCTION,
            prompt=prompt,
            response_schema=PlannerOutput,
        )

        if not isinstance(
            plan,
            PlannerOutput,
        ):
            plan = PlannerOutput.model_validate(
                plan
            )

        # ====================================================
        # ENFORCE DETERMINISTIC GRAPHIC FORMAT POLICY
        # ====================================================
        #
        # Requirement interpretation belongs to Planner.
        # Execution mechanism still belongs to Graphic Agent.
        # ====================================================

        plan = _apply_graphic_output_format_policy(
            plan,
            target_output_format,
        )

        if getattr(
            plan,
            "primary_job_type",
            None,
        ) == "graphic_design":
            print(
                "[PLANNER AGENT] "
                "Final target output format = "
                f"{plan.target_output_format}"
            )

        print(
            "[PLANNER AGENT] Initial plan generated."
        )

        return {
            "status": "planning",
            "current_step": "initial_planning",

            "llm_plan_raw": plan.model_dump(),

            "validated_plan": None,

            "planning_iteration": (
                state.get(
                    "planning_iteration",
                    0,
                )
                + 1
            ),

            "validation_passed": False,
            "validation_errors": [],

            "debug_messages": _append_debug(
                state,
                "Initial Planner candidate generated.",
            ),
        }

    except Exception as exc:

        print(
            "[PLANNER AGENT] Planning error:",
            str(exc),
        )

        return {
            "status": "failed",
            "current_step": "initial_planning_failed",
            "error": str(exc),

            "debug_messages": _append_debug(
                state,
                f"Planning failed: {exc}",
            ),
        }


# ============================================================

# NODE 3

# Deterministic Schema + Structural Validation

# ============================================================

def validate_plan_node(

    state: PlannerState,

) -> Dict[str, Any]:

    """

    Deterministic validation layer.

    NO LLM is used here.

    Why?

    Basic structural correctness should not consume tokens.

    Checks:

    - PlannerOutput schema

    - tasks exist

    - execution order references real tasks

    - dependency references are valid

    - previous asset consistency
    - graphic target_output_format support
    - output-format / target-software consistency

    """

    print(

        "[PLANNER AGENT] Validating plan..."

    )

    raw_plan = state.get(

        "llm_plan_raw"

    )

    errors: List[str] = []

    if not raw_plan:

        errors.append(

            "Planner produced no plan."

        )

        return {

            "status": "validating",

            "current_step": "schema_validation",

            "validation_passed": False,

            "validation_errors": errors,

            "debug_messages": _append_debug(

                state,

                "Validation failed: no plan.",

            ),

        }

    try:

        plan = PlannerOutput.model_validate(

            raw_plan

        )

    except ValidationError as exc:

        errors.append(str(exc))

        return {

            "status": "validating",

            "current_step": "schema_validation",

            "validation_passed": False,

            "validation_errors": errors,

            "debug_messages": _append_debug(

                state,

                "PlannerOutput schema validation failed.",

            ),

        }

    # --------------------------------------------------------

    # Invariant 1:

    # A useful execution plan needs at least one task.

    # --------------------------------------------------------

    if not plan.tasks:

        errors.append(

            "Plan contains no executable tasks."

        )

    # --------------------------------------------------------

    # Collect task IDs once.

    # --------------------------------------------------------

    task_ids = {

        task.task_id

        for task in plan.tasks

    }

    # --------------------------------------------------------

    # Invariant 2:

    # execution_order must reference existing tasks.

    # --------------------------------------------------------

    for task_id in plan.execution_order:

        if task_id not in task_ids:

            errors.append(

                "execution_order references "

                f"unknown task_id: {task_id}"

            )

    # --------------------------------------------------------

    # Invariant 3:

    # dependencies must reference existing tasks.

    # --------------------------------------------------------

    for task in plan.tasks:

        for dependency in task.depends_on:

            if dependency not in task_ids:

                errors.append(

                    f"{task.task_id} depends on "

                    f"unknown task: {dependency}"

                )

            if dependency == task.task_id:

                errors.append(

                    f"{task.task_id} cannot depend on itself."

                )

    # --------------------------------------------------------

    # Invariant 4:

    # Previous asset flag and requests must agree.

    # --------------------------------------------------------

    if (

        plan.previous_asset_required

        and not plan.asset_requests

    ):

        errors.append(

            "previous_asset_required is true "

            "but asset_requests is empty."

        )

    if (

        not plan.previous_asset_required

        and plan.asset_requests

    ):

        errors.append(

            "asset_requests exist while "

            "previous_asset_required is false."

        )

    # --------------------------------------------------------
    # Invariant 5:
    # Graphic output format must follow product policy.
    # --------------------------------------------------------
    #
    # Supported graphic formats:
    # - psd
    # - ai
    # - svg
    # - jpg
    #
    # PNG is intentionally unsupported.
    # --------------------------------------------------------

    if getattr(
        plan,
        "primary_job_type",
        None,
    ) == "graphic_design":

        supported_output_formats = {
            "psd",
            "ai",
            "svg",
            "jpg",
        }

        target_output_format = getattr(
            plan,
            "target_output_format",
            None,
        )

        if (
            target_output_format
            not in supported_output_formats
        ):
            errors.append(
                "Unsupported target_output_format: "
                f"{target_output_format!r}. "
                "Allowed graphic formats are: "
                "psd, ai, svg, jpg."
            )

        # ----------------------------------------------------
        # Invariant 6:
        # Native editable formats and production software
        # must remain consistent.
        # ----------------------------------------------------

        if (
            target_output_format == "psd"
            and plan.target_software
            != "adobe_photoshop"
        ):
            errors.append(
                "PSD output requires "
                "target_software='adobe_photoshop'."
            )

        if (
            target_output_format
            in {"ai", "svg"}
            and plan.target_software
            != "adobe_illustrator"
        ):
            errors.append(
                f"{target_output_format.upper()} output "
                "requires "
                "target_software='adobe_illustrator'."
            )

    passed = len(errors) == 0

    if passed:

        print(

            "[PLANNER AGENT] Structural validation PASSED."

        )

    else:

        print(

            "[PLANNER AGENT] Structural validation FAILED."

        )

    return {

        "status": "validating",

        "current_step": "schema_validation",

        "validated_plan": (

            plan

            if passed

            else None

        ),

        "validation_passed": passed,

        "validation_errors": errors,

        "previous_asset_required": (

            plan.previous_asset_required

        ),

        "asset_requests": [

            asset.model_dump()

            for asset in plan.asset_requests

        ],

        "debug_messages": _append_debug(

            state,

            (

                "Structural validation passed."

                if passed

                else

                "Structural validation failed."

            ),

        ),

    }

# ============================================================

# NODE 4

# Requirement Verification

# ============================================================

def verify_plan_node(

    state: PlannerState,

) -> Dict[str, Any]:

    """

    Semantic verification node.

    The deterministic validator checks structure.

    This node checks MEANING.

    Example:

    User requested:

        editable SVG

    Planner forgot it.

    Schema can still be valid.

    Semantic verifier should catch it.

    """

    print(

        "[PLANNER AGENT] Verifying requirement coverage..."

    )

    validated_plan = state.get(

        "validated_plan"

    )

    if validated_plan is None:

        return {

            "verification_score": 0.0,

            "verification_feedback": [

                "Plan cannot be semantically verified "

                "because structural validation failed."

            ],

            "debug_messages": _append_debug(

                state,

                "Semantic verification skipped because "

                "structural validation failed.",

            ),

        }

    prepared_input = state.get(

        "prepared_input",

        {},

    )

    prompt = f"""

Compare the ORIGINAL REQUIREMENTS against the GENERATED PLAN.

ORIGINAL REQUIREMENTS:

{json.dumps(

    prepared_input,

    ensure_ascii=False,

    indent=2,

)}

GENERATED PLAN:

{json.dumps(

    validated_plan.model_dump(),

    ensure_ascii=False,

    indent=2,

)}

Determine whether the plan fully covers the request.

Pay special attention to:

- missing user requirements

- previous asset references

- task dependencies

- deliverables

- constraints

- acceptance criteria

- verification coverage

- accidental tool selection

- target_software presence

- target_software suitability for the requested design
- target_output_format correctness for graphic_design jobs
- PSD -> adobe_photoshop consistency
- AI/SVG -> adobe_illustrator consistency
- PNG must never be selected as target_output_format
- no explicit graphic format -> JPG

"""

    try:

        verification = _generate_structured(

            system_instruction=VERIFIER_SYSTEM_INSTRUCTION,

            prompt=prompt,

            response_schema=PlanVerificationResult,

        )

        if not isinstance(

            verification,

            PlanVerificationResult,

        ):

            verification = (

                PlanVerificationResult.model_validate(

                    verification

                )

            )

        feedback = (

            verification.missing_requirements

            + verification.contradictions

            + verification.weaknesses

            + verification.repair_instructions

        )

        # ----------------------------------------------------

        # Keep current plan if it becomes the best candidate.

        # ----------------------------------------------------

        previous_best_score = state.get(

            "best_score",

            0.0,

        )

        current_score = verification.score

        update_best = (

            current_score > previous_best_score

            or state.get("best_plan") is None

        )

        best_plan = (

            validated_plan

            if update_best

            else state.get("best_plan")

        )

        best_score = (

            current_score

            if update_best

            else previous_best_score

        )

        complete = (

            verification.complete

            and current_score >= MIN_ACCEPTABLE_SCORE

            and not verification.missing_requirements

            and not verification.contradictions

        )

        print(

            "[PLANNER AGENT] Verification score: "

            f"{current_score:.1f}/100"

        )

        if complete:

            print(

                "[PLANNER AGENT] Requirements covered."

            )

        else:

            print(

                "[PLANNER AGENT] Improvement required."

            )

        return {

            "status": (

                "completed"

                if complete

                else "repairing"

            ),

            "current_step": "requirement_verification",

            "verification_score": current_score,

            "verification_feedback": feedback,

            "best_plan": best_plan,

            "best_score": best_score,

            # Internal completion marker.

            #

            # graph.py will use this later.

            "metadata_complete": complete,

            "debug_messages": _append_debug(

                state,

                (

                    "Plan verification complete. "

                    f"score={current_score:.1f}"

                ),

            ),

        }

    except Exception as exc:

        return {

            "status": "repairing",

            "verification_score": 0.0,

            "verification_feedback": [

                f"Verification error: {exc}"

            ],

            "debug_messages": _append_debug(

                state,

                f"Verifier error: {exc}",

            ),

        }

# ============================================================

# NODE 5

# Hill-Climbing Repair

# ============================================================

def hill_climb_node(
    state: PlannerState,
) -> Dict[str, Any]:
    """
    Improve the existing plan instead of starting from zero.

    This is our agent repair / hill-climbing step.

    Principles:

    - preserve good work
    - repair weak work
    - do not blindly regenerate
    - maintain best-so-far plan
    - use bounded attempts
    - preserve deterministic graphic output-format policy
    """

    current_attempt = state.get(
        "repair_attempt",
        0,
    )

    max_attempts = state.get(
        "max_repair_attempts",
        DEFAULT_MAX_REPAIR_ATTEMPTS,
    )

    next_attempt = current_attempt + 1

    print(
        "[PLANNER AGENT] Hill-climbing repair "
        f"{next_attempt}/{max_attempts}..."
    )

    # --------------------------------------------------------
    # Prefer the current validated candidate.
    #
    # If unavailable, fall back to best candidate.
    # --------------------------------------------------------

    current_plan = state.get(
        "validated_plan"
    )

    if current_plan is None:
        current_plan = state.get(
            "best_plan"
        )

    if current_plan is None:

        return {
            "status": "failed",
            "current_step": "hill_climb_failed",

            "error": (
                "No valid plan exists to repair."
            ),

            "repair_attempt": next_attempt,

            "debug_messages": _append_debug(
                state,
                "Hill-climbing failed: no repairable plan.",
            ),
        }

    feedback = state.get(
        "verification_feedback",
        [],
    )

    validation_errors = state.get(
        "validation_errors",
        [],
    )

    prepared_input = state.get(
        "prepared_input",
        {},
    )

    original_user_request = (
        prepared_input.get(
            "original_user_request"
        )
        or state.get(
            "original_user_request"
        )
        or ""
    )

    resolved_target_output_format = (
        _resolve_target_output_format(
            original_user_request
        )
    )

    prompt = f"""
Improve the CURRENT PLAN.

ORIGINAL REQUIREMENTS:

{json.dumps(
    prepared_input,
    ensure_ascii=False,
    indent=2,
)}

CURRENT PLAN:

{json.dumps(
    current_plan.model_dump(),
    ensure_ascii=False,
    indent=2,
)}

CURRENT SCORE:

{state.get("verification_score", 0.0)}

VERIFICATION FEEDBACK:

{json.dumps(
    feedback,
    ensure_ascii=False,
    indent=2,
)}

STRUCTURAL VALIDATION ERRORS:

{json.dumps(
    validation_errors,
    ensure_ascii=False,
    indent=2,
)}

Produce a complete improved PlannerOutput.

Preserve correct parts.

Fix identified weaknesses.

For graphic_design jobs, preserve this resolved
target_output_format exactly:

{resolved_target_output_format}

Do not introduce PNG.

Remember:
- PSD -> adobe_photoshop
- AI  -> adobe_illustrator
- SVG -> adobe_illustrator
- JPG -> keep the appropriate design-driven target software

The new candidate should improve requirement coverage and
internal consistency.
"""

    try:
        repaired_plan = _generate_structured(
            system_instruction=REPAIR_SYSTEM_INSTRUCTION,
            prompt=prompt,
            response_schema=PlannerOutput,
        )

        if not isinstance(
            repaired_plan,
            PlannerOutput,
        ):
            repaired_plan = (
                PlannerOutput.model_validate(
                    repaired_plan
                )
            )

        # ====================================================
        # RE-ENFORCE FORMAT POLICY AFTER REPAIR
        # ====================================================
        #
        # Hill-climbing must not change an explicit/default
        # format decision that Planner already resolved.
        # ====================================================

        repaired_plan = (
            _apply_graphic_output_format_policy(
                repaired_plan,
                resolved_target_output_format,
            )
        )

        print(
            "[PLANNER AGENT] Improved candidate generated."
        )

        if getattr(
            repaired_plan,
            "primary_job_type",
            None,
        ) == "graphic_design":
            print(
                "[PLANNER AGENT] "
                "Repaired target output format = "
                f"{repaired_plan.target_output_format}"
            )

        return {
            "status": "planning",
            "current_step": "hill_climb",

            "llm_plan_raw": repaired_plan.model_dump(),

            # Must be validated again.
            "validated_plan": None,

            "validation_passed": False,
            "validation_errors": [],

            "repair_attempt": next_attempt,

            "planning_iteration": (
                state.get(
                    "planning_iteration",
                    0,
                )
                + 1
            ),

            "debug_messages": _append_debug(
                state,
                (
                    "Hill-climbing candidate "
                    f"{next_attempt} generated."
                ),
            ),
        }

    except Exception as exc:

        return {
            "status": "failed",
            "current_step": "hill_climb_failed",

            "error": str(exc),

            "repair_attempt": next_attempt,

            "debug_messages": _append_debug(
                state,
                f"Hill-climbing error: {exc}",
            ),
        }


# ============================================================

# NODE 6

# Restore Best Candidate

# ============================================================

def restore_best_plan_node(

    state: PlannerState,

) -> Dict[str, Any]:

    """

    Hill climbing means we should never lose a better solution.

    If the latest candidate performs worse and repair attempts

    are exhausted, restore the best candidate found so far.

    """

    best_plan = state.get(

        "best_plan"

    )

    if best_plan is None:

        return {

            "status": "failed",

            "error": (

                "Planner exhausted repair attempts "

                "without a usable plan."

            ),

            "current_step": "restore_best_failed",

        }

    print(

        "[PLANNER AGENT] Restoring best planning candidate "

        f"({state.get('best_score', 0.0):.1f}/100)."

    )

    return {

        "validated_plan": best_plan,

        "llm_plan_raw": best_plan.model_dump(),

        "verification_score": state.get(

            "best_score",

            0.0,

        ),

        "current_step": "best_candidate_restored",

        "debug_messages": _append_debug(

            state,

            "Best Planner candidate restored.",

        ),

    }

# ============================================================

# NODE 7

# Finalize Planner Output

# ============================================================

def finalize_node(

    state: PlannerState,

) -> Dict[str, Any]:

    """

    Convert trusted PlannerOutput into JSON-safe Manager payload.

    No planning happens here.

    No verification happens here.

    """

    plan = state.get(

        "validated_plan"

    )

    # Prefer best verified plan when available.

    best_plan = state.get(

        "best_plan"

    )

    if (

        best_plan is not None

        and state.get("best_score", 0.0)

        >= state.get("verification_score", 0.0)

    ):

        plan = best_plan

    if plan is None:

        return {

            "status": "failed",

            "current_step": "finalize_failed",

            "error": (

                "No validated Planner output "

                "available for Manager."

            ),

        }

    final_output = plan.model_dump(

        mode="json"

    )

    print()

    print("=" * 70)

    print("[PLANNER AGENT] Planning completed")

    print(

        "[PLANNER AGENT] Final verification score:",

        f"{state.get('best_score', state.get('verification_score', 0.0)):.1f}/100",

    )

    print(

        "[PLANNER AGENT] Previous asset required:",

        plan.previous_asset_required,

    )

    print(

        "[PLANNER AGENT] Tasks:",

        len(plan.tasks),

    )

    
    # ========================================================
    # OUTPUT FORMAT TRACE
    # ========================================================
    #
    # For graphic jobs, show the final format that Manager and
    # Graphic Agent will receive inside final_output.
    # ========================================================

    if getattr(
        plan,
        "primary_job_type",
        None,
    ) == "graphic_design":
        print(
            "[PLANNER AGENT] Target output format:",
            plan.target_output_format,
        )

    print(

        "[PLANNER AGENT] Returning plan to Manager..."

    )

    print("=" * 70)

    return {

        "status": "completed",

        "current_step": "completed",

        "final_output": final_output,

        "previous_asset_required": (

            plan.previous_asset_required

        ),

        "asset_requests": [

            asset.model_dump(

                mode="json"

            )

            for asset in plan.asset_requests

        ],

        "error": None,

        "debug_messages": _append_debug(

            state,

            "Planner completed and prepared output for Manager.",

        ),

    }

# ============================================================

# NODE 8

# Fail Planner

# ============================================================

def fail_node(

    state: PlannerState,

) -> Dict[str, Any]:

    """

    Controlled failure state.

    Planner should fail explicitly instead of silently returning

    a broken or incomplete execution plan.

    """

    error = state.get(

        "error"

    )

    if not error:

        error = (

            "Planner could not produce a sufficiently "

            "verified execution plan within the "

            "configured repair limit."

        )

    print()

    print("=" * 70)

    print("[PLANNER AGENT] FAILED")

    print(

        "[PLANNER AGENT]",

        error,

    )

    print(

        "[PLANNER AGENT] Returning failure status to Manager."

    )

    print("=" * 70)

    return {

        "status": "failed",

        "current_step": "failed",

        "error": error,

        "final_output": None,

        "debug_messages": _append_debug(

            state,

            f"Planner failed: {error}",

        ),

    }

# ============================================================

# Routing Functions

# ============================================================

#

# IMPORTANT:

#

# These functions DO NOT execute nodes.

#

# graph.py will call these functions to decide which EDGE

# should be followed next.

#

# Keeping routing predicates here small and deterministic

# prevents unnecessary LLM calls.

# ============================================================

def route_after_validation(

    state: PlannerState,

) -> str:

    """

    Structural validation routing.

    Valid:

        → verify

    Invalid + attempts available:

        → repair

    Invalid + attempts exhausted:

        → fail

    """

    if state.get(

        "validation_passed",

        False,

    ):

        return "verify"

    attempts = state.get(

        "repair_attempt",

        0,

    )

    max_attempts = state.get(

        "max_repair_attempts",

        DEFAULT_MAX_REPAIR_ATTEMPTS,

    )

    if attempts < max_attempts:

        return "repair"

    return "fail"

def route_after_verification(

    state: PlannerState,

) -> str:

    """

    Semantic verification routing.

    Requirement complete:

        → finalize

    Incomplete and attempts remain:

        → repair

    Attempts exhausted:

        → restore_best

    """

    score = state.get(

        "verification_score",

        0.0,

    )

    feedback = state.get(

        "verification_feedback",

        [],

    )

    # Complete only when:

    #

    # - score passes threshold

    # - verifier found no issues

    #

    # This keeps routing deterministic.

    if (

        score >= MIN_ACCEPTABLE_SCORE

        and not feedback

    ):

        return "finalize"

    attempts = state.get(

        "repair_attempt",

        0,

    )

    max_attempts = state.get(

        "max_repair_attempts",

        DEFAULT_MAX_REPAIR_ATTEMPTS,

    )

    if attempts < max_attempts:

        return "repair"

    return "restore_best"




# from __future__ import annotations

# # ============================================================
# # Planner Agent - LangGraph Nodes
# # ============================================================
# #
# # RESPONSIBILITY OF THIS FILE:
# #
# # 1. Prepare clean Planner input
# # 2. Ask Gemini to generate a structured execution plan
# # 3. Validate the generated plan
# # 4. Verify requirement coverage
# # 5. Repair / hill-climb weak plans
# # 6. Keep the best plan
# # 7. Finalize Planner output for Manager
# #
# #
# # IMPORTANT ARCHITECTURE RULE:
# #
# # This file defines WHAT each node does.
# #
# # It DOES NOT define:
# #
# # - graph edges
# # - workflow routing
# # - Manager orchestration
# # - asset retrieval
# # - graphic generation
# # - motion generation
# # - tool selection
# #
# # Those responsibilities belong to their own modules.
# #
# #
# # LOOP ENGINEERING:
# #
# # generate
# #    ↓
# # validate
# #    ↓
# # verify
# #    ↓
# # repair / hill-climb
# #    ↓
# # validate again
# #
# # The actual loop connections will be implemented
# # later inside graph.py.
# # ============================================================


# import json
# import os
# import re
# from typing import Any, Dict, List, Optional

# from google import genai
# from google.genai import types
# from pydantic import BaseModel, Field, ValidationError


# from packages.planner_agent.agent.state import PlannerState
# from packages.planner_agent.domain.schema import PlannerOutput


# # ============================================================
# # Internal Verification Schema
# # ============================================================
# #
# # This schema is INTERNAL to Planner verification.
# #
# # Manager does not need this structure.
# #
# # PlannerOutput = external Planner contract
# #
# # PlanVerificationResult = internal quality-control contract
# # ============================================================


# class PlanVerificationResult(BaseModel):
#     """
#     Structured output returned by Planner verifier.

#     This verifier DOES NOT execute the plan.

#     It only checks whether the generated plan adequately covers
#     the requirements received by Planner.
#     """

#     complete: bool = False

#     # 0 - 100 requirement coverage / planning quality score.
#     score: float = Field(
#         default=0.0,
#         ge=0.0,
#         le=100.0,
#     )

#     # Requirements that are missing from the generated plan.
#     missing_requirements: List[str] = Field(default_factory=list)

#     # Conflicting or logically inconsistent plan elements.
#     contradictions: List[str] = Field(default_factory=list)

#     # Weak planning decisions that should be improved.
#     weaknesses: List[str] = Field(default_factory=list)

#     # Precise instructions that the repair node can use.
#     repair_instructions: List[str] = Field(default_factory=list)


# # ============================================================
# # Planner Configuration
# # ============================================================
# #
# # Environment variables are used instead of hard-coding.
# #
# # Future:
# #
# # PLANNER_LLM_PROVIDER=openai
# # PLANNER_LLM_PROVIDER=claude
# # PLANNER_LLM_PROVIDER=gemini
# #
# # can later be handled through a provider adapter.
# #
# # For NOW this Planner uses Gemini only.
# # ============================================================


# DEFAULT_PLANNER_MODEL = "gemini-3.5-flash-lite"

# DEFAULT_MAX_REPAIR_ATTEMPTS = 3

# # Score required before Planner considers a plan complete.
# #
# # IMPORTANT:
# # score alone is not enough.
# #
# # complete must ALSO be True.
# MIN_ACCEPTABLE_SCORE = 95.0


# # ============================================================
# # Planner System Instructions
# # ============================================================

# PLANNER_SYSTEM_INSTRUCTION = """
# You are the Planning Agent inside a multi-agent graphic,
# motion-design, and UI/UX production system.

# Your responsibility is PLANNING ONLY.

# You receive structured requirements that were already extracted
# from the user's request.

# Your job is to transform those requirements into a complete,
# structured, executable plan.

# ============================================================
# YOUR RESPONSIBILITIES
# ============================================================

# You must determine:

# 1. What work must be done.
# 2. What tasks are required.
# 3. Correct task order.
# 4. Task dependencies.
# 5. Which tasks may run in parallel.
# 6. Required capabilities.
# 7. Inputs required by each task.
# 8. Expected outputs.
# 9. Global constraints.
# 10. Acceptance criteria.
# 11. Final deliverables.
# 12. Verification requirements.
# 13. Whether previous/existing assets are required.
# 14. What kind of previous assets are required.
# 15. Any relative time reference for those assets.
# 16. The most appropriate target production software.

# You MUST always set:

# target_software

# Allowed values:

# - adobe_illustrator
# - adobe_photoshop
# - video_generation

# Choose based on the actual design requirements.

# Use adobe_illustrator when the work is primarily:
# - poster design
# - banner design
# - typography-heavy composition
# - vector illustration
# - logo or branding artwork
# - scalable graphic layout
# - shape/vector-heavy artwork
# - print-style graphic composition

# Use adobe_photoshop when the work is primarily:
# - photo manipulation
# - photographic compositing
# - raster image editing
# - realistic image treatment
# - retouching
# - pixel-based effects
# - complex photographic blending

# Use video_generation when the work is primarily:

# - motion design
# - generated video
# - cinematic video
# - text-to-video
# - image-to-video
# - animated visual sequence
# - multi-shot motion content
# - video-based creative production

# IMPORTANT:

# video_generation is a generic production target.

# Do NOT select:

# - Wan
# - LTX
# - ComfyUI
# - FFmpeg
# - Runway
# - Kling
# - Veo
# - any API/provider/model

# Those execution decisions belong to Motion Agent.


# If the user does not explicitly specify software,
# you MUST determine the appropriate target_software
# from the design requirements.

# Never omit target_software.

# ============================================================
# PREVIOUS ASSET DETECTION
# ============================================================

# You MUST identify whether the request refers to existing or
# previous materials.

# Examples:

# "Use our logo from two months ago"

# previous_asset_required = true

# asset_requests should contain a brand_logo request with:

# time_reference.offset_months = -2


# "Use the previous campaign image"

# previous_asset_required = true


# "Create a completely new logo"

# previous_asset_required = false
# asset_requests = []

# ============================================================
# STRICT BOUNDARIES
# ============================================================

# DO NOT:

# - retrieve assets
# - search RAG
# - access files
# - choose asset IDs
# - invent asset paths
# - select Canva
# - select After Effects
# - select Nano Banana
# - select Stitch
# - select rendering tools
# - select implementation libraries
# - select specific creative tools
# - execute design work
# - execute motion work
# - generate final design assets

# Execution-tool choice belongs to specialized execution agents.

# You MAY choose only the required target production software
# through the target_software field.

# Do NOT choose the execution mechanism, API, model,
# bridge, plugin, renderer, or implementation library.

# You may describe REQUIRED CAPABILITIES.

# Example:

# GOOD:
# "required_capabilities": [
#     "vector_editing",
#     "brand_consistency"
# ]

# BAD:
# "Use Adobe Illustrator"

# ============================================================
# PLANNING QUALITY
# ============================================================

# Every meaningful user requirement must appear somewhere in:

# - tasks
# - constraints
# - expected outputs
# - deliverables
# - acceptance criteria
# - asset requests
# - verification checks
# For every graphic_design job, populate graphic_execution_spec.

# graphic_execution_spec must be a generic, tool-neutral,
# structured scene plan.

# Do NOT use Adobe Illustrator commands.
# Do NOT use Photoshop commands.
# Do NOT use software-specific object names.

# Represent the design using generic:
# - document
# - palette
# - assets
# - layers
# - elements
# - placement
# - geometry
# - style
# - typography
# - children/groups

# Use generic element types such as:
# - text
# - rectangle
# - ellipse
# - line
# - polygon
# - path
# - image
# - group
# - symbol
# - custom

# Complex visual subjects should be decomposed into generic
# primitive elements whenever reasonably possible.

# Do not only describe visual intent in natural language.
# Provide enough structured data for a deterministic renderer
# to execute the composition.

# Do not hardcode a poster, banner, logo, mobile phone,
# or any other specific design pattern.

# The same schema must work for arbitrary graphic-design jobs.

# Do not silently remove requirements.

# Do not invent major requirements that were not requested.

# Keep tasks modular.

# Avoid unnecessary task fragmentation.

# Use dependencies only where logically required.

# Use parallel execution where safe.

# The final plan must be implementation-independent.
# """


# # ============================================================
# # Verification System Instruction
# # ============================================================

# VERIFIER_SYSTEM_INSTRUCTION = """
# You are the verification component of a Planning Agent.

# You are NOT verifying a finished graphic or motion artifact.

# You are verifying whether a generated EXECUTION PLAN correctly
# covers the structured user requirements.

# Check:

# 1. Requirement coverage
# 2. Missing tasks
# 3. Missing deliverables
# 4. Missing constraints
# 5. Dependency correctness
# 6. Execution-order consistency
# 7. Previous-asset requirements
# 8. Acceptance criteria
# 9. Verification criteria
# 10. Contradictions
# 11. Unsupported assumptions
# 12. Whether the Planner incorrectly selected implementation tools

# A plan is complete only when all meaningful requirements are
# represented and the plan is internally consistent.

# Scoring guidance:

# 100 = complete and internally consistent
# 95-99 = effectively complete, only negligible issues
# 85-94 = usable but important improvements remain
# 70-84 = multiple missing or weak requirements
# below 70 = major planning problems

# Do not give a high score when a meaningful requirement is missing.

# Return actionable repair instructions.
# """


# # ============================================================
# # Hill-Climbing / Repair Instruction
# # ============================================================

# REPAIR_SYSTEM_INSTRUCTION = """
# You are the repair component of a Planning Agent.

# You receive:

# 1. Original structured requirements
# 2. Current execution plan
# 3. Verification feedback

# Your responsibility is to produce an IMPROVED execution plan.

# This is a hill-climbing step.

# Preserve everything that is already correct.

# Fix only what is missing, weak, contradictory, or incomplete.

# Do not unnecessarily rewrite good parts.

# Do not remove valid user requirements.

# Do not select execution tools.

# You MUST ensure target_software is present and appropriate.

# Allowed target_software values:

# - adobe_illustrator
# - adobe_photoshop
# - video_generation

# Selecting target_software is a planning decision.

# Do NOT select the execution API, model, bridge,
# plugin, renderer, or JSX implementation.

# Do not retrieve assets.

# Do not perform design work.

# Return a complete PlannerOutput object, not a patch.
# """


# # ============================================================
# # Gemini Client Helper
# # ============================================================

# def _get_gemini_client() -> genai.Client:
#     """
#     Create Gemini client lazily.

#     Why lazy initialization?

#     - Importing nodes.py should not immediately call Gemini.
#     - Tests can import this file without triggering an API request.
#     - Future provider replacement becomes easier.
#     """

#     api_key = os.getenv("PLANNER_GEMINI_API_KEY")

#     if not api_key:
#         raise RuntimeError(
#             "PLANNER_GEMINI_API_KEY is missing. "
#             "Add PLANNER_GEMINI_API_KEY to your .env/environment."
#         )

#     return genai.Client(api_key=api_key)


# def _get_planner_model() -> str:
#     """
#     Model can be changed without changing code.

#     Example .env:

#     PLANNER_MODEL=gemini-3.5-flash-lite
#     """

#     return os.getenv(
#         "PLANNER_MODEL",
#         DEFAULT_PLANNER_MODEL,
#     )


# # ============================================================
# # Generic Structured Gemini Call
# # ============================================================

# def _generate_structured(
#     *,
#     system_instruction: str,
#     prompt: str,
#     response_schema: type[BaseModel],
# ) -> BaseModel:
#     """
#     Single reusable Gemini structured-output function.

#     Keeping Gemini interaction in one helper prevents every node
#     from implementing API logic differently.

#     Future provider abstraction can replace ONLY this layer.
#     """

#     client = _get_gemini_client()

#     model = _get_planner_model()

#     response = client.models.generate_content(
#         model=model,
#         contents=prompt,
#         config=types.GenerateContentConfig(
#             system_instruction=system_instruction,

#             # Force structured JSON response.
#             response_mime_type="application/json",

#             # Pydantic schema controls output shape.
#             response_schema=response_schema,
#         ),
#     )

#     # Current Google GenAI SDK can return parsed Pydantic output.
#     if response.parsed is not None:
#         return response.parsed

#     # Defensive fallback:
#     # if parsed is unavailable, parse response.text ourselves.
#     if not response.text:
#         raise RuntimeError(
#             "Gemini returned an empty response."
#         )

#     return response_schema.model_validate_json(
#         response.text
#     )


# # ============================================================
# # Small State Helper
# # ============================================================

# def _append_debug(
#     state: PlannerState,
#     message: str,
# ) -> List[str]:
#     """
#     Return a NEW debug list.

#     We avoid mutating the existing state list directly.

#     This makes LangGraph state updates easier to reason about.
#     """

#     messages = list(
#         state.get("debug_messages", [])
#     )

#     messages.append(message)

#     return messages

# # Output format resolver
# def _resolve_target_output_format(
#     original_user_request: str | None,
# ) -> str:
#     """
#     Resolve requested graphic output format.

#     Rules:

#     PSD explicitly requested
#         -> psd

#     Adobe Illustrator / AI explicitly requested
#         -> ai

#     SVG explicitly requested
#         -> svg

#     JPG / JPEG explicitly requested
#         -> jpg

#     PNG explicitly requested
#         -> jpg

#     Nothing specified
#         -> jpg
#     """

#     text = (
#         original_user_request
#         or
#         ""
#     ).strip().lower()


#     # ========================================================
#     # PSD
#     # ========================================================

#     if re.search(
#         r"\bpsd\b|photoshop\s+(?:file|format)",
#         text,
#     ):

#         return "psd"


#     # ========================================================
#     # ADOBE ILLUSTRATOR / AI
#     # ========================================================
#     #
#     # Avoid matching every occurrence of the word "AI",
#     # because user may mean Artificial Intelligence.
#     #
#     # Safe cases:
#     # - ".ai"
#     # - "ai format"
#     # - "ai file"
#     # - "adobe illustrator"
#     # - "illustrator file"
#     # ========================================================

#     if re.search(
#         r"\.ai\b"
#         r"|"
#         r"\bai\s+(?:format|file)\b"
#         r"|"
#         r"\badobe\s+illustrator\b"
#         r"|"
#         r"\billustrator\s+(?:format|file)\b",
#         text,
#     ):

#         return "ai"


#     # ========================================================
#     # SVG
#     # ========================================================

#     if re.search(
#         r"\bsvg\b|\.svg\b",
#         text,
#     ):

#         return "svg"


#     # ========================================================
#     # JPG / JPEG
#     # ========================================================

#     if re.search(
#         r"\bjpg\b"
#         r"|"
#         r"\bjpeg\b"
#         r"|"
#         r"\.jpg\b"
#         r"|"
#         r"\.jpeg\b",
#         text,
#     ):

#         return "jpg"


#     # ========================================================
#     # PNG UNSUPPORTED
#     # ========================================================
#     #
#     # Product policy:
#     #
#     # PNG requests fall back to JPG.
#     # ========================================================

#     if re.search(
#         r"\bpng\b|\.png\b",
#         text,
#     ):

#         return "jpg"


#     # ========================================================
#     # DEFAULT
#     # ========================================================

#     return "jpg"


# # ============================================================
# # NODE 1
# # Prepare Planner Input
# # ============================================================

# def prepare_input_node(
#     state: PlannerState,
# ) -> Dict[str, Any]:
#     """
#     Normalize Manager input before sending anything to Gemini.

#     This node does NOT plan.

#     This node does NOT call an LLM.

#     Its responsibility is input preparation only.
#     """

#     print()
#     print("=" * 70)
#     print("[PLANNER AGENT] Task received from Manager")
#     print("=" * 70)

#     manager_input = state.get(
#         "manager_input",
#         {},
#     )

#     json_agent_output = state.get(
#         "json_agent_output",
#         {},
#     )

#     original_user_request = state.get(
#         "original_user_request",
#     )

#     # --------------------------------------------------------
#     # Prefer explicitly supplied JSON Agent output.
#     #
#     # If Manager embeds it inside manager_input,
#     # use that as a safe fallback.
#     # --------------------------------------------------------

#     if not json_agent_output:
#         possible_json_output = manager_input.get(
#             "json_agent_output"
#         )

#         if isinstance(
#             possible_json_output,
#             dict,
#         ):
#             json_agent_output = possible_json_output

#     # --------------------------------------------------------
#     # Planner should receive only relevant planning information.
#     #
#     # We do NOT send the whole Manager internal state to Gemini.
#     #
#     # Benefits:
#     #
#     # - lower token usage
#     # - less accidental coupling
#     # - better security boundary
#     # - more stable prompts
#     # --------------------------------------------------------

#     prepared_input = {
#         "structured_requirements": json_agent_output,
#     }

#     if original_user_request:
#         prepared_input[
#             "original_user_request"
#         ] = original_user_request

#     print(
#         "[PLANNER AGENT] Input prepared."
#     )

#     return {
#         "status": "preparing",
#         "current_step": "prepare_input",
#         "prepared_input": prepared_input,
#         "json_agent_output": json_agent_output,

#         "repair_attempt": state.get(
#             "repair_attempt",
#             0,
#         ),

#         "max_repair_attempts": state.get(
#             "max_repair_attempts",
#             DEFAULT_MAX_REPAIR_ATTEMPTS,
#         ),

#         "planning_iteration": state.get(
#             "planning_iteration",
#             0,
#         ),

#         "verification_score": 0.0,
#         "verification_feedback": [],

#         "best_score": state.get(
#             "best_score",
#             0.0,
#         ),

#         "validation_passed": False,
#         "validation_errors": [],
#         "error": None,

#         "llm_provider": "gemini",
#         "llm_model": _get_planner_model(),

#         "debug_messages": _append_debug(
#             state,
#             "Planner input prepared.",
#         ),
#     }


# # ============================================================
# # NODE 2
# # Initial Planning
# # ============================================================

# def planning_node(
#     state: PlannerState,
# ) -> Dict[str, Any]:
#     """
#     Main Planner reasoning node.

#     Gemini creates the FIRST candidate execution plan.

#     This node does NOT decide whether the plan is good enough.

#     Verification is intentionally separated.
#     """

#     prepared_input = state.get(
#     "prepared_input",
#     {},
#     )

#     # ============================================================
# # RESOLVE REQUESTED OUTPUT FORMAT
# # ============================================================
# #
# # This value comes from the original user request.
# #
# # Planner remains the owner of requirement interpretation.
# # ============================================================

# original_user_request = (
#     prepared_input.get(
#         "original_user_request"
#     )
#     or
#     state.get(
#         "original_user_request"
#     )
#     or
#     ""
# )


# target_output_format = (
#     _resolve_target_output_format(
#         original_user_request
#     )
# )



# print(
#         "[PLANNER AGENT] "
#         "Resolved target output format = "
#         f"{target_output_format}"
#     )

# print(
#         "[PLANNER AGENT] Planning with "
#         f"{_get_planner_model()}..."
#     )

# prepared_input = state.get(
#         "prepared_input",
#         {},
#     )

# prompt = f"""
# Create a complete execution plan for the following request.

# STRUCTURED INPUT:

# {json.dumps(
#     prepared_input,
#     ensure_ascii=False,
#     indent=2,
# )}

# Remember:

# - cover every meaningful requirement
# - identify previous asset requirements
# - determine target_software
# - target_software must be one of:
#   adobe_illustrator,
#   adobe_photoshop,
#   video_generation
# - use video_generation for motion/video generation jobs
# - do not choose execution APIs, models, plugins,
#   bridges, renderers, video models, or post-processing tools
# - choose target_software based on the actual design requirement
# - do not retrieve assets
# - do not choose execution APIs, models, plugins, bridges, or renderers
# - return only the structured PlannerOutput
# """

#     try:
#         plan = _generate_structured(
#             system_instruction=PLANNER_SYSTEM_INSTRUCTION,
#             prompt=prompt,
#             response_schema=PlannerOutput,
#         )

#         if not isinstance(
#             plan,
#             PlannerOutput,
#         ):
#             plan = PlannerOutput.model_validate(
#                 plan
#             )

#         print(
#             "[PLANNER AGENT] Initial plan generated."
#         )

#         return {
#             "status": "planning",
#             "current_step": "initial_planning",

#             "llm_plan_raw": plan.model_dump(),

#             "validated_plan": None,

#             "planning_iteration": (
#                 state.get(
#                     "planning_iteration",
#                     0,
#                 )
#                 + 1
#             ),

#             "validation_passed": False,
#             "validation_errors": [],

#             "debug_messages": _append_debug(
#                 state,
#                 "Initial Planner candidate generated.",
#             ),
#         }

#     except Exception as exc:

#         print(
#             "[PLANNER AGENT] Planning error:",
#             str(exc),
#         )

#         return {
#             "status": "failed",
#             "current_step": "initial_planning_failed",
#             "error": str(exc),

#             "debug_messages": _append_debug(
#                 state,
#                 f"Planning failed: {exc}",
#             ),
#         }


# # ============================================================
# # NODE 3
# # Deterministic Schema + Structural Validation
# # ============================================================

# def validate_plan_node(
#     state: PlannerState,
# ) -> Dict[str, Any]:
#     """
#     Deterministic validation layer.

#     NO LLM is used here.

#     Why?

#     Basic structural correctness should not consume tokens.

#     Checks:
#     - PlannerOutput schema
#     - tasks exist
#     - execution order references real tasks
#     - dependency references are valid
#     - previous asset consistency
#     """

#     print(
#         "[PLANNER AGENT] Validating plan..."
#     )

#     raw_plan = state.get(
#         "llm_plan_raw"
#     )

#     errors: List[str] = []

#     if not raw_plan:

#         errors.append(
#             "Planner produced no plan."
#         )

#         return {
#             "status": "validating",
#             "current_step": "schema_validation",
#             "validation_passed": False,
#             "validation_errors": errors,

#             "debug_messages": _append_debug(
#                 state,
#                 "Validation failed: no plan.",
#             ),
#         }

#     try:
#         plan = PlannerOutput.model_validate(
#             raw_plan
#         )

#     except ValidationError as exc:

#         errors.append(str(exc))

#         return {
#             "status": "validating",
#             "current_step": "schema_validation",
#             "validation_passed": False,
#             "validation_errors": errors,

#             "debug_messages": _append_debug(
#                 state,
#                 "PlannerOutput schema validation failed.",
#             ),
#         }

#     # --------------------------------------------------------
#     # Invariant 1:
#     # A useful execution plan needs at least one task.
#     # --------------------------------------------------------

#     if not plan.tasks:
#         errors.append(
#             "Plan contains no executable tasks."
#         )

#     # --------------------------------------------------------
#     # Collect task IDs once.
#     # --------------------------------------------------------

#     task_ids = {
#         task.task_id
#         for task in plan.tasks
#     }

#     # --------------------------------------------------------
#     # Invariant 2:
#     # execution_order must reference existing tasks.
#     # --------------------------------------------------------

#     for task_id in plan.execution_order:

#         if task_id not in task_ids:
#             errors.append(
#                 "execution_order references "
#                 f"unknown task_id: {task_id}"
#             )

#     # --------------------------------------------------------
#     # Invariant 3:
#     # dependencies must reference existing tasks.
#     # --------------------------------------------------------

#     for task in plan.tasks:

#         for dependency in task.depends_on:

#             if dependency not in task_ids:
#                 errors.append(
#                     f"{task.task_id} depends on "
#                     f"unknown task: {dependency}"
#                 )

#             if dependency == task.task_id:
#                 errors.append(
#                     f"{task.task_id} cannot depend on itself."
#                 )

#     # --------------------------------------------------------
#     # Invariant 4:
#     # Previous asset flag and requests must agree.
#     # --------------------------------------------------------

#     if (
#         plan.previous_asset_required
#         and not plan.asset_requests
#     ):
#         errors.append(
#             "previous_asset_required is true "
#             "but asset_requests is empty."
#         )

#     if (
#         not plan.previous_asset_required
#         and plan.asset_requests
#     ):
#         errors.append(
#             "asset_requests exist while "
#             "previous_asset_required is false."
#         )

#     passed = len(errors) == 0

#     if passed:
#         print(
#             "[PLANNER AGENT] Structural validation PASSED."
#         )
#     else:
#         print(
#             "[PLANNER AGENT] Structural validation FAILED."
#         )

#     return {
#         "status": "validating",
#         "current_step": "schema_validation",

#         "validated_plan": (
#             plan
#             if passed
#             else None
#         ),

#         "validation_passed": passed,
#         "validation_errors": errors,

#         "previous_asset_required": (
#             plan.previous_asset_required
#         ),

#         "asset_requests": [
#             asset.model_dump()
#             for asset in plan.asset_requests
#         ],

#         "debug_messages": _append_debug(
#             state,
#             (
#                 "Structural validation passed."
#                 if passed
#                 else
#                 "Structural validation failed."
#             ),
#         ),
#     }


# # ============================================================
# # NODE 4
# # Requirement Verification
# # ============================================================

# def verify_plan_node(
#     state: PlannerState,
# ) -> Dict[str, Any]:
#     """
#     Semantic verification node.

#     The deterministic validator checks structure.

#     This node checks MEANING.

#     Example:

#     User requested:
#         editable SVG

#     Planner forgot it.

#     Schema can still be valid.

#     Semantic verifier should catch it.
#     """

#     print(
#         "[PLANNER AGENT] Verifying requirement coverage..."
#     )

#     validated_plan = state.get(
#         "validated_plan"
#     )

#     if validated_plan is None:

#         return {
#             "verification_score": 0.0,

#             "verification_feedback": [
#                 "Plan cannot be semantically verified "
#                 "because structural validation failed."
#             ],

#             "debug_messages": _append_debug(
#                 state,
#                 "Semantic verification skipped because "
#                 "structural validation failed.",
#             ),
#         }

#     prepared_input = state.get(
#         "prepared_input",
#         {},
#     )

#     prompt = f"""
# Compare the ORIGINAL REQUIREMENTS against the GENERATED PLAN.

# ORIGINAL REQUIREMENTS:

# {json.dumps(
#     prepared_input,
#     ensure_ascii=False,
#     indent=2,
# )}

# GENERATED PLAN:

# {json.dumps(
#     validated_plan.model_dump(),
#     ensure_ascii=False,
#     indent=2,
# )}

# Determine whether the plan fully covers the request.

# Pay special attention to:

# - missing user requirements
# - previous asset references
# - task dependencies
# - deliverables
# - constraints
# - acceptance criteria
# - verification coverage
# - accidental tool selection
# - target_software presence
# - target_software suitability for the requested design
# """

#     try:
#         verification = _generate_structured(
#             system_instruction=VERIFIER_SYSTEM_INSTRUCTION,
#             prompt=prompt,
#             response_schema=PlanVerificationResult,
#         )

#         if not isinstance(
#             verification,
#             PlanVerificationResult,
#         ):
#             verification = (
#                 PlanVerificationResult.model_validate(
#                     verification
#                 )
#             )

#         feedback = (
#             verification.missing_requirements
#             + verification.contradictions
#             + verification.weaknesses
#             + verification.repair_instructions
#         )

#         # ----------------------------------------------------
#         # Keep current plan if it becomes the best candidate.
#         # ----------------------------------------------------

#         previous_best_score = state.get(
#             "best_score",
#             0.0,
#         )

#         current_score = verification.score

#         update_best = (
#             current_score > previous_best_score
#             or state.get("best_plan") is None
#         )

#         best_plan = (
#             validated_plan
#             if update_best
#             else state.get("best_plan")
#         )

#         best_score = (
#             current_score
#             if update_best
#             else previous_best_score
#         )

#         complete = (
#             verification.complete
#             and current_score >= MIN_ACCEPTABLE_SCORE
#             and not verification.missing_requirements
#             and not verification.contradictions
#         )

#         print(
#             "[PLANNER AGENT] Verification score: "
#             f"{current_score:.1f}/100"
#         )

#         if complete:
#             print(
#                 "[PLANNER AGENT] Requirements covered."
#             )
#         else:
#             print(
#                 "[PLANNER AGENT] Improvement required."
#             )

#         return {
#             "status": (
#                 "completed"
#                 if complete
#                 else "repairing"
#             ),

#             "current_step": "requirement_verification",

#             "verification_score": current_score,
#             "verification_feedback": feedback,

#             "best_plan": best_plan,
#             "best_score": best_score,

#             # Internal completion marker.
#             #
#             # graph.py will use this later.
#             "metadata_complete": complete,

#             "debug_messages": _append_debug(
#                 state,
#                 (
#                     "Plan verification complete. "
#                     f"score={current_score:.1f}"
#                 ),
#             ),
#         }

#     except Exception as exc:

#         return {
#             "status": "repairing",

#             "verification_score": 0.0,

#             "verification_feedback": [
#                 f"Verification error: {exc}"
#             ],

#             "debug_messages": _append_debug(
#                 state,
#                 f"Verifier error: {exc}",
#             ),
#         }


# # ============================================================
# # NODE 5
# # Hill-Climbing Repair
# # ============================================================

# def hill_climb_node(
#     state: PlannerState,
# ) -> Dict[str, Any]:
#     """
#     Improve the existing plan instead of starting from zero.

#     This is our agent repair / hill-climbing step.

#     Principles:

#     - preserve good work
#     - repair weak work
#     - do not blindly regenerate
#     - maintain best-so-far plan
#     - use bounded attempts
#     """

#     current_attempt = state.get(
#         "repair_attempt",
#         0,
#     )

#     max_attempts = state.get(
#         "max_repair_attempts",
#         DEFAULT_MAX_REPAIR_ATTEMPTS,
#     )

#     next_attempt = current_attempt + 1

#     print(
#         "[PLANNER AGENT] Hill-climbing repair "
#         f"{next_attempt}/{max_attempts}..."
#     )

#     # --------------------------------------------------------
#     # Prefer the current validated candidate.
#     #
#     # If unavailable, fall back to best candidate.
#     # --------------------------------------------------------

#     current_plan = state.get(
#         "validated_plan"
#     )

#     if current_plan is None:
#         current_plan = state.get(
#             "best_plan"
#         )

#     if current_plan is None:

#         return {
#             "status": "failed",
#             "current_step": "hill_climb_failed",

#             "error": (
#                 "No valid plan exists to repair."
#             ),

#             "repair_attempt": next_attempt,

#             "debug_messages": _append_debug(
#                 state,
#                 "Hill-climbing failed: no repairable plan.",
#             ),
#         }

#     feedback = state.get(
#         "verification_feedback",
#         [],
#     )

#     validation_errors = state.get(
#         "validation_errors",
#         [],
#     )

#     prepared_input = state.get(
#         "prepared_input",
#         {},
#     )

#     prompt = f"""
# Improve the CURRENT PLAN.

# ORIGINAL REQUIREMENTS:

# {json.dumps(
#     prepared_input,
#     ensure_ascii=False,
#     indent=2,
# )}

# CURRENT PLAN:

# {json.dumps(
#     current_plan.model_dump(),
#     ensure_ascii=False,
#     indent=2,
# )}

# CURRENT SCORE:

# {state.get("verification_score", 0.0)}

# VERIFICATION FEEDBACK:

# {json.dumps(
#     feedback,
#     ensure_ascii=False,
#     indent=2,
# )}

# STRUCTURAL VALIDATION ERRORS:

# {json.dumps(
#     validation_errors,
#     ensure_ascii=False,
#     indent=2,
# )}

# Produce a complete improved PlannerOutput.

# Preserve correct parts.

# Fix identified weaknesses.

# The new candidate should improve requirement coverage and
# internal consistency.
# """

#     try:
#         repaired_plan = _generate_structured(
#             system_instruction=REPAIR_SYSTEM_INSTRUCTION,
#             prompt=prompt,
#             response_schema=PlannerOutput,
#         )

#         if not isinstance(
#             repaired_plan,
#             PlannerOutput,
#         ):
#             repaired_plan = (
#                 PlannerOutput.model_validate(
#                     repaired_plan
#                 )
#             )

#         print(
#             "[PLANNER AGENT] Improved candidate generated."
#         )

#         return {
#             "status": "planning",
#             "current_step": "hill_climb",

#             "llm_plan_raw": repaired_plan.model_dump(),

#             # Must be validated again.
#             "validated_plan": None,

#             "validation_passed": False,
#             "validation_errors": [],

#             "repair_attempt": next_attempt,

#             "planning_iteration": (
#                 state.get(
#                     "planning_iteration",
#                     0,
#                 )
#                 + 1
#             ),

#             "debug_messages": _append_debug(
#                 state,
#                 (
#                     "Hill-climbing candidate "
#                     f"{next_attempt} generated."
#                 ),
#             ),
#         }

#     except Exception as exc:

#         return {
#             "status": "failed",
#             "current_step": "hill_climb_failed",

#             "error": str(exc),

#             "repair_attempt": next_attempt,

#             "debug_messages": _append_debug(
#                 state,
#                 f"Hill-climbing error: {exc}",
#             ),
#         }


# # ============================================================
# # NODE 6
# # Restore Best Candidate
# # ============================================================

# def restore_best_plan_node(
#     state: PlannerState,
# ) -> Dict[str, Any]:
#     """
#     Hill climbing means we should never lose a better solution.

#     If the latest candidate performs worse and repair attempts
#     are exhausted, restore the best candidate found so far.
#     """

#     best_plan = state.get(
#         "best_plan"
#     )

#     if best_plan is None:

#         return {
#             "status": "failed",

#             "error": (
#                 "Planner exhausted repair attempts "
#                 "without a usable plan."
#             ),

#             "current_step": "restore_best_failed",
#         }

#     print(
#         "[PLANNER AGENT] Restoring best planning candidate "
#         f"({state.get('best_score', 0.0):.1f}/100)."
#     )

#     return {
#         "validated_plan": best_plan,
#         "llm_plan_raw": best_plan.model_dump(),
#         "verification_score": state.get(
#             "best_score",
#             0.0,
#         ),
#         "current_step": "best_candidate_restored",

#         "debug_messages": _append_debug(
#             state,
#             "Best Planner candidate restored.",
#         ),
#     }


# # ============================================================
# # NODE 7
# # Finalize Planner Output
# # ============================================================

# def finalize_node(
#     state: PlannerState,
# ) -> Dict[str, Any]:
#     """
#     Convert trusted PlannerOutput into JSON-safe Manager payload.

#     No planning happens here.

#     No verification happens here.
#     """

#     plan = state.get(
#         "validated_plan"
#     )

#     # Prefer best verified plan when available.
#     best_plan = state.get(
#         "best_plan"
#     )

#     if (
#         best_plan is not None
#         and state.get("best_score", 0.0)
#         >= state.get("verification_score", 0.0)
#     ):
#         plan = best_plan

#     if plan is None:

#         return {
#             "status": "failed",
#             "current_step": "finalize_failed",
#             "error": (
#                 "No validated Planner output "
#                 "available for Manager."
#             ),
#         }

#     final_output = plan.model_dump(
#         mode="json"
#     )

#     print()
#     print("=" * 70)
#     print("[PLANNER AGENT] Planning completed")
#     print(
#         "[PLANNER AGENT] Final verification score:",
#         f"{state.get('best_score', state.get('verification_score', 0.0)):.1f}/100",
#     )

#     print(
#         "[PLANNER AGENT] Previous asset required:",
#         plan.previous_asset_required,
#     )

#     print(
#         "[PLANNER AGENT] Tasks:",
#         len(plan.tasks),
#     )

#     print(
#         "[PLANNER AGENT] Returning plan to Manager..."
#     )
#     print("=" * 70)

#     return {
#         "status": "completed",
#         "current_step": "completed",

#         "final_output": final_output,

#         "previous_asset_required": (
#             plan.previous_asset_required
#         ),

#         "asset_requests": [
#             asset.model_dump(
#                 mode="json"
#             )
#             for asset in plan.asset_requests
#         ],

#         "error": None,

#         "debug_messages": _append_debug(
#             state,
#             "Planner completed and prepared output for Manager.",
#         ),
#     }


# # ============================================================
# # NODE 8
# # Fail Planner
# # ============================================================

# def fail_node(
#     state: PlannerState,
# ) -> Dict[str, Any]:
#     """
#     Controlled failure state.

#     Planner should fail explicitly instead of silently returning
#     a broken or incomplete execution plan.
#     """

#     error = state.get(
#         "error"
#     )

#     if not error:

#         error = (
#             "Planner could not produce a sufficiently "
#             "verified execution plan within the "
#             "configured repair limit."
#         )

#     print()
#     print("=" * 70)
#     print("[PLANNER AGENT] FAILED")
#     print(
#         "[PLANNER AGENT]",
#         error,
#     )
#     print(
#         "[PLANNER AGENT] Returning failure status to Manager."
#     )
#     print("=" * 70)

#     return {
#         "status": "failed",
#         "current_step": "failed",
#         "error": error,

#         "final_output": None,

#         "debug_messages": _append_debug(
#             state,
#             f"Planner failed: {error}",
#         ),
#     }


# # ============================================================
# # Routing Functions
# # ============================================================
# #
# # IMPORTANT:
# #
# # These functions DO NOT execute nodes.
# #
# # graph.py will call these functions to decide which EDGE
# # should be followed next.
# #
# # Keeping routing predicates here small and deterministic
# # prevents unnecessary LLM calls.
# # ============================================================


# def route_after_validation(
#     state: PlannerState,
# ) -> str:
#     """
#     Structural validation routing.

#     Valid:
#         → verify

#     Invalid + attempts available:
#         → repair

#     Invalid + attempts exhausted:
#         → fail
#     """

#     if state.get(
#         "validation_passed",
#         False,
#     ):
#         return "verify"

#     attempts = state.get(
#         "repair_attempt",
#         0,
#     )

#     max_attempts = state.get(
#         "max_repair_attempts",
#         DEFAULT_MAX_REPAIR_ATTEMPTS,
#     )

#     if attempts < max_attempts:
#         return "repair"

#     return "fail"


# def route_after_verification(
#     state: PlannerState,
# ) -> str:
#     """
#     Semantic verification routing.

#     Requirement complete:
#         → finalize

#     Incomplete and attempts remain:
#         → repair

#     Attempts exhausted:
#         → restore_best
#     """

#     score = state.get(
#         "verification_score",
#         0.0,
#     )

#     feedback = state.get(
#         "verification_feedback",
#         [],
#     )

#     # Complete only when:
#     #
#     # - score passes threshold
#     # - verifier found no issues
#     #
#     # This keeps routing deterministic.
#     if (
#         score >= MIN_ACCEPTABLE_SCORE
#         and not feedback
#     ):
#         return "finalize"

#     attempts = state.get(
#         "repair_attempt",
#         0,
#     )

#     max_attempts = state.get(
#         "max_repair_attempts",
#         DEFAULT_MAX_REPAIR_ATTEMPTS,
#     )

#     if attempts < max_attempts:
#         return "repair"

#     return "restore_best"

"""
Provider-backed Motion LLM Adapter

Responsibility:

Planner output
    ↓
configured AI provider
    ↓
MotionExecutionSpec

IMPORTANT:

Gemini does NOT:

- select Wan
- select LTX
- execute video model
- run FFmpeg
- verify final video
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict

from packages.motion_agent.compiler.schema import (
    MotionExecutionSpec,
)

from packages.motion_agent.llm.base import (
    MotionLLMProvider,
)
from packages.ai.provider import active_provider, openai_model, openai_structured
from packages.provider_secrets.application.runtime import resolve_provider_secret


DEFAULT_MOTION_LLM_MODEL = (
    "gemini-3.5-flash-lite"
)


MOTION_COMPILER_INSTRUCTION = """
You are the motion execution compiler inside a
multi-agent video production system.

You receive an already-verified Planner plan.

Your responsibility is NOT to re-plan the job.

Convert the Planner plan into a model-neutral
MotionExecutionSpec.

STRICT RULES:

- preserve the Planner requirements
- do not invent unrelated creative requirements
- break motion into shots when necessary
- provide subject, action, camera, environment,
  lighting and style
- use text_to_video or image_to_video
- do not select Wan
- do not select LTX
- do not select ComfyUI
- do not select FFmpeg
- do not include provider-specific parameters
- return only MotionExecutionSpec
"""


class GeminiMotionLLM(
    MotionLLMProvider,
):

    provider_id = "gemini"


    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
    ):

        self._provider = active_provider()
        if self._provider == "openai":
            self.api_key = api_key or resolve_provider_secret(
                "openai",
                environment_names=("OPENAI_API_KEY",),
            )
        else:
            self.api_key = api_key or resolve_provider_secret(
                "gemini",
                environment_names=(
                    "MOTION_GEMINI_API_KEY",
                    "PLANNER_GEMINI_API_KEY",
                    "GEMINI_API_KEY",
                ),
            )

        if not self.api_key:

            raise RuntimeError(
                f"{('OPENAI_API_KEY' if self._provider == 'openai' else 'MOTION_GEMINI_API_KEY')} is missing."
            )

        self.model = (
            model
            or (openai_model("OPENAI_MOTION_MODEL") if self._provider == "openai" else os.getenv("MOTION_LLM_MODEL", DEFAULT_MOTION_LLM_MODEL))
        )

        self.client = None
        if self._provider == "gemini":
            from google import genai
            self.client = genai.Client(api_key=self.api_key)
            self.provider_id = "gemini"
        else:
            self.provider_id = "openai"


    def compile_execution_spec(
        self,
        *,
        job_id: str,
        planner_plan: Dict[str, Any],
        original_user_request: str,
    ) -> MotionExecutionSpec:

        prompt = f"""
Convert this verified Planner output into a
MotionExecutionSpec.

JOB ID:
{job_id}

ORIGINAL USER REQUEST:
{original_user_request}

PLANNER PLAN:
{json.dumps(
    planner_plan,
    ensure_ascii=False,
    indent=2,
)}
"""

        if self._provider == "openai":
            payload = openai_structured(
                model=self.model,
                prompt=prompt,
                system_instruction=MOTION_COMPILER_INSTRUCTION,
                schema=MotionExecutionSpec.model_json_schema(),
                schema_name="motion_execution_spec",
            )
            return MotionExecutionSpec.model_validate(payload)

        from google.genai import types
        response = self.client.models.generate_content(

                model=self.model,

                contents=prompt,

                config=types.GenerateContentConfig(

                    system_instruction=(
                        MOTION_COMPILER_INSTRUCTION
                    ),

                    response_mime_type=(
                        "application/json"
                    ),

                    response_schema=(
                        MotionExecutionSpec
                    ),
                ),
            )

        if response.parsed is not None:

            return response.parsed

        if not response.text:

            raise RuntimeError(
                "Motion LLM returned empty output."
            )

        return (
            MotionExecutionSpec.model_validate_json(
                response.text
            )
        )

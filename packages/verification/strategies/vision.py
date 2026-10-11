"""LLM vision verification against the Planner's requirement checklist."""

from __future__ import annotations

import os
from pathlib import Path
from urllib.request import urlopen

from pydantic import BaseModel

from packages.graphic_agent.compiler.prompt_compiler import compile_graphic_prompt
from packages.verification.domain.contracts import VerificationIssue, VerificationRequest
from packages.verification.strategies.common import local_path
from packages.ai.provider import active_provider, openai_model, openai_multimodal_structured
from packages.provider_secrets.application.runtime import resolve_provider_secret


class VisionAssessment(BaseModel):
    passed: bool
    missing_requirements: list[str] = []
    corrections: list[str] = []
    observations: list[str] = []


class GeminiVisionVerifier:
    """Ask the active AI provider to compare output with the design brief."""

    def verify(self, request: VerificationRequest) -> list[VerificationIssue]:
        if request.execution_request.normalized_request.output.format == "svg":
            # Native SVG has deterministic structural verification. A raster
            # vision upload would lose editable-vector evidence.
            return []
        execution = request.execution_result
        if not execution.output_assets:
            return []
        asset = execution.output_assets[0]
        try:
            data, mime_type = self._read_asset(asset)
            prompt = (
                "Evaluate this rendered design against the following requirements. "
                "Pass only when all explicit requirements are visibly satisfied. "
                "Do not invent missing requirements.\n\n"
                + compile_graphic_prompt(request.execution_request)
            )
            if active_provider() == "openai":
                assessment = VisionAssessment.model_validate(openai_multimodal_structured(
                    prompt=prompt,
                    image_bytes=data,
                    image_mime_type=mime_type,
                    model=openai_model("OPENAI_VISION_MODEL"),
                    schema=VisionAssessment.model_json_schema(),
                    schema_name="vision_assessment",
                ))
            else:
                from google import genai
                from google.genai import types

                api_key = resolve_provider_secret(
                    "gemini",
                    environment_names=("GEMINI_API_KEY",),
                )
                if not api_key:
                    raise RuntimeError("GEMINI_API_KEY is missing.")
                response = genai.Client(api_key=api_key).models.generate_content(
                    model=os.getenv("GEMINI_VISION_MODEL", os.getenv("GEMINI_MODEL", "gemini-2.5-flash")),
                    contents=[prompt, types.Part.from_bytes(data=data, mime_type=mime_type)],
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=VisionAssessment,
                    ),
                )
                assessment = response.parsed or VisionAssessment.model_validate_json(response.text)
        except Exception as exc:
            return [VerificationIssue("visual_verification_unavailable", str(exc))]

        if assessment.passed and not assessment.missing_requirements:
            return []
        messages = assessment.missing_requirements or assessment.corrections or assessment.observations
        return [
            VerificationIssue(
                "visual_requirement_mismatch",
                "; ".join(messages) or "The rendered image did not satisfy the visual checklist.",
            )
        ]

    @staticmethod
    def _read_asset(asset):
        path = local_path(asset.uri)
        if path is None:
            metadata_path = (asset.metadata or {}).get("absolute_path")
            path = local_path(str(metadata_path)) if metadata_path else None
        if path is not None and path.exists():
            return path.read_bytes(), "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
        if asset.uri.startswith(("http://", "https://")):
            with urlopen(asset.uri, timeout=120) as response:
                return response.read(), response.headers.get_content_type() or "image/jpeg"
        raise FileNotFoundError("Rendered image is not accessible for visual verification.")

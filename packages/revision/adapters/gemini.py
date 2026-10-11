"""Gemini structured-output adapter for revision decisions only."""

from __future__ import annotations

import json
import os
from pydantic import BaseModel

from packages.revision.domain import RevisionDecision
from packages.ai.provider import active_provider, openai_model, openai_structured
from packages.provider_secrets.application.runtime import resolve_provider_secret


class GeminiRevisionPlanner:
    def __init__(self, *, model: str | None = None):
        self._model = model or (
            openai_model("OPENAI_MODEL")
            if active_provider() == "openai"
            else os.getenv("GEMINI_REVISION_MODEL", os.getenv("GEMINI_MODEL", "gemini-2.5-flash"))
        )
        self._client = None

    def plan(self, request):
        prompt = (
            "Choose at most one safe, targeted design revision. Return only the structured decision. "
            "Never return SVG, code, JSON Patch, JSONPath, or implementation instructions. "
            "Preserve all user requirements. Use only these exact target paths: "
            "typography.primary_heading, typography.cta, layout.primary_region, "
            "layout.supporting_region, layout.action_region, layout.visual_region, "
            "visual_hierarchy.primary_weight, visual_hierarchy.cta, "
            "color_system.background, color_system.text, color_system.cta, "
            "color_system.accent, asset.visual. "
            "For increase_contrast/decrease_contrast, target a semantic color role "
            "and set value to null. For increase/decrease_font_size use a multiplier "
            "between 0.75 and 1.50. For movement use a normalized delta between -0.15 and 0.15.\n\n"
            + json.dumps(request.model_dump(mode="json"), ensure_ascii=False)
        )
        if active_provider() == "openai":
            return RevisionDecision.model_validate(openai_structured(
                model=self._model,
                prompt=prompt,
                schema=RevisionDecision.model_json_schema(),
                schema_name="revision_decision",
            ))

        from google import genai
        from google.genai import types
        api_key = resolve_provider_secret(
            "gemini",
            environment_names=("GEMINI_API_KEY",),
        )
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY is missing.")
        if self._client is None:
            self._client = genai.Client(api_key=api_key)
        response = self._client.models.generate_content(
            model=self._model,
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json", response_schema=RevisionDecision),
        )
        return response.parsed or RevisionDecision.model_validate_json(response.text)

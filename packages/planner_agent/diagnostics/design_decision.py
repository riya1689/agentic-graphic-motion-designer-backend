"""Small AI-only Planner design-decision diagnostic.

This module is intentionally not used by production orchestration. It probes
the configured Planner model without invoking deterministic completion, SVG,
or fallback logic.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List

from pydantic import BaseModel, Field
from packages.provider_secrets.application.runtime import resolve_provider_secret


class DiagnosticResult(BaseModel):
    provider: str = "google-gemini"
    model: str
    level: int
    success: bool
    source: str = "AI"
    decisions: Dict[str, Any] = Field(default_factory=dict)
    missing_fields: List[str] = Field(default_factory=list)
    error_type: str | None = None
    error_message: str | None = None


_LEVEL_SCHEMAS = {
    1: {
        "type": "object",
        "properties": {
            "composition": {"type": "string"},
            "typography": {"type": "object", "properties": {"hierarchy": {"type": "string"}, "headline_role": {"type": "string"}}, "required": ["hierarchy", "headline_role"]},
            "color_system": {"type": "object", "properties": {"mood": {"type": "string"}, "roles": {"type": "string"}}, "required": ["mood", "roles"]},
        },
        "required": ["composition", "typography", "color_system"],
    },
    2: {
        "type": "object",
        "properties": {
            "concept": {"type": "string"},
            "composition": {"type": "string"},
            "visual_hierarchy": {"type": "object", "properties": {"focal_point": {"type": "string"}, "reading_path": {"type": "string"}}, "required": ["focal_point", "reading_path"]},
            "typography": {"type": "object", "properties": {"hierarchy": {"type": "string"}, "headline_role": {"type": "string"}}, "required": ["hierarchy", "headline_role"]},
            "color_system": {"type": "object", "properties": {"mood": {"type": "string"}, "roles": {"type": "string"}}, "required": ["mood", "roles"]},
        },
        "required": ["concept", "composition", "visual_hierarchy", "typography", "color_system"],
    },
    3: {
        "type": "object",
        "properties": {
            "concept": {"type": "string"},
            "art_direction": {"type": "object", "properties": {"mood": {"type": "string"}, "visual_language": {"type": "string"}, "imagery_direction": {"type": "string"}}, "required": ["mood", "visual_language", "imagery_direction"]},
            "content_priorities": {"type": "array", "items": {"type": "object", "properties": {"content": {"type": "string"}, "priority": {"type": "string"}, "reason": {"type": "string"}}, "required": ["content", "priority", "reason"]}},
            "visual_hierarchy": {"type": "object", "properties": {"focal_point": {"type": "string"}, "reading_path": {"type": "string"}}, "required": ["focal_point", "reading_path"]},
            "composition": {"type": "string"},
            "typography": {"type": "object", "properties": {"hierarchy": {"type": "string"}, "headline_role": {"type": "string"}}, "required": ["hierarchy", "headline_role"]},
            "color_system": {"type": "object", "properties": {"mood": {"type": "string"}, "roles": {"type": "string"}}, "required": ["mood", "roles"]},
            "asset_strategy": {"type": "object", "properties": {"imagery_required": {"type": "boolean"}, "direction": {"type": "string"}}, "required": ["imagery_required", "direction"]},
        },
        "required": ["concept", "art_direction", "content_priorities", "visual_hierarchy", "composition", "typography", "color_system", "asset_strategy"],
    },
}


class DesignDecisionDiagnostic:
    def __init__(self, *, model: str | None = None, api_key: str | None = None):
        self.model = model or os.getenv("PLANNER_MODEL", "gemini-3.5-flash-lite")
        self._api_key = api_key or resolve_provider_secret(
            "gemini",
            environment_names=("PLANNER_GEMINI_API_KEY", "GEMINI_API_KEY"),
        )
        self._client = None

    def run(self, request: str, *, level: int = 3, json_only: bool = False) -> DiagnosticResult:
        if level not in _LEVEL_SCHEMAS:
            raise ValueError("diagnostic level must be 1, 2, or 3")
        if not self._api_key:
            return DiagnosticResult(model=self.model, level=level, success=False, source="AI", error_type="MISSING_CREDENTIAL", error_message="PLANNER_GEMINI_API_KEY is missing.")
        try:
            from google import genai
            from google.genai import types

            instruction = (
                "You are a professional graphic designer and art director. Decide what the design should communicate and look like. "
                "Make contextual decisions about concept, hierarchy, composition, typography, color, and imagery. "
                "Do not return SVG, coordinates, code, tools, or implementation instructions. Return only the requested JSON."
            )
            prompt = instruction + "\n\nUSER REQUEST:\n" + request
            config = {"system_instruction": instruction, "response_mime_type": "application/json"}
            if not json_only:
                config["response_schema"] = _LEVEL_SCHEMAS[level]
            if self._client is None:
                self._client = genai.Client(api_key=self._api_key)
            response = self._client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(**config),
            )
            payload = json.loads(response.text or "{}")
            required = _LEVEL_SCHEMAS[level].get("required", [])
            missing = [field for field in required if field not in payload or payload[field] in (None, "", [], {})]
            return DiagnosticResult(model=self.model, level=level, success=not missing, decisions=payload, missing_fields=missing)
        except Exception as exc:
            message = str(exc)
            lowered = message.lower()
            error_type = "QUOTA_EXHAUSTED" if "429" in lowered or "quota" in lowered else "INVALID_ARGUMENT" if "400" in lowered or "invalid argument" in lowered else "PROVIDER_ERROR"
            return DiagnosticResult(model=self.model, level=level, success=False, error_type=error_type, error_message=message.splitlines()[0][:500])

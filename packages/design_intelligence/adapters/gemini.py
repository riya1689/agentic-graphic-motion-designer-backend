"""Provider-neutral focused design-reasoning transport boundary."""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List

from pydantic import BaseModel, Field
from packages.ai.provider import active_provider, openai_model, openai_structured
from packages.provider_secrets.application.runtime import resolve_provider_secret


class FocusedDesignDecisions(BaseModel):
    """Small AI contract for design intent, not rendering or execution."""

    concept: str = Field(min_length=1)
    art_direction: Dict[str, Any] = Field(default_factory=dict)
    content_priorities: List[Dict[str, Any]] = Field(default_factory=list)
    visual_hierarchy: Dict[str, Any] = Field(default_factory=dict)
    composition: Dict[str, Any] | str
    typography: Dict[str, Any] = Field(default_factory=dict)
    color_system: Dict[str, Any] = Field(default_factory=dict)
    asset_strategy: Dict[str, Any] = Field(default_factory=dict)
    layout_plan: Dict[str, Any] = Field(default_factory=dict)
    visual_elements: List[Dict[str, Any]] = Field(default_factory=list)
    communication_strategy: Dict[str, Any] = Field(default_factory=dict)
    spacing: Dict[str, Any] = Field(default_factory=dict)
    shape_language: Dict[str, Any] = Field(default_factory=dict)
    decorative_strategy: Dict[str, Any] = Field(default_factory=dict)
    reading_flow: Dict[str, Any] = Field(default_factory=dict)


DESIGN_CONTEXT_HINTS = {
    "social": "fast recognition, mobile readability, focal message, and clear action",
    "banner": "wide scan path, concise messaging, responsive-safe spacing, and separation",
    "certificate": "formal hierarchy, generous whitespace, structured identity, and restrained ornament",
    "invitation": "event atmosphere, intentional focal composition, and date/location clarity",
    "infographic": "information grouping, sequencing, data emphasis, and modular readability",
    "product": "product dominance, value proposition, context relationship, and commercial clarity",
    "thumbnail": "instant recognition, large readable copy, strong contrast, and small-size legibility",
    "business card": "compact identity hierarchy, contact legibility, and restrained branding",
    "educational": "conceptual sequencing, explanatory grouping, and clear technical hierarchy",
    "custom": "infer the communication goal from the brief without relying on a predefined template",
}


FOCUSED_DESIGN_SCHEMA = {
    "type": "object",
    "properties": {
        "concept": {"type": "string"},
        "art_direction": {"type": "object", "properties": {"style": {"type": "string"}, "mood": {"type": "string"}, "visual_language": {"type": "string"}, "imagery_direction": {"type": "string"}}},
        "content_priorities": {"type": "array", "items": {"type": "object", "properties": {"content": {"type": "string"}, "priority": {"type": "string"}, "reason": {"type": "string"}}}},
        "visual_hierarchy": {"type": "object", "properties": {"focal_point": {"type": "string"}, "reading_path": {"type": "string"}, "whitespace_intent": {"type": "string"}}},
        "composition": {"type": "object", "properties": {"strategy": {"type": "string"}, "alignment": {"type": "string"}, "balance": {"type": "string"}, "focal_placement": {"type": "string"}, "visual_flow": {"type": "string"}}},
        "typography": {"type": "object", "properties": {"hierarchy": {"type": "string"}, "headline_role": {"type": "string"}, "font_category": {"type": "string"}, "weight": {"type": "string"}, "readability": {"type": "string"}}},
        "color_system": {"type": "object", "properties": {"mood": {"type": "string"}, "background": {"type": "string"}, "background_treatment": {"type": "string"}, "primary": {"type": "string"}, "accent": {"type": "string"}, "text": {"type": "string"}, "cta": {"type": "string"}, "contrast_intent": {"type": "string"}}},
        "asset_strategy": {"type": "object", "properties": {"imagery_required": {"type": "boolean"}, "visual_anchor": {"type": "string"}, "direction": {"type": "string"}}},
        "layout_plan": {"type": "object", "properties": {"regions": {"type": "array", "items": {"type": "object", "properties": {"id": {"type": "string"}, "purpose": {"type": "string"}, "x": {"type": "number"}, "y": {"type": "number"}, "width": {"type": "number"}, "height": {"type": "number"}, "alignment": {"type": "string"}, "priority": {"type": "integer"}}}}, "reading_path": {"type": "string"}}},
        "visual_elements": {"type": "array", "items": {"type": "object", "properties": {"id": {"type": "string"}, "type": {"type": "string"}, "layer": {"type": "string"}, "role": {"type": "string"}, "region": {"type": "string"}, "fill_role": {"type": "string"}, "stroke_role": {"type": "string"}, "fill": {"type": "string"}, "stroke": {"type": "string"}, "opacity": {"type": "number"}, "x": {"type": "number"}, "y": {"type": "number"}, "width": {"type": "number"}, "height": {"type": "number"}, "geometry": {"type": "object"}}}},
        "communication_strategy": {"type": "object", "properties": {"goal": {"type": "string"}, "audience": {"type": "string"}, "interaction_goal": {"type": "string"}}},
        "spacing": {"type": "object", "properties": {"density": {"type": "string"}, "whitespace": {"type": "string"}, "safe_area": {"type": "string"}}},
        "shape_language": {"type": "object", "properties": {"style": {"type": "string"}, "geometry": {"type": "string"}}},
        "decorative_strategy": {"type": "object", "properties": {"approach": {"type": "string"}, "restraint": {"type": "string"}}},
        "reading_flow": {"type": "object", "properties": {"path": {"type": "string"}, "sequence": {"type": "string"}}},
    },
    "required": ["concept", "art_direction", "content_priorities", "visual_hierarchy", "composition", "typography", "color_system", "asset_strategy", "layout_plan", "visual_elements"],
}


class GeminiFocusedDesignReasoner:
    """Provider-compatible focused design reasoner kept under its legacy name."""

    def __init__(self, *, model: str | None = None, api_key: str | None = None):
        self.model = model or (
            openai_model("OPENAI_PLANNER_MODEL")
            if active_provider() == "openai"
            else os.getenv("PLANNER_MODEL", "gemini-3.5-flash-lite")
        )
        self._api_key = api_key or resolve_provider_secret(
            "gemini",
            environment_names=("PLANNER_GEMINI_API_KEY", "GEMINI_API_KEY"),
        )
        self._client = None

    def reason(self, request) -> FocusedDesignDecisions:
        if active_provider() == "openai":
            api_key_available = bool(resolve_provider_secret("openai", environment_names=("OPENAI_API_KEY",)))
        else:
            api_key_available = bool(self._api_key)
        if not api_key_available:
            provider = active_provider()
            key_name = "OPENAI_API_KEY" if provider == "openai" else "PLANNER_GEMINI_API_KEY"
            raise RuntimeError(f"{key_name} is missing.")

        design_type = (request.design_type or "custom").lower()
        hint = next((value for key, value in DESIGN_CONTEXT_HINTS.items() if key in design_type), DESIGN_CONTEXT_HINTS["custom"])
        instruction = (
            "You are a professional graphic designer and art director. Decide what the design should communicate and look like. "
            "Determine concept, communication strategy, art direction, content priorities, hierarchy, composition, typography, semantic colors, asset strategy, spacing, shape language, decorative strategy, and reading flow. "
            f"Use this design-context consideration as input, not as a fixed template: {hint}. "
            "Make contextual decisions; do not merely repeat the request. Return a normalized layout_plan with composition-specific regions and visual_elements. Use semantic region ids such as primary, supporting, action, and visual; choose different regions and element types for the actual request instead of reusing a poster template. "
            "Coordinates in layout_plan and visual_elements must be normalized 0..1 semantic placement decisions; they are not SVG or code. Do not return SVG, provider names, tools, or implementation instructions."
        )
        safe_brief = request.model_dump(mode="json")
        safe_brief["reference_assets"] = [
            {
                "kind": asset.kind,
                "description": asset.description,
                "required": asset.required,
                "uri": "[uploaded image data supplied to renderer]" if asset.uri else None,
            }
            for asset in request.reference_assets
        ]
        safe_brief["input_assets"] = safe_brief["reference_assets"]
        prompt = instruction + "\n\nUSER REQUEST:\n" + request.context_prompt + "\n\nSTRUCTURED BRIEF:\n" + json.dumps(safe_brief, ensure_ascii=False)
        if active_provider() == "openai":
            payload = openai_structured(
                model=self.model,
                prompt=prompt,
                system_instruction=instruction,
                schema=FOCUSED_DESIGN_SCHEMA,
                schema_name="focused_design_decisions",
            )
            return FocusedDesignDecisions.model_validate(payload)

        from google import genai
        from google.genai import types
        if self._client is None:
            self._client = genai.Client(api_key=self._api_key)
        response = self._client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=instruction,
                response_mime_type="application/json",
                response_schema=FOCUSED_DESIGN_SCHEMA,
            ),
        )
        payload = json.loads(response.text or "{}")
        return FocusedDesignDecisions.model_validate(payload)

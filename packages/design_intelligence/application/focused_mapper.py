"""Map focused AI design decisions into the canonical design specification."""

from __future__ import annotations

from copy import deepcopy
import re
from typing import Any

from packages.request_contract.domain.schema import NormalizedRequest

from ..adapters.gemini import FocusedDesignDecisions
from ..domain.specification import (
    ContentPriority,
    DesignSpecification,
    design_specification_from_request,
)


class FocusedDesignSpecificationMapper:
    """Apply AI design intent without allowing it to erase user requirements."""

    def map(
        self,
        request: NormalizedRequest,
        decisions: FocusedDesignDecisions,
    ) -> tuple[DesignSpecification, dict[str, Any]]:
        baseline = design_specification_from_request(request)
        data = deepcopy(baseline.model_dump(mode="python"))
        self._art_direction(data, decisions.art_direction)
        self._content(data, decisions.content_priorities)
        self._hierarchy(data, decisions.visual_hierarchy)
        self._composition(data, decisions.composition)
        self._typography(data, decisions.typography)
        self._colors(data, decisions.color_system, request.colors)
        self._assets(data, decisions.asset_strategy)
        # A user-uploaded image is a hard requirement. AI art direction may
        # refine its role, but it must never remove the image layer.
        if request.reference_assets:
            data["asset_strategy"]["imagery_required"] = True
            data["asset_strategy"]["assets"] = deepcopy(
                baseline.asset_strategy.model_dump(mode="python")["assets"]
            )
        data["layout_plan"] = deepcopy(decisions.layout_plan)
        data["visual_elements"] = deepcopy(decisions.visual_elements)
        self._extended_intent(data, decisions)
        data["concept"] = decisions.concept
        data["designer_decisions"] = [
            f"AI concept: {decisions.concept}",
            "Focused Gemini design decisions mapped into the canonical specification.",
        ]
        data["decision_sources"] = {
            "brief": "user",
            "concept": "ai",
            "art_direction": "ai",
            "content_hierarchy": "user_and_ai",
            "visual_hierarchy": "ai",
            "composition": "ai",
            "typography": "ai",
            "color_system": "user_and_ai" if request.colors else "ai",
            "asset_strategy": "ai",
            "design_tokens": "ai",
            "layout_plan": "ai",
            "visual_elements": "ai",
        }
        specification = DesignSpecification.model_validate(data)
        return specification, {
            "sources": {
                "concept": "ai",
                "art_direction": "ai",
                "content_priorities": "ai",
                "visual_hierarchy": "ai",
                "composition": "ai",
                "typography": "ai",
                "color_system": "ai_with_user_constraints",
                "asset_strategy": "ai",
                "layout_plan": "ai",
                "visual_elements": "ai",
            },
            "fallback_used": False,
            "model": "focused_gemini",
        }

    @staticmethod
    def _art_direction(data: dict[str, Any], values: dict[str, Any]) -> None:
        target = data["art_direction"]
        aliases = {"style": "style", "mood": "mood", "tone": "tone", "visual_language": "visual_language", "imagery_direction": "imagery_direction"}
        for source, destination in aliases.items():
            if values.get(source):
                target[destination] = str(values[source])
        target["attributes"].update({k: v for k, v in values.items() if k not in aliases and v is not None})

    @staticmethod
    def _content(data: dict[str, Any], values: list[dict[str, Any]]) -> None:
        by_value = {item["value"].strip().lower(): item for item in data["content_hierarchy"]}
        for decision in values:
            value = str(decision.get("content") or decision.get("value") or "").strip()
            item = by_value.get(value.lower())
            if not item:
                continue
            priority = str(decision.get("priority") or "").lower()
            try:
                item["priority"] = ContentPriority(priority).value
            except ValueError:
                pass
            if isinstance(decision.get("reason"), str):
                item["emphasis"] = decision["reason"]

    @staticmethod
    def _hierarchy(data: dict[str, Any], values: dict[str, Any]) -> None:
        target = data["visual_hierarchy"]
        for key in ("primary_focal_point", "primary_visual_anchor", "reading_path", "whitespace_intent"):
            if values.get(key):
                target[key] = str(values[key])
        if values.get("focal_point"):
            focal = str(values["focal_point"])
            target["primary_visual_anchor"] = focal
            target["primary_focal_point"] = focal
        if isinstance(values.get("secondary_focal_points"), list):
            target["secondary_focal_points"] = [str(v) for v in values["secondary_focal_points"]]

    @staticmethod
    def _composition(data: dict[str, Any], values: dict[str, Any] | str) -> None:
        target = data["composition"]
        baseline_strategy = target.get("strategy")
        if isinstance(values, str):
            raw = values
            values = {"visual_flow": raw}
        else:
            raw = " ".join(str(v) for v in values.values() if v)
        aliases = ("strategy", "grid", "alignment", "balance", "symmetry", "focal_placement", "negative_space", "density", "visual_flow", "safe_area", "margins", "reading_direction")
        for key in aliases:
            if values.get(key):
                target[key] = str(values[key])
        target["visual_flow"] = target.get("visual_flow") or raw
        lower = raw.lower()
        # Keep the AI wording in visual_flow, but translate common semantic
        # descriptions into the existing renderer-independent layout vocabulary.
        strategy_text = str(target.get("strategy") or "").lower()
        design_type = str(data.get("design_type") or "").lower()
        if "split" in lower or "asymmetric" in lower or "diagonal" in lower or "asymmetric" in strategy_text or "diagonal" in strategy_text:
            target["strategy"] = "split"
        elif "modular" in lower or "grid" in lower or "sequence" in lower or "educational" in lower:
            target["strategy"] = "modular"
        elif "certificate" in design_type or "formal" in lower or "whitespace" in lower:
            target["strategy"] = "whitespace_driven"
        elif "invitation" in design_type or "event" in lower or "center" in lower:
            target["strategy"] = "centered"
        elif "product" in design_type or "product_led" in lower or "image_led" in lower:
            target["strategy"] = "image_led"
        elif "banner" in design_type or "wide" in lower or "horizontal" in lower:
            target["strategy"] = "split"
        elif "social" in design_type or "thumbnail" in design_type or "focal" in lower or "promotional" in lower or "recognition" in lower:
            target["strategy"] = "focal_centered"
        elif target.get("strategy") not in {"split", "modular", "whitespace_driven", "centered", "image_led", "focal_centered"}:
            target["strategy"] = baseline_strategy or "intent-driven composition"

    @staticmethod
    def _typography(data: dict[str, Any], values: dict[str, Any]) -> None:
        target = data["typography"]
        display = target.get("display") or {"name": "display", "purpose": "primary communication"}
        for key in ("font_category", "weight", "scale", "alignment", "font_personality", "casing", "contrast_intent"):
            if values.get(key):
                display[key] = str(values[key])
        if values.get("hierarchy"):
            display["font_personality"] = str(values["hierarchy"])
        if values.get("headline_role"):
            display["purpose"] = str(values["headline_role"])
        target["display"] = display
        if values.get("readability"):
            target["readability_requirements"] = [str(values["readability"])]

    @staticmethod
    def _colors(data: dict[str, Any], values: dict[str, Any], required: list[str]) -> None:
        target = data["color_system"]
        explicit = {str(color).strip().lower() for color in required}
        for role in ("background", "background_treatment", "surface", "primary", "secondary", "accent", "text", "muted_text", "cta", "border", "contrast_intent", "dominance", "temperature", "saturation", "harmony", "accent_usage", "background_foreground_relationship"):
            candidate = values.get(role)
            if not candidate:
                continue
            if required and role in {"background", "primary"} and str(candidate).lower() not in explicit:
                continue
            target[role] = (
                str(candidate)
                if role == "background_treatment"
                else FocusedDesignSpecificationMapper._css_color(candidate)
            )
        target["required_colors"] = list(required)
        if isinstance(values.get("decorative"), list):
            target["decorative"] = [FocusedDesignSpecificationMapper._css_color(v) for v in values["decorative"]]

    @staticmethod
    def _css_color(value: Any) -> str:
        """Keep AI semantic colors renderer-safe without changing user colors."""
        text = str(value).strip()
        hex_value = re.search(r"#[0-9a-fA-F]{6}\b", text)
        if hex_value:
            return hex_value.group(0)
        semantic = {
            "turquoise": "#06b6d4", "cyan": "#06b6d4", "aqua": "#06b6d4",
            "coral": "#f97316", "orange": "#f97316", "yellow": "#facc15",
            "sunshine": "#facc15", "white": "#ffffff", "navy": "#0a192f",
            "blue": "#2563eb", "pink": "#ec4899", "magenta": "#d946ef",
            "lime": "#84cc16", "green": "#16a34a", "red": "#ef4444",
        }
        lowered = text.lower()
        for name, color in semantic.items():
            if name in lowered:
                return color
        return text

    @staticmethod
    def _assets(data: dict[str, Any], values: dict[str, Any]) -> None:
        target = data["asset_strategy"]
        if "imagery_required" in values:
            target["imagery_required"] = bool(values["imagery_required"])
        if values.get("visual_anchor"):
            target["visual_anchor"] = str(values["visual_anchor"])

    @staticmethod
    def _extended_intent(data: dict[str, Any], decisions: FocusedDesignDecisions) -> None:
        direction = data["art_direction"]
        if decisions.shape_language:
            direction["shape_language"] = " ".join(str(v) for v in decisions.shape_language.values() if v)
        if decisions.decorative_strategy:
            direction["decorative_direction"] = " ".join(str(v) for v in decisions.decorative_strategy.values() if v)
        spacing = decisions.spacing
        if spacing.get("density"):
            data["design_tokens"]["density"] = str(spacing["density"])
        if spacing.get("whitespace"):
            data["design_tokens"]["section_spacing"] = str(spacing["whitespace"])
        if spacing.get("safe_area"):
            data["composition"]["safe_area"] = str(spacing["safe_area"])
        flow = decisions.reading_flow
        if flow.get("path") or flow.get("sequence"):
            data["visual_hierarchy"]["reading_path"] = str(flow.get("path") or flow.get("sequence"))
        strategy = decisions.communication_strategy
        if strategy.get("goal"):
            data["brief"]["communication_goal"] = str(strategy["goal"])
        if strategy.get("interaction_goal"):
            data["brief"]["interaction_goal"] = str(strategy["interaction_goal"])

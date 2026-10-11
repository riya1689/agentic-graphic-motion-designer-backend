"""Translate existing Prompt-to-JSON output into the Phase 3 contract."""

from __future__ import annotations

import re
from typing import Any, Dict, Optional

from packages.request_contract.domain.schema import (
    CreativeType,
    NormalizedRequest,
    OutputRequirement,
    SizeSpec,
)


class PromptToJsonInterpreter:
    """Use the existing prompt parser as the new workflow's interpreter port."""

    def interpret(
        self,
        raw_input: str,
        *,
        selected_image_model: str | None = None,
        selected_video_model: str | None = None,
        **_: Any,
    ) -> Dict[str, Any]:
        # Import lazily so the provider-neutral contract remains importable in
        # tests and does not initialize the legacy graph during module import.
        from packages.prompt_to_json_agent.api.router import run_prompt_conversion

        lowered = raw_input.lower()
        motion_markers = (
            "video", "motion", "animate", "animation", "reel", "clip",
        )
        requested_type = "motion" if any(marker in lowered for marker in motion_markers) else "image"
        result = run_prompt_conversion(
            asset_type=requested_type,
            prompt=raw_input,
            auto_complete_missing=True,
        )
        spec = result.get("spec") or {}
        if not isinstance(spec, dict):
            raise ValueError("Prompt interpreter returned an invalid specification.")

        # The existing extractor owns asset-type detection. Preserve it when
        # present, while retaining image as the safe default for old prompts.
        asset_type = str(spec.get("asset_type") or "image").strip().lower()
        spec["asset_type"] = asset_type
        spec["selected_model"] = (
            selected_video_model if asset_type == "motion" else selected_image_model
        )
        return spec


def _parse_size(value: Any) -> Optional[SizeSpec]:
    if not isinstance(value, str):
        return None
    match = re.fullmatch(r"\s*(\d+)\s*[xX×]\s*(\d+)\s*", value)
    if not match:
        return None
    return SizeSpec(width=int(match.group(1)), height=int(match.group(2)))


def _default_output(
    creative_type: CreativeType,
    source: Dict[str, Any],
) -> OutputRequirement:
    requested = source.get("requested_output_format") or source.get("output_format")
    if isinstance(requested, str) and requested.strip():
        output_format = requested.strip().lower().lstrip(".")
    else:
        output_format = "jpg" if creative_type == CreativeType.IMAGE else "mp4"

    target = str(source.get("target_software") or "").lower()
    editable = bool(source.get("editable_output_required"))
    if target in {"adobe_illustrator", "illustrator"}:
        output_format = "ai"
        editable = True
    elif target in {"adobe_photoshop", "photoshop"}:
        output_format = "psd"
        editable = True
    elif target in {"after_effects", "video_generation"} and creative_type == CreativeType.MOTION:
        output_format = "editable_project" if target == "after_effects" else output_format
        editable = target == "after_effects"

    return OutputRequirement(
        media_type=creative_type,
        format=output_format,
        editable_required=editable,
        native_editable_required=editable and output_format in {"svg", "psd", "ai", "editable_project"},
    )


class PromptToJsonRequestAdapter:
    """Transitional translator; it does not invoke or duplicate the old agent."""

    def from_output(
        self,
        output: Dict[str, Any] | Any,
        *,
        request_id: str,
        original_prompt: str = "",
        selected_image_model: str | None = None,
        selected_video_model: str | None = None,
    ) -> NormalizedRequest:
        source = (
            output.model_dump(mode="python")
            if hasattr(output, "model_dump")
            else dict(output)
        )
        creative_type = CreativeType(source.get("asset_type", "image"))
        selected_model = (
            selected_image_model
            if creative_type == CreativeType.IMAGE
            else selected_video_model
        )
        additional = dict(source.get("additional_requirements") or {})

        return NormalizedRequest(
            request_id=request_id,
            creative_type=creative_type,
            context_prompt=original_prompt or str(source.get("user_goal") or "structured request"),
            design_type=source.get("design_type"),
            purpose=source.get("purpose") or source.get("user_goal"),
            size=_parse_size(source.get("canvas_dimensions")),
            brand=source.get("brand"),
            colors=list(source.get("color_palette") or []),
            text=list(source.get("editable_typography") or []),
            style=(source.get("design_preferences") or {}).get("style")
            if isinstance(source.get("design_preferences"), dict)
            else None,
            reference_assets=[],
            input_assets=[],
            quality_preferences={},
            additional_requirements=additional,
            selected_model=selected_model,
            output=_default_output(creative_type, source),
        )

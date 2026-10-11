"""Deterministic Manager-side request understanding.

This is intentionally independent from the legacy Prompt-to-JSON Agent.  The
Manager receives the user's prompt directly and produces the stable request
contract consumed by routing, planning, and execution.
"""

from __future__ import annotations

import re
import os
import time
from typing import Literal
from typing import Any

from pydantic import BaseModel

from packages.request_contract.domain.schema import (
    AssetReference,
    CreativeType,
    NormalizedRequest,
    OutputRequirement,
    SizeSpec,
)
from packages.ai.provider import active_provider, openai_model, openai_structured
from packages.provider_secrets.application.runtime import resolve_provider_secret


AUTO_MODEL_VALUES = {"", "auto", "all", "all_image_models"}
CODE_IMAGE_MODEL = "code_image"
IMAGE_TO_VECTOR_MODEL = "image_to_vector"
HYBRID_SVG_MODEL = "hybrid_svg"


class DirectRequestUnderstandingService:
    """Convert a raw Manager prompt directly into ``NormalizedRequest``."""

    def understand(
        self,
        raw_input: str,
        *,
        request_id: str,
        selected_model: str | None = None,
        selected_image_model: str | None = None,
        selected_video_model: str | None = None,
        attachments: list[dict[str, Any]] | None = None,
        **_: Any,
    ) -> NormalizedRequest:
        prompt = raw_input.strip()
        if not prompt:
            raise ValueError("Prompt must not be empty.")

        lowered = prompt.lower()
        is_motion = any(
            token in lowered
            for token in ("video", "motion", "animate", "animation", "reel", "clip")
        )
        creative_type = CreativeType.MOTION if is_motion else CreativeType.IMAGE

        output_format = self._output_format(lowered, creative_type)
        native_required = output_format in {"svg", "ai", "psd", "editable_project"}
        selected_model = self._selected_model(
            selected_model if selected_model is not None else (
                selected_video_model if is_motion else selected_image_model
            )
        )
        if selected_model == CODE_IMAGE_MODEL and creative_type == CreativeType.IMAGE:
            output_format = "svg"
            native_required = True
        if selected_model == IMAGE_TO_VECTOR_MODEL and creative_type == CreativeType.IMAGE:
            output_format = "svg"
            native_required = True
        if selected_model == HYBRID_SVG_MODEL and creative_type == CreativeType.IMAGE:
            output_format = "svg"
            native_required = True

        size = self._size(prompt)
        colors = self._colors(prompt)
        text = self._quoted_text(prompt)
        references = [
            AssetReference(
                kind="image" if str(item.get("mime_type") or "").startswith("image/") else str(item.get("type") or "reference"),
                uri=item.get("uri"),
                description=(
                    f"{item.get('name') or 'uploaded image'}; "
                    f"user asset instruction: {item.get('description')}"
                    if item.get("description")
                    else item.get("name") or item.get("description")
                ),
            )
            for item in (attachments or [])
            if isinstance(item, dict)
        ]

        return NormalizedRequest(
            request_id=request_id,
            creative_type=creative_type,
            context_prompt=prompt,
            design_type=self._design_type(lowered),
            purpose=prompt,
            size=size,
            colors=colors,
            text=text,
            style=self._style(lowered),
            reference_assets=references,
            input_assets=references,
            selected_model=selected_model,
            output=OutputRequirement(
                media_type=creative_type,
                format=output_format,
                editable_required=native_required,
                native_editable_required=native_required,
            ),
            additional_requirements={
                "requested_outputs": [output_format],
                "requires_planning": True,
                "direct_manager_understanding": True,
                "native_svg_requested": output_format == "svg",
                "asset_usage_mode": (
                    "vector_reconstruction"
                    if selected_model == IMAGE_TO_VECTOR_MODEL
                    else "hybrid_raster_vector"
                    if selected_model == HYBRID_SVG_MODEL
                    else "embedded_reference"
                ),
            },
        )

    @staticmethod
    def _selected_model(value: str | None) -> str | None:
        normalized = (value or "").strip().lower()
        if normalized == "auto":
            return "image_auto"
        return None if normalized in {"", "all", "all_image_models"} else value.strip()

    @staticmethod
    def _output_format(prompt: str, creative_type: CreativeType) -> str:
        if creative_type == CreativeType.MOTION:
            return "mp4"
        if re.search(r"(?:^|[\s.])svg(?:$|[\s.]?)|vector|icon|logo|illustration", prompt):
            return "svg"
        if re.search(r"\b(?:png|jpg|jpeg|webp)\b", prompt):
            return re.search(r"\b(?:png|jpg|jpeg|webp)\b", prompt).group(0)
        return "jpg"

    @staticmethod
    def _size(prompt: str) -> SizeSpec | None:
        match = re.search(r"(\d{2,5})\s*[x×]\s*(\d{2,5})", prompt)
        return SizeSpec(width=int(match.group(1)), height=int(match.group(2))) if match else None

    @staticmethod
    def _colors(prompt: str) -> list[str]:
        values = re.findall(r"#[0-9a-fA-F]{6}\b", prompt)
        known = re.findall(
            r"\b(?:black|white|red|blue|green|yellow|purple|pink|orange|cyan|magenta|gold)\b",
            prompt.lower(),
        )
        return list(dict.fromkeys([*values, *known]))

    @staticmethod
    def _quoted_text(prompt: str) -> list[str]:
        return list(dict.fromkeys(re.findall(r"['\"]([^'\"]+)['\"]", prompt)))

    @staticmethod
    def _design_type(prompt: str) -> str | None:
        for value in (
            "event poster", "poster", "social media advertisement", "social media post", "social media", "social",
            "promotional banner", "web banner", "banner", "campaign graphic", "product advertisement", "product",
            "sale graphic", "announcement graphic", "digital signage", "event banner", "webinar graphic", "festival graphic",
            "business card", "certificate", "letterhead", "promotional card", "invitation", "flyer", "brochure", "infographic",
            "educational graphic", "information card", "quote card", "presentation graphic", "presentation", "social carousel",
            "youtube thumbnail", "video thumbnail", "thumbnail", "app promotional graphic", "logo", "icon", "illustration",
        ):
            if value in prompt:
                return value
        return "graphic_design"

    @staticmethod
    def _style(prompt: str) -> str | None:
        for value in (
            "minimal", "modern", "futuristic", "cyberpunk", "flat", "geometric", "luxury", "retro",
            "professional", "calm", "premium", "educational", "elegant", "warm",
        ):
            if value in prompt:
                return value
        return None


class LLMUnderstandingOutput(BaseModel):
    creative_type: Literal["image", "motion"]
    output_format: str
    design_type: str | None = None
    purpose: str | None = None
    width: int | None = None
    height: int | None = None
    colors: list[str] = []
    text: list[str] = []
    style: str | None = None
    audience: str | None = None
    requirements: list[str] = []


class LLMRequestUnderstandingService:
    """Manager-owned Gemini understanding; it does not call the JSON agent."""

    def understand(
        self,
        raw_input: str,
        *,
        request_id: str,
        selected_model: str | None = None,
        selected_image_model: str | None = None,
        selected_video_model: str | None = None,
        attachments: list[dict[str, Any]] | None = None,
        **_: Any,
    ) -> NormalizedRequest:
        api_key = resolve_provider_secret(
            "gemini",
            environment_names=("GEMINI_API_KEY",),
        )

        prompt = raw_input.strip()
        instruction = (
            "You are the Manager Agent's request-understanding specialist for an "
            "agentic graphic and motion design system. Interpret the user's request "
            "into the supplied structured schema. Preserve every explicit detail. "
            "Use output_format svg only when the user asks for SVG, vector, logo, "
            "icon, or an editable vector; otherwise use jpg for images and mp4 for motion. "
            "Do not invent assets, providers, tools, or execution steps."
        )
        if active_provider() == "openai":
            payload = openai_structured(
                model=openai_model("OPENAI_MODEL"),
                prompt=prompt,
                system_instruction=instruction,
                schema=LLMUnderstandingOutput.model_json_schema(),
                schema_name="manager_request_understanding",
            )
            parsed = LLMUnderstandingOutput.model_validate(payload)
            return self._build_normalized_request(
                request_id=request_id,
                prompt=prompt,
                parsed=parsed,
                selected_model=selected_model,
                selected_image_model=selected_image_model,
                selected_video_model=selected_video_model,
                attachments=attachments,
            )

        if not api_key:
            raise RuntimeError("GEMINI_API_KEY is required for Manager understanding.")
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=api_key)
        models = [os.getenv("GEMINI_MODEL", "gemini-2.5-flash"), "gemini-flash-latest", "gemini-3.5-flash-lite"]
        last_error: Exception | None = None
        parsed: LLMUnderstandingOutput | None = None
        for model in dict.fromkeys(models):
            for attempt in range(1, 4):
                try:
                    response = client.models.generate_content(
                        model=model,
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            system_instruction=instruction,
                            response_mime_type="application/json",
                            response_schema=LLMUnderstandingOutput,
                        ),
                    )
                    parsed = response.parsed or LLMUnderstandingOutput.model_validate_json(response.text)
                    break
                except Exception as exc:
                    last_error = exc
                    if attempt < 3 and any(token in str(exc).lower() for token in ("503", "429", "unavailable", "overload")):
                        time.sleep(attempt * 2)
                    else:
                        break
            if parsed is not None:
                break
        if parsed is None:
            raise RuntimeError(f"Manager LLM understanding failed: {last_error}")

        return self._build_normalized_request(
            request_id=request_id,
            prompt=prompt,
            parsed=parsed,
            selected_model=selected_model,
            selected_image_model=selected_image_model,
            selected_video_model=selected_video_model,
            attachments=attachments,
        )

    @staticmethod
    def _build_normalized_request(*, request_id, prompt, parsed, selected_model, selected_image_model, selected_video_model, attachments):
        creative_type = CreativeType(parsed.creative_type)
        output_format = parsed.output_format.strip().lower().lstrip(".")
        if creative_type == CreativeType.MOTION:
            output_format = "mp4"
        if output_format == "jpeg":
            output_format = "jpg"
        native = output_format in {"svg", "ai", "psd", "editable_project"}
        selected = selected_model if selected_model is not None else (
            selected_video_model if creative_type == CreativeType.MOTION else selected_image_model
        )
        selected = DirectRequestUnderstandingService._selected_model(selected)
        if selected == CODE_IMAGE_MODEL and creative_type == CreativeType.IMAGE:
            output_format = "svg"
            native = True
        if selected == IMAGE_TO_VECTOR_MODEL and creative_type == CreativeType.IMAGE:
            output_format = "svg"
            native = True
        if selected == HYBRID_SVG_MODEL and creative_type == CreativeType.IMAGE:
            output_format = "svg"
            native = True
        references = [
            AssetReference(
                kind="image" if str(item.get("mime_type") or "").startswith("image/") else str(item.get("type") or "reference"),
                uri=item.get("uri"),
                description=(
                    f"{item.get('name') or 'uploaded image'}; user asset instruction: {item.get('description')}"
                    if item.get("description") else item.get("name") or item.get("description")
                ),
            )
            for item in (attachments or []) if isinstance(item, dict)
        ]
        return NormalizedRequest(
            request_id=request_id,
            creative_type=CreativeType(parsed.creative_type),
            context_prompt=prompt,
            design_type=parsed.design_type,
            purpose=parsed.purpose,
            size=SizeSpec(width=parsed.width, height=parsed.height) if parsed.width and parsed.height else None,
            colors=parsed.colors,
            text=parsed.text,
            style=parsed.style,
            audience=parsed.audience,
            reference_assets=references,
            input_assets=references,
            selected_model=selected,
            output=OutputRequirement(
                media_type=creative_type,
                format=output_format,
                editable_required=native,
                native_editable_required=native,
            ),
            additional_requirements={
                "requires_planning": True,
                "requested_outputs": [output_format],
                "llm_understood": True,
                "requirements": parsed.requirements,
                "asset_usage_mode": (
                    "vector_reconstruction"
                    if selected == IMAGE_TO_VECTOR_MODEL
                    else "hybrid_raster_vector"
                    if selected == HYBRID_SVG_MODEL
                    else "embedded_reference"
                ),
            },
        )

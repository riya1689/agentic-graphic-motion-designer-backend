"""Hybrid SVG capability: one raster layer plus an editable vector layer."""

from __future__ import annotations

import base64
import json
import os
import xml.etree.ElementTree as ET
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Callable, Protocol

from packages.ai.provider import active_provider, openai_generate_raster_image, openai_model
from packages.execution.domain.contracts import (
    ExecutionError,
    ExecutionRequest,
    ExecutionResult,
    ExecutionStatus,
    OutputAsset,
)
from core.runtime_urls import public_api_url
from packages.graphic_agent.rendering.svg_renderer import SvgRenderer, SvgStructuralValidationError
from packages.verification.strategies.preview import PillowSvgPreviewRenderer


HYBRID_SVG_MODEL = "hybrid_svg"
MAX_BACKGROUND_PROMPT_CHARS = 30_000
XLINK_NAMESPACE = "http://www.w3.org/1999/xlink"
XLINK_HREF = f"{{{XLINK_NAMESPACE}}}href"


class RasterBackgroundProvider(Protocol):
    def generate(self, *, prompt: str, width: int, height: int) -> "RasterBackground":
        ...


@dataclass(frozen=True)
class RasterBackground:
    data: bytes
    mime_type: str = "image/png"

    @property
    def data_uri(self) -> str:
        encoded = base64.b64encode(self.data).decode("ascii")
        return f"data:{self.mime_type};base64,{encoded}"


class OpenAIRasterBackgroundProvider:
    """OpenAI implementation behind the provider-neutral raster boundary."""

    def __init__(self, *, model: str | None = None, generator: Callable[..., tuple[bytes, str]] | None = None) -> None:
        self.model = model or openai_model("OPENAI_BACKGROUND_IMAGE_MODEL", "gpt-image-1")
        self._generator = generator

    def generate(self, *, prompt: str, width: int, height: int) -> RasterBackground:
        if active_provider() != "openai" and self._generator is None:
            raise RuntimeError("Hybrid SVG background generation requires the OpenAI provider.")
        size = os.getenv("OPENAI_BACKGROUND_IMAGE_SIZE", "1024x1024")
        if self._generator is not None:
            data, mime_type = self._generator(prompt=prompt, width=width, height=height, size=size, model=self.model)
        else:
            data, mime_type = openai_generate_raster_image(prompt=prompt, model=self.model, size=size)
        if not data:
            raise RuntimeError("Raster background provider returned empty image data.")
        return RasterBackground(data=data, mime_type=mime_type)


def hybrid_svg_directory(request_id: str) -> Path:
    root = Path(__file__).resolve().parents[2]
    path = root / "runtime-data" / "graphic_agent" / request_id / "hybrid"
    path.mkdir(parents=True, exist_ok=True)
    return path


def hybrid_svg_path(request_id: str) -> Path:
    return hybrid_svg_directory(request_id) / "design.svg"


def hybrid_svg_preview_path(request_id: str) -> Path:
    return hybrid_svg_directory(request_id) / "preview.png"


class HybridSvgExecutor:
    """Compose the existing vector renderer with an optional raster layer."""

    provider_id = "graphic_agent.hybrid"
    model_id = HYBRID_SVG_MODEL

    def __init__(self, *, foreground_executor, background_provider: RasterBackgroundProvider) -> None:
        self._foreground_executor = foreground_executor
        self._background_provider = background_provider

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        normalized = request.normalized_request
        if normalized.output.format != "svg":
            return self._failure(request, "OUTPUT_FORMAT_MISMATCH", "Hybrid SVG requires SVG output.")
        if not request.metadata.get("execution_plan"):
            return self._failure(request, "MISSING_PLANNER_PLAN", "Hybrid SVG requires the complete Planner execution plan.")

        try:
            plan_metadata = getattr(request.metadata["execution_plan"], "metadata", {})
            document = plan_metadata.get("graphic_execution_spec", {}).get("document", {}) if isinstance(plan_metadata, dict) else {}
            width = int(document.get("width") or (normalized.size.width if normalized.size else 1080))
            height = int(document.get("height") or (normalized.size.height if normalized.size else 1080))

            background = None
            if not normalized.reference_assets:
                background = self._background_provider.generate(
                    prompt=self._background_prompt(request, plan_metadata),
                    width=width,
                    height=height,
                )

            foreground_request = request
            if not normalized.reference_assets:
                foreground_metadata = dict(request.metadata)
                foreground_metadata["hybrid_svg_foreground"] = True
                foreground_request = replace(request, metadata=foreground_metadata)
            foreground_result = self._foreground_executor.execute(foreground_request)
            if not foreground_result.success or not foreground_result.output_assets:
                return foreground_result
            foreground_path = foreground_result.output_assets[0].metadata.get("absolute_path")
            if not foreground_path:
                return self._failure(request, "VECTOR_LAYER_MISSING", "Vector renderer did not return a local SVG artifact.")
            foreground_svg = Path(foreground_path).read_text(encoding="utf-8")
            final_svg = self._compose(foreground_svg, background, required_text=normalized.text)
            output_path = hybrid_svg_path(request.request_id)
            output_path.write_text(final_svg, encoding="utf-8")
        except (SvgStructuralValidationError, OSError, ValueError, RuntimeError) as exc:
            return self._failure(request, "HYBRID_SVG_FAILED", str(exc))
        except Exception as exc:
            # Provider SDK failures must become a normal execution failure so
            # the manager can return structured state instead of HTTP 500.
            return self._failure(request, "HYBRID_SVG_PROVIDER_FAILED", str(exc))

        preview = PillowSvgPreviewRenderer().render(
            final_svg,
            source_artifact=str(output_path),
            output_reference=str(hybrid_svg_preview_path(request.request_id)),
        )
        return ExecutionResult(
            request_id=request.request_id,
            status=ExecutionStatus.SUCCESS,
            provider=self.provider_id,
            model_id=self.model_id,
            output_assets=[OutputAsset(
                uri=public_api_url(
                    f"/api/manager/jobs/{request.request_id}/hybrid/preview"
                ),
                format="svg",
                editable=True,
                native_editable=True,
                metadata={
                    "absolute_path": str(output_path),
                    "download_uri": public_api_url(
                        f"/api/manager/jobs/{request.request_id}/hybrid/download"
                    ),
                    "preview_reference": preview.reference,
                    "preview_uri": (
                        public_api_url(
                            f"/api/manager/jobs/{request.request_id}/hybrid/preview.png"
                        )
                        if preview.render_status == "success"
                        else None
                    ),
                    "preview_status": preview.render_status,
                    "preview_error": preview.error,
                    "provider_verified": True,
                    "native_editable_evidence": "hybrid_raster_and_vector_layers",
                    "hybrid_svg": True,
                    "raster_background_generated": background is not None,
                    "media_type": "image",
                },
            )],
            metadata={
                "renderer": "graphic_agent.hybrid_svg",
                "absolute_path": str(output_path),
                "hybrid_svg": True,
                "raster_background_generated": background is not None,
            },
        )

    @staticmethod
    def _background_prompt(request: ExecutionRequest, plan_metadata: dict[str, Any]) -> str:
        planner_requirements = {
            key: plan_metadata.get(key)
            for key in (
                "job_summary",
                "primary_job_type",
                "target_output_format",
                "global_constraints",
                "graphic_execution_spec",
                "design_specification",
                "layout_specification",
                "execution_order",
            )
            if key in plan_metadata
        }
        compact_plan = _compact_value(planner_requirements)
        user_request = str(request.normalized_request.context_prompt or "")
        if len(user_request) > 6_000:
            user_request = user_request[:6_000] + "…"
        plan_text = json.dumps(compact_plan, ensure_ascii=False, separators=(",", ":"), default=str)
        if len(plan_text) > 20_000:
            plan_text = plan_text[:20_000] + "…"
        prompt = (
            "Generate only a clean, premium raster background for the requested graphic. "
            "This image will be embedded behind an editable SVG design. "
            "Absolutely no text, letters, numbers, words, logos, signage, UI, buttons, labels, or typography. "
            "Leave intentional visual breathing room for the foreground vector design. "
            "Use the subject, industry, mood, palette, and composition from the planner requirements. "
            "Do not render any poster copy or CTA into the background.\n\n"
            f"USER REQUEST:\n{user_request}\n\n"
            f"PLANNER REQUIREMENTS:\n{plan_text}"
        )
        return prompt[:MAX_BACKGROUND_PROMPT_CHARS]

    @staticmethod
    def _compose(svg_text: str, background: RasterBackground | None, *, required_text: list[str]) -> str:
        try:
            root = ET.fromstring(svg_text)
        except ET.ParseError as exc:
            raise SvgStructuralValidationError(f"Vector foreground SVG is malformed: {exc}") from exc
        if root.tag.rsplit("}", 1)[-1].lower() != "svg":
            raise SvgStructuralValidationError("Hybrid SVG foreground root must be svg.")

        ET.register_namespace("", "http://www.w3.org/2000/svg")
        ET.register_namespace("xlink", XLINK_NAMESPACE)
        root_namespace = root.tag[1:].split("}", 1)[0] if root.tag.startswith("{") else ""
        group_tag = f"{{{root_namespace}}}g" if root_namespace else "g"
        image_tag = f"{{{root_namespace}}}image" if root_namespace else "image"

        children = list(root)
        for child in children:
            root.remove(child)
        defs = [child for child in children if child.tag.rsplit("}", 1)[-1].lower() == "defs"]
        other_children = [child for child in children if child not in defs]
        for child in defs:
            root.append(child)

        if background is not None:
            background_group = ET.Element(group_tag, {
                "id": "raster-background-layer",
                "data-layer-type": "raster-background",
                "data-embedded": "true",
            })
            background_image = ET.SubElement(background_group, image_tag, {
                "id": "raster-background",
                "x": "0",
                "y": "0",
                "width": root.attrib.get("width", "1080"),
                "height": root.attrib.get("height", "1080"),
                "preserveAspectRatio": "xMidYMid slice",
            })
            background_image.set(XLINK_HREF, background.data_uri)
            root.append(background_group)

        vector_group = ET.Element(group_tag, {
            "id": "vector-design-layer",
            "data-layer-type": "editable-vector-design",
        })
        for child in other_children:
            vector_group.append(child)
        root.append(vector_group)

        serialized = ET.tostring(root, encoding="unicode", short_empty_elements=True)
        SvgRenderer().validate(serialized, required_text=required_text)
        if background is not None and "data:image/" not in serialized.lower():
            raise SvgStructuralValidationError("Hybrid SVG raster background was not embedded.")
        return serialized

    @staticmethod
    def _failure(request: ExecutionRequest, code: str, message: str) -> ExecutionResult:
        return ExecutionResult(
            request_id=request.request_id,
            status=ExecutionStatus.FAILED,
            provider=HybridSvgExecutor.provider_id,
            model_id=HYBRID_SVG_MODEL,
            error=ExecutionError(code, message),
        )


def _compact_value(value: Any) -> Any:
    if isinstance(value, str):
        if value.startswith("data:image/"):
            return "[asset data omitted]"
        return value if len(value) <= 1600 else value[:1600] + "…"
    if isinstance(value, dict):
        return {str(key): _compact_value(nested) for key, nested in value.items() if key not in {"uri", "path", "raw_prompt"}}
    if isinstance(value, list):
        return [_compact_value(item) for item in value[:100]]
    return value

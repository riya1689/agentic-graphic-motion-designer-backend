"""Dedicated image-to-vector reconstruction executor.

This capability treats an uploaded image as a visual reference only.  It is
intentionally separate from the normal uploaded-asset renderer, where the
image must remain embedded as an SVG ``<image>`` layer.
"""

from __future__ import annotations

import base64
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Callable
from urllib.parse import unquote_to_bytes

from packages.ai.provider import active_provider, openai_model, openai_multimodal_structured
from core.runtime_urls import public_api_url
from packages.execution.domain.contracts import (
    ExecutionError,
    ExecutionRequest,
    ExecutionResult,
    ExecutionStatus,
    OutputAsset,
)
from packages.graphic_agent.rendering.svg_renderer import SvgStructuralValidationError
from packages.verification.strategies.preview import PillowSvgPreviewRenderer


IMAGE_TO_VECTOR_MODEL = "image_to_vector"


def vector_svg_directory(request_id: str) -> Path:
    root = Path(__file__).resolve().parents[2]
    path = root / "runtime-data" / "graphic_agent" / request_id / "vector"
    path.mkdir(parents=True, exist_ok=True)
    return path


def vector_svg_path(request_id: str) -> Path:
    return vector_svg_directory(request_id) / "design.svg"


def vector_svg_preview_path(request_id: str) -> Path:
    return vector_svg_directory(request_id) / "preview.png"


class ImageToVectorExecutor:
    """Reconstruct one uploaded image as editable, self-contained SVG."""

    provider_id = "openai_vector"
    model_id = IMAGE_TO_VECTOR_MODEL
    _response_schema = {
        "type": "object",
        "properties": {
            "svg_code": {"type": "string"},
            "implementation_notes": {"type": "string"},
        },
        "required": ["svg_code"],
    }

    def __init__(
        self,
        *,
        model: str | None = None,
        generator: Callable[..., dict[str, Any]] | None = None,
    ) -> None:
        self.model = model or openai_model(
            "OPENAI_VECTOR_MODEL",
            openai_model(
                "OPENAI_VISION_MODEL",
                openai_model("OPENAI_MODEL", "gpt-5"),
            ),
        )
        self._generator = generator

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        normalized = request.normalized_request
        if normalized.output.format != "svg":
            return self._failure(request, "OUTPUT_FORMAT_MISMATCH", "Image-to-vector reconstruction requires SVG output.")
        if active_provider() != "openai" and self._generator is None:
            return self._failure(request, "VECTOR_PROVIDER_UNAVAILABLE", "Image-to-vector reconstruction requires the OpenAI provider.")
        if len(normalized.reference_assets) != 1:
            return self._failure(request, "VECTOR_REFERENCE_REQUIRED", "Upload exactly one PNG, JPG, or SVG image for vector reconstruction.")

        try:
            image_bytes, mime_type = _decode_data_image(normalized.reference_assets[0].uri)
            plan = request.metadata.get("execution_plan")
            plan_metadata = getattr(plan, "metadata", {}) if plan else {}
            prompt = self._prompt(request, plan_metadata)
            payload = self._generate(prompt, image_bytes, mime_type)
            svg_code = self._validate_svg(payload.get("svg_code"))
            path = vector_svg_path(request.request_id)
            path.write_text(svg_code, encoding="utf-8")
        except (SvgStructuralValidationError, ValueError, TypeError) as exc:
            return self._failure(request, "VECTOR_RECONSTRUCTION_FAILED", str(exc))
        except Exception as exc:
            return self._failure(request, "VECTOR_RECONSTRUCTION_FAILED", str(exc))

        preview = PillowSvgPreviewRenderer().render(
            svg_code,
            source_artifact=str(path),
            output_reference=str(vector_svg_preview_path(request.request_id)),
        )
        preview_uri = public_api_url(
            f"/api/manager/jobs/{request.request_id}/vector/preview.png"
        )
        return ExecutionResult(
            request_id=request.request_id,
            status=ExecutionStatus.SUCCESS,
            provider=self.provider_id,
            model_id=self.model_id,
            output_assets=[OutputAsset(
                uri=public_api_url(
                    f"/api/manager/jobs/{request.request_id}/vector/preview"
                ),
                format="svg",
                editable=True,
                native_editable=True,
                metadata={
                    "absolute_path": str(path),
                    "download_uri": public_api_url(
                        f"/api/manager/jobs/{request.request_id}/vector/download"
                    ),
                    "preview_reference": preview.reference,
                    "preview_uri": preview_uri if preview.render_status == "success" else None,
                    "preview_status": preview.render_status,
                    "preview_error": preview.error,
                    "provider_verified": True,
                    "native_editable_evidence": "vector_reconstruction",
                    "vector_only": True,
                    "media_type": "image",
                },
            )],
            metadata={
                "renderer": "graphic_agent.image_to_vector",
                "absolute_path": str(path),
                "vector_only": True,
            },
        )

    def _generate(self, prompt: str, image_bytes: bytes, mime_type: str) -> dict[str, Any]:
        if self._generator is not None:
            return self._generator(
                prompt=prompt,
                image_bytes=image_bytes,
                image_mime_type=mime_type,
                model=self.model,
                schema=self._response_schema,
            )
        return openai_multimodal_structured(
            prompt=prompt,
            image_bytes=image_bytes,
            image_mime_type=mime_type,
            model=self.model,
            schema=self._response_schema,
            schema_name="image_to_vector_svg",
        )

    @staticmethod
    def _prompt(request: ExecutionRequest, plan_metadata: dict[str, Any]) -> str:
        safe_plan = _compact_value(plan_metadata)
        plan_text = json.dumps(safe_plan, ensure_ascii=False, separators=(",", ":"), default=str)
        return (
            "You are the dedicated Image-to-Vector Reconstruction renderer. "
            "Use the attached uploaded image as a visual reference only. "
            "Recreate its visible components as editable SVG vector elements: paths, shapes, lines, curves, text, gradients, masks, and groups where appropriate. "
            "Preserve composition, proportions, colors, typography, spacing, outlines, shadows, layering, and negative space as accurately as possible. "
            "Return one complete SVG inside the svg_code field. "
            "The final SVG must be self-contained and contain no image element, no raster data URI, no linked file, no external URL, no script, and no foreignObject. "
            "Do not put the original uploaded image into the SVG. Do not explain the plan inside the artwork. "
            "Group logical components with stable ids so the SVG remains editable in Adobe Illustrator.\n\n"
            f"USER RECONSTRUCTION REQUEST:\n{request.normalized_request.context_prompt}\n\n"
            f"AUTHORITATIVE PLANNER REQUIREMENTS:\n{plan_text}"
        )

    @staticmethod
    def _validate_svg(svg_code: Any) -> str:
        if not isinstance(svg_code, str) or not svg_code.strip():
            raise SvgStructuralValidationError("Vector renderer returned no SVG code.")
        code = re.sub(r"^```(?:svg|xml)?\s*|\s*```$", "", svg_code.strip(), flags=re.IGNORECASE | re.DOTALL)
        try:
            root = ET.fromstring(code)
        except ET.ParseError as exc:
            raise SvgStructuralValidationError(f"Vector renderer returned malformed SVG: {exc}") from exc
        if root.tag.rsplit("}", 1)[-1].lower() != "svg":
            raise SvgStructuralValidationError("Vector reconstruction output root must be svg.")
        lowered = code.lower()
        for forbidden in ("<image", "<foreignobject", "<script", "javascript:"):
            if forbidden in lowered:
                raise SvgStructuralValidationError(f"Vector SVG contains forbidden raster or external content: {forbidden}")
        for element in root.iter():
            for attribute, value in element.attrib.items():
                local_attribute = attribute.rsplit("}", 1)[-1].lower()
                value_text = str(value).strip().lower()
                if local_attribute in {"href", "src"} and (
                    value_text.startswith(("data:image/", "http://", "https://", "file:", "asset:", "data-asset:"))
                ):
                    raise SvgStructuralValidationError(
                        "Vector SVG contains forbidden raster or external content in a resource attribute."
                    )
                if "url(http://" in value_text or "url(https://" in value_text or "url(file:" in value_text:
                    raise SvgStructuralValidationError(
                        "Vector SVG contains an external resource reference in a style attribute."
                    )
        primitive_names = {"path", "rect", "circle", "ellipse", "line", "polygon", "polyline", "text", "tspan"}
        if not any(element.tag.rsplit("}", 1)[-1].lower() in primitive_names for element in root.iter()):
            raise SvgStructuralValidationError("Vector reconstruction produced no editable vector primitives.")
        return code

    def _failure(self, request: ExecutionRequest, code: str, message: str) -> ExecutionResult:
        return ExecutionResult(
            request_id=request.request_id,
            status=ExecutionStatus.FAILED,
            provider=self.provider_id,
            model_id=self.model_id,
            error=ExecutionError(code, message),
        )


def _decode_data_image(uri: str | None) -> tuple[bytes, str]:
    value = str(uri or "")
    if not value.lower().startswith("data:image/") or "," not in value:
        raise ValueError("Uploaded image must be an embedded data:image URI.")
    header, body = value.split(",", 1)
    mime_type = header[5:].split(";", 1)[0].lower()
    if mime_type not in {"image/png", "image/jpeg", "image/svg+xml"}:
        raise ValueError("Only PNG, JPG, and SVG images can be reconstructed as vectors.")
    if ";base64" in header.lower():
        return base64.b64decode(body), mime_type
    return unquote_to_bytes(body), mime_type


def _compact_value(value: Any) -> Any:
    if isinstance(value, str):
        if value.startswith("data:image/"):
            return "[uploaded image supplied separately to the vector renderer]"
        return value if len(value) <= 1800 else value[:1800] + "…"
    if isinstance(value, dict):
        return {
            str(key): _compact_value(nested)
            for key, nested in value.items()
            if key not in {"uri", "path", "raw_prompt"}
        }
    if isinstance(value, list):
        return [_compact_value(item) for item in value[:100]]
    return value

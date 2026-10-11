"""Native SVG execution owned by the Graphic Agent.

The renderer writes vector primitives directly.  It never invokes a raster
image model and never wraps, traces, or embeds a raster image in SVG.
"""

from __future__ import annotations

from pathlib import Path

from packages.execution.domain.contracts import (
    ExecutionError,
    ExecutionRequest,
    ExecutionResult,
    ExecutionStatus,
    OutputAsset,
)
from core.runtime_urls import public_api_url
from packages.graphic_agent.rendering.svg_renderer import (
    SvgRenderCompiler,
    SvgRenderer,
    SvgStructuralValidationError,
)
from packages.graphic_agent.rendering.illustrator import make_illustrator_compatible_svg
from packages.verification.strategies.preview import PillowSvgPreviewRenderer


def native_svg_path(request_id: str) -> Path:
    root = Path(__file__).resolve().parents[2]
    output_dir = root / "runtime-data" / "graphic_agent" / request_id / "native"
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir / "design.svg"


def native_svg_preview_path(request_id: str) -> Path:
    path = native_svg_path(request_id)
    return path.with_name("preview.png")


class NativeSvgGraphicExecutor:
    """Render the normalized graphic request into editable SVG primitives."""

    provider_id = "graphic_agent"

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        normalized = request.normalized_request
        if normalized.output.format != "svg":
            return ExecutionResult(
                request_id=request.request_id,
                status=ExecutionStatus.FAILED,
                provider=self.provider_id,
                model_id="native_svg_renderer",
                error=ExecutionError("OUTPUT_FORMAT_MISMATCH", "Native SVG executor requires SVG output."),
            )

        width = normalized.size.width if normalized.size else 1080
        height = normalized.size.height if normalized.size else 1080
        execution_plan = request.metadata.get("execution_plan")
        plan_metadata = getattr(execution_plan, "metadata", {}) if execution_plan else {}
        graphic_spec = plan_metadata.get("graphic_execution_spec") if isinstance(plan_metadata, dict) else None
        if not isinstance(graphic_spec, dict):
            return ExecutionResult(
                request_id=request.request_id,
                status=ExecutionStatus.FAILED,
                provider=self.provider_id,
                model_id="native_svg_renderer",
                error=ExecutionError(
                    "MISSING_GRAPHIC_EXECUTION_SPEC",
                    "Planner did not return an LLM-generated graphic execution specification.",
                ),
            )

        document = graphic_spec.get("document") or {}
        width = int(document.get("width") or width)
        height = int(document.get("height") or height)
        path = native_svg_path(request.request_id)
        try:
            render_spec = SvgRenderCompiler().compile(
                graphic_spec,
                title=normalized.design_type or "Graphic design",
                description=normalized.context_prompt,
                required_text=normalized.text,
            )
            svg_text = SvgRenderer().render(render_spec)
            if normalized.reference_assets:
                svg_text = make_illustrator_compatible_svg(
                    svg_text,
                    normalized.reference_assets,
                )
                SvgRenderer().validate(svg_text, required_text=normalized.text)
            SvgRenderer.validate_required_asset_layers(svg_text, normalized.reference_assets)
        except SvgStructuralValidationError as exc:
            return ExecutionResult(
                request_id=request.request_id,
                status=ExecutionStatus.FAILED,
                provider=self.provider_id,
                model_id="native_svg_renderer",
                error=ExecutionError("SVG_VALIDATION_FAILED", str(exc)),
            )
        path.write_text(svg_text, encoding="utf-8")
        preview = PillowSvgPreviewRenderer().render(
            svg_text,
            source_artifact=str(path),
            output_reference=str(native_svg_preview_path(request.request_id)),
        )
        uri = public_api_url(
            f"/api/manager/jobs/{request.request_id}/preview"
        )
        preview_uri = public_api_url(
            f"/api/manager/jobs/{request.request_id}/preview.png"
        )
        return ExecutionResult(
            request_id=request.request_id,
            status=ExecutionStatus.SUCCESS,
            provider=self.provider_id,
            model_id="native_svg_renderer",
            output_assets=[
                OutputAsset(
                    uri=uri,
                    format="svg",
                    editable=True,
                    native_editable=True,
                    metadata={
                        "native_editable_evidence": "vector_objects",
                        "vector_object_count": svg_text.count("<") - svg_text.count("</"),
                        "absolute_path": str(path),
                        "preview_reference": preview.reference,
                        "preview_uri": preview_uri if preview.render_status == "success" else None,
                        "preview_status": preview.render_status,
                        "preview_error": preview.error,
                    },
                )
            ],
            metadata={
                "renderer": "graphic_agent.native_svg",
                "absolute_path": str(path),
                "preview_reference": preview.reference,
                "preview_uri": preview_uri if preview.render_status == "success" else None,
                "preview_status": preview.render_status,
                "preview_error": preview.error,
            },
        )

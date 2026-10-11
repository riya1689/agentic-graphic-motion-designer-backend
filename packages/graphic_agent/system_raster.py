"""Local raster output for Auto/system mode.

The system path reuses the canonical execution specification and native SVG
compiler. It never calls Higgsfield and never converts a provider raster into
SVG. Raster output is only produced when the user selected Auto/no model.
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
from packages.verification.strategies.preview import PillowSvgPreviewRenderer


def system_raster_directory(request_id: str) -> Path:
    root = Path(__file__).resolve().parents[2]
    path = root / "runtime-data" / "graphic_agent" / request_id / "system"
    path.mkdir(parents=True, exist_ok=True)
    return path


def system_raster_path(request_id: str, output_format: str) -> Path:
    return system_raster_directory(request_id) / f"design.{output_format.lower().lstrip('.') or 'png'}"


def system_raster_source_path(request_id: str) -> Path:
    return system_raster_directory(request_id) / "design.svg"


class SystemRasterGraphicExecutor:
    provider_id = "system"
    model_id = "system_graphic_renderer"

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        output_format = request.normalized_request.output.format.lower().lstrip(".")
        if output_format not in {"png", "jpg", "webp"}:
            return ExecutionResult(
                request_id=request.request_id,
                status=ExecutionStatus.FAILED,
                provider=self.provider_id,
                model_id=self.model_id,
                error=ExecutionError("OUTPUT_FORMAT_MISMATCH", "System raster renderer supports PNG, JPG, and WEBP."),
            )

        plan = request.metadata.get("execution_plan")
        metadata = getattr(plan, "metadata", {}) if plan else {}
        graphic_spec = metadata.get("graphic_execution_spec") if isinstance(metadata, dict) else None
        if not isinstance(graphic_spec, dict):
            return ExecutionResult(
                request_id=request.request_id,
                status=ExecutionStatus.FAILED,
                provider=self.provider_id,
                model_id=self.model_id,
                error=ExecutionError("MISSING_GRAPHIC_EXECUTION_SPEC", "System rendering requires a compiled graphic execution specification."),
            )

        source_path = system_raster_source_path(request.request_id)
        output_path = system_raster_path(request.request_id, output_format)
        try:
            render_spec = SvgRenderCompiler().compile(
                graphic_spec,
                title=request.normalized_request.design_type or "Graphic design",
                description=request.normalized_request.context_prompt,
                required_text=request.normalized_request.text,
            )
            svg_text = SvgRenderer().render(render_spec)
            SvgRenderer.validate_required_asset_layers(svg_text, request.normalized_request.reference_assets)
            source_path.write_text(svg_text, encoding="utf-8")
            preview = PillowSvgPreviewRenderer().render(
                svg_text,
                source_artifact=str(source_path),
                output_reference=str(output_path if output_format == "png" else output_path.with_suffix(".png")),
            )
            if preview.render_status != "success" or not preview.reference:
                raise RuntimeError(preview.error or "System raster preview could not be rendered.")
            png_path = Path(preview.reference)
            if output_format != "png":
                from PIL import Image

                with Image.open(png_path) as image:
                    image.convert("RGB").save(output_path, format=output_format.upper())
                if png_path != output_path:
                    png_path.unlink(missing_ok=True)
            else:
                output_path = png_path
        except (SvgStructuralValidationError, OSError, ValueError, RuntimeError) as exc:
            return ExecutionResult(
                request_id=request.request_id,
                status=ExecutionStatus.FAILED,
                provider=self.provider_id,
                model_id=self.model_id,
                error=ExecutionError("SYSTEM_RENDER_FAILED", str(exc)),
            )
        return ExecutionResult(
            request_id=request.request_id,
            status=ExecutionStatus.SUCCESS,
            provider=self.provider_id,
            model_id=self.model_id,
            output_assets=[OutputAsset(
                uri=public_api_url(
                    f"/api/manager/jobs/{request.request_id}/system/preview"
                ),
                format=output_format,
                editable=False,
                native_editable=False,
                metadata={
                    "absolute_path": str(output_path),
                    "download_uri": public_api_url(
                        f"/api/manager/jobs/{request.request_id}/system/download"
                    ),
                    "provider_verified": True,
                    "media_type": "image",
                    "system_generated": True,
                },
            )],
            metadata={"renderer": "system.graphic_renderer", "source_svg": str(source_path)},
        )

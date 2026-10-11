"""
Graphic Format Router

RESPONSIBILITY:

- Receive target_output_format
- Route to correct formatter
- Return artifact metadata

IMPORTANT:

NO:
- planner logic
- manager logic
- image generation
- tool selection
"""

from __future__ import annotations

from packages.graphic_agent.artifacts.jpg_formatter import (
    format_to_jpg,
)
from packages.graphic_agent.artifacts.svg_formatter import (
    format_to_svg,
)
from packages.graphic_agent.artifacts.psd_formatter import (
    format_to_psd,
)
from packages.graphic_agent.artifacts.ai_formatter import (
    format_to_ai,
)


# ============================================================
# BUILD GRAPHIC ARTIFACT
# ============================================================

def build_graphic_artifact(
    *,
    job_id: str,
    source_path: str,
    target_output_format: str,
    allow_raster_conversion: bool = True,
) -> dict:
    normalized = (
        target_output_format
        or "jpg"
    ).strip().lower()

    if normalized in (
        "jpg",
        "jpeg",
    ):
        return format_to_jpg(
            job_id=job_id,
            source_path=source_path,
        )

    if normalized == "svg":
        if not allow_raster_conversion and not str(source_path).lower().endswith(".svg"):
            raise ValueError(
                "Native SVG output is unavailable for a raster provider result. "
                "Raster tracing/embedding is not treated as native editable output."
            )
        return format_to_svg(
            job_id=job_id,
            source_path=source_path,
        )

    if normalized == "ai":
        if not allow_raster_conversion and not str(source_path).lower().endswith(".ai"):
            raise ValueError(
                "Native AI output is unavailable for a raster provider result."
            )
        return format_to_ai(
            job_id=job_id,
            source_path=source_path,
        )

    if normalized == "psd":
        if not allow_raster_conversion and not str(source_path).lower().endswith(".psd"):
            raise ValueError(
                "Native PSD output is unavailable for a raster provider result."
            )
        return format_to_psd(
            job_id=job_id,
            source_path=source_path,
        )

    return format_to_jpg(
        job_id=job_id,
        source_path=source_path,
    )

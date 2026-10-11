"""
SVG Formatter

RESPONSIBILITY:

- Accept generated source image path
- Wrap image inside an SVG document
- Save final SVG artifact + metadata

IMPORTANT:

Phase-1 SVG implementation:
- This creates a valid SVG file
- The original generated image is embedded inside the SVG

This allows:
- browser preview
- download
- basic SVG workflow

Later you can replace this with a true vector generator.
"""

from __future__ import annotations

import base64

from pathlib import Path

from packages.graphic_agent.artifacts.image_store import (
    save_remote_image_artifact,
)
from packages.graphic_agent.artifacts.store import (
    GraphicArtifactRecord,
    build_download_url,
    build_preview_url,
    get_output_dir,
    save_artifact_record,
)


# ============================================================
# MIME RESOLUTION
# ============================================================

def _resolve_image_mime(
    suffix: str,
) -> str:
    normalized = suffix.lower()

    if normalized in (
        ".jpg",
        ".jpeg",
    ):
        return "image/jpeg"

    if normalized == ".png":
        return "image/png"

    if normalized == ".webp":
        return "image/webp"

    raise ValueError(
        f"Unsupported SVG source type: {suffix}"
    )


# ============================================================
# FORMAT TO SVG
# ============================================================

def format_to_svg(
    *,
    job_id: str,
    source_path: str,
) -> dict:
    if isinstance(source_path, str) and source_path.startswith(("http://", "https://")):
        source_path = save_remote_image_artifact(
            job_id=job_id,
            image_url=source_path,
        )

    source = Path(
        source_path
    )

    if not source.exists():
        raise FileNotFoundError(
            f"Source image not found: {source}"
        )

    image_bytes = source.read_bytes()

    mime_type = _resolve_image_mime(
        source.suffix
    )

    encoded = base64.b64encode(
        image_bytes
    ).decode(
        "utf-8"
    )

    output_dir = get_output_dir(
        job_id
    )

    output_path = (
        output_dir
        / "design.svg"
    )

    vector_traced = False
    try:
        import vtracer
        vtracer.convert_image_to_svg_py(
            str(source),
            str(output_path),
            colormode="color",
            hierarchical="stacked",
            mode="spline",
            filter_speckle=4,
            color_precision=6,
            layer_difference=16,
            corner_threshold=60,
            length_threshold=4.0,
            max_iterations=10,
            splice_threshold=45,
            path_precision=3
        )
        vector_traced = True
    except Exception as exc:
        print(f"[SVG FORMATTER] Vector tracing notice ({exc}). Using embedded vector fallback...")

    if not vector_traced or not output_path.exists() or output_path.stat().st_size == 0:
        svg_text = f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" version="1.1" width="1024" height="1024" viewBox="0 0 1024 1024">
  <rect width="100%" height="100%" fill="white" />
  <image
    href="data:{mime_type};base64,{encoded}"
    x="0"
    y="0"
    width="1024"
    height="1024"
    preserveAspectRatio="xMidYMid meet"
  />
</svg>
"""
        output_path.write_text(
            svg_text,
            encoding="utf-8",
        )

    record = GraphicArtifactRecord(
        job_id=job_id,
        format="svg",
        filename=output_path.name,
        absolute_path=str(
            output_path.resolve()
        ),
        mime_type="image/svg+xml",
        preview_url=build_preview_url(
            job_id
        ),
        download_url=build_download_url(
            job_id
        ),
    )

    return save_artifact_record(
        record
    )
"""
AI Formatter (Phase 2 - Adobe Illustrator Native Generator & SVG Fallback)

RESPONSIBILITY:
- Convert design into native Adobe Illustrator (.ai) document using Illustrator ExtendScript JSX
- If Illustrator is not available locally, falls back to crisp vector SVG format (which Illustrator natively opens as vector)

IMPORTANT:
- Independent of Manager and Planner logic
- Returns standard GraphicArtifactRecord
"""

from __future__ import annotations

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

from packages.graphic_agent.artifacts.svg_formatter import (
    format_to_svg,
)


def format_to_ai(
    *,
    job_id: str,
    source_path: str,
    execution_spec: dict | None = None,
) -> dict:
    """
    Format output into native Adobe Illustrator (.ai) file if Illustrator is available,
    otherwise fallback to vector SVG.
    """
    if isinstance(source_path, str) and source_path.startswith(("http://", "https://")):
        source_path = save_remote_image_artifact(
            job_id=job_id,
            image_url=source_path,
        )

    output_dir = get_output_dir(job_id)
    output_ai_path = output_dir / "design.ai"

    from packages.graphic_agent.bridges.adobe_bridge import (
        is_illustrator_available,
        execute_illustrator_jsx,
    )

    adobe_executed = False
    if is_illustrator_available():
        jsx_script_path = Path("runtime-data") / "graphic_agent" / job_id / "fallback" / "illustrator_design.jsx"
        if jsx_script_path.exists():
            adobe_executed = execute_illustrator_jsx(jsx_script_path)

    if adobe_executed and output_ai_path.exists():
        record = GraphicArtifactRecord(
            job_id=job_id,
            format="ai",
            filename=output_ai_path.name,
            absolute_path=str(output_ai_path.resolve()),
            mime_type="application/illustrator",
            preview_url=build_preview_url(job_id),
            download_url=build_download_url(job_id),
        )
        return save_artifact_record(record)

    # Fallback to vector SVG
    print("[AI FORMATTER] Adobe Illustrator not running locally. Using SVG vector fallback for .ai request...")
    return format_to_svg(
        job_id=job_id,
        source_path=source_path,
    )

"""
JPG Formatter

RESPONSIBILITY:

- Accept generated source image path (local file or remote URL)
- Produce final JPG artifact
- Save artifact metadata
"""

from __future__ import annotations

from pathlib import Path
from shutil import copy2
from PIL import Image

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
# FORMAT TO JPG
# ============================================================

def format_to_jpg(
    *,
    job_id: str,
    source_path: str,
) -> dict:
    # If source_path is a remote HTTP/HTTPS URL, download it first
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

    output_dir = get_output_dir(
        job_id
    )

    output_path = (
        output_dir
        / "design.jpg"
    )

    if source.suffix.lower() in (".jpg", ".jpeg"):
        copy2(
            source,
            output_path,
        )
    else:
        # Convert PNG, WEBP or other image formats to JPEG using Pillow
        with Image.open(source) as img:
            rgb_img = img.convert("RGB")
            rgb_img.save(
                output_path,
                "JPEG",
                quality=95,
            )

    record = GraphicArtifactRecord(
        job_id=job_id,
        format="jpg",
        filename=output_path.name,
        absolute_path=str(
            output_path.resolve()
        ),
        mime_type="image/jpeg",
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
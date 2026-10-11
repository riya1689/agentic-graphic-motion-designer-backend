"""
Graphic Image Artifact Store

RESPONSIBILITY:

Remote generated image URL
        ↓
Local runtime artifact

IMPORTANT:

NO:
- Manager logic
- Planner logic
- Higgsfield model selection
- CLI command construction
- Graphic workflow routing
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen


# ============================================================
# EXTENSION RESOLUTION
# ============================================================

_CONTENT_TYPE_EXTENSIONS = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


def _resolve_extension(
    *,
    image_url: str,
    content_type: str,
) -> str:

    normalized_content_type = (
        content_type
        .split(";")[0]
        .strip()
        .lower()
    )

    if normalized_content_type in _CONTENT_TYPE_EXTENSIONS:

        return _CONTENT_TYPE_EXTENSIONS[
            normalized_content_type
        ]


    suffix = Path(
        urlparse(image_url).path
    ).suffix.lower()


    if suffix in {
        ".jpg",
        ".jpeg",
        ".png",
        ".webp",
    }:

        if suffix == ".jpeg":
            return ".jpg"

        return suffix


    return ".jpg"


# ============================================================
# SAVE REMOTE IMAGE
# ============================================================

def save_remote_image_artifact(
    *,
    job_id: str,
    image_url: str,
) -> str:
    """
    Download one generated image and persist it under
    Graphic Agent runtime-data.
    """

    if not image_url.strip():

        raise ValueError(
            "Generated image URL is empty."
        )


    request = Request(
        image_url,
        headers={
            "User-Agent":
                "NGX-Graphic-Agent/1.0",
        },
    )


    with urlopen(
        request,
        timeout=120,
    ) as response:

        image_bytes = response.read()

        content_type = (
            response.headers.get(
                "Content-Type",
                "",
            )
        )


    if not image_bytes:

        raise RuntimeError(
            "Downloaded Higgsfield image is empty."
        )


    extension = _resolve_extension(
        image_url=image_url,
        content_type=content_type,
    )


    output_dir = (
        Path("runtime-data")
        / "graphic_agent"
        / job_id
        / "generated"
    )


    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )


    output_path = (
        output_dir
        / f"generated-image{extension}"
    )


    output_path.write_bytes(
        image_bytes
    )


    return str(
        output_path.resolve()
    )
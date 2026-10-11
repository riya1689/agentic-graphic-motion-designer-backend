"""
Motion Video Artifact Store

RESPONSIBILITY:

video bytes
    ↓
runtime filesystem

Provider/API code does NOT write project files.

This keeps cloud execution and artifact persistence separate.
"""

from __future__ import annotations

from pathlib import Path


# ============================================================
# SAVE VIDEO ARTIFACT
# ============================================================

def save_video_artifact(
    *,
    job_id: str,
    shot_id: str,
    video_bytes: bytes,
) -> str:

    if not video_bytes:

        raise RuntimeError(
            "Cannot store empty video bytes."
        )


    output_dir = (

        Path("runtime-data")

        / "motion_agent"

        / job_id

        / "raw"

    )


    output_dir.mkdir(

        parents=True,

        exist_ok=True,

    )


    output_path = (

        output_dir

        / f"{shot_id}.mp4"

    )


    output_path.write_bytes(
        video_bytes
    )


    return str(
        output_path.resolve()
    )
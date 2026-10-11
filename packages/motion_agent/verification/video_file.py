"""
Generated Video Technical Verification

PHASE-2B:

Only objective artifact verification.

Future phases can add:

- ffprobe
- duration
- FPS
- resolution
- codec
- black frame
- frozen video
- semantic verification
"""

from __future__ import annotations

from pathlib import Path
from typing import List


# ============================================================
# VERIFY GENERATED VIDEO
# ============================================================

def verify_generated_video(
    video_path: str,
) -> List[str]:

    errors: List[str] = []


    if not video_path:

        return [
            "Generated video path is missing."
        ]


    path = Path(
        video_path
    )


    if not path.exists():

        errors.append(
            "Generated video file does not exist."
        )

        return errors


    if not path.is_file():

        errors.append(
            "Generated video path is not a file."
        )

        return errors


    if path.stat().st_size <= 0:

        errors.append(
            "Generated video file is empty."
        )


    if path.suffix.lower() not in {

        ".mp4",
        ".mov",
        ".webm",
        ".mkv",

    }:

        errors.append(
            "Generated artifact does not have "
            "a supported video extension."
        )


    return errors
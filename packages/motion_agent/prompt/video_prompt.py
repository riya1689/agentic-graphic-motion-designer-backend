"""
Generic Video Prompt Compiler

MotionShotSpec
      ↓
natural-language generation prompt

IMPORTANT:

This compiler does NOT know:

- Hugging Face
- Fal
- Replicate
- Wan
- LTX
- Kling
- Veo

Therefore the prompt layer remains reusable.
"""

from __future__ import annotations

from packages.motion_agent.compiler.schema import (
    MotionShotSpec,
)


# ============================================================
# GENERIC VIDEO PROMPT
# ============================================================

def compile_video_prompt(
    shot: MotionShotSpec,
) -> str:

    parts: list[str] = []


    # ========================================================
    # SUBJECT
    # ========================================================

    if shot.subject:

        parts.append(
            f"Subject: {shot.subject.strip()}"
        )


    # ========================================================
    # ACTION
    # ========================================================

    if shot.action:

        parts.append(
            f"Action: {shot.action.strip()}"
        )


    # ========================================================
    # ENVIRONMENT
    # ========================================================

    if shot.environment:

        parts.append(
            f"Environment: {shot.environment.strip()}"
        )


    # ========================================================
    # CAMERA
    # ========================================================

    if shot.camera.movement:

        parts.append(
            "Camera movement: "
            f"{shot.camera.movement.strip()}"
        )


    if shot.camera.angle:

        parts.append(
            "Camera angle: "
            f"{shot.camera.angle.strip()}"
        )


    if shot.camera.framing:

        parts.append(
            "Framing: "
            f"{shot.camera.framing.strip()}"
        )


    # ========================================================
    # LIGHTING
    # ========================================================

    if shot.lighting:

        parts.append(
            f"Lighting: {shot.lighting.strip()}"
        )


    # ========================================================
    # STYLE
    # ========================================================

    if shot.style:

        parts.append(
            f"Visual style: {shot.style.strip()}"
        )


    # ========================================================
    # NEGATIVE REQUIREMENTS
    # ========================================================

    if shot.negative_constraints:

        negatives = ", ".join(
            shot.negative_constraints
        )

        parts.append(
            f"Avoid: {negatives}"
        )


    return ". ".join(
        parts
    ).strip()
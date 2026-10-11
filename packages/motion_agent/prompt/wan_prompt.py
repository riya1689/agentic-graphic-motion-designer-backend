"""
Wan Prompt Compiler

Responsibility:

Generic MotionShotSpec
        ↓
Wan-friendly natural-language prompt

IMPORTANT:

No execution happens here.

No subprocess.
No model loading.
No file writing.
"""

from __future__ import annotations

from packages.motion_agent.compiler.schema import (
    MotionShotSpec,
)


def compile_wan_prompt(
    shot: MotionShotSpec,
) -> str:

    parts: list[str] = []

    if shot.subject:

        parts.append(
            f"Subject: {shot.subject}."
        )

    if shot.action:

        parts.append(
            f"Action: {shot.action}."
        )

    if shot.environment:

        parts.append(
            f"Environment: {shot.environment}."
        )

    if shot.camera.movement:

        parts.append(
            f"Camera movement: "
            f"{shot.camera.movement}."
        )

    if shot.camera.angle:

        parts.append(
            f"Camera angle: "
            f"{shot.camera.angle}."
        )

    if shot.camera.framing:

        parts.append(
            f"Framing: "
            f"{shot.camera.framing}."
        )

    if shot.lighting:

        parts.append(
            f"Lighting: {shot.lighting}."
        )

    if shot.style:

        parts.append(
            f"Visual style: {shot.style}."
        )

    if shot.negative_constraints:

        negatives = ", ".join(
            shot.negative_constraints
        )

        parts.append(
            "Avoid: "
            f"{negatives}."
        )

    return " ".join(parts).strip()
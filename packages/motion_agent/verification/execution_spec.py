"""
MotionExecutionSpec Verification

Responsibility:

Validate the model-neutral execution contract BEFORE
sending anything to a video model.

IMPORTANT:

This verifier knows NOTHING about:
- Wan CLI
- LTX parameters
- ComfyUI
- FFmpeg
"""

from __future__ import annotations

from typing import List

from packages.motion_agent.compiler.schema import (
    MotionExecutionSpec,
)


def verify_motion_execution_spec(
    spec: MotionExecutionSpec,
) -> List[str]:

    errors: List[str] = []

    if not spec.shots:

        errors.append(
            "MotionExecutionSpec contains no shots."
        )

        return errors

    shot_ids = set()

    total_shot_duration = 0.0

    for shot in spec.shots:

        if not shot.shot_id.strip():

            errors.append(
                "Motion shot contains an empty shot_id."
            )

        if shot.shot_id in shot_ids:

            errors.append(
                f"Duplicate shot_id: {shot.shot_id}"
            )

        shot_ids.add(
            shot.shot_id
        )

        total_shot_duration += (
            shot.duration_seconds
        )

        if not shot.subject.strip():

            errors.append(
                f"{shot.shot_id} has no subject."
            )

        if (
            shot.generation_type
            == "image_to_video"
            and not shot.reference_asset
        ):

            errors.append(
                f"{shot.shot_id} requires a reference_asset "
                "for image_to_video."
            )

    if spec.fps <= 0:

        errors.append(
            "FPS must be greater than zero."
        )

    if (
        spec.resolution.width <= 0
        or spec.resolution.height <= 0
    ):

        errors.append(
            "Motion resolution is invalid."
        )

    if total_shot_duration <= 0:

        errors.append(
            "Total shot duration must be greater than zero."
        )

    return errors
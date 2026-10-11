"""
Motion Video Provider Configuration

PURPOSE:

Keep runtime provider/model selection OUTSIDE:

- Manager
- Planner
- Motion graph
- Motion nodes
- MotionExecutionSpec

Future provider/model changes should happen through
configuration + adapters only.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


# ============================================================
# VIDEO RUNTIME CONFIG
# ============================================================

@dataclass(frozen=True)
class MotionVideoRuntimeConfig:
    """
    Runtime infrastructure configuration.

    This is NOT business-plan data.
    """

    gateway: str

    provider: str

    model: str


# ============================================================
# LOAD CONFIG
# ============================================================

def get_motion_video_runtime_config(
) -> MotionVideoRuntimeConfig:

    # --------------------------------------------------------
    # Gateway
    # --------------------------------------------------------
    #
    # Current:
    #   huggingface
    #
    # Future:
    #   fal_direct
    #   replicate_direct
    #   premium_provider
    # --------------------------------------------------------

    gateway = os.getenv(
        "MOTION_VIDEO_GATEWAY",
        "higgsfield",
    ).strip().lower()


    # --------------------------------------------------------
    # Hugging Face provider routing
    # --------------------------------------------------------
    #
    # "auto" means Hugging Face selects an available
    # inference provider for the selected model.
    #
    # Can later become:
    #   fal-ai
    #   replicate
    #   etc.
    # --------------------------------------------------------

    provider = os.getenv(
        "HF_VIDEO_PROVIDER",
        "auto",
    ).strip()


    # --------------------------------------------------------
    # MODEL
    # --------------------------------------------------------
    #
    # Model is infrastructure configuration.
    #
    # Motion Agent does NOT hardcode it.
    # --------------------------------------------------------

    if gateway == "higgsfield":
        model = os.getenv(
            "HIGGSFIELD_VIDEO_MODEL",
            "seedance_2_5",
        ).strip()
    else:
        model = os.getenv(
            "HF_VIDEO_MODEL",
            "Wan-AI/Wan2.1-T2V-1.3B",
        ).strip()


    if not gateway:

        raise RuntimeError(
            "MOTION_VIDEO_GATEWAY is missing."
        )


    if not provider:

        raise RuntimeError(
            "HF_VIDEO_PROVIDER is missing."
        )


    if not model:

        raise RuntimeError(
            "HF_VIDEO_MODEL is missing."
        )


    return MotionVideoRuntimeConfig(

        gateway=gateway,

        provider=provider,

        model=model,

    )
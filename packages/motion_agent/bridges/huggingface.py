"""
Hugging Face Inference Providers Bridge

RESPONSIBILITY:

Generic VideoProviderRequest
        ↓
Hugging Face InferenceClient
        ↓
text_to_video()
        ↓
video bytes

IMPORTANT:

No Motion Agent workflow logic here.

This file alone knows about:

    huggingface_hub
    InferenceClient
    HF_TOKEN
"""

from __future__ import annotations

import os

from huggingface_hub import (
    InferenceClient,
)

from packages.motion_agent.bridges.base import (
    VideoProviderBridge,
    VideoProviderRequest,
    VideoProviderResponse,
)


# ============================================================
# HUGGING FACE BRIDGE
# ============================================================

class HuggingFaceVideoBridge(
    VideoProviderBridge,
):

    provider_id = "huggingface"


    def __init__(
        self,
        *,
        provider: str = "auto",
        api_token: str | None = None,
    ):

        self.provider = provider


        self.api_token = (

            api_token

            or os.getenv(
                "HF_TOKEN"
            )

        )


        if not self.api_token:

            raise RuntimeError(
                "HF_TOKEN is missing."
            )


        # ====================================================
        # HUGGING FACE CLIENT
        # ====================================================
        #
        # provider="auto":
        #
        # Hugging Face can route the model request through
        # an available supported inference provider.
        #
        # Motion Agent does not need to know whether the
        # underlying inference ultimately runs on Fal,
        # Replicate, or another supported provider.
        # ====================================================

        self.client = InferenceClient(

            provider=self.provider,

            api_key=self.api_token,

        )


    # ========================================================
    # GENERATE
    # ========================================================

    def generate(
        self,
        request: VideoProviderRequest,
    ) -> VideoProviderResponse:

        print(
            "[MOTION BRIDGE] "
            "Calling Hugging Face Inference Providers"
        )

        print(
            "[MOTION BRIDGE] "
            f"Provider routing = {self.provider}"
        )

        print(
            "[MOTION BRIDGE] "
            f"Model = {request.model}"
        )


        # ====================================================
        # REMOTE VIDEO INFERENCE
        # ====================================================
        #
        # No model is downloaded locally.
        # No CUDA/GPU execution occurs locally.
        # ====================================================

        video_bytes = (
            self.client.text_to_video(

                request.prompt,

                model=request.model,

            )
        )


        if not video_bytes:

            raise RuntimeError(
                "Hugging Face returned empty video output."
            )


        if not isinstance(
            video_bytes,
            bytes,
        ):

            raise RuntimeError(
                "Hugging Face returned an unexpected "
                "video response type: "
                f"{type(video_bytes).__name__}"
            )


        return VideoProviderResponse(

            success=True,

            provider=self.provider_id,

            model=request.model,

            video_bytes=video_bytes,

        )
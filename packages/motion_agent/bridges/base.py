"""
Generic Video Provider Bridge Contract

Architecture:

CloudVideoTool
      ↓
VideoProviderBridge
      ↓
HuggingFaceVideoBridge

Future:

CloudVideoTool
      ↓
VideoProviderBridge
      ├── HuggingFaceVideoBridge
      ├── FalDirectBridge
      ├── ReplicateDirectBridge
      └── PremiumVideoBridge

No provider-specific dependency belongs above this layer.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from dataclasses import dataclass


# ============================================================
# GENERIC PROVIDER REQUEST
# ============================================================

@dataclass(frozen=True)
class VideoProviderRequest:
    """
    Generic cloud-video generation request.

    No Hugging Face / Fal / Replicate-specific fields.
    """

    prompt: str

    model: str


# ============================================================
# GENERIC PROVIDER RESPONSE
# ============================================================

@dataclass
class VideoProviderResponse:
    """
    Provider-neutral video response.

    video_bytes stays inside runtime only.
    It is NOT returned through Manager JSON.
    """

    success: bool

    provider: str

    model: str

    video_bytes: bytes


# ============================================================
# PROVIDER INTERFACE
# ============================================================

class VideoProviderBridge(ABC):

    provider_id: str


    @abstractmethod
    def generate(
        self,
        request: VideoProviderRequest,
    ) -> VideoProviderResponse:

        raise NotImplementedError
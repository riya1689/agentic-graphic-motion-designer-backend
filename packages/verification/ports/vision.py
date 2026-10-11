"""Provider-neutral vision inspection port."""

from __future__ import annotations

from typing import Protocol

from packages.verification.domain.visual import VisualCritiqueRequest, VisualInspectionResult


class VisionInspectionPort(Protocol):
    def inspect(self, request: VisualCritiqueRequest) -> VisualInspectionResult:
        ...

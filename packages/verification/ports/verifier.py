"""Port for deterministic verification strategies."""

from __future__ import annotations

from typing import Protocol

from packages.verification.domain.contracts import VerificationRequest, VerificationResult


class VerificationPort(Protocol):
    def verify(self, request: VerificationRequest) -> VerificationResult:
        ...

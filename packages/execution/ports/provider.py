"""Provider-neutral execution port implemented by provider adapters."""

from __future__ import annotations

from typing import Protocol

from packages.execution.domain.contracts import (
    ProviderExecutionRequest,
    ProviderExecutionResponse,
)


class ProviderExecutionPort(Protocol):
    provider_id: str

    def execute(
        self,
        request: ProviderExecutionRequest,
    ) -> ProviderExecutionResponse:
        ...

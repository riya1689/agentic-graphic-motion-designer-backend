"""Provider adapter registry used only at the application composition edge."""

from __future__ import annotations

from typing import Mapping

from packages.execution.domain.contracts import ProviderExecutionRequest, ProviderExecutionResponse
from packages.execution.domain.errors import ExecutionAdapterError
from packages.execution.ports.provider import ProviderExecutionPort


class ProviderExecutionRegistry:
    """Route provider-neutral requests to registered provider adapters."""

    def __init__(self, providers: Mapping[str, ProviderExecutionPort] | None = None) -> None:
        self._providers = {str(key).strip().lower(): value for key, value in (providers or {}).items()}

    def register(self, provider_id: str, adapter: ProviderExecutionPort) -> None:
        self._providers[provider_id.strip().lower()] = adapter

    def execute(self, request: ProviderExecutionRequest) -> ProviderExecutionResponse:
        provider_id = str(request.metadata.get("provider_id") or "").strip().lower()
        adapter = self._providers.get(provider_id)
        if adapter is None:
            raise ExecutionAdapterError(
                "PROVIDER_UNAVAILABLE",
                f"No execution adapter is registered for provider '{provider_id or 'unknown'}'.",
            )
        return adapter.execute(request)

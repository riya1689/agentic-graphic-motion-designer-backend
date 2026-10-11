"""Understanding service that converts interpreter output to the contract."""

from __future__ import annotations

from typing import Any

from packages.request_contract.domain.schema import NormalizedRequest

from .ports import UnderstandingPort


class RequestUnderstandingService:
    """Orchestrates interpretation and contract construction, not workflow routing."""

    def __init__(self, interpreter: UnderstandingPort) -> None:
        self._interpreter = interpreter

    def understand(
        self,
        raw_input: str,
        *,
        request_id: str,
        selected_model: str | None = None,
        **context: Any,
    ) -> NormalizedRequest:
        interpreted = self._interpreter.interpret(raw_input, **context)
        payload = dict(interpreted)
        payload.setdefault("context_prompt", raw_input)
        payload["request_id"] = request_id
        if selected_model is not None:
            payload["selected_model"] = selected_model
        return NormalizedRequest.model_validate(payload)

"""Ports for the understanding operation."""

from __future__ import annotations

from typing import Any, Dict, Protocol


class UnderstandingPort(Protocol):
    """Replaceable interpretation boundary; implementations may use any LLM."""

    def interpret(self, raw_input: str, **context: Any) -> Dict[str, Any]:
        ...

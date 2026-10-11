"""Controlled errors crossing the provider adapter boundary."""

from __future__ import annotations


class ExecutionAdapterError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message

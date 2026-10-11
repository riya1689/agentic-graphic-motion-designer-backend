"""Bounded deterministic repair/re-execution loop."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Protocol

from packages.execution.domain.contracts import ExecutionRequest, ExecutionResult
from packages.verification.domain.contracts import (
    RepairRequest,
    RepairResult,
    RepairStatus,
    VerificationIssue,
    VerificationRequest,
    VerificationResult,
    VerificationStatus,
)


class ExecutionPort(Protocol):
    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        ...


class RepairStrategy(Protocol):
    def prepare(self, request: RepairRequest) -> ExecutionRequest | None:
        ...


class DeterministicRetryStrategy:
    """Retry the same routed model; never downgrades hard capabilities."""

    non_retriable = {
        "provider_execution_failed",
        "provider_unavailable",
        "provider_timeout",
        "malformed_provider_response",
        "media_type_mismatch",
        "editable_capability_mismatch",
        "native_editable_capability_mismatch",
        "native_editable_not_confirmed",
    }

    def prepare(self, request: RepairRequest) -> ExecutionRequest | None:
        if any(issue.code in self.non_retriable for issue in request.verification_result.issues):
            return None
        metadata = dict(request.execution_request.metadata)
        metadata.update(
            {
                "repair_attempt": request.repair_attempt,
                "repair_issue_codes": [issue.code for issue in request.verification_result.issues],
                "repair_instructions": "; ".join(
                    issue.message for issue in request.verification_result.issues
                ),
            }
        )
        return replace(request.execution_request, metadata=metadata)


class BoundedRepairLoop:
    def __init__(
        self,
        executor: ExecutionPort,
        verifier,
        *,
        max_repair_attempts: int = 2,
        strategy: RepairStrategy | None = None,
    ) -> None:
        if max_repair_attempts < 0:
            raise ValueError("max_repair_attempts must be non-negative")
        self._executor = executor
        self._verifier = verifier
        self._max_repair_attempts = max_repair_attempts
        self._strategy = strategy or DeterministicRetryStrategy()

    def run(self, request: ExecutionRequest) -> RepairResult:
        current_request = request
        repair_attempts = 0
        while True:
            execution = self._executor.execute(current_request)
            verification = self._verifier.verify(
                VerificationRequest(request.request_id, current_request, execution)
            )
            if verification.status == VerificationStatus.PASSED:
                return RepairResult(
                    request_id=request.request_id,
                    status=RepairStatus.SUCCESS,
                    execution_result=execution,
                    verification_result=verification,
                    repair_attempts=repair_attempts,
                )
            if repair_attempts >= self._max_repair_attempts:
                return self._failed(
                    request,
                    execution,
                    verification,
                    repair_attempts,
                    "REPAIR_ATTEMPTS_EXHAUSTED",
                )
            repair_attempts += 1
            repair_request = RepairRequest(
                request_id=request.request_id,
                execution_request=current_request,
                verification_result=verification,
                repair_attempt=repair_attempts,
                max_repair_attempts=self._max_repair_attempts,
            )
            next_request = self._strategy.prepare(repair_request)
            if next_request is None:
                return self._failed(
                    request,
                    execution,
                    verification,
                    repair_attempts - 1,
                    "REPAIR_NOT_APPLICABLE",
                )
            if next_request.selected_model.model_id != request.selected_model.model_id:
                return self._failed(
                    request,
                    execution,
                    verification,
                    repair_attempts - 1,
                    "MODEL_SWITCH_FORBIDDEN",
                )
            current_request = next_request

    @staticmethod
    def _failed(request, execution, verification, attempts, code):
        detail = "; ".join(
            f"{issue.code}: {issue.message}"
            for issue in verification.issues
        )
        return RepairResult(
            request_id=request.request_id,
            status=RepairStatus.FAILED,
            execution_result=execution,
            verification_result=verification,
            repair_attempts=attempts,
            error=VerificationIssue(
                code,
                "Bounded repair did not produce a verified result."
                + (f" {detail}" if detail else ""),
            ),
        )

"""Provider-neutral deterministic verification and repair contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from packages.execution.domain.contracts import ExecutionRequest, ExecutionResult


class VerificationStatus(str, Enum):
    PASSED = "passed"
    FAILED = "failed"
    INCONCLUSIVE = "inconclusive"


class RepairStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"


@dataclass(frozen=True)
class VerificationIssue:
    code: str
    message: str


@dataclass(frozen=True)
class VerificationRequest:
    request_id: str
    execution_request: ExecutionRequest
    execution_result: ExecutionResult


@dataclass(frozen=True)
class VerificationResult:
    request_id: str
    status: VerificationStatus
    passed: bool
    issues: List[VerificationIssue] = field(default_factory=list)
    checked_requirements: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RepairRequest:
    request_id: str
    execution_request: ExecutionRequest
    verification_result: VerificationResult
    repair_attempt: int
    max_repair_attempts: int


@dataclass(frozen=True)
class RepairResult:
    request_id: str
    status: RepairStatus
    execution_result: ExecutionResult
    verification_result: VerificationResult
    repair_attempts: int
    error: Optional[VerificationIssue] = None

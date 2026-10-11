"""Provider-neutral conditional planner contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from packages.request_contract.domain.schema import NormalizedRequest


@dataclass(frozen=True)
class ComplexityDecision:
    required: bool
    reason: str
    signals: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class PlanStep:
    step_id: str
    operation: str
    depends_on: List[str] = field(default_factory=list)
    expected_outputs: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ExecutionPlan:
    request_id: str
    steps: List[PlanStep]
    dependencies: Dict[str, List[str]] = field(default_factory=dict)
    expected_outputs: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PlanningOutcome:
    request_id: str
    decision: ComplexityDecision
    plan: Optional[ExecutionPlan] = None
    success: bool = True
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    request: Optional[NormalizedRequest] = None

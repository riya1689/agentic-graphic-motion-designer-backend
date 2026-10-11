"""Provider-neutral planner port."""

from __future__ import annotations

from typing import Protocol

from packages.request_contract.domain.schema import NormalizedRequest
from packages.planner_integration.domain.contracts import ExecutionPlan


class PlannerPort(Protocol):
    def plan(self, request: NormalizedRequest) -> ExecutionPlan:
        ...

"""Bounded logical validation before a plan reaches a renderer."""

from __future__ import annotations

from packages.graphic_agent.compiler.prompt_compiler import validate_graphic_plan
from packages.request_contract.domain.schema import NormalizedRequest

from ..domain.contracts import ExecutionPlan


class LogicalRepairingPlanner:
    """Re-run the Planner when its structured graphic plan is incomplete."""

    def __init__(self, planner, *, max_attempts: int = 2) -> None:
        self._planner = planner
        self._max_attempts = max_attempts

    def plan(self, request: NormalizedRequest) -> ExecutionPlan:
        current = request
        last_errors: list[str] = []
        for attempt in range(self._max_attempts + 1):
            plan = self._planner.plan(current)
            probe_plan = type("PlanProbe", (), {"metadata": plan.metadata})()
            probe_request = type(
                "RequestProbe",
                (),
                {"metadata": {"execution_plan": probe_plan}, "normalized_request": current},
            )()
            errors = validate_graphic_plan(probe_request)
            if not errors:
                return plan
            last_errors = errors
            if attempt >= self._max_attempts:
                break
            requirements = dict(current.additional_requirements)
            requirements["logical_repair_attempt"] = attempt + 1
            requirements["logical_repair_errors"] = errors
            current = current.model_copy(update={"additional_requirements": requirements})
        raise RuntimeError("Logical Planner repair failed: " + "; ".join(last_errors))

"""Conditional planner orchestration without execution or model selection."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import ValidationError

from packages.request_contract.domain.schema import NormalizedRequest

from ..domain.contracts import ComplexityDecision, ExecutionPlan, PlanningOutcome
from ..domain.decision import ComplexityDecider
from ..ports.planner import PlannerPort


class ConditionalPlannerService:
    """Bypass Planner for simple requests and invoke it only when required."""

    def __init__(
        self,
        planner: PlannerPort,
        *,
        decider: Optional[ComplexityDecider] = None,
    ) -> None:
        self._planner = planner
        self._decider = decider or ComplexityDecider()

    def prepare(self, request: NormalizedRequest | dict[str, Any], *, force: bool = False) -> PlanningOutcome:
        try:
            normalized = (
                request
                if isinstance(request, NormalizedRequest)
                else NormalizedRequest.model_validate(request)
            )
        except ValidationError as exc:
            request_id = request.get("request_id", "unknown") if isinstance(request, dict) else "unknown"
            decision = ComplexityDecision(False, "request validation failed before planning", [])
            return PlanningOutcome(
                request_id=request_id,
                decision=decision,
                success=False,
                error_code="INVALID_REQUEST",
                error_message=str(exc),
            )

        decision = (
            ComplexityDecision(True, "full planning explicitly requested by the execution mode", ["forced_planning"])
            if force
            else self._decider.decide(normalized)
        )
        if not decision.required:
            return PlanningOutcome(
                request_id=normalized.request_id,
                decision=decision,
                request=normalized,
            )

        try:
            plan = self._planner.plan(normalized)
        except Exception as exc:
            return PlanningOutcome(
                request_id=normalized.request_id,
                decision=decision,
                request=normalized,
                success=False,
                error_code="PLANNER_FAILED",
                error_message=str(exc),
            )

        if not isinstance(plan, ExecutionPlan):
            return PlanningOutcome(
                request_id=normalized.request_id,
                decision=decision,
                request=normalized,
                success=False,
                error_code="INVALID_PLAN",
                error_message="Planner returned a non-provider-neutral execution plan.",
            )
        return PlanningOutcome(
            request_id=normalized.request_id,
            decision=decision,
            request=normalized,
            plan=plan,
        )

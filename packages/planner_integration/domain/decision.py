"""Deterministic complexity decision boundary."""

from __future__ import annotations

from typing import Any, Iterable, List

from packages.request_contract.domain.schema import NormalizedRequest

from .contracts import ComplexityDecision


class ComplexityDecider:
    """Identify explicit multi-step signals without an LLM or model choice."""

    def decide(self, request: NormalizedRequest) -> ComplexityDecision:
        signals: List[str] = []
        requirements = request.additional_requirements

        requested_outputs = self._as_items(
            requirements.get("requested_outputs", requirements.get("outputs"))
        )
        if len(requested_outputs) > 1:
            signals.append("multiple_requested_outputs")

        explicit_steps = self._as_items(
            requirements.get("workflow_steps", requirements.get("steps"))
        )
        if len(explicit_steps) > 1 or requirements.get("multi_step") is True:
            signals.append("explicit_multi_step_workflow")

        transformation_chain = self._as_items(
            requirements.get("transformation_chain", requirements.get("transformations"))
        )
        if len(transformation_chain) > 1:
            signals.append("transformation_chain")

        dependencies = self._as_items(
            requirements.get("dependencies", requirements.get("dependent_operations"))
        )
        if dependencies:
            signals.append("dependent_operations")

        if requirements.get("requires_planning") is True:
            signals.append("explicit_planning_requirement")

        if signals:
            return ComplexityDecision(
                required=True,
                reason="deterministic multi-step or dependency signals require a plan",
                signals=signals,
            )
        return ComplexityDecision(
            required=False,
            reason="request contains no deterministic multi-step or dependency signal",
            signals=[],
        )

    @staticmethod
    def _as_items(value: Any) -> List[Any]:
        if value is None or value is False:
            return []
        if isinstance(value, str):
            return [value] if value.strip() else []
        if isinstance(value, (list, tuple, set)):
            return list(value)
        return [value]

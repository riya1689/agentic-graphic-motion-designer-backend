"""Application-level design reasoning orchestration."""

from __future__ import annotations

from typing import Any, Mapping

from packages.request_contract.domain.schema import NormalizedRequest

from ..domain.specification import (
    DesignBrief,
    DesignSpecification,
    design_specification_from_request,
)
from ..ports.reasoning import DesignReasoningPort


class DesignReasoningEngine:
    """Turn a brief into a complete design specification.

    The default reasoner is deterministic and provider-neutral.  A future LLM
    adapter can implement DesignReasoningPort and be injected at the
    application boundary without changing domain models.
    """

    def __init__(self, reasoner: DesignReasoningPort | None = None) -> None:
        self._reasoner = reasoner

    def reason(self, request: NormalizedRequest) -> DesignSpecification:
        brief = DesignBrief.model_validate(
            design_specification_from_request(request).brief
        )
        if self._reasoner is None:
            specification = design_specification_from_request(request)
        else:
            specification = self._reasoner.reason(brief)
        self.validate(specification, request)
        return specification

    def complete(
        self,
        request: NormalizedRequest,
        candidate: DesignSpecification | Mapping[str, Any] | None,
    ) -> DesignSpecification:
        baseline = self.reason(request)
        if candidate is None:
            return baseline
        candidate_model = (
            candidate
            if isinstance(candidate, DesignSpecification)
            else DesignSpecification.model_validate(candidate)
        )
        merged = _merge_models(baseline.model_dump(mode="python"), candidate_model.model_dump(mode="python"))
        specification = DesignSpecification.model_validate(merged)
        self.validate(specification, request)
        return specification

    @staticmethod
    def validate(specification: DesignSpecification, request: NormalizedRequest) -> None:
        errors: list[str] = []
        if specification.design_type != (request.design_type or "custom design"):
            errors.append("design type is not preserved")
        content = {item.value for item in specification.content_hierarchy}
        for value in request.text:
            if value not in content:
                errors.append(f"required text is missing: {value}")
        for value in request.colors:
            if value not in specification.color_system.required_colors:
                errors.append(f"required color is missing: {value}")
        if request.output.editable_required and not specification.brief.editable_requirement:
            errors.append("editable output requirement is not preserved")
        if errors:
            raise ValueError("Design reasoning validation failed: " + "; ".join(errors))


def _merge_models(base: Any, candidate: Any) -> Any:
    """Prefer Planner decisions while filling omitted fields from the baseline."""
    if isinstance(base, dict) and isinstance(candidate, dict):
        result = dict(base)
        for key, value in candidate.items():
            if value is None or value == {} or value == []:
                continue
            result[key] = _merge_models(result.get(key), value)
        return result
    return candidate if candidate not in (None, "", [], {}) else base

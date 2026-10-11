"""Application boundary between design intent and execution planning."""

from __future__ import annotations

from typing import Any, Mapping

from packages.request_contract.domain.schema import NormalizedRequest

from ..domain.specification import DesignSpecification, design_specification_from_request


def build_design_specification(request: NormalizedRequest) -> DesignSpecification:
    """Create a deterministic baseline when an LLM specification is absent."""
    return design_specification_from_request(request)


def validate_design_specification(
    specification: DesignSpecification,
    request: NormalizedRequest,
) -> list[str]:
    """Validate logical requirement preservation, not rendered appearance."""
    errors: list[str] = []
    if specification.design_type != (request.design_type or "custom design"):
        errors.append("design type is not preserved")
    values = {item.value for item in specification.content_hierarchy}
    for value in request.text:
        if value not in values:
            errors.append(f"required text is missing: {value}")
    for color in request.colors:
        if color not in specification.color_system.required_colors:
            errors.append(f"required color is missing: {color}")
    if request.output.editable_required and not specification.brief.editable_requirement:
        errors.append("editable output requirement is not preserved")
    return errors


def attach_design_specification(
    metadata: Mapping[str, Any],
    specification: DesignSpecification,
) -> dict[str, Any]:
    """Add design intent beside, never inside, the renderer execution spec."""
    result = dict(metadata)
    result["design_specification"] = specification.model_dump(mode="json")
    return result

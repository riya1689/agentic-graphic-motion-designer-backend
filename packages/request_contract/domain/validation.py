"""Deterministic validation for the normalized request."""

from __future__ import annotations

from typing import List

from pydantic import ValidationError

from .schema import CreativeType, NormalizedRequest


IMAGE_FORMATS = {"png", "jpg", "jpeg", "webp", "svg", "psd", "ai"}
MOTION_FORMATS = {"mp4", "mov", "webm", "mkv", "editable_project"}
EDITABLE_FORMATS = {"svg", "psd", "ai", "editable_project"}


class RequestValidationResult:
    """Serializable validation result returned by the deterministic validator."""

    def __init__(self, passed: bool, issues: List[str]) -> None:
        self.passed = passed
        self.issues = issues

    def model_dump(self) -> dict:
        return {"passed": self.passed, "issues": list(self.issues)}


def validate_normalized_request(
    request: NormalizedRequest | dict,
) -> RequestValidationResult:
    """Validate contract shape and domain-level combinations only.

    This does not check whether a model exists or is available. That belongs to
    the later Model Catalog/Router phase.
    """

    try:
        normalized = (
            request
            if isinstance(request, NormalizedRequest)
            else NormalizedRequest.model_validate(request)
        )
    except ValidationError as exc:
        return RequestValidationResult(
            passed=False,
            issues=[error["msg"] for error in exc.errors()],
        )

    issues: List[str] = []
    output = normalized.output

    if output.media_type != normalized.creative_type:
        issues.append("output media_type must match creative_type")

    allowed_formats = (
        IMAGE_FORMATS
        if normalized.creative_type == CreativeType.IMAGE
        else MOTION_FORMATS
    )
    if output.format not in allowed_formats:
        issues.append(
            f"format '{output.format}' is invalid for {normalized.creative_type.value}"
        )

    if output.editable_required and output.format not in EDITABLE_FORMATS:
        issues.append(
            f"editable output is not supported by format '{output.format}'"
        )

    if output.native_editable_required and not output.editable_required:
        issues.append(
            "native_editable_required requires editable_required"
        )

    return RequestValidationResult(
        passed=not issues,
        issues=issues,
    )

"""Phase 3 normalized request contract boundary."""

from .domain.schema import (
    AssetReference,
    CreativeType,
    NormalizedRequest,
    OutputRequirement,
    SizeSpec,
)
from .domain.validation import (
    RequestValidationResult,
    validate_normalized_request,
)

__all__ = [
    "AssetReference",
    "CreativeType",
    "NormalizedRequest",
    "OutputRequirement",
    "RequestValidationResult",
    "SizeSpec",
    "validate_normalized_request",
]

"""Single authoritative policy for standard/editable/native-editable output."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, TYPE_CHECKING

from packages.model_catalog.domain.model import CatalogModel
from packages.request_contract.domain.schema import NormalizedRequest

if TYPE_CHECKING:
    from packages.execution.domain.contracts import OutputAsset


class CapabilityLevel(str, Enum):
    STANDARD = "standard"
    EDITABLE = "editable"
    NATIVE_EDITABLE = "native_editable"


@dataclass(frozen=True)
class CapabilityEvidence:
    """Normalized evidence supplied by an execution result."""

    format: str
    editable: bool = False
    native_editable: bool = False
    metadata: Dict[str, Any] | None = None


@dataclass(frozen=True)
class CapabilityAssessment:
    allowed: bool
    code: str | None = None
    message: str | None = None
    inconclusive: bool = False


class EditableCapabilityPolicy:
    """Derive requirements and assess model/result capability claims."""

    @staticmethod
    def required_level(request: NormalizedRequest) -> CapabilityLevel:
        if request.output.native_editable_required:
            return CapabilityLevel.NATIVE_EDITABLE
        if request.output.editable_required:
            return CapabilityLevel.EDITABLE
        return CapabilityLevel.STANDARD

    @classmethod
    def model_assessment(
        cls,
        request: NormalizedRequest,
        model: CatalogModel,
    ) -> CapabilityAssessment:
        required_format = cls.normalize_format(request.output.format)
        supported_formats = {cls.normalize_format(value) for value in model.supported_output_formats}
        if required_format not in supported_formats:
            return cls._reject(
                "OUTPUT_FORMAT_UNSUPPORTED",
                f"Model does not support requested format '{required_format}'.",
            )

        level = cls.required_level(request)
        if level == CapabilityLevel.EDITABLE and not (
            model.editable_output_support or model.native_editable_support
        ):
            return cls._reject(
                "EDITABLE_CAPABILITY_UNSUPPORTED",
                "Model does not declare editable output support.",
            )
        if level == CapabilityLevel.NATIVE_EDITABLE and not model.native_editable_support:
            return cls._reject(
                "NATIVE_EDITABLE_CAPABILITY_UNSUPPORTED",
                "Model does not declare native editable output support.",
            )

        native_formats = model.capability_metadata.get("native_editable_formats")
        if level == CapabilityLevel.NATIVE_EDITABLE and native_formats is not None:
            allowed_formats = {cls.normalize_format(value) for value in native_formats}
            if required_format not in allowed_formats:
                return cls._reject(
                    "NATIVE_EDITABLE_FORMAT_UNSUPPORTED",
                    f"Model does not declare native editable support for '{required_format}'.",
                )
        return CapabilityAssessment(allowed=True)

    @classmethod
    def result_assessment(
        cls,
        request: NormalizedRequest,
        asset: OutputAsset,
    ) -> CapabilityAssessment:
        expected = cls.normalize_format(request.output.format)
        actual = cls.normalize_format(asset.format)
        if actual != expected:
            return cls._reject(
                "FORMAT_CAPABILITY_MISMATCH",
                f"Result format '{actual}' does not satisfy requested '{expected}'.",
            )

        level = cls.required_level(request)
        if level == CapabilityLevel.STANDARD:
            return CapabilityAssessment(allowed=True)
        if level == CapabilityLevel.EDITABLE and not asset.editable:
            return cls._reject(
                "EDITABLE_CAPABILITY_MISMATCH",
                "Result does not provide positive editable evidence.",
            )
        if level == CapabilityLevel.NATIVE_EDITABLE:
            if asset.native_editable:
                return CapabilityAssessment(allowed=True)
            evidence_state = (asset.metadata or {}).get("native_editable_evidence")
            if evidence_state == "absent":
                return cls._reject(
                    "NATIVE_EDITABLE_CAPABILITY_MISMATCH",
                    "Result explicitly lacks native editable evidence.",
                )
            return CapabilityAssessment(
                allowed=False,
                code="NATIVE_EDITABLE_CAPABILITY_INCONCLUSIVE",
                message="Native editable evidence was not established.",
                inconclusive=True,
            )
        return CapabilityAssessment(allowed=False, code="UNKNOWN_CAPABILITY", message="Unknown capability level.")

    @staticmethod
    def normalize_format(value: str) -> str:
        normalized = str(value).strip().lower().lstrip(".")
        return {"jpeg": "jpg", "quicktime": "mov"}.get(normalized, normalized)

    @staticmethod
    def _reject(code: str, message: str) -> CapabilityAssessment:
        return CapabilityAssessment(allowed=False, code=code, message=message)

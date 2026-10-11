"""Deterministic capability-based model routing."""

from __future__ import annotations

import os
import re
from typing import Iterable, List, Optional, Sequence

from packages.model_catalog.domain.model import CatalogModel, MediaType, ModelAvailability
from packages.model_catalog.service.catalog import ModelCatalogService
from packages.request_contract.domain.schema import NormalizedRequest
from packages.capability_policy import EditableCapabilityPolicy

from ..domain.contracts import RoutingError, RoutingResult, RoutingSource


class ModelRouter:
    """Choose one catalog model without invoking providers or generation."""

    def __init__(
        self,
        catalog_service: ModelCatalogService,
        *,
        default_model_id: Optional[str] = None,
        capability_policy: Optional[EditableCapabilityPolicy] = None,
    ) -> None:
        self._catalog_service = catalog_service
        self._default_model_id = default_model_id or os.getenv(
            "MODEL_ROUTER_DEFAULT_MODEL"
        )
        self._capability_policy = capability_policy or EditableCapabilityPolicy()

    def route(self, request: NormalizedRequest) -> RoutingResult:
        """Return a deterministic result; routing failures are not exceptions."""
        if request.selected_model is not None:
            return self._route_user_selected(request)

        candidates = [
            model
            for model in self._catalog_service.list_models()
            if model.model_id != self._default_model_id
            if self._compatibility_reasons(request, model) == []
        ]
        if candidates:
            selected = self._stable_candidate(candidates)
            return RoutingResult(
                request_id=request.request_id,
                selected_model=selected,
                routing_reason="selected the deterministically ordered compatible catalog model",
                routing_source=RoutingSource.CAPABILITY_MATCH,
            )

        if self._default_model_id:
            default_model = self._catalog_service.get_model(self._default_model_id)
            if default_model is None:
                return self._failure(
                    request,
                    "SYSTEM_DEFAULT_NOT_FOUND",
                    f"System default model '{self._default_model_id}' is not present in the catalog.",
                )
            reasons = self._compatibility_reasons(request, default_model)
            if not reasons:
                return RoutingResult(
                    request_id=request.request_id,
                    selected_model=default_model,
                    routing_reason="no capability match existed; compatible system default selected",
                    routing_source=RoutingSource.SYSTEM_DEFAULT,
                )
            return self._failure(
                request,
                "SYSTEM_DEFAULT_INCOMPATIBLE",
                f"System default model '{default_model.model_id}' is incompatible: {', '.join(reasons)}.",
            )

        code = "CATALOG_EMPTY" if not self._catalog_service.list_models() else "NO_COMPATIBLE_MODEL"
        message = (
            "The model catalog is empty; no model can satisfy the request."
            if code == "CATALOG_EMPTY"
            else "No catalog model satisfies the request and no compatible system default is configured."
        )
        return self._failure(request, code, message)

    def _route_user_selected(self, request: NormalizedRequest) -> RoutingResult:
        assert request.selected_model is not None
        model = self._catalog_service.get_model(request.selected_model)
        if model is None:
            return self._failure(
                request,
                "SELECTED_MODEL_NOT_FOUND",
                f"Selected model '{request.selected_model}' is not present in the catalog.",
            )
        reasons = self._compatibility_reasons(request, model)
        if reasons:
            return self._failure(
                request,
                "SELECTED_MODEL_INCOMPATIBLE",
                f"Selected model '{model.model_id}' is incompatible: {', '.join(reasons)}.",
            )
        return RoutingResult(
            request_id=request.request_id,
            selected_model=model,
            routing_reason="explicitly selected model satisfies all hard requirements",
            routing_source=RoutingSource.USER_SELECTED,
        )

    @staticmethod
    def _stable_candidate(candidates: Sequence[CatalogModel]) -> CatalogModel:
        def sort_key(model: CatalogModel) -> tuple[int, int, int, str, str]:
            availability_rank = 0 if model.availability == ModelAvailability.AVAILABLE else 1
            auto_rank = 0 if model.model_id == "image_auto" else 1
            completeness = sum(
                bool(values)
                for values in (
                    model.supported_operations,
                    model.supported_input_types,
                    model.supported_output_formats,
                    model.capabilities,
                )
            )
            return (availability_rank, auto_rank, -completeness, model.provider.lower(), model.model_id.lower())

        return sorted(candidates, key=sort_key)[0]

    def _compatibility_reasons(
        self,
        request: NormalizedRequest,
        model: CatalogModel,
    ) -> List[str]:
        reasons: List[str] = []
        expected_media = (
            MediaType.IMAGE
            if request.output.media_type.value == "image"
            else MediaType.VIDEO
        )
        if model.media_type != expected_media:
            reasons.append(f"media type must be {expected_media.value}")
        if model.availability == ModelAvailability.UNAVAILABLE:
            reasons.append("model is unavailable")

        capability_assessment = self._capability_policy.model_assessment(request, model)
        if not capability_assessment.allowed:
            reasons.append(capability_assessment.message or "required editable capability is unsupported")

        required_operation = (
            "text_to_image" if expected_media == MediaType.IMAGE else "text_to_video"
        )
        live_catalog_record = bool(model.capability_metadata.get("live_provider_catalog"))
        if not live_catalog_record and not self._has_token(model.supported_operations, required_operation) and not self._has_token(
            model.capabilities, required_operation
        ):
            reasons.append(f"missing capability {required_operation}")

        output_format = self._token(request.output.format)
        if not live_catalog_record and not self._has_token(model.supported_output_formats, output_format):
            reasons.append(f"output format {output_format} is not supported")

        required_inputs = self._requested_input_types(request)
        for input_type in required_inputs:
            if not self._has_token(model.supported_input_types, input_type):
                reasons.append(f"input type {input_type} is not supported")

        if request.output.editable_required and not (
            model.editable_output_support or model.native_editable_support
        ):
            reasons.append("editable output is not supported")
        if request.output.native_editable_required and not model.native_editable_support:
            reasons.append("native editable output is not supported")
        return reasons

    @staticmethod
    def _requested_input_types(request: NormalizedRequest) -> Iterable[str]:
        value = request.additional_requirements.get("input_types")
        if value is None:
            value = request.additional_requirements.get("input_type")
        if value is None:
            return []
        if isinstance(value, str):
            return [value]
        if isinstance(value, (list, tuple, set)):
            return value
        return [str(value)]

    @staticmethod
    def _token(value: str) -> str:
        return re.sub(r"[^a-z0-9]+", "_", str(value).strip().lower()).strip("_")

    @classmethod
    def _has_token(cls, values: Iterable[str], expected: str) -> bool:
        target = cls._token(expected)
        return any(cls._token(value) == target for value in values)

    @staticmethod
    def _failure(
        request: NormalizedRequest,
        code: str,
        message: str,
    ) -> RoutingResult:
        return RoutingResult(
            request_id=request.request_id,
            error=RoutingError(code=code, message=message),
        )

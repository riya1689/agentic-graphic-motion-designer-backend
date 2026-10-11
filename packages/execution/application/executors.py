"""Image and motion executors that depend only on the provider port."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

from packages.execution.domain.contracts import (
    ExecutionError,
    ExecutionRequest,
    ExecutionResult,
    ExecutionStatus,
    ProviderExecutionRequest,
    ProviderExecutionResponse,
)
from packages.execution.domain.errors import ExecutionAdapterError
from packages.execution.ports.provider import ProviderExecutionPort
from packages.capability_policy import EditableCapabilityPolicy
from packages.model_catalog.domain.model import MediaType
from packages.graphic_agent.compiler.prompt_compiler import compile_graphic_prompt


class _BaseExecutor(ABC):
    expected_media_type: MediaType

    def __init__(self, provider: ProviderExecutionPort) -> None:
        self._provider = provider

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        validation_error = self._validate_request(request)
        if validation_error is not None:
            return self._failure(request, validation_error.code, validation_error.message)

        provider_request = ProviderExecutionRequest(
            request_id=request.request_id,
            model_id=request.selected_model.model_id,
            media_type=request.selected_model.media_type,
            prompt=(
                request.metadata.get("generation_prompt")
                or (
                    compile_graphic_prompt(request)
                    if self.expected_media_type == MediaType.IMAGE
                    and (
                        request.metadata.get("execution_plan") is not None
                        or request.metadata.get("prompt_compilation_required") is True
                    )
                    else request.normalized_request.context_prompt
                )
            ),
            output_format=request.normalized_request.output.format,
            input_assets=list(request.normalized_request.input_assets),
            metadata={
                **dict(request.metadata),
                "provider_id": request.selected_model.provider,
            },
        )
        try:
            response = self._provider.execute(provider_request)
            self._validate_provider_response(request, response)
            return ExecutionResult(
                request_id=request.request_id,
                status=ExecutionStatus.SUCCESS,
                provider=response.provider,
                model_id=response.model_id,
                output_assets=list(response.output_assets),
                metadata=dict(response.metadata),
            )
        except ExecutionAdapterError as exc:
            return self._failure(request, exc.code, exc.message)
        except Exception as exc:
            return self._failure(request, "PROVIDER_EXECUTION_FAILED", str(exc))

    def _validate_request(self, request: ExecutionRequest) -> ExecutionError | None:
        if request.selected_model.media_type != self.expected_media_type:
            return ExecutionError(
                "MODEL_MEDIA_MISMATCH",
                f"Executor requires {self.expected_media_type.value} model.",
            )
        expected_request_media = "image" if self.expected_media_type == MediaType.IMAGE else "motion"
        if request.normalized_request.output.media_type.value != expected_request_media:
            return ExecutionError(
                "REQUEST_MEDIA_MISMATCH",
                f"Executor requires {expected_request_media} request.",
            )
        return None

    @staticmethod
    def _validate_provider_response(
        request: ExecutionRequest,
        response: ProviderExecutionResponse,
    ) -> None:
        if not isinstance(response, ProviderExecutionResponse):
            raise ExecutionAdapterError(
                "MALFORMED_PROVIDER_RESPONSE",
                "Provider adapter returned an invalid response contract.",
            )
        if response.model_id != request.selected_model.model_id:
            raise ExecutionAdapterError(
                "MODEL_NOT_PRESERVED",
                "Provider response model does not match the routed model.",
            )
        if not response.output_assets:
            raise ExecutionAdapterError(
                "MISSING_OUTPUT",
                "Provider reported success without usable output assets.",
            )
        policy = EditableCapabilityPolicy()
        for asset in response.output_assets:
            assessment = policy.result_assessment(request.normalized_request, asset)
            if not assessment.allowed:
                code = assessment.code or "OUTPUT_CAPABILITY_MISMATCH"
                if code == "NATIVE_EDITABLE_CAPABILITY_INCONCLUSIVE":
                    code = "NATIVE_EDITABLE_NOT_CONFIRMED"
                raise ExecutionAdapterError(code, assessment.message or "Output capability requirement was not satisfied.")

    @staticmethod
    def _failure(request: ExecutionRequest, code: str, message: str) -> ExecutionResult:
        return ExecutionResult(
            request_id=request.request_id,
            status=ExecutionStatus.FAILED,
            provider=request.selected_model.provider,
            model_id=request.selected_model.model_id,
            error=ExecutionError(code=code, message=message),
        )


class GraphicExecutor(_BaseExecutor):
    expected_media_type = MediaType.IMAGE


class MotionExecutor(_BaseExecutor):
    expected_media_type = MediaType.VIDEO

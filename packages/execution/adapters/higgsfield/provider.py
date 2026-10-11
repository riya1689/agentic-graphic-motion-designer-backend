"""Higgsfield provider adapter over the existing CLI bridges."""

from __future__ import annotations

from typing import Any, Dict, Optional

from packages.execution.domain.contracts import (
    OutputAsset,
    ProviderExecutionRequest,
    ProviderExecutionResponse,
)
from packages.execution.domain.errors import ExecutionAdapterError
from packages.model_catalog.domain.model import MediaType
from packages.graphic_agent.bridges.higgsfield_cli import HiggsfieldGraphicCLI
from packages.motion_agent.bridges.higgsfield_cli import HiggsfieldMotionCLI


class HiggsfieldExecutionAdapter:
    """Translate provider-neutral execution requests to Higgsfield CLI calls."""

    provider_id = "higgsfield"

    def __init__(
        self,
        *,
        graphic_bridge: Optional[Any] = None,
        motion_bridge: Optional[Any] = None,
    ) -> None:
        self._graphic_bridge = graphic_bridge or HiggsfieldGraphicCLI()
        self._motion_bridge = motion_bridge or HiggsfieldMotionCLI()

    def execute(self, request: ProviderExecutionRequest) -> ProviderExecutionResponse:
        command = [
            "higgsfield",
            "generate",
            "create",
            request.model_id,
            "--wait",
            "--json",
            "--no-color",
        ]
        bridge = (
            self._graphic_bridge
            if request.media_type == MediaType.IMAGE
            else self._motion_bridge
        )
        try:
            provider_result = bridge.execute(command=command, stdin_text=request.prompt)
        except FileNotFoundError as exc:
            raise ExecutionAdapterError("PROVIDER_UNAVAILABLE", str(exc)) from exc
        except TimeoutError as exc:
            raise ExecutionAdapterError("PROVIDER_TIMEOUT", str(exc)) from exc
        except Exception as exc:
            raise ExecutionAdapterError("PROVIDER_EXECUTION_FAILED", str(exc)) from exc

        result_url = getattr(provider_result, "result_url", None)
        if not isinstance(result_url, str) or not result_url:
            raise ExecutionAdapterError(
                "MISSING_OUTPUT",
                "Higgsfield returned no usable output URL.",
            )

        raw_data = getattr(provider_result, "data", None)
        if isinstance(raw_data, dict) and "raw_output" in raw_data:
            raise ExecutionAdapterError(
                "MALFORMED_PROVIDER_RESPONSE",
                "Higgsfield returned non-JSON provider output.",
            )
        native_editable = self._native_editable_claim(raw_data)
        if request.model_id == "recraft_v4_1" and request.output_format.lower().lstrip(".") == "svg":
            native_editable = True
        if request.metadata.get("native_editable_required") and not native_editable:
            raise ExecutionAdapterError(
                "NATIVE_EDITABLE_NOT_CONFIRMED",
                "Higgsfield did not explicitly confirm native editable output.",
            )

        asset = OutputAsset(
            uri=result_url,
            format=request.output_format,
            editable=native_editable,
            native_editable=native_editable,
            metadata={
                "provider_verified": True,
                "remote_result": True,
                "native_editable_evidence": "provider_model_direct_svg" if native_editable else "absent",
            },
        )
        return ProviderExecutionResponse(
            provider=self.provider_id,
            model_id=request.model_id,
            output_assets=[asset],
            metadata={"provider_status": "success"},
        )

    @staticmethod
    def _native_editable_claim(data: Any) -> bool:
        if not isinstance(data, dict):
            return False
        return any(
            data.get(key) is True
            for key in (
                "native_editable",
                "nativeEditable",
                "native_editable_support",
            )
        )

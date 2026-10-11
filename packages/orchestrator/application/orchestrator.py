"""Single workflow coordinator for the provider-neutral architecture."""

from __future__ import annotations

from dataclasses import asdict, replace
import json
from typing import Any, Callable, Dict, Optional, Protocol

from packages.execution.domain.contracts import ExecutionRequest, ExecutionResult
from packages.model_router.service.router import ModelRouter
from packages.planner_integration.application.service import ConditionalPlannerService
from packages.request_contract.domain.schema import NormalizedRequest
from packages.request_contract.domain.validation import validate_normalized_request
from packages.verification.application.repair import BoundedRepairLoop
from packages.verification.domain.contracts import VerificationStatus
from packages.model_catalog.domain.model import CatalogModel, MediaType, ModelAvailability
from packages.planner_integration.domain.contracts import ComplexityDecision, PlanningOutcome
from packages.graphic_agent.system_raster import SystemRasterGraphicExecutor
from packages.design_intelligence.application.layout_compiler import LayoutCompiler
from packages.design_intelligence.domain.specification import DesignSpecification
from packages.revision.application.loop import RevisionLoop
from packages.revision.ports.planner import RevisionPlannerPort
from packages.verification.domain.visual import VisualInspectionResult
from packages.graphic_agent.image_to_vector import IMAGE_TO_VECTOR_MODEL
from packages.graphic_agent.hybrid_svg import HYBRID_SVG_MODEL

from ..domain.state import OrchestratorState, WorkflowStage


class UnderstandingService(Protocol):
    def understand(self, raw_input: str, *, request_id: str, selected_model: str | None = None, **context: Any) -> NormalizedRequest:
        ...


class Executor(Protocol):
    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        ...


class Orchestrator:
    """Coordinate workflow stages while delegating component responsibilities."""

    def __init__(
        self,
        *,
        understanding: UnderstandingService,
        router: ModelRouter,
        planner: ConditionalPlannerService,
        graphic_executor: Executor,
        motion_executor: Executor,
        verifier,
        native_svg_executor: Executor | None = None,
        system_raster_executor: Executor | None = None,
        code_svg_executor: Executor | None = None,
        image_to_vector_executor: Executor | None = None,
        hybrid_svg_executor: Executor | None = None,
        max_repair_attempts: int = 2,
        validator: Callable[[NormalizedRequest | dict], Any] = validate_normalized_request,
        revision_planner: RevisionPlannerPort | None = None,
        design_revision_enabled: bool = False,
        max_design_revisions: int = 3,
    ) -> None:
        self._understanding = understanding
        self._router = router
        self._planner = planner
        self._graphic_executor = graphic_executor
        self._motion_executor = motion_executor
        self._native_svg_executor = native_svg_executor
        self._system_raster_executor = system_raster_executor
        self._code_svg_executor = code_svg_executor
        self._image_to_vector_executor = image_to_vector_executor
        self._hybrid_svg_executor = hybrid_svg_executor
        self._verifier = verifier
        self._max_repair_attempts = max_repair_attempts
        self._validator = validator
        self._revision_planner = revision_planner
        self._design_revision_enabled = design_revision_enabled
        self._max_design_revisions = max_design_revisions

    def run(
        self,
        raw_input: str,
        *,
        request_id: str,
        selected_model: str | None = None,
        **context: Any,
    ) -> OrchestratorState:
        state = OrchestratorState(request_id=request_id, raw_input=raw_input)

        try:
            state.request = self._understanding.understand(
                raw_input,
                request_id=request_id,
                selected_model=selected_model,
                **context,
            )
            if not isinstance(state.request, NormalizedRequest):
                state.request = NormalizedRequest.model_validate(state.request)
        except Exception as exc:
            return self._fail(state, "UNDERSTANDING_FAILED", str(exc))

        state.current_stage = WorkflowStage.VALIDATING
        validation = self._validator(state.request)
        if not validation.passed:
            return self._fail(
                state,
                "VALIDATION_FAILED",
                "; ".join(validation.issues),
            )

        state.current_stage = WorkflowStage.ROUTING
        code_image_requested = (
            state.request.creative_type.value == "image"
            and state.request.selected_model == "code_image"
            and self._code_svg_executor is not None
        )
        image_to_vector_requested = (
            state.request.creative_type.value == "image"
            and state.request.selected_model == IMAGE_TO_VECTOR_MODEL
            and self._image_to_vector_executor is not None
        )
        hybrid_svg_requested = (
            state.request.creative_type.value == "image"
            and state.request.selected_model == HYBRID_SVG_MODEL
            and self._hybrid_svg_executor is not None
        )
        native_svg_requested = (
            state.request.output.format == "svg"
            and state.request.output.native_editable_required
            and self._native_svg_executor is not None
            and state.request.selected_model in {None, "", "auto", "image_auto", "all", "all_image_models"}
        )
        system_raster_requested = (
            state.request.output.format in {"png", "jpg", "webp"}
            and self._system_raster_executor is not None
            and state.request.selected_model in {None, "", "auto", "image_auto", "all", "all_image_models"}
        )
        if hybrid_svg_requested:
            state.selected_model = CatalogModel(
                model_id=HYBRID_SVG_MODEL,
                model_name="Hybrid SVG — Raster Background + Vector Design",
                provider="graphic_agent.hybrid",
                media_type=MediaType.IMAGE,
                supported_operations=["hybrid_svg", "raster_background", "vector_render"],
                supported_input_types=["text", "image"],
                supported_output_formats=["svg"],
                capabilities=["hybrid_svg", "embedded_raster_layer", "native_svg", "editable_vector"],
                editable_output_support=True,
                native_editable_support=True,
                availability=ModelAvailability.AVAILABLE,
                capability_metadata={"native_editable_formats": ["svg"]},
            )
        elif image_to_vector_requested:
            state.selected_model = CatalogModel(
                model_id=IMAGE_TO_VECTOR_MODEL,
                model_name="Image-to-Vector Reconstruction",
                provider="openai_vector",
                media_type=MediaType.IMAGE,
                supported_operations=["image_to_vector", "vector_render"],
                supported_input_types=["image"],
                supported_output_formats=["svg"],
                capabilities=["image_to_vector", "native_svg", "editable_vector"],
                editable_output_support=True,
                native_editable_support=True,
                availability=ModelAvailability.AVAILABLE,
                capability_metadata={"native_editable_formats": ["svg"]},
            )
        elif code_image_requested:
            state.selected_model = CatalogModel(
                model_id="code_image",
                model_name="OpenAI Code Image",
                provider="openai_code",
                media_type=MediaType.IMAGE,
                supported_operations=["text_to_image", "vector_render"],
                supported_output_formats=["svg"],
                capabilities=["code_generated_svg", "native_svg", "editable_vector"],
                editable_output_support=True,
                native_editable_support=True,
                availability=ModelAvailability.AVAILABLE,
            )
        elif native_svg_requested:
            state.selected_model = CatalogModel(
                model_id="native_svg_renderer",
                model_name="Graphic Agent Native SVG Renderer",
                provider="graphic_agent",
                media_type=MediaType.IMAGE,
                supported_operations=["text_to_image", "vector_render"],
                supported_output_formats=["svg"],
                capabilities=["native_svg", "editable_vector"],
                editable_output_support=True,
                native_editable_support=True,
                availability=ModelAvailability.AVAILABLE,
            )
        elif system_raster_requested:
            state.selected_model = CatalogModel(
                model_id=SystemRasterGraphicExecutor.model_id,
                model_name="System Graphic Renderer",
                provider="system",
                media_type=MediaType.IMAGE,
                supported_operations=["text_to_image"],
                supported_output_formats=["png", "jpg", "webp"],
                capabilities=["design_specification_rendering"],
                availability=ModelAvailability.AVAILABLE,
            )
        else:
            routing = self._router.route(state.request)
            if not routing.success:
                return self._fail(
                    state,
                    routing.error.code if routing.error else "ROUTING_FAILED",
                    routing.error.message if routing.error else "Model routing failed.",
                )
            state.selected_model = routing.selected_model

        state.current_stage = WorkflowStage.DECIDING
        explicit_model_requested = state.request.selected_model not in {
            None, "", "auto", "image_auto", "all", "all_image_models", "code_image", IMAGE_TO_VECTOR_MODEL, HYBRID_SVG_MODEL
        }
        if explicit_model_requested:
            # Explicit provider mode is intentionally planner-free. The image
            # executor still compiles the normalized brief into a provider
            # prompt, so provider adapters never receive business logic.
            planning = PlanningOutcome(
                request_id=state.request.request_id,
                decision=ComplexityDecision(False, "explicit model fast path", ["user_selected_model"]),
                request=state.request,
            )
        else:
            planning = self._planner.prepare(state.request, force=True)
        state.complexity = planning.decision
        if planning.decision.required:
            state.current_stage = WorkflowStage.PLANNING
        if not planning.success:
            return self._fail(
                state,
                planning.error_code or "PLANNER_FAILED",
                planning.error_message or "Planner failed.",
            )
        state.plan = planning.plan
        if state.plan is not None:
            self._print_planner_plan(state.plan, state.request.request_id)

        execution_request = ExecutionRequest(
            request_id=state.request.request_id,
            normalized_request=state.request,
            selected_model=state.selected_model,
            metadata=(
                {"execution_plan": state.plan}
                if state.plan is not None
                else {"execution_mode": "explicit_model", "prompt_compilation_required": True}
            ),
        )
        executor = (
            self._hybrid_svg_executor
            if hybrid_svg_requested
            else self._image_to_vector_executor
            if image_to_vector_requested
            else self._code_svg_executor
            if code_image_requested
            else self._native_svg_executor
            if native_svg_requested
            else self._system_raster_executor
            if system_raster_requested
            else self._executor_for(state.request)
        )
        state.current_stage = WorkflowStage.EXECUTING
        loop = BoundedRepairLoop(
            executor,
            self._verifier,
            max_repair_attempts=self._max_repair_attempts,
        )
        outcome = loop.run(execution_request)
        state.retry_count = outcome.repair_attempts
        state.execution_result = outcome.execution_result
        state.execution_status = outcome.execution_result.status.value
        state.verification_result = outcome.verification_result

        if outcome.repair_attempts:
            state.current_stage = WorkflowStage.REPAIRING
        state.current_stage = WorkflowStage.VERIFYING
        if outcome.status.value != "success":
            return self._fail(
                state,
                outcome.error.code if outcome.error else "WORKFLOW_FAILED",
                outcome.error.message if outcome.error else "Execution did not produce verified output.",
            )

        revision_history = []
        if (
            self._design_revision_enabled
            and self._revision_planner is not None
            and native_svg_requested
            and state.plan is not None
            and state.verification_result is not None
        ):
            state.execution_result, state.verification_result, state.plan, revision_history = self._run_design_revisions(
                state, execution_request
            )

        state.current_stage = WorkflowStage.COMPLETED
        state.final_output = self._final_output(state)
        if revision_history:
            state.final_output["design_revisions"] = [item.model_dump(mode="json") for item in revision_history]
        return state

    def _run_design_revisions(self, state, execution_request):
        """Run Phase 8 only for the native SVG path; failures keep last valid output."""
        metadata = dict(state.plan.metadata)
        try:
            specification = DesignSpecification.model_validate(metadata["design_specification"])
            inspection_data = state.verification_result.metadata.get("visual_inspection")
            inspection = VisualInspectionResult.model_validate(inspection_data)
        except Exception:
            return state.execution_result, state.verification_result, state.plan, []

        current_execution = state.execution_result
        current_verification = state.verification_result
        current_plan = state.plan
        rendered = []

        def render_and_inspect(revised_spec, revised_layout):
            nonlocal current_execution, current_verification, current_plan
            new_metadata = dict(current_plan.metadata)
            new_metadata["design_specification"] = revised_spec.model_dump(mode="json")
            new_metadata["layout_specification"] = revised_layout.model_dump(mode="json")
            new_metadata["graphic_execution_spec"] = LayoutCompiler().compile_to_execution_spec(revised_spec)
            current_plan = replace(current_plan, metadata=new_metadata)
            request = replace(execution_request, metadata={"execution_plan": current_plan})
            current_execution = self._native_svg_executor.execute(request)
            current_verification = self._verifier.verify(VerificationRequest(request.request_id, request, current_execution))
            raw = current_verification.metadata.get("visual_inspection")
            if raw is None:
                raise RuntimeError("revision render produced no visual inspection")
            rendered.append((current_execution, current_verification, current_plan))
            return VisualInspectionResult.model_validate(raw)

        from packages.verification.domain.contracts import VerificationRequest
        final_spec, final_inspection, history = RevisionLoop(
            self._revision_planner,
            max_iterations=self._max_design_revisions,
            render_and_inspect=render_and_inspect,
        ).run(specification, inspection)
        if rendered and history and any(item.status.value == "applied" for item in history):
            current_execution, current_verification, current_plan = rendered[-1]
        return current_execution, current_verification, current_plan, history

    def _executor_for(self, request: NormalizedRequest) -> Executor:
        # The concrete executor is selected by the orchestrator boundary; the
        # executor itself still owns all execution behavior.
        return (
            self._graphic_executor
            if request.creative_type.value == "image"
            else self._motion_executor
        )

    @staticmethod
    def _print_planner_plan(plan, request_id: str) -> None:
        """Print the authoritative plan at the Manager boundary for debugging."""
        payload = {
            "request_id": request_id,
            "steps": [asdict(step) for step in (plan.steps or [])],
            "expected_outputs": list(plan.expected_outputs or []),
            "metadata": plan.metadata or {},
        }
        print("[MANAGER] Planner plan received")
        print(json.dumps(Orchestrator._console_safe_value(payload), ensure_ascii=False, indent=2, default=str))

    @staticmethod
    def _console_safe_value(value: Any) -> Any:
        """Redact binary upload data from terminal diagnostics.

        Uploaded SVG/PNG/JPG files are carried as data URIs. They are valid
        runtime data, but printing them makes the server log unreadable and
        can flood the terminal with base64 characters. Only diagnostics are
        changed; the original value remains untouched in the workflow state.
        """
        if isinstance(value, str):
            if value.startswith("data:image/") or "base64," in value[:256]:
                return f"[uploaded image data redacted; {len(value)} characters]"
            if len(value) > 12000:
                return f"[long diagnostic value redacted; {len(value)} characters]"
            return value
        if isinstance(value, dict):
            return {key: Orchestrator._console_safe_value(nested) for key, nested in value.items()}
        if isinstance(value, list):
            return [Orchestrator._console_safe_value(item) for item in value]
        if isinstance(value, tuple):
            return [Orchestrator._console_safe_value(item) for item in value]
        return value

    @staticmethod
    def _fail(state: OrchestratorState, code: str, message: str) -> OrchestratorState:
        state.current_stage = WorkflowStage.FAILED
        state.error_code = code
        state.error_message = message
        return state

    @staticmethod
    def _final_output(state: OrchestratorState) -> Dict[str, Any]:
        execution = state.execution_result
        verification = state.verification_result
        return {
            "request_id": state.request_id,
            "status": "completed",
            "execution_mode": (
                "hybrid_svg"
                if state.request and state.request.selected_model == HYBRID_SVG_MODEL
                else "image_to_vector"
                if state.request and state.request.selected_model == IMAGE_TO_VECTOR_MODEL
                else "code_image"
                if state.request and state.request.selected_model == "code_image"
                else "explicit_model"
                if state.request and state.request.selected_model not in {None, "", "auto", "image_auto", "all", "all_image_models"}
                else "auto_planner"
            ),
            "selected_model": state.selected_model.model_id if state.selected_model else None,
            "complexity": state.complexity.required if state.complexity else False,
            "outputs": [
                {
                    "uri": asset.uri,
                    "download_uri": (asset.metadata or {}).get("download_uri"),
                    "format": asset.format,
                    "editable": asset.editable,
                    "native_editable": asset.native_editable,
                }
                for asset in (execution.output_assets if execution else [])
            ],
            "verification": {
                "status": verification.status.value if verification else None,
                "passed": verification.passed if verification else False,
                "visual_inspection": verification.metadata.get("visual_inspection") if verification else None,
            },
        }

"""Adapter from the existing Planner Agent to the provider-neutral plan."""

from __future__ import annotations

from typing import Any, Dict, List

from packages.planner_agent.agent.graph import run_planner
from packages.design_intelligence.application.mapper import attach_design_specification
from packages.design_intelligence.application.reasoning import DesignReasoningEngine
from packages.design_intelligence.application.layout_compiler import LayoutCompiler
from packages.design_intelligence.application.focused_mapper import FocusedDesignSpecificationMapper
from packages.design_intelligence.adapters.gemini import GeminiFocusedDesignReasoner
from packages.request_contract.domain.schema import NormalizedRequest

from ..domain.contracts import ExecutionPlan, PlanStep


class ExistingPlannerAdapter:
    """Reuse the existing bounded Planner Agent behind PlannerPort."""

    def __init__(self, *, prefer_focused_design: bool = False) -> None:
        self._prefer_focused_design = prefer_focused_design

    def plan(self, request: NormalizedRequest) -> ExecutionPlan:
        if self._prefer_focused_design and request.creative_type.value == "image":
            try:
                return self._focused_plan(request)
            except Exception as focused_error:
                # Preserve the legacy PlannerOutput path as a compatibility
                # fallback. The focused contract never fabricates AI output.
                try:
                    return self._legacy_plan(request)
                except Exception as legacy_error:
                    return self._deterministic_fallback(
                        request,
                        focused_error=focused_error,
                        legacy_error=legacy_error,
                    )
        return self._legacy_plan(request)

    def _legacy_plan(self, request: NormalizedRequest) -> ExecutionPlan:
        payload = _planner_safe_request_payload(request)
        result = run_planner(
            {
                "job_id": request.request_id,
                "manager_input": {"normalized_request": payload},
                "json_agent_output": payload,
                "original_user_request": request.context_prompt,
                "previous_asset_required": bool(request.reference_assets or request.input_assets),
                "asset_requests": _planner_asset_requests(request),
                "prepared_input": {},
                "llm_plan_raw": None,
                "validated_plan": None,
                "final_output": None,
                "validation_passed": False,
                "status": "pending",
                "error": None,
                "planning_iteration": 0,
                "repair_attempt": 0,
            }
        )
        if not result.get("success", True) or result.get("status") == "failed":
            raise RuntimeError(result.get("error") or "Existing Planner failed.")
        output = result.get("final_output") or {}
        return self._translate(request, output)
    @staticmethod
    def _focused_plan(request: NormalizedRequest) -> ExecutionPlan:
        decisions = GeminiFocusedDesignReasoner().reason(request)
        specification, attribution = FocusedDesignSpecificationMapper().map(request, decisions)
        compiler = LayoutCompiler()
        metadata = attach_design_specification(
            {
                "source": "focused_gemini_design_reasoning",
                "design_decision_attribution": attribution,
                "job_summary": decisions.concept,
                "primary_job_type": "graphic_design",
                "target_output_format": request.output.format,
                "graphic_execution_spec": compiler.compile_to_execution_spec(specification),
                "layout_specification": compiler.compile(specification).model_dump(mode="json"),
                "planner_graphic_execution_spec": None,
                "global_constraints": list(specification.constraints),
                "execution_order": ["design_specification", "layout_compilation", "native_svg_render"],
            },
            specification,
        )
        return ExecutionPlan(
            request_id=request.request_id,
            steps=[PlanStep(
                step_id="focused-design",
                operation="graphic_design",
                expected_outputs=[request.output.format],
                metadata={"required_capabilities": ["native_svg", "design_intelligence"]},
            )],
            expected_outputs=[request.output.format],
            metadata=metadata,
        )

    @staticmethod
    def _deterministic_fallback(request: NormalizedRequest, *, focused_error: Exception, legacy_error: Exception) -> ExecutionPlan:
        specification = DesignReasoningEngine().reason(request)
        compiler = LayoutCompiler()
        attribution = {
            "sources": {"all": "deterministic_baseline"},
            "fallback_used": True,
            "model": None,
            "error_types": [type(focused_error).__name__, type(legacy_error).__name__],
        }
        metadata = attach_design_specification(
            {
                "source": "deterministic_fallback",
                "design_decision_attribution": attribution,
                "job_summary": specification.concept,
                "primary_job_type": "graphic_design",
                "target_output_format": request.output.format,
                "graphic_execution_spec": compiler.compile_to_execution_spec(specification),
                "layout_specification": compiler.compile(specification).model_dump(mode="json"),
                "planner_graphic_execution_spec": None,
                "global_constraints": list(specification.constraints),
                "execution_order": ["deterministic_design_specification", "layout_compilation", "native_svg_render"],
            },
            specification,
        )
        return ExecutionPlan(
            request_id=request.request_id,
            steps=[PlanStep(step_id="deterministic-design", operation="graphic_design", expected_outputs=[request.output.format], metadata={"required_capabilities": ["native_svg"]})],
            expected_outputs=[request.output.format],
            metadata=metadata,
        )

    @staticmethod
    def _translate(request: NormalizedRequest, output: Dict[str, Any]) -> ExecutionPlan:
        raw_tasks = output.get("tasks") or []
        steps: List[PlanStep] = []
        for index, task in enumerate(raw_tasks):
            steps.append(
                PlanStep(
                    step_id=str(task.get("task_id") or f"step-{index + 1}"),
                    operation=str(task.get("job_type") or task.get("title") or "execute"),
                    depends_on=list(task.get("depends_on") or []),
                    expected_outputs=list(task.get("expected_outputs") or []),
                    metadata={
                        "description": task.get("description", ""),
                        "required_capabilities": list(task.get("required_capabilities") or []),
                        "constraints": list(task.get("constraints") or []),
                    },
                )
            )
        dependencies = {step.step_id: list(step.depends_on) for step in steps if step.depends_on}
        raw_specification = output.get("design_specification")
        specification = DesignReasoningEngine().complete(request, raw_specification)
        compiled_execution_spec = LayoutCompiler().compile_to_execution_spec(specification)
        layout_specification = LayoutCompiler().compile(specification)
        metadata = attach_design_specification(
            {
                "source": "existing_planner_agent",
                "job_summary": output.get("job_summary"),
                "primary_job_type": output.get("primary_job_type"),
                "target_software": output.get("target_software"),
                "target_output_format": output.get("target_output_format"),
                "graphic_execution_spec": compiled_execution_spec,
                "layout_specification": layout_specification.model_dump(mode="json"),
                "planner_graphic_execution_spec": output.get("graphic_execution_spec"),
                "global_constraints": list(output.get("global_constraints") or []),
                "execution_order": list(output.get("execution_order") or []),
            },
            specification,
        )
        return ExecutionPlan(
            request_id=request.request_id,
            steps=steps,
            dependencies=dependencies,
            expected_outputs=list(output.get("final_deliverables") or []),
            metadata=metadata,
        )


def _planner_safe_request_payload(request: NormalizedRequest) -> dict[str, Any]:
    """Keep binary image data out of the legacy Planner LLM input."""
    payload = request.model_dump(mode="json")
    payload["reference_assets"] = _planner_asset_requests(request)
    payload["input_assets"] = _planner_asset_requests(request)
    payload["uploaded_asset_count"] = len(request.reference_assets)
    return payload


def _planner_asset_requests(request: NormalizedRequest) -> list[dict[str, Any]]:
    return [
        {
            "id": f"uploaded-asset-{index}",
            "type": asset.kind or "image",
            "name": (asset.description or f"uploaded asset {index}").split(";", 1)[0],
            "description": asset.description or "User-provided image asset.",
            "required": asset.required,
        }
        for index, asset in enumerate(request.reference_assets, start=1)
    ]

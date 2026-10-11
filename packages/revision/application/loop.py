"""Bounded revision engine with deterministic quality gates and rollback."""

from __future__ import annotations

import logging
from typing import Callable, Optional

from packages.design_intelligence.application.layout_compiler import LayoutCompiler
from packages.design_intelligence.domain.layout import LayoutSpecification
from packages.design_intelligence.domain.specification import DesignSpecification
from packages.revision.domain import (
    RevisionDecision, RevisionPatch, RevisionRecord, RevisionRequest, RevisionResult,
    RevisionStatus,
)
from packages.revision.ports.planner import RevisionPlannerPort
from packages.verification.domain.visual import VisualInspectionResult, InspectionSeverity, RequirementInspectionStatus

logger = logging.getLogger(__name__)


class RevisionLoop:
    """One targeted patch per iteration; rendering is supplied by the caller."""

    def __init__(self, planner: RevisionPlannerPort, *, max_iterations: int = 3, applier=None,
                 render_and_inspect: Optional[Callable[[DesignSpecification, LayoutSpecification], VisualInspectionResult]] = None):
        if max_iterations < 1:
            raise ValueError("max_iterations must be positive")
        self._planner = planner
        self._max_iterations = max_iterations
        from .patches import RevisionPatchApplier
        self._applier = applier or RevisionPatchApplier()
        self._render_and_inspect = render_and_inspect

    def run(self, specification: DesignSpecification, inspection: VisualInspectionResult,
            *, layout: LayoutSpecification | None = None) -> tuple[DesignSpecification, VisualInspectionResult, list[RevisionRecord]]:
        current_spec = specification.model_copy(deep=True)
        current_inspection = inspection
        current_layout = layout or LayoutCompiler().compile(current_spec)
        history: list[RevisionRecord] = []
        seen: set[tuple[str, str]] = set()
        for iteration in range(1, self._max_iterations + 1):
            if not self._needs_revision(current_inspection):
                break
            request = RevisionRequest(
                inspection=current_inspection,
                design_brief=current_spec.brief,
                design_specification=current_spec,
                layout_specification=current_layout,
                iteration=iteration,
                maximum_iterations=self._max_iterations,
                constraints=list(current_spec.constraints),
            )
            try:
                decision = self._planner.plan(request)
                if not decision.should_revise:
                    history.append(RevisionRecord(iteration=iteration, decision=decision, status=RevisionStatus.REJECTED, reason="planner stopped revision"))
                    break
                patch = RevisionPatch(target=decision.target, operation=decision.change_type, value=decision.value, finding_reference=decision.finding_reference)
                key = (patch.target, patch.operation.value)
                if (patch.target, self._opposite(patch.operation.value)) in seen:
                    history.append(RevisionRecord(iteration=iteration, decision=decision, patch=patch, status=RevisionStatus.REJECTED, reason="oscillation detected"))
                    break
                seen.add(key)
                previous_spec = current_spec
                previous_inspection = current_inspection
                revised = self._applier.apply(previous_spec, patch)
                revised_layout = LayoutCompiler().compile(revised)
                if self._render_and_inspect is None:
                    history.append(RevisionRecord(iteration=iteration, decision=decision, patch=patch, status=RevisionStatus.APPLIED, reason="patch applied; render callback not configured"))
                    current_spec, current_layout = revised, revised_layout
                    break
                revised_inspection = self._render_and_inspect(revised, revised_layout)
                if self._quality_gate(previous_inspection, revised_inspection):
                    current_spec, current_layout, current_inspection = revised, revised_layout, revised_inspection
                    history.append(RevisionRecord(iteration=iteration, decision=decision, patch=patch, status=RevisionStatus.APPLIED))
                else:
                    history.append(RevisionRecord(iteration=iteration, decision=decision, patch=patch, status=RevisionStatus.REJECTED, reason="quality gate regression"))
                    break
            except Exception as exc:
                logger.warning("revision failed at iteration %s: %s", iteration, exc)
                history.append(RevisionRecord(iteration=iteration, decision=decision if 'decision' in locals() else RevisionDecision(should_revise=False, reason=str(exc)), status=RevisionStatus.FAILED, reason=str(exc)))
                break
        return current_spec, current_inspection, history

    @staticmethod
    def _needs_revision(inspection):
        return any(i.severity in {InspectionSeverity.CRITICAL, InspectionSeverity.ERROR, InspectionSeverity.WARNING} for i in inspection.issues) or any(r.status == RequirementInspectionStatus.NOT_SATISFIED for r in inspection.requirements)

    @staticmethod
    def _quality_gate(before, after):
        before_bad = sum(i.severity in {InspectionSeverity.CRITICAL, InspectionSeverity.ERROR} for i in before.issues)
        after_bad = sum(i.severity in {InspectionSeverity.CRITICAL, InspectionSeverity.ERROR} for i in after.issues)
        before_req = sum(r.status == RequirementInspectionStatus.NOT_SATISFIED for r in before.requirements)
        after_req = sum(r.status == RequirementInspectionStatus.NOT_SATISFIED for r in after.requirements)
        return after_bad <= before_bad and after_req <= before_req

    @staticmethod
    def _opposite(operation: str) -> str:
        pairs = {"increase_font_size": "decrease_font_size", "decrease_font_size": "increase_font_size", "increase_spacing": "decrease_spacing", "decrease_spacing": "increase_spacing", "increase_visual_weight": "decrease_visual_weight", "decrease_visual_weight": "increase_visual_weight", "increase_asset_size": "decrease_asset_size", "decrease_asset_size": "increase_asset_size"}
        return pairs.get(operation, "")

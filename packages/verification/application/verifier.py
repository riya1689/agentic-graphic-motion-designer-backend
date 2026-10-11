"""Deterministic image and motion verification orchestration."""

from __future__ import annotations

from packages.execution.domain.contracts import ExecutionStatus
from packages.capability_policy import EditableCapabilityPolicy
from packages.verification.domain.contracts import (
    VerificationIssue,
    VerificationRequest,
    VerificationResult,
    VerificationStatus,
)
from packages.verification.strategies.image import ImageVerifier
from packages.verification.strategies.motion import MotionVerifier
from packages.verification.application.visual_inspection import DeterministicVisualInspector
from packages.verification.application.visual_inspection import combine_visual_inspection
from packages.verification.domain.visual import PreviewArtifact, VisualCritiqueRequest


class Verifier:
    def __init__(self, *, image=None, motion=None, vision=None, visual_inspector=None, vision_inspector=None) -> None:
        self._image = image or ImageVerifier()
        self._motion = motion or MotionVerifier()
        self._vision = vision
        self._visual_inspector = visual_inspector
        self._vision_inspector = vision_inspector
        self._capability_policy = EditableCapabilityPolicy()

    def verify(self, request: VerificationRequest) -> VerificationResult:
        execution = request.execution_result
        if execution.status != ExecutionStatus.SUCCESS:
            provider_message = execution.error.message if execution.error else "Execution did not produce a successful result."
            issue_code = (
                execution.error.code.lower()
                if execution.error and execution.error.code
                else "execution_failed"
            )
            issue = VerificationIssue(issue_code, provider_message)
            return VerificationResult(request.request_id, VerificationStatus.FAILED, False, [issue], ["execution_status"])
        if not execution.output_assets:
            issue = VerificationIssue("missing_output", "Execution reported success without output assets.")
            return VerificationResult(request.request_id, VerificationStatus.FAILED, False, [issue], ["output_exists"])

        normalized = request.execution_request.normalized_request
        all_issues = []
        checked = []
        inspected = True
        capability_inconclusive = False
        visual_inspection = None
        for asset in execution.output_assets:
            if normalized.output.media_type.value == "image":
                issues, checks, inspected_asset = self._image.verify_asset(
                    asset,
                    normalized.output.format,
                    normalized.size,
                    allow_embedded_assets=bool(normalized.reference_assets),
                )
            else:
                issues, checks, inspected_asset = self._motion.verify_asset(
                    asset,
                    normalized.output.format,
                    normalized.size,
                    execution.metadata,
                )
            all_issues.extend(issues)
            checked.extend(checks)
            inspected = inspected and inspected_asset
            capability = self._capability_policy.result_assessment(normalized, asset)
            if not capability.allowed:
                issue_code = capability.code or "output_capability_mismatch"
                if issue_code == "NATIVE_EDITABLE_CAPABILITY_INCONCLUSIVE":
                    issue_code = "native_editable_capability_mismatch"
                    capability_inconclusive = True
                all_issues.append(
                    VerificationIssue(
                        issue_code,
                        capability.message or "Output capability requirement was not satisfied.",
                    )
                )

            if self._vision is not None and normalized.output.media_type.value == "image":
                all_issues.extend(self._vision.verify(request))

            if (
                self._visual_inspector is not None
                and normalized.output.format == "svg"
                and asset.metadata.get("absolute_path")
            ):
                try:
                    from pathlib import Path

                    svg_text = Path(asset.metadata["absolute_path"]).read_text(encoding="utf-8")
                    plan = request.execution_request.metadata.get("execution_plan")
                    plan_metadata = getattr(plan, "metadata", {}) if plan else {}
                    visual_inspection = self._visual_inspector.inspect(
                        svg_text,
                        design_specification=(plan_metadata or {}).get("design_specification", {}),
                        layout_specification=(plan_metadata or {}).get("layout_specification", {}),
                        user_requirements=list(normalized.text),
                        render_success=True,
                    )
                    if self._vision_inspector is not None:
                        plan = request.execution_request.metadata.get("execution_plan")
                        plan_metadata = getattr(plan, "metadata", {}) if plan else {}
                        preview = PreviewArtifact(
                            source_artifact=str(asset.metadata.get("absolute_path")),
                            reference=asset.metadata.get("preview_reference"),
                            width=int((plan_metadata or {}).get("layout_specification", {}).get("canvas", {}).get("width") or normalized.size.width if normalized.size else 1),
                            height=int((plan_metadata or {}).get("layout_specification", {}).get("canvas", {}).get("height") or normalized.size.height if normalized.size else 1),
                            render_status=str(asset.metadata.get("preview_status") or "unknown"),
                            error=asset.metadata.get("preview_error"),
                        )
                        vision_result = self._vision_inspector.inspect(
                            VisualCritiqueRequest(
                                preview=preview,
                                design_brief=((plan_metadata or {}).get("design_specification") or {}).get("brief", {}),
                                design_specification=(plan_metadata or {}).get("design_specification", {}),
                                layout_specification=(plan_metadata or {}).get("layout_specification", {}),
                                user_requirements=list(normalized.text),
                                inspection_criteria=[
                                    "communication", "hierarchy", "composition", "typography",
                                    "color", "assets", "explicit requirement visibility",
                                ],
                            )
                        )
                        visual_inspection = combine_visual_inspection(visual_inspection, vision_result)
                except Exception as exc:
                    visual_inspection = {
                        "render_success": False,
                        "source": "deterministic",
                        "warnings": [f"Visual inspection unavailable: {exc}"],
                    }

        if all_issues:
            status = VerificationStatus.INCONCLUSIVE if capability_inconclusive or (not inspected and all(
                issue.code == "output_uninspectable" for issue in all_issues
            )) else VerificationStatus.FAILED
            return VerificationResult(
                request.request_id,
                status,
                False,
                all_issues,
                sorted(set(checked)),
                metadata={"visual_inspection": visual_inspection.model_dump(mode="json") if hasattr(visual_inspection, "model_dump") else visual_inspection} if visual_inspection is not None else {},
            )
        return VerificationResult(
            request.request_id,
            VerificationStatus.PASSED,
            True,
            [],
            sorted(set(checked)),
            metadata={"visual_inspection": visual_inspection.model_dump(mode="json") if hasattr(visual_inspection, "model_dump") else visual_inspection} if visual_inspection is not None else {},
        )

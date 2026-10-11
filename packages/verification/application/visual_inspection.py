"""Deterministic visual inspection and optional vision-result combination."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from typing import Any, Mapping

from packages.verification.domain.visual import (
    InspectionCategory,
    InspectionCategoryResult,
    InspectionSeverity,
    InspectionConfidence,
    RequirementInspection,
    RequirementInspectionStatus,
    VisualInspectionIssue,
    VisualInspectionResult,
)


class DeterministicVisualInspector:
    """Inspect logical geometry and semantic coverage without redesigning."""

    def inspect(
        self,
        svg_text: str,
        *,
        design_specification: Mapping[str, Any] | None = None,
        layout_specification: Mapping[str, Any] | None = None,
        user_requirements: list[str] | None = None,
        render_success: bool = True,
    ) -> VisualInspectionResult:
        design = design_specification or {}
        layout = layout_specification or {}
        issues: list[VisualInspectionIssue] = []
        geometry_issues: list[VisualInspectionIssue] = []
        requirement_issues: list[VisualInspectionIssue] = []
        try:
            root = ET.fromstring(svg_text)
        except ET.ParseError as exc:
            issue = VisualInspectionIssue(severity=InspectionSeverity.CRITICAL, category=InspectionCategory.RENDERING, message=f"Preview source SVG is malformed: {exc}")
            return VisualInspectionResult(render_success=False, issues=[issue], warnings=[], source="deterministic")

        canvas = layout.get("canvas") or {}
        width = float(canvas.get("width") or root.attrib.get("width") or 0)
        height = float(canvas.get("height") or root.attrib.get("height") or 0)
        safe = (canvas.get("safe_area") or {})
        elements = layout.get("elements") or []
        regions = {region.get("id"): region for region in layout.get("regions") or [] if isinstance(region, dict)}
        for element in elements:
            if not isinstance(element, dict):
                continue
            bounds = element.get("bounds") or {}
            x, y = float(bounds.get("x") or 0), float(bounds.get("y") or 0)
            w, h = float(bounds.get("width") or 0), float(bounds.get("height") or 0)
            element_id = element.get("id")
            if w <= 0 or h <= 0:
                geometry_issues.append(self._issue("invalid element dimensions", element_id, InspectionSeverity.ERROR))
            if x < 0 or y < 0 or x + w > 1 or y + h > 1:
                geometry_issues.append(self._issue("element is outside the normalized canvas", element_id, InspectionSeverity.ERROR))
            if safe and not element.get("allow_overlap") and element.get("constraints") and (
                x < float(safe.get("x") or 0) or y < float(safe.get("y") or 0)
                or x + w > float(safe.get("x") or 0) + float(safe.get("width") or 1)
                or y + h > float(safe.get("y") or 0) + float(safe.get("height") or 1)
            ):
                geometry_issues.append(self._issue("required element extends beyond the safe area", element_id, InspectionSeverity.WARNING))

        text_content = " ".join(part.strip() for part in root.itertext() if part.strip())
        required = list(user_requirements or [])
        brief = design.get("brief") or {}
        required.extend(value for value in brief.get("required_text") or [] if value not in required)
        for value in required:
            if value not in text_content:
                requirement_issues.append(
                    VisualInspectionIssue(
                        severity=InspectionSeverity.ERROR,
                        category=InspectionCategory.REQUIREMENT_VISIBILITY,
                        message=f"required text is not visible in the SVG text layer: {value}",
                        evidence="SVG text content inspection",
                    )
                )

        requirement_results = [
            RequirementInspection(
                requirement_reference=value,
                status=RequirementInspectionStatus.SATISFIED if value in text_content else RequirementInspectionStatus.NOT_SATISFIED,
                evidence=("Required text is present in the SVG text layer." if value in text_content else "Required text was not found in the SVG text layer."),
                confidence=InspectionConfidence.HIGH,
                source="deterministic",
            )
            for value in required
        ]

        focal_region = layout.get("focal_region")
        composition_issues = [] if focal_region and focal_region in regions else [self._issue("no focal region is represented", None, InspectionSeverity.WARNING)]
        hierarchy_issues = [] if (design.get("visual_hierarchy") or {}).get("primary_focal_point") else [self._issue("primary focal point is not declared", None, InspectionSeverity.WARNING)]
        result = VisualInspectionResult(
            render_success=render_success,
            geometry=InspectionCategoryResult(passed=not geometry_issues, issues=geometry_issues),
            composition=InspectionCategoryResult(passed=not composition_issues, issues=composition_issues),
            hierarchy=InspectionCategoryResult(passed=not hierarchy_issues, issues=hierarchy_issues),
            requirement_visibility=InspectionCategoryResult(passed=not requirement_issues, issues=requirement_issues),
            issues=geometry_issues + composition_issues + hierarchy_issues + requirement_issues,
            requirements=requirement_results,
            warnings=["Text collision and readability are only logically inspected; font metrics are not measured."] if width and height else ["Canvas dimensions could not be determined."],
            source="deterministic",
        )
        return result

    @staticmethod
    def _issue(message, element_id, severity):
        return VisualInspectionIssue(severity=severity, category=InspectionCategory.GEOMETRY, message=message, affected_element=element_id)


def combine_visual_inspection(
    deterministic: VisualInspectionResult,
    vision_issues: list[VisualInspectionIssue] | VisualInspectionResult | None = None,
) -> VisualInspectionResult:
    if isinstance(vision_issues, VisualInspectionResult):
        additions = list(vision_issues.issues)
        requirement_additions = list(vision_issues.requirements)
    else:
        additions = list(vision_issues or [])
        requirement_additions = []
    return deterministic.model_copy(update={
        "issues": list(deterministic.issues) + additions,
        "requirements": list(deterministic.requirements) + requirement_additions,
        "source": "deterministic+vision" if additions else deterministic.source,
    })

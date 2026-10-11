"""Compile Planner output into a renderer-safe natural-language brief."""

from __future__ import annotations

from typing import Any

from packages.execution.domain.contracts import ExecutionRequest


class GraphicPlanValidationError(ValueError):
    """Raised when the Planner plan cannot safely reach a renderer."""


def validate_graphic_plan(request: ExecutionRequest) -> list[str]:
    plan = request.metadata.get("execution_plan")
    if plan is None:
        return ["Planner did not provide an execution plan."]
    metadata = getattr(plan, "metadata", {})
    if not isinstance(metadata, dict):
        return ["Planner execution plan metadata is invalid."]
    errors: list[str] = []
    if request.normalized_request.output.format == "svg":
        spec = metadata.get("graphic_execution_spec")
        if not isinstance(spec, dict):
            errors.append("SVG requests require a structured graphic execution specification.")
        elif not spec.get("layers"):
            errors.append("Graphic execution specification contains no layers.")
    if request.normalized_request.text:
        plan_text = _plan_text(metadata).lower()
        for value in request.normalized_request.text:
            if value.lower() not in plan_text:
                errors.append(f"Required text is missing from the plan: {value}")
    for color in request.normalized_request.colors:
        if color.lower() not in _plan_text(metadata).lower():
            errors.append(f"Required color is missing from the plan: {color}")
    return errors


def compile_graphic_prompt(request: ExecutionRequest) -> str:
    """Create a human-readable prompt; never serialize the plan as JSON."""
    normalized = request.normalized_request
    plan = request.metadata.get("execution_plan")
    metadata = getattr(plan, "metadata", {}) if plan else {}
    lines = [
        "Create one polished final graphic design.",
        f"Original creative direction: {normalized.context_prompt}",
        f"Output format: {normalized.output.format.upper()}.",
        "Follow every requirement below exactly. Do not add unrelated text, logos, watermarks, or UI elements.",
    ]
    if normalized.size:
        lines.append(f"Canvas: {normalized.size.width} by {normalized.size.height} {normalized.size.unit}.")
    if normalized.text:
        lines.append("Exact visible copy: " + "; ".join(f'\"{value}\"' for value in normalized.text) + ".")
    if normalized.colors:
        lines.append("Required color palette: " + ", ".join(normalized.colors) + ".")
    if normalized.style:
        lines.append(f"Style direction: {normalized.style}.")
    if normalized.design_type:
        lines.append(f"Design type: {normalized.design_type}.")
    if normalized.reference_assets:
        lines.append(
            "User-provided image assets are authoritative design layers. "
            "Use each asset according to the user's instruction (for example logo, background, product image, or reference), preserve its identity, and do not replace it with generated artwork."
        )
        for asset in normalized.reference_assets:
            lines.append(f"Uploaded asset: {asset.description or asset.kind}; role and placement are defined by the original user request.")
    if isinstance(metadata, dict):
        design_specification = metadata.get("design_specification")
        if isinstance(design_specification, dict):
            brief = design_specification.get("brief") or {}
            if brief.get("purpose"):
                lines.append(f"Design purpose: {brief['purpose']}.")
            direction = design_specification.get("art_direction") or {}
            direction_values = [
                direction.get(key)
                for key in ("style", "mood", "tone", "visual_language")
                if direction.get(key)
            ]
            if direction_values:
                lines.append("Art direction: " + ", ".join(map(str, direction_values)) + ".")
            priorities = design_specification.get("content_hierarchy") or []
            priority_lines = []
            for item in priorities:
                if isinstance(item, dict) and item.get("value") and item.get("priority"):
                    priority_lines.append(f"{item['priority']}: {item['value']}")
            if priority_lines:
                lines.append("Content priorities: " + "; ".join(priority_lines) + ".")
            composition = design_specification.get("composition") or {}
            composition_values = [
                composition.get(key)
                for key in ("strategy", "alignment", "balance", "negative_space", "visual_flow")
                if composition.get(key)
            ]
            if composition_values:
                lines.append("Composition intent: " + "; ".join(map(str, composition_values)) + ".")
            typography = design_specification.get("typography") or {}
            if typography.get("font_pairing_intent"):
                lines.append(f"Typography intent: {typography['font_pairing_intent']}.")
        if metadata.get("job_summary"):
            lines.append(f"Planner summary: {metadata['job_summary']}.")
        if metadata.get("global_constraints"):
            lines.append("Planner constraints: " + "; ".join(map(str, metadata["global_constraints"])) + ".")
        spec = metadata.get("graphic_execution_spec")
        if isinstance(spec, dict):
            document = spec.get("document") or {}
            if document:
                lines.append(f"Planned document: {document.get('width', 'auto')} by {document.get('height', 'auto')}.")
            palette = spec.get("palette") or []
            planned_colors = [str(item.get("value")) for item in palette if isinstance(item, dict) and item.get("value")]
            if planned_colors:
                lines.append("Planner palette: " + ", ".join(planned_colors) + ".")
            for layer in spec.get("layers") or []:
                if not isinstance(layer, dict):
                    continue
                layer_name = layer.get("name") or layer.get("id") or "unnamed layer"
                elements = []
                for element in layer.get("elements") or []:
                    if isinstance(element, dict):
                        detail = str(element.get("type") or "element")
                        if element.get("content"):
                            detail += f" containing \"{element['content']}\""
                        if element.get("name"):
                            detail += f" ({element['name']})"
                        elements.append(detail)
                if elements:
                    lines.append(f"Layer {layer_name}: " + ", ".join(elements) + ".")
    repair = request.metadata.get("repair_instructions")
    if repair:
        lines.append("Correction instructions from verification: " + str(repair))
    lines.append("Make all required elements clearly visible and legible in the final composition.")
    return "\n".join(lines)


def _plan_text(metadata: dict[str, Any]) -> str:
    return repr(metadata)

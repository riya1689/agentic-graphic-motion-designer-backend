"""Deterministic, copy-on-write application of the small revision vocabulary."""

from __future__ import annotations

from pydantic import ValidationError

from packages.design_intelligence.domain.specification import DesignSpecification
from packages.revision.domain import RevisionChangeType, RevisionPatch


class RevisionPatchError(ValueError):
    pass


class RevisionPatchApplier:
    """Apply only allowlisted design-level changes; never touches SVG/files."""

    def apply(self, specification: DesignSpecification, patch: RevisionPatch) -> DesignSpecification:
        try:
            revised = specification.model_copy(deep=True)
            operation = patch.operation
            if patch.target.startswith("typography."):
                self._typography(revised, patch)
            elif patch.target.startswith("layout."):
                self._layout(revised, patch)
            elif patch.target.startswith("visual_hierarchy."):
                self._hierarchy(revised, patch)
            elif patch.target.startswith("color_system."):
                self._color(revised, patch)
            elif patch.target.startswith("asset."):
                self._asset(revised, patch)
            else:
                raise RevisionPatchError(f"unsupported revision target: {patch.target}")
            self._preserve_requirements(specification, revised)
            return DesignSpecification.model_validate(revised.model_dump(mode="python"))
        except (ValidationError, TypeError, ValueError) as exc:
            if isinstance(exc, RevisionPatchError):
                raise
            raise RevisionPatchError(str(exc)) from exc

    @staticmethod
    def _level(spec, target: str):
        name = target.split(".", 1)[1]
        aliases = {"primary_heading": "display", "headline": "display", "body_text": "body"}
        name = aliases.get(name, name)
        level = getattr(spec.typography, name, None)
        if level is None:
            level = next((item for item in spec.typography.hierarchy_levels if item.name.lower() == name.lower()), None)
        if level is None:
            raise RevisionPatchError(f"unknown typography target: {target}")
        return level

    def _typography(self, spec, patch):
        level = self._level(spec, patch.target)
        op = patch.operation
        if op in {RevisionChangeType.INCREASE_FONT_SIZE, RevisionChangeType.DECREASE_FONT_SIZE}:
            current = level.font_size or {"largest": 72, "prominent": 48, "medium": 32, "readable": 24, "small": 18}.get(level.scale, 24)
            factor = float(patch.value)
            level.font_size = current * factor if op == RevisionChangeType.INCREASE_FONT_SIZE else current / factor
        elif op == RevisionChangeType.ADJUST_LETTER_SPACING:
            level.letter_spacing_value = float(patch.value)
        elif op == RevisionChangeType.ADJUST_LINE_HEIGHT:
            level.line_height_value = float(patch.value)
        elif op == RevisionChangeType.CHANGE_TEXT_ALIGNMENT:
            if patch.value not in {"left", "center", "right", "justify"}:
                raise RevisionPatchError("unsupported text alignment")
            level.alignment = patch.value
        elif op in {RevisionChangeType.INCREASE_FONT_WEIGHT, RevisionChangeType.DECREASE_FONT_WEIGHT}:
            current = int(level.font_size and 700 or 400)  # semantic fallback; renderer uses weight string
            level.weight = str(min(900, current + 100) if op == RevisionChangeType.INCREASE_FONT_WEIGHT else max(100, current - 100))
        else:
            raise RevisionPatchError(f"operation {op.value} is not valid for {patch.target}")

    @staticmethod
    def _region(spec, target):
        region_id = target.split(".", 1)[1]
        region_id = {
            "primary_region": "primary",
            "supporting_region": "supporting",
            "action_region": "action",
            "visual_region": "visual",
        }.get(region_id, region_id)
        if region_id not in {"primary", "supporting", "action", "visual"}:
            raise RevisionPatchError(f"unknown layout target: {target}")
        return region_id

    def _layout(self, spec, patch):
        region = self._region(spec, patch.target)
        op = patch.operation
        if op not in {RevisionChangeType.MOVE_REGION, RevisionChangeType.RESIZE_REGION,
                      RevisionChangeType.INCREASE_SPACING, RevisionChangeType.DECREASE_SPACING,
                      RevisionChangeType.ADJUST_ALIGNMENT}:
            raise RevisionPatchError(f"operation {op.value} is not valid for {patch.target}")
        override = dict(spec.layout_overrides.get(region, {}))
        if op == RevisionChangeType.MOVE_REGION:
            delta = float(patch.value)
            override["dx"] = max(-0.15, min(0.15, float(override.get("dx", 0)) + delta))
        elif op == RevisionChangeType.RESIZE_REGION:
            override["scale"] = max(0.75, min(1.25, float(override.get("scale", 1)) * float(patch.value)))
        elif op in {RevisionChangeType.INCREASE_SPACING, RevisionChangeType.DECREASE_SPACING}:
            factor = float(patch.value) if op == RevisionChangeType.INCREASE_SPACING else 1 / float(patch.value)
            override["spacing"] = max(0.5, min(2.0, float(override.get("spacing", 1)) * factor))
        else:
            override["alignment"] = str(patch.value)
        spec.layout_overrides[region] = override

    def _hierarchy(self, spec, patch):
        if patch.target not in {"visual_hierarchy.primary_weight", "visual_hierarchy.primary", "visual_hierarchy.cta", "typography.cta"}:
            raise RevisionPatchError(f"unknown hierarchy target: {patch.target}")
        if patch.operation not in {RevisionChangeType.INCREASE_VISUAL_WEIGHT, RevisionChangeType.DECREASE_VISUAL_WEIGHT,
                                   RevisionChangeType.PROMOTE_ELEMENT, RevisionChangeType.DEMOTE_ELEMENT}:
            raise RevisionPatchError(f"operation {patch.operation.value} is not valid for hierarchy")
        if not spec.content_hierarchy:
            raise RevisionPatchError("cannot revise hierarchy without content")
        item = spec.content_hierarchy[0]
        if patch.target in {"visual_hierarchy.cta", "typography.cta"}:
            item = next((candidate for candidate in spec.content_hierarchy if candidate.priority.value == "cta"), item)
        delta = 1 if patch.operation in {RevisionChangeType.INCREASE_VISUAL_WEIGHT, RevisionChangeType.PROMOTE_ELEMENT} else -1
        item.prominence = max(1, min(5, item.prominence + delta))

    def _color(self, spec, patch):
        role = patch.target.split(".", 1)[1]
        if role not in {"background", "surface", "primary", "secondary", "accent", "text", "muted_text", "cta", "border"}:
            raise RevisionPatchError(f"unknown semantic color role: {patch.target}")
        if patch.operation == RevisionChangeType.CHANGE_SEMANTIC_COLOR_ROLE:
            setattr(spec.color_system, role, str(patch.value))
        elif patch.operation in {RevisionChangeType.INCREASE_CONTRAST, RevisionChangeType.DECREASE_CONTRAST}:
            spec.color_system.contrast_intent = (
                "strong contrast for required content"
                if patch.operation == RevisionChangeType.INCREASE_CONTRAST
                else "reduced contrast for secondary content"
            )
        else:
            raise RevisionPatchError(f"operation {patch.operation.value} is not valid for color roles")

    def _asset(self, spec, patch):
        if not spec.asset_strategy.assets:
            raise RevisionPatchError("cannot revise asset placement without an asset")
        if patch.operation not in {RevisionChangeType.INCREASE_ASSET_SIZE, RevisionChangeType.DECREASE_ASSET_SIZE, RevisionChangeType.MOVE_ASSET, RevisionChangeType.ADJUST_ASSET_FIT}:
            raise RevisionPatchError(f"operation {patch.operation.value} is not valid for assets")
        spec.layout_overrides["visual"] = {"asset_operation": patch.operation.value, "asset_value": patch.value}

    @staticmethod
    def _preserve_requirements(original, revised):
        before_text = {item.value for item in original.content_hierarchy if item.required}
        after_text = {item.value for item in revised.content_hierarchy if item.required}
        if not before_text.issubset(after_text):
            raise RevisionPatchError("revision would remove required content")
        if not set(original.brief.required_colors).issubset(set(revised.color_system.required_colors)):
            raise RevisionPatchError("revision would remove required colors")

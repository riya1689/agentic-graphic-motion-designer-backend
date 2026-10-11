"""Compile semantic design intent into a renderer-independent layout."""

from __future__ import annotations

import re
from typing import Any, Dict, List

from packages.design_intelligence.domain.layout import (
    LayoutCanvas,
    LayoutElement,
    LayoutElementType,
    LayoutGrid,
    LayoutInsets,
    LayoutRegion,
    LayoutRelationship,
    LayoutSpecification,
    NormalizedBounds,
    SizingStrategy,
)
from packages.design_intelligence.domain.specification import (
    ContentPriority,
    DesignSpecification,
)
from packages.planner_agent.domain.graphic_execution_schema import PlannerGraphicExecutionSpec


class LayoutCompiler:
    """Deterministically compile a DesignSpecification into spatial intent."""

    def compile(self, specification: DesignSpecification) -> LayoutSpecification:
        brief = specification.brief
        width = brief.canvas.width if brief.canvas else 1080
        height = brief.canvas.height if brief.canvas else 1080
        orientation = "landscape" if width > height else "portrait" if height > width else "square"
        margin = 0.08 if orientation != "landscape" else 0.06
        safe = NormalizedBounds(x=margin, y=margin, width=1 - margin * 2, height=1 - margin * 2)
        canvas = LayoutCanvas(
            width=width,
            height=height,
            aspect_ratio=round(width / height, 6),
            orientation=orientation,
            margins=LayoutInsets(top=margin, right=margin, bottom=margin, left=margin),
            safe_area=safe,
            background=specification.color_system.background,
        )

        strategy = self._normalize_strategy(specification.composition.strategy, specification.design_type)
        regions = self._planned_regions(specification, safe) or self._regions(specification, strategy, safe)
        regions = self._apply_overrides(regions, specification.layout_overrides)
        region_by_id = {region.id: region for region in regions}
        elements: List[LayoutElement] = []
        content_items = list(specification.content_hierarchy)
        for index, item in enumerate(content_items):
            region_id = self._region_for_priority(item.priority, region_by_id)
            region = region_by_id[region_id]
            bounds = self._content_bounds(region.bounds, item.priority, index, len(content_items))
            element_type = LayoutElementType.TEXT
            role = item.priority.value
            elements.append(
                LayoutElement(
                    id=f"layout-{item.content_id}",
                    type=element_type,
                    role=role,
                    content_reference=item.content_id,
                    region_reference=region_id,
                    bounds=bounds,
                    alignment=region.alignment or "center",
                    alignment_reference=region_id,
                    z_index=30 if item.priority == ContentPriority.PRIMARY else 40 if item.priority == ContentPriority.CTA else 20,
                    constraints=["preserve required text", "remain inside safe area"],
                    sizing=SizingStrategy.PRIORITY_BASED if item.priority == ContentPriority.PRIMARY else SizingStrategy.RELATIVE,
                )
            )

        if specification.asset_strategy.imagery_required:
            image_region = region_by_id.get("visual") or region_by_id.get("primary")
            if image_region:
                elements.append(
                    LayoutElement(
                        id="layout-visual-anchor",
                        type=LayoutElementType.IMAGE,
                        role="primary visual anchor",
                        region_reference=image_region.id,
                        bounds=image_region.bounds,
                        alignment="center",
                        alignment_reference=image_region.id,
                        z_index=10,
                        constraints=["support the primary communication", "remain inside safe area"],
                        sizing=SizingStrategy.ASPECT_LOCKED,
                        fit="cover",
                    )
                )

        relationships = self._relationships(elements, content_items)
        return LayoutSpecification(
            canvas=canvas,
            composition_strategy=strategy,
            grid=self._grid(specification, strategy),
            regions=regions,
            elements=elements,
            relationships=relationships,
            focal_region="primary" if "primary" in region_by_id else None,
            reading_path=specification.visual_hierarchy.reading_path,
            spacing_tokens=dict(specification.design_tokens.spacing),
            constraints=list(specification.constraints) + ["required content must remain represented"],
        )

    def compile_to_execution_spec(self, specification: DesignSpecification) -> Dict[str, Any]:
        """Compile through LayoutSpecification into the existing scene schema."""
        layout = self.compile(specification)
        palette = self._palette(specification)
        layers: Dict[str, Dict[str, Any]] = {
            "background": {"id": "layer-background", "name": "Background", "visible": True, "elements": []},
            "decorative": {"id": "layer-decorative", "name": "Decorative", "visible": True, "elements": []},
            "visual": {"id": "layer-visual", "name": "Visual", "visible": True, "elements": []},
            "content": {"id": "layer-content", "name": "Content", "visible": True, "elements": []},
        }
        background = specification.color_system.background or palette[0]
        background_style = self._background_style(specification, background, palette)
        layers["background"]["elements"].append(
            {"id": "background", "type": "background", "placement": {"x": 0, "y": 0, "width": layout.canvas.width, "height": layout.canvas.height}, "style": background_style}
        )
        planned_visuals = self._planned_visual_elements(specification, layout, palette)
        if planned_visuals:
            for layer_name, element in planned_visuals:
                if layer_name not in layers:
                    layers[layer_name] = {"id": f"layer-{layer_name}", "name": layer_name.title(), "visible": True, "elements": []}
                layers[layer_name]["elements"].append(element)
        else:
            layers["decorative"]["elements"].extend(self._decorative_elements(specification, layout, palette))
        content_by_id = {item.content_id: item for item in specification.content_hierarchy}
        for element in layout.elements:
            bounds = self._actual_bounds(element.bounds, layout.canvas.width, layout.canvas.height)
            if element.type == LayoutElementType.IMAGE:
                asset_role = " ".join(
                    str(value).lower()
                    for asset in specification.asset_strategy.assets
                    for value in (asset.role, asset.placement_intent)
                    if value
                )
                target = "background" if "background" in asset_role or "backdrop" in asset_role else "visual"
                scene_type = "image"
            else:
                target = "content"
                scene_type = "text"
            item = content_by_id.get(element.content_reference or "")
            if item and item.priority == ContentPriority.CTA:
                layers["content"]["elements"].append({
                    "id": f"button-{element.id}",
                    "type": "rectangle",
                    "name": "CTA button",
                    "placement": {**bounds, "x": bounds["x"] - 18, "y": bounds["y"] - 10, "width": bounds["width"] + 36, "height": bounds["height"] + 20},
                    "style": {"fill": specification.color_system.cta or specification.color_system.accent or palette[-1], "stroke": specification.color_system.text or "#111111", "stroke_width": 2},
                    "geometry": {"corner_radius": 18},
                })
            style = {"fill": self._text_color(specification, item.priority if item else None)}
            scene_element: Dict[str, Any] = {
                "id": element.id,
                "type": scene_type,
                "name": element.role,
                "content": item.value if item else None,
                "requirement_reference": item.value if item else None,
                "placement": bounds,
                "style": style,
                "typography": self._typography(specification, item.priority if item else None),
                "geometry": {},
            }
            if element.type == LayoutElementType.IMAGE and specification.asset_strategy.assets:
                asset = specification.asset_strategy.assets[0]
                scene_element["asset_uri"] = next(
                    (reference.uri for reference in specification.assets if reference.kind == asset.asset_type and reference.uri),
                    None,
                )
                scene_element["fit"] = element.fit or "contain"
            layers[target]["elements"].append(scene_element)
        return PlannerGraphicExecutionSpec(
            document={"width": layout.canvas.width, "height": layout.canvas.height, "unit": "px", "color_mode": "RGB", "background_color": background},
            palette=[{"name": f"color-{index + 1}", "value": color} for index, color in enumerate(palette)],
            assets=[asset.model_dump(mode="json") for asset in specification.assets],
            layers=list(layers.values()),
        ).model_dump(mode="json")

    @staticmethod
    def _planned_regions(specification, safe: NormalizedBounds) -> List[LayoutRegion] | None:
        """Use planner-supplied normalized regions when they are complete."""
        raw_regions = (specification.layout_plan or {}).get("regions")
        if not isinstance(raw_regions, list):
            return None
        aliases = {
            "headline": "primary", "title": "primary", "body": "supporting",
            "details": "supporting", "button": "action", "cta": "action",
            "image": "visual", "hero": "visual",
        }
        parsed: dict[str, LayoutRegion] = {}
        for raw in raw_regions:
            if not isinstance(raw, dict):
                continue
            raw_id = str(raw.get("id") or raw.get("role") or "").strip().lower().replace(" ", "-")
            if not raw_id:
                continue
            region_id = aliases.get(raw_id, raw_id)
            bounds = raw.get("bounds") if isinstance(raw.get("bounds"), dict) else raw
            try:
                normalized = NormalizedBounds(
                    x=float(bounds.get("x")),
                    y=float(bounds.get("y")),
                    width=float(bounds.get("width")),
                    height=float(bounds.get("height")),
                )
            except (TypeError, ValueError):
                continue
            parsed[region_id] = LayoutRegion(
                id=region_id,
                purpose=str(raw.get("purpose") or raw.get("role") or region_id),
                bounds=normalized,
                priority=int(raw.get("priority") or 3),
                alignment=str(raw.get("alignment") or "center"),
                allow_overlap=bool(raw.get("allow_overlap", region_id == "visual")),
            )
        if not {"primary", "supporting", "action"}.issubset(parsed):
            return None
        if "background" not in parsed:
            parsed["background"] = LayoutRegion(
                id="background", purpose="canvas background",
                bounds=NormalizedBounds(x=0, y=0, width=1, height=1),
                priority=1, alignment="center",
            )
        ordered = ["background", "visual", "primary", "supporting", "action"]
        return [parsed[key] for key in ordered if key in parsed] + [
            region for key, region in parsed.items() if key not in ordered
        ]

    @staticmethod
    def _planned_visual_elements(specification, layout, palette):
        """Translate planner visual intents into renderer-neutral scene elements."""
        raw_elements = specification.visual_elements
        if not isinstance(raw_elements, list) or not raw_elements:
            return []
        regions = {region.id: region for region in layout.regions}
        colors = {
            "background": specification.color_system.background,
            "surface": specification.color_system.surface,
            "primary": specification.color_system.primary,
            "secondary": specification.color_system.secondary,
            "accent": specification.color_system.accent,
            "text": specification.color_system.text,
            "muted_text": specification.color_system.muted_text,
            "cta": specification.color_system.cta,
            "border": specification.color_system.border,
        }
        result = []
        for index, raw in enumerate(raw_elements):
            if not isinstance(raw, dict):
                continue
            region_id = str(raw.get("region") or "").strip().lower().replace(" ", "-")
            region = regions.get(region_id)
            bounds = raw.get("bounds") if isinstance(raw.get("bounds"), dict) else raw
            values = None
            if isinstance(bounds, dict) and all(bounds.get(key) is not None for key in ("x", "y", "width", "height")):
                try:
                    values = {key: float(bounds[key]) for key in ("x", "y", "width", "height")}
                except (TypeError, ValueError):
                    values = None
            if values is None and region is not None:
                values = region.bounds.model_dump()
            if values is None:
                continue
            normalized_values = all(0 <= values[key] <= 1 for key in ("x", "y", "width", "height"))
            placement = (
                LayoutCompiler._actual_bounds(NormalizedBounds(**values), layout.canvas.width, layout.canvas.height)
                if normalized_values
                else values
            )
            kind = str(raw.get("type") or raw.get("kind") or "shape").lower()
            if kind == "button":
                kind = "rectangle"
            if kind in {"circle", "ellipse"}:
                kind = "ellipse"
            style = dict(raw.get("style") or {}) if isinstance(raw.get("style"), dict) else {}
            fill = raw.get("fill") or colors.get(str(raw.get("fill_role") or "").lower())
            stroke = raw.get("stroke") or colors.get(str(raw.get("stroke_role") or "").lower())
            if fill is not None:
                style["fill"] = fill
            if stroke is not None:
                style["stroke"] = stroke
            if kind == "line" and "fill" not in style:
                style["fill"] = "none"
            if raw.get("opacity") is not None:
                style["opacity"] = raw["opacity"]
            geometry = dict(raw.get("geometry") or {}) if isinstance(raw.get("geometry"), dict) else {}
            if "corner_radius" in geometry and normalized_values and float(geometry["corner_radius"]) <= 1:
                geometry["corner_radius"] = float(geometry["corner_radius"]) * min(layout.canvas.width, layout.canvas.height)
            element = {
                "id": str(raw.get("id") or f"planned-element-{index + 1}"),
                "type": kind,
                "name": str(raw.get("role") or raw.get("name") or kind),
                "placement": placement,
                "style": style,
                "geometry": geometry,
            }
            for key in ("content", "content_reference", "requirement_reference", "href", "asset_uri", "fit", "typography"):
                if raw.get(key) is not None:
                    element[key] = raw[key]
            layer = str(raw.get("layer") or "decorative").strip().lower().replace(" ", "-")
            result.append((layer, element))
        return result

    @staticmethod
    def _decorative_elements(specification, layout, palette):
        """Compile only decorative forms explicitly implied by the plan.

        The compiler intentionally does not own a poster template.  A planner
        can request geometric forms, lines, framing, or a restrained/no
        decoration treatment through its art-direction and decorative intent.
        When it does not, the content and background are rendered without
        invented ornaments.
        """
        width, height = layout.canvas.width, layout.canvas.height
        accent = specification.color_system.accent or palette[min(1, len(palette) - 1)]
        secondary = specification.color_system.secondary or palette[min(2, len(palette) - 1)]
        intent = LayoutCompiler._intent_text(specification)
        if LayoutCompiler._mentions(intent, "no decoration", "no decorative", "undecorated", "plain"):
            return []

        elements = []
        strategy = (layout.composition_strategy or "").lower()
        if LayoutCompiler._mentions(intent, "circle", "circular", "orb", "ellipse", "bubble", "glow"):
            size = min(width, height) * (0.18 if "focal" in strategy else 0.14)
            elements.append({
                "id": "decorative-circle",
                "type": "ellipse",
                "name": "planned circular accent",
                "placement": {"x": width * 0.72 - size / 2, "y": height * 0.18 - size / 2, "width": size, "height": size},
                "style": {"fill": accent, "opacity": 0.22, "stroke": accent, "stroke_width": max(2, width * 0.004)},
            })
        if LayoutCompiler._mentions(intent, "line", "lines", "linework", "diagonal", "ribbon", "rule", "path"):
            direction = -1 if LayoutCompiler._mentions(intent, "diagonal", "ascending", "upward") else 1
            elements.append({
                "id": "decorative-line",
                "type": "line",
                "name": "planned directional line",
                "placement": {"x": width * 0.08, "y": height * (0.78 if direction < 0 else 0.22), "width": width * 0.84, "height": direction * height * 0.26},
                "style": {"fill": "none", "stroke": secondary, "stroke_width": max(2, width * 0.005), "opacity": 0.72},
            })
        if LayoutCompiler._mentions(intent, "geometric", "geometry", "diamond", "polygon", "triangle", "angular"):
            center_x = width * (0.78 if "split" in strategy else 0.84)
            center_y = height * (0.72 if "whitespace" not in strategy else 0.84)
            size = min(width, height) * 0.08
            elements.append({
                "id": "decorative-polygon",
                "type": "polygon",
                "name": "planned geometric accent",
                "placement": {"x": center_x - size, "y": center_y - size, "width": size * 2, "height": size * 2},
                "style": {"fill": accent, "stroke": secondary, "stroke_width": 2, "opacity": 0.9},
                "geometry": {"points": [center_x, center_y - size, center_x + size, center_y, center_x, center_y + size, center_x - size, center_y]},
            })
        if LayoutCompiler._mentions(intent, "frame", "border", "panel", "outline"):
            margin = min(width, height) * 0.06
            elements.append({
                "id": "decorative-frame",
                "type": "rectangle",
                "name": "planned frame",
                "placement": {"x": margin, "y": margin, "width": width - margin * 2, "height": height - margin * 2},
                "style": {"fill": "none", "stroke": secondary, "stroke_width": max(1, width * 0.002), "opacity": 0.65},
                "geometry": {"corner_radius": min(width, height) * 0.02},
            })
        return elements

    @staticmethod
    def _background_style(specification, background, palette):
        """Return the planner-selected background treatment.

        A solid fill is the neutral default.  This prevents the renderer from
        silently turning every design into a gradient while still allowing an
        explicit planner decision to produce one.
        """
        intent = LayoutCompiler._intent_text(specification)
        treatment = str(specification.color_system.background_treatment or "").lower()
        explicitly_gradient = "gradient" in treatment or "gradient" in intent
        explicitly_solid = treatment in {"solid", "flat", "flat_color"} or LayoutCompiler._mentions(intent, "no gradient", "solid background", "flat color", "solid fill")
        if explicitly_gradient and not explicitly_solid and len(palette) > 1:
            return {"fill": {"type": "linear", "stops": [{"offset": "0%", "color": background}, {"offset": "100%", "color": palette[1]}]}}
        return {"fill": background}

    @staticmethod
    def _intent_text(specification) -> str:
        values = [
            specification.brief.context,
            specification.brief.visual_mood,
            specification.brief.preferred_style,
            specification.concept,
            specification.art_direction.style,
            specification.art_direction.visual_language,
            specification.art_direction.shape_language,
            specification.art_direction.decorative_direction,
            specification.art_direction.texture,
            specification.art_direction.depth,
            specification.composition.strategy,
            specification.composition.visual_flow,
            specification.composition.negative_space,
            specification.color_system.background_treatment,
            *specification.user_requirements,
            *specification.designer_decisions,
        ]
        values.extend(str(value) for value in specification.art_direction.attributes.values())
        values.extend(str(value) for value in specification.color_system.additional_roles.values())
        return " ".join(str(value) for value in values if value).lower()

    @staticmethod
    def _mentions(text: str, *terms: str) -> bool:
        return any(re.search(rf"(?<!\w){re.escape(term.lower())}(?!\w)", text) for term in terms)

    @staticmethod
    def _normalize_strategy(value: str | None, design_type: str | None = None) -> str:
        text = f"{value or ''} {design_type or ''}".lower().replace("-", "_")
        if any(token in text for token in ("banner", "wide", "horizontal", "split", "asymmetric", "diagonal")):
            return "split"
        if any(token in text for token in ("certificate", "formal", "whitespace", "generous")):
            return "whitespace_driven"
        if any(token in text for token in ("infographic", "modular", "grid", "sequence", "educational")):
            return "modular"
        if any(token in text for token in ("product_led", "product", "image_led")):
            return "image_led"
        if "focal_centered" in text or "focal" in text or "thumbnail" in text or "social" in text:
            return "focal_centered"
        if any(token in text for token in ("centered", "invitation", "event")):
            return "centered"
        return (value or "intent-driven").lower().replace(" ", "_")

    @staticmethod
    def _regions(specification, strategy: str, safe: NormalizedBounds) -> List[LayoutRegion]:
        """Resolve regions from planner intent instead of a fixed poster grid."""
        composition = specification.composition
        intent = LayoutCompiler._intent_text(specification)
        placement = " ".join(
            str(value or "")
            for value in (
                composition.focal_placement,
                specification.visual_hierarchy.primary_focal_point,
                specification.visual_hierarchy.primary_visual_anchor,
                composition.alignment,
                composition.visual_flow,
            )
        ).lower()
        content_count = max(1, len(specification.content_hierarchy))
        dense = LayoutCompiler._mentions(f"{composition.density or ''} {intent}", "dense", "compact", "information-rich")
        generous = LayoutCompiler._mentions(f"{composition.negative_space or ''} {intent}", "generous", "airy", "whitespace", "breathing room")

        side_composition = strategy in {"split", "image_led"} or any(
            LayoutCompiler._mentions(placement, term) for term in ("left", "right", "side", "asymmetric")
        )
        primary_height = 0.18 if dense else 0.25 if generous else 0.22
        primary_height = min(0.36, primary_height + min(content_count, 4) * 0.018)

        if side_composition:
            primary_width = 0.38 if dense else 0.46
            visual_width = 0.30 if dense else 0.36
            visual_height = 0.52 if dense else 0.62
            visual_on_left = LayoutCompiler._mentions(placement, "visual left", "image left", "left visual", "left side")
            if visual_on_left:
                visual = NormalizedBounds(x=safe.x, y=0.16, width=visual_width, height=visual_height)
                primary_x = 1.0 - safe.x - primary_width
            else:
                primary_x = safe.x
                visual = NormalizedBounds(x=1.0 - safe.x - visual_width, y=0.16, width=visual_width, height=visual_height)
            primary = NormalizedBounds(x=primary_x, y=0.25, width=primary_width, height=primary_height + 0.18)
        elif LayoutCompiler._mentions(placement, "top", "upper"):
            primary_width = 0.74 if generous else 0.84
            primary = NormalizedBounds(x=(1.0 - primary_width) / 2, y=safe.y, width=primary_width, height=primary_height)
            visual = NormalizedBounds(x=0.20, y=0.50, width=0.60, height=0.24 if not dense else 0.18)
        elif LayoutCompiler._mentions(placement, "bottom", "lower"):
            primary_width = 0.74 if generous else 0.84
            primary = NormalizedBounds(x=(1.0 - primary_width) / 2, y=0.60, width=primary_width, height=primary_height)
            visual = NormalizedBounds(x=0.20, y=0.12, width=0.60, height=0.24 if not dense else 0.18)
        else:
            primary_width = 0.68 if generous else 0.80 if dense else 0.74
            primary = NormalizedBounds(x=(1.0 - primary_width) / 2, y=0.27, width=primary_width, height=primary_height)
            visual = NormalizedBounds(x=0.22, y=0.10, width=0.56, height=0.16 if dense else 0.20)

        supporting_height = min(0.24, 0.08 + content_count * (0.018 if dense else 0.024))
        supporting_y = min(0.68, primary.y + primary.height + (0.035 if generous else 0.055))
        action_y = min(0.86, supporting_y + supporting_height + (0.025 if dense else 0.05))
        action_height = 0.08 if dense else 0.11
        return [
            LayoutRegion(id="background", purpose="canvas background", bounds=NormalizedBounds(x=0, y=0, width=1, height=1), priority=1, alignment="center"),
            LayoutRegion(id="visual", purpose="primary visual anchor", bounds=visual, priority=5, alignment="center", allow_overlap=True),
            LayoutRegion(id="primary", purpose="primary communication", bounds=primary, priority=5, alignment=composition.alignment or "center"),
            LayoutRegion(id="supporting", purpose="secondary and supporting content", bounds=NormalizedBounds(x=safe.x, y=supporting_y, width=safe.width, height=supporting_height), priority=3, alignment=composition.alignment or "center"),
            LayoutRegion(id="action", purpose="call to action and metadata", bounds=NormalizedBounds(x=0.22, y=action_y, width=0.56, height=action_height), priority=4, alignment=composition.alignment or "center"),
        ]

    @staticmethod
    def _apply_overrides(regions: List[LayoutRegion], overrides: Dict[str, Dict[str, float | str]]) -> List[LayoutRegion]:
        """Apply bounded semantic adjustments before elements are compiled."""
        result = []
        for region in regions:
            override = overrides.get(region.id, {})
            bounds = region.bounds
            dx = float(override.get("dx", 0))
            scale = float(override.get("scale", 1))
            width = min(1.0 - bounds.x, bounds.width * scale)
            height = min(1.0 - bounds.y, bounds.height * scale)
            x = max(0.0, min(1.0 - width, bounds.x + dx))
            y = max(0.0, min(1.0 - height, bounds.y))
            result.append(region.model_copy(update={
                "bounds": NormalizedBounds(x=x, y=y, width=max(0.001, width), height=max(0.001, height)),
                "alignment": override.get("alignment", region.alignment),
                "spacing": str(override.get("spacing", region.spacing)) if "spacing" in override else region.spacing,
            }))
        return result

    @staticmethod
    def _region_for_priority(priority, regions):
        if priority == ContentPriority.PRIMARY:
            return "primary"
        if priority == ContentPriority.CTA:
            return "action"
        if priority in {ContentPriority.METADATA, ContentPriority.SUPPORTING}:
            return "supporting"
        return "supporting"

    @staticmethod
    def _content_bounds(region: NormalizedBounds, priority, index: int, total: int) -> NormalizedBounds:
        if priority == ContentPriority.PRIMARY:
            return region
        row_height = min(region.height, max(0.06, region.height / max(1, total)))
        y = min(region.y + index * row_height, region.y + region.height - row_height)
        return NormalizedBounds(x=region.x, y=y, width=region.width, height=row_height)

    @staticmethod
    def _relationships(elements, content_items):
        relationships: List[LayoutRelationship] = []
        ordered = [element for element in elements if element.content_reference]
        for previous, current in zip(ordered, ordered[1:]):
            relationships.append(LayoutRelationship(source_id=previous.id, relationship="above_or_before", target_id=current.id))
        return relationships

    @staticmethod
    def _grid(specification, strategy):
        if strategy in {"grid", "editorial", "modular", "card_based"}:
            return LayoutGrid(columns=12, rows=12, gutters=0.02, outer_margin=0.08, inner_padding=0.02, baseline_alignment="content rhythm")
        return LayoutGrid(outer_margin=0.08, inner_padding=0.02)

    @staticmethod
    def _actual_bounds(bounds, width, height):
        return {"x": round(bounds.x * width, 2), "y": round(bounds.y * height, 2), "width": round(bounds.width * width, 2), "height": round(bounds.height * height, 2)}

    @staticmethod
    def _palette(specification):
        colors = []
        system = specification.color_system
        for value in (system.background, system.surface, system.primary, system.secondary, system.accent, system.text, system.cta):
            if value and value not in colors:
                colors.append(value)
        colors.extend(value for value in system.required_colors if value not in colors)
        return colors[:6] or ["#ffffff", "#111111"]

    @staticmethod
    def _text_color(specification, priority):
        if priority == ContentPriority.CTA and specification.color_system.cta:
            return specification.color_system.cta
        return specification.color_system.text or "#111111"

    @staticmethod
    def _typography(specification, priority):
        if priority == ContentPriority.PRIMARY and specification.typography.display:
            level = specification.typography.display
        elif specification.typography.body:
            level = specification.typography.body
        else:
            level = None
        if level is None:
            return {}
        sizes = {"largest": 72, "prominent": 48, "medium": 32, "readable": 24, "small": 18, "compact": 16}
        return {
            "font_family": "sans-serif",
            "font_size": level.font_size or sizes.get(level.scale or "readable", 24),
            "font_weight": level.weight or "400",
            "text_align": level.alignment or "middle",
            "letter_spacing": level.letter_spacing_value,
            "line_height": level.line_height_value or 1.2,
        }

"""Renderer-facing SVG compilation and safe native serialization."""

from __future__ import annotations

import html
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List
from urllib.parse import urlparse

from packages.graphic_agent.rendering.colors import normalize_color


class SvgStructuralValidationError(ValueError):
    """Raised when trusted renderer output is structurally invalid."""


@dataclass(frozen=True)
class SvgRenderSpecification:
    width: int
    height: int
    layers: List[Dict[str, Any]]
    title: str = "Graphic design"
    description: str = ""
    required_text: List[str] | None = None


class SvgRenderCompiler:
    """Translate the existing execution scene into an SVG-facing model."""

    def compile(
        self,
        execution_spec: Dict[str, Any],
        *,
        title: str = "Graphic design",
        description: str = "",
        required_text: Iterable[str] = (),
    ) -> SvgRenderSpecification:
        document = execution_spec.get("document") or {}
        width = int(document.get("width") or 1080)
        height = int(document.get("height") or 1080)
        if width <= 0 or height <= 0:
            raise SvgStructuralValidationError("SVG document dimensions must be positive")
        layers = execution_spec.get("layers") or []
        if not isinstance(layers, list):
            raise SvgStructuralValidationError("SVG execution layers must be a list")
        return SvgRenderSpecification(
            width=width,
            height=height,
            layers=[layer for layer in layers if isinstance(layer, dict)],
            title=title,
            description=description,
            required_text=list(required_text),
        )


class SvgRenderer:
    """Serialize native editable SVG without making design decisions."""

    _layer_order = {"background": 0, "decorative": 10, "visual": 20, "imagery": 20, "content": 30, "foreground": 40, "accent": 50}

    @staticmethod
    def validate_required_asset_layers(svg: str, assets: Iterable[Any]) -> None:
        """Ensure every uploaded image is represented by an SVG image layer."""
        if not assets:
            return
        if "<image" not in svg.lower():
            raise SvgStructuralValidationError("Uploaded image asset layer is missing from SVG.")
        for asset in assets:
            uri = getattr(asset, "uri", None)
            if not uri:
                continue
            escaped_uri = html.escape(str(uri), quote=True)
            if str(uri) not in svg and escaped_uri not in svg:
                raise SvgStructuralValidationError(
                    f"Uploaded image asset {getattr(asset, 'description', None) or 'asset'} is missing from SVG."
                )
    def render(self, specification: SvgRenderSpecification) -> str:
        used_ids: set[str] = set()
        defs: List[str] = []
        rendered_layers: List[str] = []
        sorted_layers = sorted(
            specification.layers,
            key=lambda layer: (
                self._layer_order.get(str(layer.get("name") or "").lower(), 25),
                str(layer.get("id") or ""),
            ),
        )
        for layer in sorted_layers:
            layer_id = self._stable_id(layer.get("id") or layer.get("name") or "layer", used_ids)
            elements = layer.get("elements") or []
            if not isinstance(elements, list):
                raise SvgStructuralValidationError(f"layer {layer_id} elements must be a list")
            body: List[str] = []
            for element in sorted(
                (item for item in elements if isinstance(item, dict)),
                key=lambda item: int(item.get("z_index") or 0),
            ):
                rendered = self._element(element, used_ids, defs, specification.width, specification.height)
                if rendered:
                    body.append(rendered)
            if body:
                rendered_layers.append(
                    f'<g id="{layer_id}" data-design-role="layer" data-layer-name="{html.escape(str(layer.get("name") or ""))}">'
                    + "".join(body)
                    + "</g>"
                )
        defs_text = f'<defs>{"".join(defs)}</defs>' if defs else ""
        safe_title = html.escape(specification.title[:200])
        safe_description = html.escape(specification.description[:500])
        svg = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            f'<svg xmlns="http://www.w3.org/2000/svg" version="1.1" width="{specification.width}" height="{specification.height}" '
            f'viewBox="0 0 {specification.width} {specification.height}" role="img" aria-labelledby="title desc">'
            f'<title id="title">{safe_title}</title><desc id="desc">{safe_description}</desc>'
            f"{defs_text}{''.join(rendered_layers)}</svg>"
        )
        self.validate(svg, required_text=specification.required_text or [])
        return svg

    def validate(self, svg: str, *, required_text: Iterable[str] = ()) -> None:
        try:
            root = ET.fromstring(svg)
        except ET.ParseError as exc:
            raise SvgStructuralValidationError(f"malformed SVG XML: {exc}") from exc
        if root.tag.rsplit("}", 1)[-1] != "svg":
            raise SvgStructuralValidationError("SVG root element is missing")
        if not root.attrib.get("viewBox") or not root.attrib.get("width") or not root.attrib.get("height"):
            raise SvgStructuralValidationError("SVG width, height, and viewBox are required")
        ids: set[str] = set()
        for element in root.iter():
            element_id = element.attrib.get("id")
            if element_id:
                if element_id in ids:
                    raise SvgStructuralValidationError(f"duplicate SVG id: {element_id}")
                ids.add(element_id)
            for attr, value in element.attrib.items():
                if attr in {"href", "xlink:href"}:
                    self._validate_resource(value)
                if value.startswith("url(#") and not value.endswith(")"):
                    raise SvgStructuralValidationError(f"malformed SVG reference: {value}")
        text_content = " ".join(part.strip() for part in root.itertext() if part.strip())
        for value in required_text:
            if value not in text_content:
                raise SvgStructuralValidationError(f"required text missing from SVG: {value}")

    def _element(self, element: Dict[str, Any], used_ids: set[str], defs: List[str], width: int, height: int) -> str:
        kind = str(element.get("type") or "shape").lower()
        element_id = self._stable_id(element.get("id") or element.get("name") or kind, used_ids)
        attrs = self._semantic_attrs(element, element_id)
        placement = element.get("placement") or {}
        x = self._number(placement.get("x"), 0)
        y = self._number(placement.get("y"), 0)
        w = self._number(placement.get("width"), width)
        h = self._number(placement.get("height"), height)
        style = element.get("style") or {}
        geometry = element.get("geometry") or {}
        paint = self._paint(style, defs, element_id)
        common = f'{attrs} x="{x:g}" y="{y:g}" {paint}'
        transform = self._transform(element)
        if kind in {"background", "rectangle", "rect", "shape"}:
            radius = self._number(geometry.get("corner_radius"), 0)
            return f'<rect {common} width="{w:g}" height="{h:g}" rx="{radius:g}"{transform} />'
        if kind in {"circle", "ellipse"}:
            if kind == "circle":
                radius = min(w, h) / 2
                return f'<circle {attrs} cx="{x + w / 2:g}" cy="{y + h / 2:g}" r="{radius:g}" {paint}{transform} />'
            return f'<ellipse {attrs} cx="{x + w / 2:g}" cy="{y + h / 2:g}" rx="{w / 2:g}" ry="{h / 2:g}" {paint}{transform} />'
        if kind == "line":
            return f'<line {attrs} x1="{x:g}" y1="{y:g}" x2="{x + w:g}" y2="{y + h:g}" {paint}{transform} />'
        if kind in {"polygon", "polyline"}:
            points = geometry.get("points") or [x, y, x + w, y, x + w, y + h]
            point_text = " ".join(f"{float(points[i]):g},{float(points[i + 1]):g}" for i in range(0, len(points) - 1, 2))
            return f'<{kind} {attrs} points="{point_text}" {paint}{transform} />'
        if kind == "path":
            path_data = html.escape(str(element.get("content") or geometry.get("path") or ""), quote=True)
            if not path_data:
                return ""
            return f'<path {attrs} d="{path_data}" {paint}{transform} />'
        if kind == "image":
            href = element.get("href") or element.get("source") or element.get("asset_uri")
            if not href:
                return ""
            preserve = "xMidYMid slice" if element.get("fit") == "cover" else "xMidYMid meet"
            return f'<image {attrs} href="{html.escape(str(href), quote=True)}" width="{w:g}" height="{h:g}" preserveAspectRatio="{preserve}"{transform} />'
        if kind == "group":
            children = element.get("children") or []
            child_markup = "".join(self._element(child, used_ids, defs, width, height) for child in children if isinstance(child, dict))
            return f'<g {attrs}{transform}>{child_markup}</g>'
        if kind in {"text", "tspan", "badge", "label"} or element.get("content") is not None:
            return self._text(element, attrs, paint, x, y, w, h, transform)
        return f'<rect {common} width="{w:g}" height="{h:g}"{transform} />'

    @staticmethod
    def _text(element, attrs, paint, x, y, w, h, transform):
        typography = element.get("typography") or {}
        content = str(element.get("content") or "")
        font_family = html.escape(str(typography.get("font_family") or "sans-serif"), quote=True)
        font_size = SvgRenderer._number(typography.get("font_size"), 24)
        weight = html.escape(str(typography.get("font_weight") or "400"), quote=True)
        anchor = html.escape(str(typography.get("text_align") or "middle"), quote=True)
        letter_spacing = typography.get("letter_spacing")
        line_height = SvgRenderer._number(typography.get("line_height"), 1.2)
        casing = str(typography.get("casing") or "").lower()
        if casing == "uppercase":
            content = content.upper()
        lines = SvgRenderer._wrap(content, max_width=w, font_size=font_size)
        line_step = font_size * line_height if line_height <= 4 else line_height
        start_y = y + min(h, line_step) if len(lines) > 1 else y + h / 2
        attrs_text = f'{attrs} x="{x + w / 2:g}" y="{start_y:g}" text-anchor="{anchor}" font-family="{font_family}" font-size="{font_size:g}" font-weight="{weight}"'
        if letter_spacing is not None:
            attrs_text += f' letter-spacing="{html.escape(str(letter_spacing), quote=True)}"'
        body = "".join(
            f'<tspan x="{x + w / 2:g}" dy="{0 if index == 0 else line_step:g}">{html.escape(line)}</tspan>'
            for index, line in enumerate(lines)
        )
        return f'<text {attrs_text} {paint}{transform}>{body}</text>'

    @staticmethod
    def _wrap(content: str, max_width: float, font_size: float) -> List[str]:
        if max_width <= 0:
            return [content]
        max_chars = max(1, int(max_width / max(font_size * 0.55, 1)))
        lines: List[str] = []
        for paragraph in content.splitlines() or [""]:
            words = paragraph.split()
            if not words:
                lines.append("")
                continue
            current = words[0]
            for word in words[1:]:
                if len(current) + 1 + len(word) <= max_chars:
                    current += " " + word
                else:
                    lines.append(current)
                    current = word
            lines.append(current)
        return lines or [""]

    @staticmethod
    def _semantic_attrs(element, element_id):
        attrs = [f'id="{element_id}"']
        role = element.get("role") or element.get("name")
        if role:
            attrs.append(f'data-design-role="{html.escape(str(role), quote=True)}"')
        for source, target in (("content_reference", "data-content-reference"), ("region_reference", "data-region-reference"), ("requirement_reference", "data-requirement-reference")):
            if element.get(source):
                attrs.append(f'{target}="{html.escape(str(element[source]), quote=True)}"')
        return " ".join(attrs)

    @staticmethod
    def _paint(style, defs, element_id):
        fill = style.get("fill") or "none"
        stroke = style.get("stroke") or "none"
        opacity = style.get("opacity", 1)
        stroke_width = style.get("stroke_width")
        if isinstance(fill, dict) and fill.get("type") in {"linear", "radial"}:
            gradient_id = f"gradient-{element_id}"
            gradient_type = "linearGradient" if fill["type"] == "linear" else "radialGradient"
            stops = fill.get("stops") or []
            stop_markup = "".join(f'<stop offset="{html.escape(str(stop.get("offset", 0)), quote=True)}" stop-color="{html.escape(str(stop.get("color", "#000")), quote=True)}" />' for stop in stops if isinstance(stop, dict))
            defs.append(f'<{gradient_type} id="{gradient_id}">{stop_markup}</{gradient_type}>')
            fill = f"url(#{gradient_id})"
        elif isinstance(fill, str):
            fill = normalize_color(fill, fallback="#000000")
        if isinstance(stroke, str):
            stroke = normalize_color(stroke, fallback="none")
        result = f'fill="{html.escape(str(fill), quote=True)}" stroke="{html.escape(str(stroke), quote=True)}" opacity="{float(opacity):g}"'
        if stroke_width is not None:
            result += f' stroke-width="{html.escape(str(stroke_width), quote=True)}"'
        return result

    @staticmethod
    def _transform(element):
        transforms = element.get("transforms") or []
        if not transforms:
            return ""
        values = []
        for transform in transforms:
            if not isinstance(transform, dict):
                continue
            kind = str(transform.get("type") or "").lower()
            if kind not in {"translate", "scale", "rotate"}:
                continue
            arguments = transform.get("values") or []
            values.append(f'{kind}({" ".join(str(value) for value in arguments)})')
        return f' transform="{html.escape(" ".join(values), quote=True)}"' if values else ""

    @staticmethod
    def _stable_id(value, used_ids):
        base = re.sub(r"[^A-Za-z0-9_-]+", "-", str(value)).strip("-") or "element"
        candidate = base
        index = 2
        while candidate in used_ids:
            candidate = f"{base}-{index}"
            index += 1
        used_ids.add(candidate)
        return candidate

    @staticmethod
    def _number(value, default):
        try:
            return float(value) if value is not None else float(default)
        except (TypeError, ValueError):
            return float(default)

    @staticmethod
    def _validate_resource(value):
        parsed = urlparse(str(value))
        if parsed.scheme not in {"http", "https", "data"}:
            raise SvgStructuralValidationError(f"unsupported external SVG resource scheme: {parsed.scheme or 'none'}")
        if parsed.scheme == "data" and not str(value).lower().startswith("data:image/"):
            raise SvgStructuralValidationError("only data:image resources are allowed")

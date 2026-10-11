"""Small deterministic Pillow preview adapter for project SVG primitives."""

from __future__ import annotations

import html
import re
import xml.etree.ElementTree as ET
from pathlib import Path

from packages.graphic_agent.rendering.colors import normalize_color

from packages.verification.domain.visual import PreviewArtifact


_COLORS = {
    "white": "#ffffff", "black": "#111111", "red": "#ef4444", "blue": "#2563eb",
    "green": "#16a34a", "yellow": "#facc15", "navy": "#0b1020",
    "dark navy": "#0b1020", "electric blue": "#2563eb",
}


class PillowSvgPreviewRenderer:
    """Render basic trusted SVG primitives to PNG without browser dependencies."""

    def render(self, svg_text: str, *, source_artifact: str, output_reference: str) -> PreviewArtifact:
        try:
            from PIL import Image, ImageDraw, ImageFont
            root = ET.fromstring(svg_text)
            width = int(float(root.attrib.get("width", 0)))
            height = int(float(root.attrib.get("height", 0)))
            if width <= 0 or height <= 0:
                raise ValueError("SVG preview requires positive dimensions")
            image = Image.new("RGBA", (width, height), (255, 255, 255, 0))
            draw = ImageDraw.Draw(image)
            self._draw_children(root, draw, width, height, ImageFont)
            output_path = Path(output_reference)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            image.save(output_path, format="PNG")
            return PreviewArtifact(source_artifact=source_artifact, width=width, height=height, reference=str(output_path), render_status="success", metadata={"renderer": "pillow_svg_preview"})
        except Exception as exc:
            return PreviewArtifact(source_artifact=source_artifact, width=1, height=1, reference=None, render_status="failed", error=str(exc), metadata={"renderer": "pillow_svg_preview"})

    def _draw_children(self, parent, draw, width, height, font_module):
        for node in list(parent):
            tag = node.tag.rsplit("}", 1)[-1]
            if tag in {"title", "desc", "defs", "linearGradient", "radialGradient", "stop"}:
                continue
            if tag == "g":
                self._draw_children(node, draw, width, height, font_module)
                continue
            fill = self._color(node.attrib.get("fill"))
            stroke = self._color(node.attrib.get("stroke"))
            stroke_width = max(1, int(float(node.attrib.get("stroke-width", 1))))
            if tag == "rect":
                box = self._box(node)
                draw.rounded_rectangle(box, radius=int(float(node.attrib.get("rx", 0))), fill=fill, outline=stroke, width=stroke_width if stroke else 1)
            elif tag == "ellipse":
                box = (float(node.attrib.get("cx", 0)) - float(node.attrib.get("rx", 0)), float(node.attrib.get("cy", 0)) - float(node.attrib.get("ry", 0)), float(node.attrib.get("cx", 0)) + float(node.attrib.get("rx", 0)), float(node.attrib.get("cy", 0)) + float(node.attrib.get("ry", 0)))
                draw.ellipse(box, fill=fill, outline=stroke, width=stroke_width if stroke else 1)
            elif tag == "circle":
                cx, cy, radius = float(node.attrib.get("cx", 0)), float(node.attrib.get("cy", 0)), float(node.attrib.get("r", 0))
                draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), fill=fill, outline=stroke, width=stroke_width if stroke else 1)
            elif tag == "line":
                draw.line((float(node.attrib.get("x1", 0)), float(node.attrib.get("y1", 0)), float(node.attrib.get("x2", 0)), float(node.attrib.get("y2", 0))), fill=stroke or fill, width=stroke_width)
            elif tag in {"polygon", "polyline"}:
                points = self._points(node.attrib.get("points", ""))
                if points:
                    draw.polygon(points, fill=fill)
                    if stroke:
                        draw.line(points + ([points[0]] if tag == "polygon" else []), fill=stroke, width=stroke_width)
            elif tag == "text":
                text = "".join(node.itertext())
                size = int(float(node.attrib.get("font-size", 18)))
                try:
                    font = font_module.truetype("arial.ttf", size)
                except Exception:
                    font = font_module.load_default()
                draw.text((float(node.attrib.get("x", 0)), float(node.attrib.get("y", 0)) - size), text, fill=fill or "#111111", font=font, anchor="ms")

    @staticmethod
    def _box(node):
        x, y = float(node.attrib.get("x", 0)), float(node.attrib.get("y", 0))
        w, h = float(node.attrib.get("width", 0)), float(node.attrib.get("height", 0))
        return x, y, x + w, y + h

    @staticmethod
    def _points(value):
        numbers = [float(item) for item in re.findall(r"-?\d+(?:\.\d+)?", value)]
        return [(numbers[index], numbers[index + 1]) for index in range(0, len(numbers) - 1, 2)]

    @staticmethod
    def _color(value):
        if not value or value == "none" or value.startswith("url("):
            return None
        return normalize_color(_COLORS.get(value.lower(), value), fallback="#000000")

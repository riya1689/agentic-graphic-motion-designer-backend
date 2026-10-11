"""
Dynamic Illustrator JSX Generator

GraphicExecutionSpec -> Adobe Illustrator JSX

IMPORTANT:
- No hardcoded poster template
- No hardcoded title
- No hardcoded canvas size
- No LLM call
- Planner JSON is metadata only
- GraphicExecutionSpec controls actual rendering
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from packages.graphic_agent.compiler.execution_spec import (
    GraphicElementSpec,
    GraphicExecutionSpec,
    GraphicPlacementSpec,
)


# ============================================================
# HELPERS
# ============================================================

def _escape_js_string(
    value: Optional[str],
) -> str:

    if value is None:
        return ""

    return (
        str(value)
        .replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\r", "")
        .replace("\n", "\\n")
    )


def _hex_to_rgb(
    color: Optional[str],
) -> Tuple[int, int, int]:

    if not color:
        return 0, 0, 0

    value = color.strip().lstrip("#")

    if len(value) != 6:
        return 0, 0, 0

    try:

        return (
            int(value[0:2], 16),
            int(value[2:4], 16),
            int(value[4:6], 16),
        )

    except ValueError:

        return 0, 0, 0


def _resolve_position(
    placement: GraphicPlacementSpec,
    document_width: float,
    document_height: float,
) -> Tuple[float, float]:

    if (
        placement.x is not None
        and
        placement.y is not None
    ):
        return (
            placement.x,
            placement.y,
        )

    anchor = placement.anchor or "center"

    margin_x = document_width * 0.08
    margin_y = document_height * 0.08

    positions = {

        "top_left":
            (
                margin_x,
                document_height - margin_y,
            ),

        "top_center":
            (
                document_width * 0.5,
                document_height - margin_y,
            ),

        "top_right":
            (
                document_width - margin_x,
                document_height - margin_y,
            ),

        "center_left":
            (
                margin_x,
                document_height * 0.5,
            ),

        "center":
            (
                document_width * 0.5,
                document_height * 0.5,
            ),

        "center_right":
            (
                document_width - margin_x,
                document_height * 0.5,
            ),

        "bottom_left":
            (
                margin_x,
                margin_y,
            ),

        "bottom_center":
            (
                document_width * 0.5,
                margin_y,
            ),

        "bottom_right":
            (
                document_width - margin_x,
                margin_y,
            ),
    }

    return positions.get(
        anchor,
        positions["center"],
    )


# ============================================================
# GENERATOR
# ============================================================

class IllustratorJSXGenerator:

    tool_id = "illustrator_jsx"


    def generate(
        self,
        *,
        job_id: str,
        planner_plan: Dict[str, Any],
        execution_spec: GraphicExecutionSpec,
        output_path: Path,
    ) -> Dict[str, Any]:

        output_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        planner_json = json.dumps(
            planner_plan,
            ensure_ascii=False,
        )

        escaped_plan = _escape_js_string(
            planner_json
        )

        width = execution_spec.document.width
        height = execution_spec.document.height

        jsx_parts = [

            self._build_header(
                job_id=job_id,
            ),

            self._build_document(
                width=width,
                height=height,
                color_mode=(
                    execution_spec
                    .document
                    .color_mode
                ),
            ),
        ]


        # ====================================================
        # RENDER LAYERS
        # ====================================================

        for layer_index, layer in enumerate(
            execution_spec.layers
        ):

            variable_name = (
                f"layer_{layer_index}"
            )

            jsx_parts.append(
                f"""
// ============================================================
// LAYER: {_escape_js_string(layer.name)}
// ============================================================

var {variable_name} = doc.layers.add();

{variable_name}.name =
    "{_escape_js_string(layer.name)}";

{variable_name}.visible =
    {"true" if layer.visible else "false"};

{variable_name}.locked =
    {"true" if layer.locked else "false"};
"""
            )

            for element_index, element in enumerate(
                layer.elements
            ):

                jsx_parts.append(
                    self._render_element(
                        element=element,
                        layer_variable=variable_name,
                        variable_suffix=(
                            f"{layer_index}_{element_index}"
                        ),
                        document_width=width,
                        document_height=height,
                    )
                )


        # ====================================================
        # METADATA LAYER
        # ====================================================

        jsx_parts.append(
            self._build_metadata_layer(
                planner_json=escaped_plan,
            )
        )


        # ====================================================
        # FINISH
        # ====================================================

        jsx_parts.append(
            """
    app.redraw();

    alert(
        "NGX Illustrator fallback generated successfully."
    );

})();
"""
        )


        jsx_code = "\n".join(
            jsx_parts
        )


        output_path.write_text(
            jsx_code,
            encoding="utf-8",
        )


        return {
            "success": True,
            "tool": self.tool_id,
            "output_path": str(output_path),
            "document_width": width,
            "document_height": height,
            "layer_count": len(
                execution_spec.layers
            ),
        }


    # ========================================================
    # HEADER
    # ========================================================

    def _build_header(
        self,
        *,
        job_id: str,
    ) -> str:

        return f"""
// ============================================================
// NGX GRAPHIC AGENT
// DYNAMIC ILLUSTRATOR FALLBACK
//
// Job ID: {_escape_js_string(job_id)}
//
// GraphicExecutionSpec -> Illustrator JSX
// ============================================================

#target illustrator

(function () {{
"""


    # ========================================================
    # DOCUMENT
    # ========================================================

    def _build_document(
        self,
        *,
        width: float,
        height: float,
        color_mode: str,
    ) -> str:

        illustrator_mode = (
            "DocumentColorSpace.CMYK"
            if color_mode.upper() == "CMYK"
            else
            "DocumentColorSpace.RGB"
        )

        return f"""
// ============================================================
// DOCUMENT
// ============================================================

var doc = app.documents.add(
    {illustrator_mode},
    {width},
    {height}
);
"""


    # ========================================================
    # ELEMENT ROUTER
    # ========================================================

    def _render_element(
        self,
        *,
        element: GraphicElementSpec,
        layer_variable: str,
        variable_suffix: str,
        document_width: float,
        document_height: float,
    ) -> str:

        element_type = element.type


        if element_type == "background":

            return self._render_rectangle(
                element=element,
                layer_variable=layer_variable,
                variable_suffix=variable_suffix,
                document_width=document_width,
                document_height=document_height,
                force_full_canvas=True,
            )


        if element_type == "rectangle":

            return self._render_rectangle(
                element=element,
                layer_variable=layer_variable,
                variable_suffix=variable_suffix,
                document_width=document_width,
                document_height=document_height,
            )


        if element_type == "text":

            return self._render_text(
                element=element,
                layer_variable=layer_variable,
                variable_suffix=variable_suffix,
                document_width=document_width,
                document_height=document_height,
            )


        if element_type == "ellipse":

            return self._render_ellipse(
                element=element,
                layer_variable=layer_variable,
                variable_suffix=variable_suffix,
                document_width=document_width,
                document_height=document_height,
            )


        if element_type == "line":

            return self._render_line(
                element=element,
                layer_variable=layer_variable,
                variable_suffix=variable_suffix,
                document_width=document_width,
                document_height=document_height,
            )


        if element_type in (
            "product_illustration",
            "decorative_vector",
            "logo",
            "image",
            "icon",
            "path",
            "group",
            "custom",
        ):

            return self._render_semantic_element(
                element=element,
                layer_variable=layer_variable,
                variable_suffix=variable_suffix,
                document_width=document_width,
                document_height=document_height,
            )


        return (
            "\n// Unsupported element type: "
            + _escape_js_string(
                element_type
            )
            + "\n"
        )


    # ========================================================
    # TEXT
    # ========================================================

    def _render_text(
        self,
        *,
        element: GraphicElementSpec,
        layer_variable: str,
        variable_suffix: str,
        document_width: float,
        document_height: float,
    ) -> str:

        x, y = _resolve_position(
            element.placement,
            document_width,
            document_height,
        )

        content = _escape_js_string(
            element.content
            or
            element.name
            or
            ""
        )

        font_size = (
            element.style.font_size
            or
            max(
                18,
                document_width * 0.055,
            )
        )

        fill = (
            element.style.fill
            or
            "#FFFFFF"
        )

        red, green, blue = (
            _hex_to_rgb(fill)
        )

        variable = (
            f"text_{variable_suffix}"
        )

        color_variable = (
            f"textColor_{variable_suffix}"
        )

        jsx = f"""
// TEXT: {_escape_js_string(element.id)}

var {variable} =
    {layer_variable}.textFrames.add();

{variable}.contents =
    "{content}";

{variable}.position = [
    {x},
    {y}
];

{variable}.textRange.characterAttributes.size =
    {font_size};

var {color_variable} =
    new RGBColor();

{color_variable}.red = {red};
{color_variable}.green = {green};
{color_variable}.blue = {blue};

{variable}.textRange.characterAttributes.fillColor =
    {color_variable};
"""


        # ----------------------------------------------------
        # TEXT ALIGNMENT
        # ----------------------------------------------------

        alignment = (
            element.style.text_align
        )

        if (
            alignment == "center"
            or
            element.placement.anchor in (
                "top_center",
                "center",
                "bottom_center",
            )
        ):

            jsx += f"""
{variable}.paragraphs[0].paragraphAttributes.justification =
    Justification.CENTER;
"""


        elif alignment == "right":

            jsx += f"""
{variable}.paragraphs[0].paragraphAttributes.justification =
    Justification.RIGHT;
"""


        return jsx


    # ========================================================
    # RECTANGLE / BACKGROUND
    # ========================================================

    def _render_rectangle(
        self,
        *,
        element: GraphicElementSpec,
        layer_variable: str,
        variable_suffix: str,
        document_width: float,
        document_height: float,
        force_full_canvas: bool = False,
    ) -> str:

        if force_full_canvas:

            x = 0
            y = document_height

            width = document_width
            height = document_height

        else:

            x, center_y = _resolve_position(
                element.placement,
                document_width,
                document_height,
            )

            width = (
                element.placement.width
                or
                document_width * 0.3
            )

            height = (
                element.placement.height
                or
                document_height * 0.15
            )

            y = center_y


        fill = (
            element.style.fill
            or
            "#000000"
        )

        red, green, blue = (
            _hex_to_rgb(fill)
        )

        variable = (
            f"rect_{variable_suffix}"
        )

        color_variable = (
            f"rectColor_{variable_suffix}"
        )

        return f"""
// RECTANGLE: {_escape_js_string(element.id)}

var {variable} =
    {layer_variable}.pathItems.rectangle(
        {y},
        {x},
        {width},
        {height}
    );

var {color_variable} =
    new RGBColor();

{color_variable}.red = {red};
{color_variable}.green = {green};
{color_variable}.blue = {blue};

{variable}.fillColor =
    {color_variable};

{variable}.stroked = false;

{variable}.opacity =
    {element.style.opacity * 100};
"""


    # ========================================================
    # ELLIPSE
    # ========================================================

    def _render_ellipse(
        self,
        *,
        element: GraphicElementSpec,
        layer_variable: str,
        variable_suffix: str,
        document_width: float,
        document_height: float,
    ) -> str:

        x, y = _resolve_position(
            element.placement,
            document_width,
            document_height,
        )

        width = (
            element.placement.width
            or
            document_width * 0.15
        )

        height = (
            element.placement.height
            or
            width
        )

        fill = (
            element.style.fill
            or
            "#FFFFFF"
        )

        red, green, blue = (
            _hex_to_rgb(fill)
        )

        variable = (
            f"ellipse_{variable_suffix}"
        )

        color_variable = (
            f"ellipseColor_{variable_suffix}"
        )

        return f"""
// ELLIPSE: {_escape_js_string(element.id)}

var {variable} =
    {layer_variable}.pathItems.ellipse(
        {y},
        {x},
        {width},
        {height}
    );

var {color_variable} =
    new RGBColor();

{color_variable}.red = {red};
{color_variable}.green = {green};
{color_variable}.blue = {blue};

{variable}.fillColor =
    {color_variable};

{variable}.stroked = false;

{variable}.opacity =
    {element.style.opacity * 100};
"""


    # ========================================================
    # LINE
    # ========================================================

    def _render_line(
        self,
        *,
        element: GraphicElementSpec,
        layer_variable: str,
        variable_suffix: str,
        document_width: float,
        document_height: float,
    ) -> str:

        x, y = _resolve_position(
            element.placement,
            document_width,
            document_height,
        )

        length = (
            element.placement.width
            or
            document_width * 0.25
        )

        stroke = (
            element.style.stroke
            or
            element.style.fill
            or
            "#FFFFFF"
        )

        red, green, blue = (
            _hex_to_rgb(stroke)
        )

        stroke_width = (
            element.style.stroke_width
            or
            2
        )

        variable = (
            f"line_{variable_suffix}"
        )

        color_variable = (
            f"lineColor_{variable_suffix}"
        )

        return f"""
// LINE: {_escape_js_string(element.id)}

var {variable} =
    {layer_variable}.pathItems.add();

{variable}.setEntirePath([
    [{x}, {y}],
    [{x + length}, {y}]
]);

var {color_variable} =
    new RGBColor();

{color_variable}.red = {red};
{color_variable}.green = {green};
{color_variable}.blue = {blue};

{variable}.stroked = true;
{variable}.filled = false;

{variable}.strokeColor =
    {color_variable};

{variable}.strokeWidth =
    {stroke_width};

{variable}.opacity =
    {element.style.opacity * 100};
"""


    # ========================================================
    # SEMANTIC ELEMENT
    # ========================================================

    def _render_semantic_element(
        self,
        *,
        element: GraphicElementSpec,
        layer_variable: str,
        variable_suffix: str,
        document_width: float,
        document_height: float,
    ) -> str:
        """
        Semantic elements cannot always be deterministically
        converted into detailed vector artwork.

        We preserve them as editable Illustrator groups with
        traceable labels instead of hardcoding a design.
        """

        x, y = _resolve_position(
            element.placement,
            document_width,
            document_height,
        )

        width = (
            element.placement.width
            or
            document_width * 0.35
        )

        height = (
            element.placement.height
            or
            document_height * 0.25
        )

        subject = _escape_js_string(
            element.subject
            or
            element.name
            or
            element.type
        )

        variable = (
            f"semantic_{variable_suffix}"
        )

        frame_variable = (
            f"semanticFrame_{variable_suffix}"
        )

        label_variable = (
            f"semanticLabel_{variable_suffix}"
        )

        return f"""
// SEMANTIC ELEMENT
// Type: {_escape_js_string(element.type)}
// ID: {_escape_js_string(element.id)}

var {variable} =
    {layer_variable}.groupItems.add();

var {frame_variable} =
    {variable}.pathItems.rectangle(
        {y},
        {x},
        {width},
        {height}
    );

{frame_variable}.filled = false;
{frame_variable}.stroked = true;
{frame_variable}.strokeWidth = 1;

var {label_variable} =
    {variable}.textFrames.add();

{label_variable}.contents =
    "{subject}";

{label_variable}.position = [
    {x + 10},
    {y - 20}
];

{label_variable}.textRange.characterAttributes.size =
    12;
"""


    # ========================================================
    # METADATA
    # ========================================================

    def _build_metadata_layer(
        self,
        *,
        planner_json: str,
    ) -> str:

        return f"""
// ============================================================
// PLANNER METADATA
// ============================================================

var metadataLayer =
    doc.layers.add();

metadataLayer.name =
    "Planner Metadata";

var metadata =
    metadataLayer.textFrames.add();

metadata.contents =
    "{planner_json}";

metadata.position = [
    0,
    0
];

metadata.textRange.characterAttributes.size =
    6;

metadataLayer.visible =
    false;
"""
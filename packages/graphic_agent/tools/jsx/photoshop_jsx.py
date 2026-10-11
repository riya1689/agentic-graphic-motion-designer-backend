"""
Dynamic Photoshop JSX Generator

GraphicExecutionSpec -> Adobe Photoshop JSX

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
        "top_left": (
            margin_x,
            margin_y,
        ),
        "top_center": (
            document_width * 0.5,
            margin_y,
        ),
        "top_right": (
            document_width - margin_x,
            margin_y,
        ),
        "center_left": (
            margin_x,
            document_height * 0.5,
        ),
        "center": (
            document_width * 0.5,
            document_height * 0.5,
        ),
        "center_right": (
            document_width - margin_x,
            document_height * 0.5,
        ),
        "bottom_left": (
            margin_x,
            document_height - margin_y,
        ),
        "bottom_center": (
            document_width * 0.5,
            document_height - margin_y,
        ),
        "bottom_right": (
            document_width - margin_x,
            document_height - margin_y,
        ),
    }

    return positions.get(
        anchor,
        positions["center"],
    )


# ============================================================
# GENERATOR
# ============================================================

class PhotoshopJSXGenerator:

    tool_id = "photoshop_jsx"


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
                    execution_spec.document.color_mode
                ),
            ),
        ]


        # ====================================================
        # RENDER LAYERS
        # ====================================================

        for layer_index, layer in enumerate(
            execution_spec.layers
        ):

            group_variable = (
                f"group_{layer_index}"
            )

            jsx_parts.append(
                f"""
// ============================================================
// GROUP: {_escape_js_string(layer.name)}
// ============================================================

var {group_variable} =
    doc.layerSets.add();

{group_variable}.name =
    "{_escape_js_string(layer.name)}";

{group_variable}.visible =
    {"true" if layer.visible else "false"};
"""
            )

            for element_index, element in enumerate(
                layer.elements
            ):

                jsx_parts.append(
                    self._render_element(
                        element=element,
                        group_variable=group_variable,
                        variable_suffix=(
                            f"{layer_index}_{element_index}"
                        ),
                        document_width=width,
                        document_height=height,
                    )
                )


        jsx_parts.append(
            self._build_metadata_layer(
                planner_json=escaped_plan,
            )
        )

        jsx_parts.append(
            """
app.activeDocument = doc;

alert(
    "NGX Photoshop fallback generated successfully."
);
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
// DYNAMIC PHOTOSHOP FALLBACK
//
// Job ID: {_escape_js_string(job_id)}
//
// GraphicExecutionSpec -> Photoshop JSX
// ============================================================

#target photoshop

app.displayDialogs =
    DialogModes.NO;
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

        mode = (
            "NewDocumentMode.CMYK"
            if color_mode.upper() == "CMYK"
            else
            "NewDocumentMode.RGB"
        )

        return f"""
// ============================================================
// DOCUMENT
// ============================================================

var doc =
    app.documents.add(
        {width},
        {height},
        72,
        "NGX Graphic Agent",
        {mode},
        DocumentFill.TRANSPARENT
    );
"""


    # ========================================================
    # ELEMENT ROUTER
    # ========================================================

    def _render_element(
        self,
        *,
        element: GraphicElementSpec,
        group_variable: str,
        variable_suffix: str,
        document_width: float,
        document_height: float,
    ) -> str:

        if element.type == "background":

            return self._render_rectangle(
                element=element,
                group_variable=group_variable,
                variable_suffix=variable_suffix,
                document_width=document_width,
                document_height=document_height,
                force_full_canvas=True,
            )


        if element.type == "rectangle":

            return self._render_rectangle(
                element=element,
                group_variable=group_variable,
                variable_suffix=variable_suffix,
                document_width=document_width,
                document_height=document_height,
            )


        if element.type == "text":

            return self._render_text(
                element=element,
                group_variable=group_variable,
                variable_suffix=variable_suffix,
                document_width=document_width,
                document_height=document_height,
            )


        if element.type in (
            "product_illustration",
            "decorative_vector",
            "logo",
            "image",
            "icon",
            "path",
            "ellipse",
            "line",
            "group",
            "custom",
        ):

            return self._render_semantic_element(
                element=element,
                group_variable=group_variable,
                variable_suffix=variable_suffix,
                document_width=document_width,
                document_height=document_height,
            )


        return (
            "\n// Unsupported element type: "
            + _escape_js_string(
                element.type
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
        group_variable: str,
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

        return f"""
// TEXT: {_escape_js_string(element.id)}

var {variable} =
    doc.artLayers.add();

{variable}.kind =
    LayerKind.TEXT;

{variable}.name =
    "{_escape_js_string(element.id)}";

{variable}.move(
    {group_variable},
    ElementPlacement.INSIDE
);

{variable}.textItem.contents =
    "{content}";

{variable}.textItem.position = [
    {x},
    {y}
];

{variable}.textItem.size =
    {font_size};

var textColor_{variable_suffix} =
    new SolidColor();

textColor_{variable_suffix}.rgb.red =
    {red};

textColor_{variable_suffix}.rgb.green =
    {green};

textColor_{variable_suffix}.rgb.blue =
    {blue};

{variable}.textItem.color =
    textColor_{variable_suffix};
"""


    # ========================================================
    # RECTANGLE
    # ========================================================

    def _render_rectangle(
        self,
        *,
        element: GraphicElementSpec,
        group_variable: str,
        variable_suffix: str,
        document_width: float,
        document_height: float,
        force_full_canvas: bool = False,
    ) -> str:

        if force_full_canvas:

            x = 0
            y = 0

            width = document_width
            height = document_height

        else:

            x, y = _resolve_position(
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

        return f"""
// RECTANGLE: {_escape_js_string(element.id)}

var {variable} =
    doc.artLayers.add();

{variable}.name =
    "{_escape_js_string(element.id)}";

{variable}.move(
    {group_variable},
    ElementPlacement.INSIDE
);

doc.activeLayer =
    {variable};

var rectColor_{variable_suffix} =
    new SolidColor();

rectColor_{variable_suffix}.rgb.red =
    {red};

rectColor_{variable_suffix}.rgb.green =
    {green};

rectColor_{variable_suffix}.rgb.blue =
    {blue};

doc.selection.select([
    [{x}, {y}],
    [{x + width}, {y}],
    [{x + width}, {y + height}],
    [{x}, {y + height}]
]);

doc.selection.fill(
    rectColor_{variable_suffix}
);

doc.selection.deselect();

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
        group_variable: str,
        variable_suffix: str,
        document_width: float,
        document_height: float,
    ) -> str:

        x, y = _resolve_position(
            element.placement,
            document_width,
            document_height,
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

        return f"""
// SEMANTIC ELEMENT
// Type: {_escape_js_string(element.type)}
// ID: {_escape_js_string(element.id)}

var {variable} =
    doc.artLayers.add();

{variable}.kind =
    LayerKind.TEXT;

{variable}.name =
    "{_escape_js_string(element.id)}";

{variable}.move(
    {group_variable},
    ElementPlacement.INSIDE
);

{variable}.textItem.contents =
    "{subject}";

{variable}.textItem.position = [
    {x},
    {y}
];

{variable}.textItem.size =
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

var metadata =
    doc.artLayers.add();

metadata.kind =
    LayerKind.TEXT;

metadata.name =
    "Planner Metadata";

metadata.textItem.contents =
    "{planner_json}";

metadata.textItem.position = [
    5,
    10
];

metadata.textItem.size =
    6;

metadata.visible =
    false;
"""
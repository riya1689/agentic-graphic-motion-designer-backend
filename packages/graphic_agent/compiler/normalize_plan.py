from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from packages.graphic_agent.compiler.execution_spec import (
    GraphicAssetSpec,
    GraphicDocumentSpec,
    GraphicElementSpec,
    GraphicExecutionSpec,
    GraphicLayerSpec,
    GraphicPaletteSpec,
    GraphicPlacementSpec,
    GraphicStyleSpec,
)


# ============================================================
# PUBLIC API
# ============================================================

def normalize_planner_plan(
    planner_plan: Dict[str, Any],
) -> GraphicExecutionSpec:
    """
    Convert PlannerOutput-style dictionary into a
    tool-neutral GraphicExecutionSpec.

    IMPORTANT:

    This normalizer does NOT:
        - call an LLM
        - generate Illustrator commands
        - generate Photoshop commands
        - invent complex visual composition

    It only extracts deterministic information that is
    already present in the Planner plan.

    Complex interpretation should eventually be produced
    structurally by Planner itself.
    """

    if not isinstance(planner_plan, dict):
        raise TypeError(
            "planner_plan must be a dictionary."
        )

    if not planner_plan:
        raise ValueError(
            "planner_plan cannot be empty."
        )

    # ========================================================
    # PRIMARY PATH:
    # Use Planner-generated structured execution spec directly
    # ========================================================

    raw_execution_spec = planner_plan.get(
        "graphic_execution_spec"
    )

    if raw_execution_spec:

        normalized_spec = (
            _normalize_structured_execution_spec(
                raw_execution_spec
            )
        )

        return GraphicExecutionSpec.model_validate(
            normalized_spec
        )

    # ========================================================
    # LEGACY / EMERGENCY FALLBACK
    # ========================================================

    tasks = planner_plan.get("tasks", [])

    if not isinstance(tasks, list):
        tasks = []

    # ========================================================
    # DOCUMENT
    # ========================================================

    width, height = _extract_document_dimensions(
        planner_plan
    )

    color_mode = _extract_color_mode(
        planner_plan
    )

    # ========================================================
    # PALETTE
    # ========================================================

    palette_colors = _extract_hex_colors(
        planner_plan
    )

    palette = GraphicPaletteSpec(
        colors={
            f"color_{index + 1}": color
            for index, color in enumerate(
                palette_colors
            )
        }
    )

    # ========================================================
    # ASSETS
    # ========================================================

    assets = _normalize_assets(
        planner_plan
    )

    # ========================================================
    # LAYERS / ELEMENTS
    # ========================================================

    layers = _normalize_tasks_to_layers(
        tasks=tasks,
        width=width,
        height=height,
        palette_colors=palette_colors,
    )

    # ========================================================
    # EXECUTION SPEC
    # ========================================================

    return GraphicExecutionSpec(
        version="1.0",

        document=GraphicDocumentSpec(
            width=width,
            height=height,
            unit="px",
            color_mode=color_mode,
        ),

        palette=palette,

        assets=assets,

        layers=layers,

        metadata={
            "source": "planner_plan",
            "target_software": planner_plan.get(
                "target_software"
            ),
            "job_summary": planner_plan.get(
                "job_summary"
            ),
            "execution_order": planner_plan.get(
                "execution_order",
                [],
            ),
            "global_constraints": planner_plan.get(
                "global_constraints",
                [],
            ),
            "final_deliverables": planner_plan.get(
                "final_deliverables",
                [],
            ),
        },
    )


# ============================================================
# STRUCTURED EXECUTION SPEC NORMALIZER
# ============================================================

def _normalize_structured_execution_spec(
    raw_spec: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Translate Planner-side generic execution JSON into
    Graphic Agent's internal GraphicExecutionSpec format.

    IMPORTANT:
    - No Illustrator logic
    - No Photoshop logic
    - No design-template logic
    - Only contract normalization
    """

    normalized = dict(
        raw_spec
    )


    # ========================================================
    # DOCUMENT
    # ========================================================

    document = dict(
        normalized.get(
            "document",
            {},
        )
    )

    unit = str(
        document.get(
            "unit",
            "px",
        )
    ).lower().strip()

    unit_aliases = {
        "pixel": "px",
        "pixels": "px",
        "px": "px",

        "point": "pt",
        "points": "pt",
        "pt": "pt",

        "millimeter": "mm",
        "millimeters": "mm",
        "mm": "mm",

        "centimeter": "cm",
        "centimeters": "cm",
        "cm": "cm",

        "inch": "in",
        "inches": "in",
        "in": "in",
    }

    document["unit"] = unit_aliases.get(
        unit,
        "px",
    )

    color_mode = str(
        document.get(
            "color_mode",
            "RGB",
        )
    ).upper()

    document["color_mode"] = (
        "CMYK"
        if color_mode == "CMYK"
        else
        "RGB"
    )

    normalized["document"] = document


    # ========================================================
    # PALETTE
    # ========================================================
    #
    # Planner:
    #
    # [
    #   {"name": "Neon Pink", "value": "#FF00FF"},
    #   {"name": "White", "value": "#FFFFFF"}
    # ]
    #
    # Graphic Agent:
    #
    # {
    #   "colors": {
    #       "Neon Pink": "#FF00FF",
    #       "White": "#FFFFFF"
    #   }
    # }
    # ========================================================

    raw_palette = normalized.get(
        "palette",
        [],
    )

    palette_colors: Dict[str, str] = {}

    if isinstance(
        raw_palette,
        list,
    ):

        for index, color in enumerate(
            raw_palette
        ):

            if not isinstance(
                color,
                dict,
            ):
                continue

            name = (
                color.get("name")
                or
                f"color_{index + 1}"
            )

            value = color.get(
                "value"
            )

            if value:

                palette_colors[
                    str(name)
                ] = str(value)


    elif isinstance(
        raw_palette,
        dict,
    ):

        existing_colors = (
            raw_palette.get(
                "colors",
                raw_palette,
            )
        )

        if isinstance(
            existing_colors,
            dict,
        ):

            palette_colors = {
                str(key): str(value)
                for key, value
                in existing_colors.items()
            }


    normalized["palette"] = {
        "colors": palette_colors
    }


    # ========================================================
    # LAYERS / ELEMENTS
    # ========================================================

    layers = normalized.get(
        "layers",
        [],
    )

    normalized_layers = []

    if isinstance(
        layers,
        list,
    ):

        for layer in layers:

            if not isinstance(
                layer,
                dict,
            ):
                continue

            normalized_layer = dict(
                layer
            )

            elements = layer.get(
                "elements",
                [],
            )

            normalized_elements = []

            if isinstance(
                elements,
                list,
            ):

                for element in elements:

                    if not isinstance(
                        element,
                        dict,
                    ):
                        continue

                    normalized_elements.append(
                        _normalize_structured_element(
                            element
                        )
                    )


            normalized_layer[
                "elements"
            ] = normalized_elements

            normalized_layers.append(
                normalized_layer
            )


    normalized["layers"] = (
        normalized_layers
    )

    return normalized

def _normalize_structured_element(
    raw_element: Dict[str, Any],
) -> Dict[str, Any]:

    element = dict(
        raw_element
    )


    # ========================================================
    # ELEMENT TYPE NORMALIZATION
    # ========================================================

    raw_type = str(element.get("type", "custom")).strip().lower()

    type_aliases = {
        "background": "background",
        "bg": "background",

        "text": "text",
        "title": "text",
        "heading": "text",
        "header": "text",
        "paragraph": "text",
        "body": "text",
        "caption": "text",
        "label": "text",

        "rectangle": "rectangle",
        "rect": "rectangle",
        "box": "rectangle",

        "ellipse": "ellipse",
        "circle": "ellipse",

        "line": "line",

        "polygon": "polygon",
        "path": "path",

        "image": "image",
        "photo": "image",
        "picture": "image",

        "logo": "logo",
        "icon": "icon",

        "group": "group",
        "container": "group",

        "decorative_vector": "decorative_vector",
        "vector": "decorative_vector",
        "svg": "decorative_vector",
        "shape": "decorative_vector",
        "star": "decorative_vector",
        "triangle": "decorative_vector",

        "product_illustration": "product_illustration",
        "illustration": "product_illustration",

        "custom": "custom",
    }

    element["type"] = type_aliases.get(
        raw_type,
        "custom",
    )


    # ========================================================
    # PLACEMENT / ANCHOR
    # ========================================================

    placement = dict(
        element.get(
            "placement",
            {},
        )
    )

    anchor = placement.get(
        "anchor"
    )

    if isinstance(
        anchor,
        str,
    ):

        normalized_anchor = (
            anchor
            .strip()
            .lower()
            .replace("-", "_")
            .replace(" ", "_")
        )

        anchor_aliases = {

            "top_left":
                "top_left",

            "top_center":
                "top_center",

            "top_right":
                "top_right",

            "center_left":
                "center_left",

            "middle_left":
                "center_left",

            "center":
                "center",

            "middle":
                "center",

            "center_right":
                "center_right",

            "middle_right":
                "center_right",

            "bottom_left":
                "bottom_left",

            "bottom_center":
                "bottom_center",

            "bottom_right":
                "bottom_right",
        }

        placement["anchor"] = (
            anchor_aliases.get(
                normalized_anchor,
                "center",
            )
        )


    element["placement"] = placement


    # ========================================================
    # STYLE
    # ========================================================

    style = dict(
        element.get(
            "style",
            {},
        )
    )


    # ========================================================
    # TYPOGRAPHY
    #
    # Planner keeps typography separately.
    # Graphic Agent currently stores typography fields
    # inside style.
    # ========================================================

    typography = element.get(
        "typography",
        {},
    )

    if isinstance(
        typography,
        dict,
    ):

        for field in (
            "font_family",
            "font_size",
            "font_weight",
            "text_align",
        ):

            value = typography.get(
                field
            )

            if (
                value is not None
                and
                style.get(field) is None
            ):

                style[field] = value

    # Normalize font_weight to allowed Literal values
    font_weight = style.get("font_weight")
    if font_weight is not None:
        fw_str = str(font_weight).strip().lower()
        fw_aliases = {
            "light": "light",
            "300": "light",
            "regular": "regular",
            "normal": "regular",
            "400": "regular",
            "medium": "medium",
            "500": "medium",
            "semibold": "semibold",
            "semi-bold": "semibold",
            "600": "semibold",
            "bold": "bold",
            "700": "bold",
            "black": "black",
            "heavy": "black",
            "900": "black",
        }
        style["font_weight"] = fw_aliases.get(
            fw_str,
            "regular",
        )

    # Normalize text_align to allowed Literal values
    text_align = style.get("text_align")
    if text_align is not None:
        ta_str = str(text_align).strip().lower()
        ta_aliases = {
            "left": "left",
            "center": "center",
            "middle": "center",
            "right": "right",
            "justify": "left",
        }
        style["text_align"] = ta_aliases.get(
            ta_str,
            "left",
        )

    element["style"] = style


    # ========================================================
    # CHILDREN
    # ========================================================

    children = element.get(
        "children",
        [],
    )

    if isinstance(
        children,
        list,
    ):

        element["children"] = [

            _normalize_structured_element(
                child
            )

            for child in children

            if isinstance(
                child,
                dict,
            )
        ]


    return element


# ============================================================
# DOCUMENT DIMENSIONS
# ============================================================

def _extract_document_dimensions(
    planner_plan: Dict[str, Any],
) -> Tuple[int, int]:
    """
    Search planner text for dimensions such as:

        1080x1920
        2400 x 3000
        1920×1080

    If no dimensions exist, use a conservative default.

    NOTE:
    This default is not a design template.
    It only prevents execution from crashing when Planner
    omitted document dimensions.
    """

    searchable_text = _flatten_plan_text(
        planner_plan
    )

    patterns = [
        r"\b(\d{2,5})\s*[xX×]\s*(\d{2,5})\b",
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            searchable_text,
        )

        if match:

            width = int(
                match.group(1)
            )

            height = int(
                match.group(2)
            )

            if width > 0 and height > 0:
                return width, height

    # --------------------------------------------------------
    # Safety fallback only.
    # --------------------------------------------------------

    return 1920, 1080


# ============================================================
# COLOR MODE
# ============================================================

def _extract_color_mode(
    planner_plan: Dict[str, Any],
) -> str:

    text = _flatten_plan_text(
        planner_plan
    ).upper()

    if "CMYK" in text:
        return "CMYK"

    return "RGB"


# ============================================================
# HEX COLOR EXTRACTION
# ============================================================

def _extract_hex_colors(
    planner_plan: Dict[str, Any],
) -> List[str]:

    text = _flatten_plan_text(
        planner_plan
    )

    matches = re.findall(
        r"#[0-9A-Fa-f]{6}\b",
        text,
    )

    colors: List[str] = []

    seen = set()

    for color in matches:

        normalized = color.upper()

        if normalized in seen:
            continue

        seen.add(
            normalized
        )

        colors.append(
            normalized
        )

    return colors


# ============================================================
# ASSET NORMALIZATION
# ============================================================

def _normalize_assets(
    planner_plan: Dict[str, Any],
) -> List[GraphicAssetSpec]:

    raw_assets = planner_plan.get(
        "asset_requests",
        [],
    )

    if not isinstance(
        raw_assets,
        list,
    ):
        return []

    assets: List[
        GraphicAssetSpec
    ] = []

    for index, asset in enumerate(
        raw_assets
    ):

        if not isinstance(
            asset,
            dict,
        ):
            continue

        raw_type = str(
            asset.get(
                "type",
                "other",
            )
        ).lower()

        normalized_type = (
            _normalize_asset_type(
                raw_type
            )
        )

        assets.append(
            GraphicAssetSpec(
                id=(
                    f"asset_{index + 1}"
                ),
                type=normalized_type,
                name=asset.get(
                    "name"
                ),
                description=asset.get(
                    "description"
                ),
                required=bool(
                    asset.get(
                        "required",
                        True,
                    )
                ),
            )
        )

    return assets


def _normalize_asset_type(
    asset_type: str,
) -> str:

    if "logo" in asset_type:
        return "logo"

    if "icon" in asset_type:
        return "icon"

    if (
        "reference" in asset_type
        or
        "previous_design" in asset_type
    ):
        return "reference"

    if (
        "image" in asset_type
        or
        "photo" in asset_type
    ):
        return "image"

    return "other"


# ============================================================
# TASK -> LAYER NORMALIZATION
# ============================================================

def _normalize_tasks_to_layers(
    *,
    tasks: List[Any],
    width: int,
    height: int,
    palette_colors: List[str],
) -> List[GraphicLayerSpec]:

    layers: List[
        GraphicLayerSpec
    ] = []

    for index, task in enumerate(
        tasks
    ):

        if not isinstance(
            task,
            dict,
        ):
            continue

        task_id = str(
            task.get(
                "task_id",
                f"task_{index + 1}",
            )
        )

        title = str(
            task.get(
                "title",
                f"Layer {index + 1}",
            )
        )

        task_text = _flatten_task_text(
            task
        )

        elements = (
            _extract_elements_from_task(
                task_id=task_id,
                task_title=title,
                task_text=task_text,
                width=width,
                height=height,
                palette_colors=palette_colors,
            )
        )

        # ----------------------------------------------------
        # Setup-only tasks may create no visual element.
        # That's okay.
        # ----------------------------------------------------

        if not elements:
            continue

        layers.append(
            GraphicLayerSpec(
                id=task_id,
                name=title,
                elements=elements,
            )
        )

    return layers


# ============================================================
# TASK ELEMENT EXTRACTION
# ============================================================

def _extract_elements_from_task(
    *,
    task_id: str,
    task_title: str,
    task_text: str,
    width: int,
    height: int,
    palette_colors: List[str],
) -> List[GraphicElementSpec]:

    lowered = task_text.lower()

    elements: List[
        GraphicElementSpec
    ] = []

    # ========================================================
    # BACKGROUND
    # ========================================================

    if "background" in lowered:

        fill = (
            palette_colors[0]
            if palette_colors
            else None
        )

        effects: List[str] = []

        if "gradient" in lowered:
            effects.append(
                "gradient"
            )

        if "glow" in lowered:
            effects.append(
                "glow"
            )

        elements.append(
            GraphicElementSpec(
                id=f"{task_id}_background",
                type="background",
                name=task_title,
                placement=GraphicPlacementSpec(
                    x=0,
                    y=0,
                    width=width,
                    height=height,
                ),
                style=GraphicStyleSpec(
                    fill=fill,
                    effects=effects,
                ),
                metadata={
                    "source_task": task_id,
                    "source_text": task_text,
                },
            )
        )

    # ========================================================
    # TEXT CONTENT
    # ========================================================

    quoted_strings = (
        _extract_quoted_strings(
            task_text
        )
    )

    if (
        "typography" in lowered
        or
        "text" in lowered
        or
        quoted_strings
    ):

        for index, content in enumerate(
            quoted_strings
        ):

            placement = (
                _infer_text_placement(
                    index=index,
                    total=len(
                        quoted_strings
                    ),
                )
            )

            fill = (
                _infer_text_color(
                    lowered,
                    palette_colors,
                )
            )

            effects: List[str] = []

            if "glow" in lowered:
                effects.append(
                    "glow"
                )

            elements.append(
                GraphicElementSpec(
                    id=(
                        f"{task_id}_text_"
                        f"{index + 1}"
                    ),
                    type="text",
                    content=content,
                    placement=placement,
                    style=GraphicStyleSpec(
                        fill=fill,
                        effects=effects,
                    ),
                    metadata={
                        "source_task": task_id,
                    },
                )
            )

    # ========================================================
    # PRODUCT / SUBJECT ILLUSTRATION
    # ========================================================

    if (
        "product" in lowered
        or
        "mockup" in lowered
        or
        "illustration" in lowered
    ):

        subject = (
            _infer_subject(
                task_text
            )
        )

        elements.append(
            GraphicElementSpec(
                id=f"{task_id}_subject",
                type="product_illustration",
                name=task_title,
                subject=subject,
                placement=GraphicPlacementSpec(
                    anchor="center",
                ),
                metadata={
                    "source_task": task_id,
                    "source_text": task_text,
                },
            )
        )

    # ========================================================
    # DECORATIVE VECTOR
    # ========================================================

    decorative_terms = [
        "cybernetic",
        "abstract",
        "decorative",
        "vector lines",
        "geometric",
        "futuristic",
    ]

    if any(
        term in lowered
        for term in decorative_terms
    ):

        elements.append(
            GraphicElementSpec(
                id=f"{task_id}_decorative",
                type="decorative_vector",
                name=task_title,
                placement=GraphicPlacementSpec(
                    anchor="center",
                ),
                metadata={
                    "source_task": task_id,
                    "source_text": task_text,
                },
            )
        )

    return elements


# ============================================================
# QUOTED COPY EXTRACTION
# ============================================================

def _extract_quoted_strings(
    text: str,
) -> List[str]:

    results: List[str] = []

    patterns = [
        r"'([^']+)'",
        r'"([^"]+)"',
    ]

    for pattern in patterns:

        for match in re.findall(
            pattern,
            text,
        ):

            cleaned = match.strip()

            if (
                cleaned
                and
                cleaned not in results
            ):
                results.append(
                    cleaned
                )

    return results


# ============================================================
# SIMPLE TEXT PLACEMENT
# ============================================================

def _infer_text_placement(
    *,
    index: int,
    total: int,
) -> GraphicPlacementSpec:
    """
    Conservative semantic layout only.

    This is NOT a poster template.

    It simply assigns readable semantic anchors when
    Planner gave text but no coordinates.
    """

    if total <= 1:

        return GraphicPlacementSpec(
            anchor="top_center"
        )

    if index == 0:

        return GraphicPlacementSpec(
            anchor="top_center"
        )

    if index == total - 1:

        return GraphicPlacementSpec(
            anchor="bottom_center"
        )

    return GraphicPlacementSpec(
        anchor="center"
    )


# ============================================================
# TEXT COLOR
# ============================================================

def _infer_text_color(
    task_text_lower: str,
    palette_colors: List[str],
) -> Optional[str]:

    if not palette_colors:
        return None

    # --------------------------------------------------------
    # If cyan is explicitly mentioned,
    # find common cyan palette candidate.
    # --------------------------------------------------------

    if "cyan" in task_text_lower:

        for color in palette_colors:

            if color in (
                "#00E5FF",
                "#00FFFF",
            ):
                return color

    # --------------------------------------------------------
    # White is a safe readable text candidate when explicitly
    # available.
    # --------------------------------------------------------

    if "#FFFFFF" in palette_colors:
        return "#FFFFFF"

    return palette_colors[0]


# ============================================================
# SUBJECT EXTRACTION
# ============================================================

def _infer_subject(
    task_text: str,
) -> str:
    """
    Keep source task text as semantic subject description.

    Do not attempt complicated NLP parsing here.
    """

    cleaned = task_text.strip()

    if not cleaned:

        return "visual subject"

    return cleaned


# ============================================================
# TEXT FLATTENING HELPERS
# ============================================================

def _flatten_plan_text(
    planner_plan: Dict[str, Any],
) -> str:

    values: List[str] = []

    def walk(
        value: Any,
    ) -> None:

        if value is None:
            return

        if isinstance(
            value,
            str,
        ):
            values.append(
                value
            )
            return

        if isinstance(
            value,
            dict,
        ):

            for nested in value.values():
                walk(
                    nested
                )

            return

        if isinstance(
            value,
            list,
        ):

            for nested in value:
                walk(
                    nested
                )

            return

    walk(
        planner_plan
    )

    return "\n".join(
        values
    )


def _flatten_task_text(
    task: Dict[str, Any],
) -> str:

    relevant_fields = [
        "title",
        "description",
        "inputs",
        "expected_outputs",
        "constraints",
        "acceptance_criteria",
    ]

    values: List[str] = []

    for field in relevant_fields:

        value = task.get(
            field
        )

        if isinstance(
            value,
            str,
        ):
            values.append(
                value
            )

        elif isinstance(
            value,
            list,
        ):

            values.extend(
                str(item)
                for item in value
                if item is not None
            )

    return "\n".join(
        values
    )
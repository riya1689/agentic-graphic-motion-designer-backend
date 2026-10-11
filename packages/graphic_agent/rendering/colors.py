"""Shared semantic-to-CSS color normalization for SVG and raster previews."""

from __future__ import annotations

import re
import colorsys


SEMANTIC_COLORS = {
    "deep navy": "#0b1020",
    "dark navy": "#0b1020",
    "navy": "#0b1020",
    "electric blue": "#2563eb",
    "white": "#ffffff",
    "black": "#111111",
    "red": "#ef4444",
    "blue": "#2563eb",
    "green": "#16a34a",
    "yellow": "#facc15",
    "purple": "#7c3aed",
    "pink": "#ec4899",
    "orange": "#f97316",
    "brown": "#92400e",
    "cyan": "#06b6d4",
    "magenta": "#d946ef",
    "gold": "#eab308",
    "teal": "#0d9488",
    "turquoise": "#14b8a6",
    "lime": "#84cc16",
    "olive": "#808000",
    "maroon": "#800000",
    "burgundy": "#800020",
    "beige": "#f5f5dc",
    "cream": "#fffdd0",
    "gray": "#6b7280",
    "grey": "#6b7280",
    "charcoal": "#36454f",
    "silver": "#c0c0c0",
    "bronze": "#cd7f32",
    "coral": "#ff7f50",
    "peach": "#ffdab9",
    "lavender": "#a78bfa",
    "indigo": "#4f46e5",
    "violet": "#8b5cf6",
    "transparent": "#00000000",
    "none": "none",
}


def normalize_color(value: object, *, fallback: str = "#000000") -> str:
    text = str(value or "").strip()
    lowered = text.lower()
    if lowered in SEMANTIC_COLORS:
        return SEMANTIC_COLORS[lowered]
    if lowered == "none":
        return "none"
    if re.fullmatch(r"#[0-9a-fA-F]{3,8}", text):
        return text
    if re.fullmatch(r"rgba?\([^)]*\)", lowered) or re.fullmatch(r"hsla?\([^)]*\)", lowered):
        return text
    return fallback


def color_requirement_satisfied(required: object, svg_source: str) -> bool:
    """Match a requested semantic color against colors actually used by SVG.

    Gemini may choose a visually equivalent shade instead of the canonical
    palette hex value. Exact hex matching is retained for arbitrary colors;
    named design colors also receive a small semantic tolerance.
    """
    value = _normalize_requirement_text(required)
    if not value:
        return True

    # Planner/LLM output often describes a palette instead of one CSS value:
    # ``brown-orange gradient``, ``deep navy and electric blue``,
    # ``warm orange/cream accents``. Verify each recognizable color separately.
    # This avoids treating the complete phrase as an invalid CSS literal.
    compound_tokens = _compound_color_tokens(value)
    if compound_tokens:
        return all(_single_color_requirement_satisfied(token, svg_source) for token in compound_tokens)

    # A descriptive phrase with no recognizable color is not a literal color
    # that this deterministic verifier can prove or disprove. The planner and
    # renderer still receive the phrase; skipping it prevents false failures
    # for names such as ``sunset palette`` or brand-specific color names.
    if value not in SEMANTIC_COLORS and not _is_css_color_literal(value):
        return True

    return _single_color_requirement_satisfied(value, svg_source)


def _single_color_requirement_satisfied(value: str, svg_source: str) -> bool:
    """Verify one semantic/CSS color against SVG attributes and CSS rules."""
    value = _normalize_requirement_text(value)
    canonical = normalize_color(value, fallback=value).lower()
    source = _extract_color_declarations(svg_source)

    # Accept a named CSS color when the renderer emitted a named color instead
    # of a hex value. Match declaration tokens, not arbitrary visible text.
    if value in SEMANTIC_COLORS and re.search(rf"(?<![a-z]){re.escape(value)}(?![a-z])", source):
        return True

    if canonical.startswith("#") and canonical in source:
        return True
    if not canonical.startswith("#") or len(canonical) not in {4, 7}:
        return False
    expected = _hex_rgb(canonical)
    if expected is None:
        return False
    for token in re.findall(r"#[0-9a-f]{3,8}\b", source):
        actual = _hex_rgb(token)
        if actual is None:
            continue
        if _distance(expected, actual) <= 32:
            return True

    # Semantic families cover visually equivalent LLM palette substitutions.
    return any(_semantic_rgb_match(value, rgb) for rgb in _source_rgb(source))


def _compound_color_tokens(value: str) -> list[str]:
    """Extract recognizable colors from a natural-language palette phrase.

    Longest semantic names are matched first so ``deep navy`` remains one
    color. A single exact color is handled by the normal path; any phrase
    containing one or more color terms is treated as a requirement list.
    """
    value = _normalize_requirement_text(value)
    if value in SEMANTIC_COLORS or _is_css_color_literal(value):
        return []

    matches: list[tuple[int, int, str]] = []
    for semantic in sorted(SEMANTIC_COLORS, key=len, reverse=True):
        if semantic in {"transparent", "none"}:
            continue
        for match in re.finditer(rf"(?<![a-z]){re.escape(semantic)}(?![a-z])", value):
            matches.append((match.start(), match.end(), semantic))

    # Remove overlaps caused by matching both ``navy`` and ``deep navy``.
    tokens: list[str] = []
    occupied: list[tuple[int, int]] = []
    for start, end, semantic in sorted(matches, key=lambda item: (item[0], -(item[1] - item[0]))):
        if any(start < other_end and end > other_start for other_start, other_end in occupied):
            continue
        occupied.append((start, end))
        tokens.append(semantic)
    return list(dict.fromkeys(tokens))


def _normalize_requirement_text(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def _is_css_color_literal(value: str) -> bool:
    return bool(
        re.fullmatch(r"#[0-9a-f]{3,8}", value)
        or re.fullmatch(r"rgba?\([^)]*\)", value)
        or re.fullmatch(r"hsla?\([^)]*\)", value)
    )


def _extract_color_declarations(svg_source: str) -> str:
    """Return SVG color declarations from attributes and embedded CSS."""
    declarations = [
        match.group(1)
        for match in re.finditer(
            r"(?:fill|stroke|color|stop-color|flood-color|lighting-color|style)\s*=\s*['\"]([^'\"]+)['\"]",
            svg_source,
            flags=re.IGNORECASE,
        )
    ]
    declarations.extend(
        match.group(1)
        for match in re.finditer(
            r"(?:fill|stroke|color|stop-color|flood-color|lighting-color)\s*:\s*([^;{}]+)",
            svg_source,
            flags=re.IGNORECASE,
        )
    )
    return " ".join(declarations).lower()


def _semantic_rgb_match(value: str, rgb: tuple[int, int, int]) -> bool:
    """Match common semantic names by hue/lightness, not one fixed hex."""
    red, green, blue = rgb
    maximum = max(rgb)
    minimum = min(rgb)
    if maximum == 0:
        return value in {"black", "charcoal"}
    # rgb_to_hls returns hue, lightness, saturation (not hue, saturation,
    # lightness). Keeping this explicit prevents dark/light palette matching
    # from being accidentally inverted.
    hue, lightness, saturation = colorsys.rgb_to_hls(red / 255, green / 255, blue / 255)
    hue_degrees = hue * 360

    if value in {"deep navy", "dark navy", "navy"}:
        return lightness < 0.32 and blue >= green >= red and blue < 0.55
    if value == "black":
        return maximum < 70
    if value in {"gray", "grey", "silver", "charcoal"}:
        return saturation < 0.16 and (value != "charcoal" or lightness < 0.38)
    if value in {"red", "maroon", "burgundy"}:
        return (hue_degrees < 18 or hue_degrees >= 345) and (value == "red" or lightness < 0.45)
    if value == "brown":
        return 15 <= hue_degrees < 48 and lightness < 0.62 and saturation > 0.35
    if value in {"orange", "bronze", "peach", "coral"}:
        return (
            15 <= hue_degrees < 48
            and red >= 160
            and green >= 50
            and lightness > 0.35
        )
    if value in {"yellow", "gold", "beige", "cream"}:
        return 42 <= hue_degrees < 72 and (value in {"yellow", "gold"} or lightness > 0.65)
    if value in {"green", "lime", "olive"}:
        return 72 <= hue_degrees < 165 and (value != "lime" or lightness > 0.35)
    if value in {"cyan", "teal", "turquoise"}:
        return 165 <= hue_degrees < 205
    if value == "electric blue":
        return 175 <= hue_degrees < 270 and blue >= red + 35
    if value in {"blue", "indigo"}:
        return 205 <= hue_degrees < 270
    if value in {"purple", "violet", "lavender"}:
        return 255 <= hue_degrees < 315 and (value != "lavender" or lightness > 0.55)
    if value == "pink" or value == "magenta":
        return hue_degrees >= 315 or hue_degrees < 345
    if value == "white":
        return lightness > 0.9 and saturation < 0.16
    return False


def _hex_rgb(value: str) -> tuple[int, int, int] | None:
    text = value.lstrip("#")
    if len(text) == 3:
        text = "".join(char * 2 for char in text)
    if len(text) not in {6, 8}:
        return None
    try:
        return int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16)
    except ValueError:
        return None


def _distance(left: tuple[int, int, int], right: tuple[int, int, int]) -> float:
    return sum((a - b) ** 2 for a, b in zip(left, right)) ** 0.5


def _source_rgb(source: str):
    for token in re.findall(r"#[0-9a-f]{3,8}\b", source):
        rgb = _hex_rgb(token)
        if rgb is not None:
            yield rgb

"""Illustrator-compatible SVG asset normalization.

This adapter only changes downloaded SVG serialization. It does not alter the
planner contract or the browser-facing design decisions. Uploaded images are
kept embedded, placed in explicit asset groups, and exposed through the
legacy SVG 1.1 ``xlink:href`` attribute that older Illustrator importers
expect.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
import re
from typing import Any, Iterable

from .svg_renderer import SvgStructuralValidationError


XLINK_NAMESPACE = "http://www.w3.org/1999/xlink"
XLINK_HREF = f"{{{XLINK_NAMESPACE}}}href"


def make_illustrator_compatible_svg(svg_text: str, assets: Iterable[Any] = ()) -> str:
    """Normalize embedded image nodes for Illustrator import.

    The function deliberately accepts only embedded ``data:image`` resources.
    It rejects empty image references because Illustrator interprets those as
    missing linked files and opens the ``could not find the linked file`` dialog.
    """
    try:
        root = ET.fromstring(svg_text)
    except ET.ParseError as exc:
        raise SvgStructuralValidationError(f"malformed SVG XML: {exc}") from exc
    if root.tag.rsplit("}", 1)[-1] != "svg":
        raise SvgStructuralValidationError("SVG root element is missing")

    ET.register_namespace("", "http://www.w3.org/2000/svg")
    ET.register_namespace("xlink", XLINK_NAMESPACE)
    root_namespace = (
        root.tag[1:].split("}", 1)[0]
        if root.tag.startswith("{")
        else ""
    )
    group_tag = f"{{{root_namespace}}}g" if root_namespace else "g"

    asset_list = [
        asset
        for asset in assets
        if str(getattr(asset, "uri", "") or "").lower().startswith("data:image/")
    ]
    embedded_asset_map = _embedded_asset_map(asset_list)
    image_nodes = [
        (parent, child)
        for parent in list(root.iter())
        for child in list(parent)
        if child.tag.rsplit("}", 1)[-1].lower() == "image"
    ]
    for image_index, (parent, child) in enumerate(image_nodes, start=1):
        href = (
            child.attrib.get("href")
            or child.attrib.get(XLINK_HREF)
            or child.attrib.get("{http://www.w3.org/1999/xlink}href")
        )
        if not href or not str(href).strip():
            raise SvgStructuralValidationError(
                f"image element {image_index} has an empty resource reference"
            )
        href = str(href).strip()
        href = _resolve_asset_alias(href, embedded_asset_map, asset_list)
        if not href.lower().startswith("data:image/"):
            raise SvgStructuralValidationError(
                "Illustrator export requires every image to use an embedded data:image resource; "
                f"unresolved reference: {href[:160]}"
            )

        # Remove SVG 2 href and write the SVG 1.1 compatibility attribute.
        # Chrome, Edge, and Illustrator all understand xlink:href.
        child.attrib.pop("href", None)
        child.attrib[XLINK_HREF] = href

        if not child.attrib.get("id"):
            child.set("id", f"asset-image-{image_index}")
        role = _asset_role(asset_list[image_index - 1]) if image_index <= len(asset_list) else "image"

        # Keep the image as a real SVG group so Illustrator exposes a stable
        # asset unit without changing its coordinates or transform.
        group = ET.Element(group_tag, {
            "id": f"asset-group-{image_index}",
            "data-asset-role": role,
            "data-asset-embedded": "true",
        })
        child_index = list(parent).index(child)
        parent.remove(child)
        group.append(child)
        parent.insert(child_index, group)

    serialized = ET.tostring(root, encoding="unicode", short_empty_elements=True)
    # Keep the output explicit and easy to inspect in Illustrator diagnostics.
    if "<image" in serialized.lower() and "data:image/" not in serialized.lower():
        raise SvgStructuralValidationError("Illustrator SVG contains an image without embedded data.")
    return serialized


def _asset_role(asset: Any) -> str:
    description = str(getattr(asset, "description", None) or "").lower()
    for role, terms in (
        ("background", ("background", "backdrop")),
        ("logo", ("logo", "brand", "mark")),
        ("product", ("product", "subject", "object")),
    ):
        if any(term in description for term in terms):
            return role
    return "image"


def _embedded_asset_map(assets: list[Any]) -> dict[str, str]:
    """Build aliases used by Planner and Code Image for uploaded assets."""
    aliases: dict[str, str] = {}
    for index, asset in enumerate(assets, start=1):
        uri = str(getattr(asset, "uri", "") or "")
        if not uri.lower().startswith("data:image/"):
            continue
        aliases[f"uploaded-asset-{index}"] = uri
        aliases[f"asset-{index}"] = uri
        description = str(getattr(asset, "description", "") or "")
        slug = re.sub(r"[^a-z0-9]+", "-", description.lower()).strip("-")
        if slug:
            aliases[slug] = uri
    return aliases


def _resolve_asset_alias(href: str, aliases: dict[str, str], assets: list[Any]) -> str:
    """Resolve non-URL Planner asset tokens without accepting external files."""
    lowered = href.lower()
    if lowered.startswith(("asset://", "data-asset://")):
        key = href.split("://", 1)[1].strip().lower()
        if key in aliases:
            return aliases[key]
        # A single uploaded asset is unambiguous even when the planner chose a
        # custom id that was not copied into the renderer request.
        if len(assets) == 1:
            return str(getattr(assets[0], "uri"))
    key = href.strip().lower()
    if key in aliases:
        return aliases[key]
    return href

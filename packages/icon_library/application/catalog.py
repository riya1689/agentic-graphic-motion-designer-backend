"""Manifest-driven built-in icon catalog importer."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from packages.icon_library.application.service import IconLibraryService
from packages.icon_library.domain.models import IconRecord, IconSource
from packages.icon_library.ports import IconNotFoundError


@dataclass(frozen=True)
class BuiltinIconDefinition:
    icon_id: str
    name: str
    filename: str
    category: str | None = None
    tags: tuple[str, ...] = ()
    style: str | None = None
    description: str | None = None


def load_builtin_manifest(path: Path) -> list[BuiltinIconDefinition]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("Built-in icon manifest must contain a list.")
    return [BuiltinIconDefinition(
        icon_id=str(item["icon_id"]),
        name=str(item["name"]),
        filename=str(item["filename"]),
        category=item.get("category"),
        tags=tuple(str(tag).strip().lower() for tag in item.get("tags", []) if str(tag).strip()),
        style=item.get("style"),
        description=item.get("description"),
    ) for item in payload]


def seed_builtin_icons(
    service: IconLibraryService,
    *,
    manifest_path: Path,
    asset_directory: Path,
) -> tuple[str, ...]:
    """Idempotently register manifest assets and return newly added IDs."""
    added: list[str] = []
    for definition in load_builtin_manifest(manifest_path):
        try:
            service.get(definition.icon_id)
            continue
        except IconNotFoundError:
            pass
        asset_path = (asset_directory / definition.filename).resolve()
        if asset_path.parent != asset_directory.resolve():
            raise ValueError(f"Built-in icon asset escapes catalog directory: {asset_path}")
        content = asset_path.read_bytes()
        service.add(
            IconRecord(
                icon_id=definition.icon_id,
                name=definition.name,
                source=IconSource.BUILT_IN,
                asset_ref="pending",
                category=definition.category,
                tags=definition.tags,
                style=definition.style,
                description=definition.description,
            ),
            svg_content=content,
        )
        added.append(definition.icon_id)
    return tuple(added)

"""PostgreSQL adapters for Icon Library persistence."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Sequence

from packages.icon_library.domain.models import IconRecord, IconSearchQuery, IconSource
from packages.icon_library.ports import IconAssetStore, IconRepository


class PostgresIconAssetStore(IconAssetStore):
    def __init__(self, connection_factory) -> None:
        self._connection_factory = connection_factory

    def put_svg(self, *, icon_id: str, content: bytes) -> str:
        digest = hashlib.sha256(content).hexdigest()
        asset_ref = f"sha256:{digest}"
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO icon_library.icon_assets
                        (asset_ref, mime_type, content, sha256)
                    VALUES (%s, 'image/svg+xml', %s, %s)
                    ON CONFLICT (asset_ref) DO NOTHING
                    """,
                    (asset_ref, content, digest),
                )
        return asset_ref

    def get(self, asset_ref: str) -> bytes:
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT content FROM icon_library.icon_assets WHERE asset_ref = %s",
                    (asset_ref,),
                )
                row = cursor.fetchone()
        if row is None:
            raise KeyError(f"Icon asset not found: {asset_ref}")
        return bytes(row[0])


class PostgresIconRepository(IconRepository):
    def __init__(self, connection_factory) -> None:
        self._connection_factory = connection_factory

    def create(self, icon: IconRecord) -> IconRecord:
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO icon_library.icons
                    (icon_id, name, source, asset_ref, category, tags, style,
                     description, mime_type, version, is_deleted, created_at,
                     updated_at, metadata)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    _params(icon),
                )
        return icon

    def get(self, icon_id: str, *, include_deleted: bool = False) -> IconRecord | None:
        where_deleted = "" if include_deleted else " AND is_deleted = FALSE"
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT * FROM icon_library.icons WHERE icon_id = %s" + where_deleted,
                    (icon_id,),
                )
                row = cursor.fetchone()
        return _record(row) if row else None

    def search(self, query: IconSearchQuery) -> Sequence[IconRecord]:
        clauses = ["is_deleted = FALSE"] if not query.include_deleted else []
        params: list[Any] = []
        if query.text.strip():
            clauses.append("(name ILIKE %s OR description ILIKE %s OR %s = ANY(tags))")
            term = f"%{query.text.strip()}%"
            params.extend([term, term, query.text.strip().lower()])
        if query.category:
            clauses.append("category = %s")
            params.append(query.category)
        if query.source:
            clauses.append("source = %s")
            params.append(query.source.value)
        if query.style:
            clauses.append("style = %s")
            params.append(query.style)
        for tag in query.tags:
            clauses.append("%s = ANY(tags)")
            params.append(tag)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        params.extend([query.limit, query.offset])
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT * FROM icon_library.icons" + where
                    + " ORDER BY updated_at DESC LIMIT %s OFFSET %s",
                    tuple(params),
                )
                rows = cursor.fetchall()
        return [_record(row) for row in rows]

    def update(self, icon: IconRecord) -> IconRecord:
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE icon_library.icons
                    SET name = %s, source = %s, asset_ref = %s, category = %s,
                        tags = %s, style = %s, description = %s, mime_type = %s,
                        version = %s, is_deleted = %s, updated_at = %s, metadata = %s
                    WHERE icon_id = %s
                    """,
                    (
                        icon.name,
                        icon.source.value,
                        icon.asset_ref,
                        icon.category,
                        list(icon.tags),
                        icon.style,
                        icon.description,
                        icon.mime_type,
                        icon.version,
                        icon.is_deleted,
                        icon.updated_at,
                        json.dumps(icon.metadata),
                        icon.icon_id,
                    ),
                )
        return icon

    def soft_delete(self, icon_id: str) -> None:
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE icon_library.icons SET is_deleted = TRUE, updated_at = %s WHERE icon_id = %s",
                    (datetime.now(timezone.utc), icon_id),
                )


def _params(icon: IconRecord) -> tuple[Any, ...]:
    return (
        icon.icon_id,
        icon.name,
        icon.source.value,
        icon.asset_ref,
        icon.category,
        list(icon.tags),
        icon.style,
        icon.description,
        icon.mime_type,
        icon.version,
        icon.is_deleted,
        icon.created_at,
        icon.updated_at,
        json.dumps(icon.metadata),
    )


def _record(row: tuple[Any, ...]) -> IconRecord:
    return IconRecord(
        icon_id=row[0],
        name=row[1],
        source=IconSource(row[2]),
        asset_ref=row[3],
        category=row[4],
        tags=tuple(row[5] or ()),
        style=row[6],
        description=row[7],
        mime_type=row[8],
        version=row[9],
        is_deleted=row[10],
        created_at=row[11],
        updated_at=row[12],
        metadata=row[13] or {},
    )

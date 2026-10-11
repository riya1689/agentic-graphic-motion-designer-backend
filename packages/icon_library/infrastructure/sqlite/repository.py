from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

from packages.icon_library.domain.models import IconRecord, IconSearchQuery, IconSource
from packages.icon_library.ports import IconAssetStore, IconRepository


class SQLiteIconAssetStore(IconAssetStore):
    def __init__(self, connection_factory):
        self._connection_factory = connection_factory

    def put_svg(self, *, icon_id, content):
        digest = hashlib.sha256(content).hexdigest()
        asset_ref = f"sha256:{digest}"
        with self._connection_factory() as db:
            db.execute("INSERT OR IGNORE INTO icon_assets(asset_ref,mime_type,content,sha256) VALUES (?,?,?,?)", (asset_ref,"image/svg+xml",content,digest))
        return asset_ref

    def get(self, asset_ref):
        with self._connection_factory() as db:
            row = db.execute("SELECT content FROM icon_assets WHERE asset_ref=?", (asset_ref,)).fetchone()
        if row is None:
            raise KeyError(f"Icon asset not found: {asset_ref}")
        return bytes(row[0])


class SQLiteIconRepository(IconRepository):
    def __init__(self, connection_factory):
        self._connection_factory = connection_factory

    def create(self, icon):
        with self._connection_factory() as db:
            db.execute("INSERT INTO icons(icon_id,name,source,asset_ref,category,tags,style,description,mime_type,version,is_deleted,created_at,updated_at,metadata) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", _params(icon))
        return icon

    def get(self, icon_id, *, include_deleted=False):
        query = "SELECT * FROM icons WHERE icon_id=?" + ("" if include_deleted else " AND is_deleted=0")
        with self._connection_factory() as db:
            row = db.execute(query, (icon_id,)).fetchone()
        return _record(row) if row else None

    def search(self, query):
        clauses = [] if query.include_deleted else ["is_deleted=0"]
        params = []
        if query.text.strip():
            term = f"%{query.text.strip().lower()}%"
            clauses.append("(LOWER(name) LIKE ? OR LOWER(description) LIKE ? OR LOWER(tags) LIKE ?)")
            params.extend([term, term, f"%{query.text.strip().lower()}%"])
        if query.category:
            clauses.append("category=?"); params.append(query.category)
        if query.source:
            clauses.append("source=?"); params.append(query.source.value)
        if query.style:
            clauses.append("style=?"); params.append(query.style)
        for tag in query.tags:
            clauses.append("LOWER(tags) LIKE ?"); params.append(f'%"{tag.lower()}"%')
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        params.extend([query.limit, query.offset])
        with self._connection_factory() as db:
            rows = db.execute("SELECT * FROM icons" + where + " ORDER BY updated_at DESC LIMIT ? OFFSET ?", tuple(params)).fetchall()
        return [_record(row) for row in rows]

    def update(self, icon):
        with self._connection_factory() as db:
            db.execute("UPDATE icons SET name=?,source=?,asset_ref=?,category=?,tags=?,style=?,description=?,mime_type=?,version=?,is_deleted=?,updated_at=?,metadata=? WHERE icon_id=?", (icon.name,icon.source.value,icon.asset_ref,icon.category,json.dumps(list(icon.tags)),icon.style,icon.description,icon.mime_type,icon.version,int(icon.is_deleted),_timestamp(icon.updated_at),json.dumps(icon.metadata),icon.icon_id))
        return icon

    def soft_delete(self, icon_id):
        with self._connection_factory() as db:
            db.execute("UPDATE icons SET is_deleted=1,updated_at=? WHERE icon_id=?", (_timestamp(datetime.now(timezone.utc)),icon_id))


def _params(icon):
    return (icon.icon_id,icon.name,icon.source.value,icon.asset_ref,icon.category,json.dumps(list(icon.tags)),icon.style,icon.description,icon.mime_type,icon.version,int(icon.is_deleted),_timestamp(icon.created_at),_timestamp(icon.updated_at),json.dumps(icon.metadata))


def _record(row):
    return IconRecord(icon_id=row[0],name=row[1],source=IconSource(row[2]),asset_ref=row[3],category=row[4],tags=tuple(json.loads(row[5] or "[]")),style=row[6],description=row[7],mime_type=row[8],version=int(row[9]),is_deleted=bool(row[10]),created_at=_datetime(row[11]),updated_at=_datetime(row[12]),metadata=json.loads(row[13] or "{}"))


def _timestamp(value):
    return value.astimezone(timezone.utc).isoformat() if isinstance(value, datetime) else str(value)


def _datetime(value):
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


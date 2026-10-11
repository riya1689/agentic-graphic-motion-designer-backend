from __future__ import annotations

import json
from datetime import datetime, timezone

from packages.provider_secrets.domain.models import ProviderSecretSummary


class SQLiteProviderSecretRepository:
    def __init__(self, connection_factory):
        self._connection_factory = connection_factory

    def list(self):
        with self._connection_factory() as db:
            rows = db.execute("SELECT provider,secret_name,masked_value,is_active,version,created_at,updated_at FROM auth_provider_secrets ORDER BY provider,secret_name").fetchall()
        return [_summary(row) for row in rows]

    def get_active_ciphertext(self, *, provider, secret_name):
        with self._connection_factory() as db:
            row = db.execute("SELECT ciphertext FROM auth_provider_secrets WHERE provider=? AND secret_name=? AND is_active=1", (provider,secret_name)).fetchone()
        return str(row[0]) if row else None

    def upsert(self, *, provider, secret_name, ciphertext, masked_value, updated_by):
        with self._connection_factory() as db:
            db.execute("INSERT INTO auth_provider_secrets(provider,secret_name,ciphertext,masked_value,is_active,version,updated_by) VALUES (?,?,?,?,1,1,?) ON CONFLICT(provider,secret_name) DO UPDATE SET ciphertext=excluded.ciphertext,masked_value=excluded.masked_value,is_active=1,version=auth_provider_secrets.version+1,updated_at=CURRENT_TIMESTAMP,updated_by=excluded.updated_by", (provider,secret_name,ciphertext,masked_value,updated_by))
            db.execute("INSERT INTO auth_audit_log(user_id,event,metadata) VALUES (?,?,?)", (updated_by,"provider_secret_upserted",json.dumps({"provider":provider,"secret_name":secret_name})))
            row = db.execute("SELECT provider,secret_name,masked_value,is_active,version,created_at,updated_at FROM auth_provider_secrets WHERE provider=? AND secret_name=?", (provider,secret_name)).fetchone()
        return _summary(row)

    def revoke(self, *, provider, secret_name, updated_by):
        with self._connection_factory() as db:
            db.execute("UPDATE auth_provider_secrets SET is_active=0,version=version+1,updated_at=CURRENT_TIMESTAMP,updated_by=? WHERE provider=? AND secret_name=?", (updated_by,provider,secret_name))
            db.execute("INSERT INTO auth_audit_log(user_id,event,metadata) VALUES (?,?,?)", (updated_by,"provider_secret_revoked",json.dumps({"provider":provider,"secret_name":secret_name})))


def _summary(row):
    return ProviderSecretSummary(provider=str(row[0]),secret_name=str(row[1]),masked_value=str(row[2]),is_active=bool(row[3]),version=int(row[4]),created_at=_datetime(row[5]),updated_at=_datetime(row[6]))


def _datetime(value):
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


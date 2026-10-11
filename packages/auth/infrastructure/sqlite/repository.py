"""SQLite implementation of the authentication repository contract."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Callable
from uuid import uuid4

from packages.auth.domain.models import AuthenticatedUser, UserAccount


class SQLiteAuthRepository:
    def __init__(self, connection_factory: Callable[[], Any]) -> None:
        self._connection_factory = connection_factory

    def create_user(self, *, email, display_name, password_hash, roles):
        user_id = str(uuid4())
        with self._connection_factory() as db:
            db.execute(
                "INSERT INTO auth_users(id,email,display_name,password_hash) VALUES (?,?,?,?)",
                (user_id, _email(email), display_name.strip(), password_hash),
            )
            db.executemany(
                "INSERT INTO auth_user_roles(user_id,role_id) VALUES (?,?)",
                [(user_id, role) for role in roles],
            )
        return self._get_user(user_id)

    def find_by_email(self, email):
        with self._connection_factory() as db:
            row = db.execute(
                "SELECT id,email,display_name,status,created_at,last_login_at,must_change_password,password_hash FROM auth_users WHERE email = ? COLLATE NOCASE",
                (_email(email),),
            ).fetchone()
            if row is None:
                return None
            roles = db.execute(
                "SELECT role_id FROM auth_user_roles WHERE user_id = ? ORDER BY role_id",
                (row[0],),
            ).fetchall()
        return _user(row[:7]), str(row[7]), tuple(item[0] for item in roles)

    def list_users(self):
        with self._connection_factory() as db:
            rows = db.execute(
                "SELECT id,email,display_name,status,created_at,last_login_at,must_change_password FROM auth_users ORDER BY created_at,email"
            ).fetchall()
            result = []
            for row in rows:
                roles = db.execute("SELECT role_id FROM auth_user_roles WHERE user_id=? ORDER BY role_id", (row[0],)).fetchall()
                result.append((_user(row), tuple(item[0] for item in roles)))
        return result

    def update_status(self, *, user_id, status):
        with self._connection_factory() as db:
            db.execute("UPDATE auth_users SET status=?,updated_at=CURRENT_TIMESTAMP WHERE id=?", (status, user_id))
        return self._get_user(user_id)

    def update_password(self, *, user_id, password_hash):
        with self._connection_factory() as db:
            db.execute("UPDATE auth_users SET password_hash=?,must_change_password=1,updated_at=CURRENT_TIMESTAMP WHERE id=?", (password_hash, user_id))
        return self._get_user(user_id)

    def find_active_user(self, user_id):
        with self._connection_factory() as db:
            row = db.execute("SELECT id,email,display_name,status,created_at,last_login_at,must_change_password FROM auth_users WHERE id=? AND status='active'", (user_id,)).fetchone()
            if row is None:
                return None
            roles = db.execute("SELECT role_id FROM auth_user_roles WHERE user_id=? ORDER BY role_id", (user_id,)).fetchall()
        return AuthenticatedUser(user=_user(row), roles=tuple(item[0] for item in roles))

    def mark_login(self, *, user_id):
        with self._connection_factory() as db:
            db.execute("UPDATE auth_users SET last_login_at=CURRENT_TIMESTAMP,updated_at=CURRENT_TIMESTAMP WHERE id=?", (user_id,))

    def create_session(self, *, user_id, refresh_token_hash, expires_at, device_label, ip_address, user_agent):
        session_id = str(uuid4())
        with self._connection_factory() as db:
            db.execute("INSERT INTO auth_sessions(id,user_id,refresh_token_hash,expires_at,device_label,ip_address,user_agent) VALUES (?,?,?,?,?,?,?)", (session_id,user_id,refresh_token_hash,_timestamp(expires_at),device_label,ip_address,user_agent))
        return session_id

    def find_session(self, *, refresh_token_hash):
        with self._connection_factory() as db:
            row = db.execute("SELECT id,user_id FROM auth_sessions WHERE refresh_token_hash=? AND revoked_at IS NULL AND expires_at > ?", (refresh_token_hash,_timestamp(datetime.now(timezone.utc)))).fetchone()
        return (str(row[0]), str(row[1])) if row else None

    def touch_session(self, *, session_id):
        with self._connection_factory() as db:
            db.execute("UPDATE auth_sessions SET last_seen_at=CURRENT_TIMESTAMP WHERE id=?", (session_id,))

    def revoke_session(self, *, session_id):
        with self._connection_factory() as db:
            db.execute("UPDATE auth_sessions SET revoked_at=CURRENT_TIMESTAMP WHERE id=?", (session_id,))

    def audit(self, *, user_id, event, ip_address=None, user_agent=None, metadata=None):
        with self._connection_factory() as db:
            db.execute("INSERT INTO auth_audit_log(user_id,event,ip_address,user_agent,metadata) VALUES (?,?,?,?,?)", (user_id,event,ip_address,user_agent,json.dumps(metadata or {})))

    def _get_user(self, user_id):
        with self._connection_factory() as db:
            row = db.execute("SELECT id,email,display_name,status,created_at,last_login_at,must_change_password FROM auth_users WHERE id=?", (user_id,)).fetchone()
        if row is None:
            raise ValueError("User was not found")
        return _user(row)


def hash_refresh_token(refresh_token: str) -> str:
    return hashlib.sha256(refresh_token.encode("utf-8")).hexdigest()


def _email(value):
    return value.strip().lower()


def _timestamp(value):
    return value.astimezone(timezone.utc).isoformat() if isinstance(value, datetime) else str(value)


def _datetime(value):
    if not value:
        return None
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _user(row):
    return UserAccount(user_id=str(row[0]), email=str(row[1]), display_name=str(row[2]), status=str(row[3]), created_at=_datetime(row[4]), last_login_at=_datetime(row[5]), must_change_password=bool(row[6]))


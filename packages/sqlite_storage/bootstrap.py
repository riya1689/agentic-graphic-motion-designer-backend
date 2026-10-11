"""Create and seed the private per-install desktop database."""

from __future__ import annotations

from packages.icon_library.application.catalog import seed_builtin_icons
from packages.sqlite_storage.connection import connect


def initialize_database() -> None:
    with connect() as db:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS app_schema_migrations (
                version INTEGER PRIMARY KEY,
                applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS auth_roles (
                role_id TEXT PRIMARY KEY,
                description TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS auth_users (
                id TEXT PRIMARY KEY,
                email TEXT NOT NULL COLLATE NOCASE UNIQUE,
                display_name TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                last_login_at TEXT,
                must_change_password INTEGER NOT NULL DEFAULT 1
            );
            CREATE TABLE IF NOT EXISTS auth_user_roles (
                user_id TEXT NOT NULL REFERENCES auth_users(id) ON DELETE CASCADE,
                role_id TEXT NOT NULL REFERENCES auth_roles(role_id),
                PRIMARY KEY (user_id, role_id)
            );
            CREATE TABLE IF NOT EXISTS auth_sessions (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL REFERENCES auth_users(id) ON DELETE CASCADE,
                refresh_token_hash TEXT NOT NULL UNIQUE,
                expires_at TEXT NOT NULL,
                device_label TEXT,
                ip_address TEXT,
                user_agent TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                last_seen_at TEXT,
                revoked_at TEXT
            );
            CREATE TABLE IF NOT EXISTS auth_audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                event TEXT NOT NULL,
                ip_address TEXT,
                user_agent TEXT,
                metadata TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS auth_provider_secrets (
                provider TEXT NOT NULL,
                secret_name TEXT NOT NULL,
                ciphertext TEXT NOT NULL,
                masked_value TEXT NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 1,
                version INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_by TEXT,
                PRIMARY KEY (provider, secret_name)
            );
            CREATE TABLE IF NOT EXISTS icon_assets (
                asset_ref TEXT PRIMARY KEY,
                mime_type TEXT NOT NULL,
                content BLOB NOT NULL,
                sha256 TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS icons (
                icon_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                source TEXT NOT NULL,
                asset_ref TEXT NOT NULL REFERENCES icon_assets(asset_ref),
                category TEXT,
                tags TEXT NOT NULL DEFAULT '[]',
                style TEXT,
                description TEXT,
                mime_type TEXT NOT NULL,
                version INTEGER NOT NULL,
                is_deleted INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                metadata TEXT NOT NULL DEFAULT '{}'
            );
            INSERT OR IGNORE INTO auth_roles(role_id, description) VALUES
                ('admin', 'Application administrator'),
                ('designer', 'Design workspace user'),
                ('viewer', 'Read-only workspace user');
            INSERT OR IGNORE INTO app_schema_migrations(version) VALUES (1);
            """
        )


def seed_builtin_catalog(service) -> tuple[str, ...]:
    from pathlib import Path

    root = Path(__file__).resolve().parents[1] / "icon_library"
    return seed_builtin_icons(
        service,
        manifest_path=root / "assets" / "builtin" / "manifest.json",
        asset_directory=root / "assets" / "builtin",
    )


CREATE SCHEMA IF NOT EXISTS icon_library;

CREATE TABLE IF NOT EXISTS icon_library.icon_assets (
    asset_ref TEXT PRIMARY KEY,
    mime_type TEXT NOT NULL DEFAULT 'image/svg+xml',
    content BYTEA NOT NULL,
    sha256 TEXT NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS icon_library.icons (
    icon_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    source TEXT NOT NULL CHECK (source IN ('built_in', 'user_uploaded', 'ai_generated')),
    asset_ref TEXT NOT NULL REFERENCES icon_library.icon_assets(asset_ref),
    category TEXT,
    tags TEXT[] NOT NULL DEFAULT '{}',
    style TEXT,
    description TEXT,
    mime_type TEXT NOT NULL DEFAULT 'image/svg+xml',
    version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0),
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS icons_category_idx
    ON icon_library.icons (category);

CREATE INDEX IF NOT EXISTS icons_source_idx
    ON icon_library.icons (source);

CREATE INDEX IF NOT EXISTS icons_active_idx
    ON icon_library.icons (is_deleted);

CREATE INDEX IF NOT EXISTS icons_tags_idx
    ON icon_library.icons USING GIN (tags);

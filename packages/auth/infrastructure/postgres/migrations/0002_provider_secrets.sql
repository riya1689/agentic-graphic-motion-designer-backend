CREATE TABLE IF NOT EXISTS auth.provider_secrets (
    provider TEXT NOT NULL,
    secret_name TEXT NOT NULL DEFAULT 'api_key',
    ciphertext TEXT NOT NULL,
    masked_value TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    version INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_by UUID NULL REFERENCES auth.users(id) ON DELETE SET NULL,
    PRIMARY KEY (provider, secret_name)
);

CREATE INDEX IF NOT EXISTS auth_provider_secrets_active_idx
    ON auth.provider_secrets (provider, is_active);

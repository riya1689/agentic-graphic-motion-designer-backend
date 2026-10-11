"""Runtime provider-secret resolution boundary.

Provider adapters depend on this small interface instead of knowing how
secrets are persisted.  Database values are preferred; environment variables
remain a safe development/deployment fallback when the database secret is not
configured yet.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Iterable, Protocol


class RuntimeSecretSource(Protocol):
    def get_secret(self, *, provider: str, secret_name: str = "api_key") -> str | None:
        """Return a decrypted secret only inside trusted backend code."""


@dataclass
class _CacheEntry:
    value: str
    expires_at: float


class DatabaseBackedProviderSecretResolver:
    """Resolve provider credentials without coupling adapters to PostgreSQL."""

    def __init__(self, source: RuntimeSecretSource, *, cache_seconds: float = 10.0) -> None:
        self._source = source
        self._cache_seconds = max(0.0, cache_seconds)
        self._cache: dict[tuple[str, str], _CacheEntry] = {}

    def resolve(
        self,
        provider: str,
        *,
        secret_name: str = "api_key",
        environment_names: Iterable[str] = (),
    ) -> str | None:
        normalized_provider = provider.strip().lower()
        normalized_name = secret_name.strip().lower()
        cache_key = (normalized_provider, normalized_name)
        cached = self._cache.get(cache_key)
        if cached and cached.expires_at >= time.monotonic():
            return cached.value

        # A database outage must not turn a local development fallback into a
        # hard import-time failure. The adapter will still report a clear
        # missing credential error if no fallback exists.
        try:
            value = self._source.get_secret(
                provider=normalized_provider,
                secret_name=normalized_name,
            )
        except Exception:
            value = None
        if value and value.strip():
            clean_value = value.strip()
            self._cache[cache_key] = _CacheEntry(
                value=clean_value,
                expires_at=time.monotonic() + self._cache_seconds,
            )
            return clean_value

        for name in environment_names:
            fallback = os.getenv(name, "").strip()
            if fallback:
                return fallback
        return None

    def invalidate(self, provider: str | None = None, secret_name: str = "api_key") -> None:
        if provider is None:
            self._cache.clear()
            return
        self._cache.pop((provider.strip().lower(), secret_name.strip().lower()), None)


_runtime_resolver: DatabaseBackedProviderSecretResolver | None = None


def configure_runtime_provider_secret_resolver(source: RuntimeSecretSource) -> DatabaseBackedProviderSecretResolver:
    """Install the process-local resolver at the application composition root."""
    global _runtime_resolver
    _runtime_resolver = DatabaseBackedProviderSecretResolver(source)
    return _runtime_resolver


def resolve_provider_secret(
    provider: str,
    *,
    secret_name: str = "api_key",
    environment_names: Iterable[str] = (),
) -> str | None:
    """Resolve a secret for adapters; env-only behavior remains valid in tests."""
    if _runtime_resolver is not None:
        return _runtime_resolver.resolve(
            provider,
            secret_name=secret_name,
            environment_names=environment_names,
        )
    for name in environment_names:
        fallback = os.getenv(name, "").strip()
        if fallback:
            return fallback
    return None


def invalidate_runtime_provider_secret(provider: str | None = None, secret_name: str = "api_key") -> None:
    if _runtime_resolver is not None:
        _runtime_resolver.invalidate(provider, secret_name)

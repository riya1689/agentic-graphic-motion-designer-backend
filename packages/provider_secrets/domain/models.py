"""Provider-secret models that never expose secret plaintext."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class ProviderSecretSummary:
    provider: str
    secret_name: str
    masked_value: str
    is_active: bool
    version: int
    created_at: datetime
    updated_at: datetime

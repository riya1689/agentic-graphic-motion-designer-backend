from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class GoogleDriveIconSettings:
    folder_id: str = ""
    access_token: str = ""
    api_key: str = ""
    enabled: bool = False
    pull_interval_seconds: int = 30

    @classmethod
    def from_environment(cls) -> "GoogleDriveIconSettings":
        return cls(
            folder_id=os.getenv("GOOGLE_DRIVE_ICON_FOLDER_ID", "").strip(),
            access_token=os.getenv("GOOGLE_DRIVE_ACCESS_TOKEN", "").strip(),
            api_key=os.getenv("GOOGLE_DRIVE_API_KEY", "").strip(),
            enabled=_truthy(os.getenv("GOOGLE_DRIVE_ICON_SYNC_ENABLED", "false")),
            pull_interval_seconds=_positive_int(os.getenv("GOOGLE_DRIVE_ICON_PULL_INTERVAL_SECONDS", "30")),
        )

    @property
    def configured(self) -> bool:
        return self.enabled and bool(self.folder_id)


def _truthy(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _positive_int(value: str, default: int = 30) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default

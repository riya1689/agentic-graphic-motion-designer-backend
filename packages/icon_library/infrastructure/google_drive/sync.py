from __future__ import annotations

import time

from packages.icon_library.application.service import IconLibraryService
from packages.icon_library.domain.models import IconRecord, IconSource
from packages.icon_library.infrastructure.google_drive.client import GoogleDriveClient
from packages.icon_library.infrastructure.google_drive.config import GoogleDriveIconSettings
from packages.icon_library.infrastructure.google_drive.oauth import GoogleDriveOAuthManager
from packages.icon_library.ports import IconNotFoundError


class GoogleDriveIconSync:
    """Mirrors custom icons to a shared Drive folder and pulls new icons locally."""

    def __init__(self, service: IconLibraryService, settings: GoogleDriveIconSettings, oauth: GoogleDriveOAuthManager | None = None) -> None:
        self._service = service
        self._settings = settings
        self._oauth = oauth or GoogleDriveOAuthManager(settings)
        self._last_pull = 0.0

    @property
    def configured(self) -> bool:
        return bool(self._settings.configured and (self._oauth.access_token() or self._settings.api_key))

    def status(self) -> dict[str, object]:
        return {
            **self._oauth.status(),
            "ready": self.configured,
            "folder_id": self._settings.folder_id,
        }

    def start_authorization(self) -> str:
        return self._oauth.start()

    def complete_authorization(self, *, state: str, code: str) -> None:
        self._oauth.complete(state=state, code=code)

    def disconnect(self) -> None:
        self._oauth.disconnect()

    def pull_if_due(self) -> int:
        if not self.configured or time.monotonic() - self._last_pull < self._settings.pull_interval_seconds:
            return 0
        self._last_pull = time.monotonic()
        return self.pull()

    def pull(self) -> int:
        if not self.configured:
            return 0
        imported = 0
        client = self._client()
        for remote in client.list_svg_files(self._settings.folder_id):
            properties = remote.get("appProperties") or {}
            icon_id = properties.get("icon_id") or f"drive-{remote['id']}"
            try:
                self._service.get(icon_id)
                continue
            except IconNotFoundError:
                pass
            content = client.download(str(remote["id"]))
            record = IconRecord(
                icon_id=icon_id,
                name=properties.get("name") or str(remote.get("name", icon_id)).removesuffix(".svg"),
                source=IconSource(properties.get("source", IconSource.USER_UPLOADED)),
                asset_ref="pending",
                category=properties.get("category") or "shared",
                tags=tuple(tag for tag in properties.get("tags", "").split(",") if tag),
                style=properties.get("style") or None,
                description=properties.get("description") or None,
                metadata={"shared_drive_file_id": str(remote["id"]), "shared_drive_modified_time": remote.get("modifiedTime")},
            )
            self._service.add(record, svg_content=content)
            imported += 1
        return imported

    def push(self, icon: IconRecord, content: bytes) -> dict[str, str] | None:
        if not self.configured or icon.source == IconSource.BUILT_IN:
            return None
        remote = self._client().upload_svg(
            folder_id=self._settings.folder_id,
            filename=f"{icon.icon_id}.svg",
            content=content,
            properties={
                "icon_id": icon.icon_id,
                "name": icon.name,
                "source": icon.source.value,
                "category": icon.category or "",
                "tags": ",".join(icon.tags),
                "style": icon.style or "",
                "description": icon.description or "",
            },
        )
        return {"file_id": str(remote["id"]), "modified_time": str(remote.get("modifiedTime", ""))}

    def _client(self) -> GoogleDriveClient:
        return GoogleDriveClient(
            access_token=self._oauth.access_token() or "",
            api_key=self._settings.api_key,
        )

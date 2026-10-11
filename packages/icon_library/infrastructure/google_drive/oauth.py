from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any

from packages.sqlite_storage.credentials import CredentialManagerSecretStore


DRIVE_SCOPES = ("https://www.googleapis.com/auth/drive",)


class GoogleDriveOAuthManager:
    """Desktop OAuth flow with refresh credentials protected by Credential Manager."""

    def __init__(self, settings) -> None:
        self._settings = settings
        self._store = CredentialManagerSecretStore("GoogleDrive/OAuthCredentials")
        self._pending: dict[str, Any] = {}
        self._lock = threading.Lock()

    def client_config_path(self) -> Path:
        configured = os.getenv("GOOGLE_DRIVE_OAUTH_CLIENT_FILE", "").strip()
        if configured:
            return Path(configured).expanduser().resolve()
        config_dir = os.getenv("AGENTIC_CONFIG_DIR", "").strip()
        root = Path(config_dir) if config_dir else Path(os.getenv("LOCALAPPDATA", Path.home())) / "AgenticGraphicMotionDesigner"
        expected = (root / "google-drive-client.json").resolve()
        if expected.is_file():
            return expected

        # Google Cloud often downloads a generated filename. Accept a valid
        # OAuth client JSON from the app-data directory instead of requiring
        # the user to rename a credential file manually.
        for candidate in sorted(root.glob("*.json"), key=lambda item: item.name.lower()):
            if self._is_oauth_client_file(candidate):
                return candidate.resolve()
        return expected

    @staticmethod
    def _is_oauth_client_file(path: Path) -> bool:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, TypeError):
            return False
        for section_name in ("installed", "web"):
            section = payload.get(section_name) if isinstance(payload, dict) else None
            if not isinstance(section, dict):
                continue
            required = ("client_id", "client_secret", "auth_uri", "token_uri")
            if all(section.get(key) for key in required):
                return True
        return False

    def status(self) -> dict[str, Any]:
        return {
            "client_configured": self.client_config_path().is_file(),
            "client_path": str(self.client_config_path()),
            "connected": self._load_credentials() is not None,
            "folder_configured": bool(self._settings.folder_id),
            "enabled": self._settings.enabled,
        }

    def start(self) -> str:
        flow = self._new_flow()
        authorization_url, state = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            prompt="consent",
        )
        with self._lock:
            self._pending[state] = flow
        return authorization_url

    def complete(self, *, state: str, code: str) -> None:
        with self._lock:
            flow = self._pending.pop(state, None)
        if flow is None:
            raise ValueError("Google Drive authorization session expired. Start again.")
        flow.fetch_token(code=code)
        self._store.write(
            flow.credentials.to_json(),
            comment="Agentic Graphic Motion Designer Google Drive OAuth credentials",
        )

    def access_token(self) -> str | None:
        credentials = self._load_credentials()
        if credentials is None:
            return self._settings.access_token or None
        if not credentials.valid and credentials.expired and credentials.refresh_token:
            from google.auth.transport.requests import Request

            credentials.refresh(Request())
            self._store.write(
                credentials.to_json(),
                comment="Agentic Graphic Motion Designer Google Drive OAuth credentials",
            )
        return credentials.token if credentials.valid else None

    def disconnect(self) -> None:
        self._store.delete()

    def _new_flow(self):
        try:
            from google_auth_oauthlib.flow import InstalledAppFlow
        except ImportError as exc:
            raise RuntimeError(
                "Google OAuth dependencies are missing. Install google-auth-oauthlib."
            ) from exc
        path = self.client_config_path()
        if not path.is_file():
            raise RuntimeError(
                f"Google OAuth client JSON was not found at {path}. "
                "Download a Desktop OAuth client from Google Cloud Console."
            )
        flow = InstalledAppFlow.from_client_secrets_file(str(path), DRIVE_SCOPES)
        host = os.getenv("AGENTIC_BACKEND_HOST", "127.0.0.1")
        port = os.getenv("AGENTIC_BACKEND_PORT", "8000")
        if host in {"127.0.0.1", "0.0.0.0", "::1", "::"}:
            host = "localhost"
        flow.redirect_uri = f"http://{host}:{port}/api/icon-library/drive/callback"
        return flow

    def _load_credentials(self):
        raw = self._store.read()
        if not raw:
            return None
        try:
            from google.oauth2.credentials import Credentials

            return Credentials.from_authorized_user_info(json.loads(raw), DRIVE_SCOPES)
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            raise RuntimeError("Stored Google Drive OAuth credentials are invalid.") from exc

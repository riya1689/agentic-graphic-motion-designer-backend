"""Windows Credential Manager storage for the local SQLCipher key."""

from __future__ import annotations

import hashlib
import os
import secrets
from pathlib import Path
from typing import Callable


class CredentialManagerKeyStore:
    """Stores one random SQLCipher key in the current Windows credential vault."""

    def __init__(self, database_path: Path) -> None:
        self._target = (
            "AgenticGraphicMotionDesigner/SQLCipher/"
            + hashlib.sha256(str(database_path).lower().encode("utf-8")).hexdigest()
        )

    def get_or_create(self) -> str:
        try:
            import win32cred
        except ImportError as exc:
            raise RuntimeError(
                "pywin32 is required to unlock the desktop database through "
                "Windows Credential Manager."
            ) from exc

        try:
            credential = win32cred.CredRead(
                self._target,
                win32cred.CRED_TYPE_GENERIC,
            )
            value = credential.get("CredentialBlob", b"")
            if isinstance(value, bytes):
                value = value.decode("utf-8").replace("\x00", "")
            if value:
                return str(value).replace("\x00", "")
        except Exception as exc:
            error_code = getattr(exc, "winerror", None)
            if error_code not in {2, 1168}:  # credential not found
                raise RuntimeError("Could not read the desktop database key.") from exc

        key = secrets.token_hex(32)
        win32cred.CredWrite(
            {
                "Type": win32cred.CRED_TYPE_GENERIC,
                "TargetName": self._target,
                "CredentialBlob": key,
                "Persist": win32cred.CRED_PERSIST_LOCAL_MACHINE,
                "Comment": "Agentic Graphic Motion Designer SQLCipher key",
            },
            0,
        )
        return key


class CredentialManagerSecretStore:
    """Generic machine-persistent secret storage for desktop integrations."""

    def __init__(self, target_name: str) -> None:
        self._target = "AgenticGraphicMotionDesigner/" + target_name

    def read(self) -> str | None:
        import win32cred

        try:
            credential = win32cred.CredRead(self._target, win32cred.CRED_TYPE_GENERIC)
        except Exception as exc:
            if getattr(exc, "winerror", None) in {2, 1168}:
                return None
            raise RuntimeError("Could not read the stored desktop integration credential.") from exc
        value = credential.get("CredentialBlob", b"")
        if isinstance(value, bytes):
            value = value.decode("utf-8", errors="ignore")
        value = str(value).replace("\x00", "")
        return value or None

    def get_or_create(self, factory: Callable[[], str], *, comment: str) -> str:
        """Return a stable secret, creating it once in Credential Manager."""
        existing = self.read()
        if existing:
            return existing

        value = str(factory()).strip()
        if not value:
            raise RuntimeError("Credential Manager secret factory returned an empty value.")
        self.write(value, comment=comment)
        return value

    def write(self, value: str, *, comment: str) -> None:
        import win32cred

        win32cred.CredWrite(
            {
                "Type": win32cred.CRED_TYPE_GENERIC,
                "TargetName": self._target,
                "CredentialBlob": value,
                "Persist": win32cred.CRED_PERSIST_LOCAL_MACHINE,
                "Comment": comment,
            },
            0,
        )

    def delete(self) -> None:
        import win32cred

        try:
            win32cred.CredDelete(self._target, win32cred.CRED_TYPE_GENERIC, 0)
        except Exception as exc:
            if getattr(exc, "winerror", None) not in {2, 1168}:
                raise RuntimeError("Could not remove the stored desktop integration credential.") from exc


def database_path_from_environment() -> Path:
    configured = os.getenv("AGENTIC_SQLITE_PATH", "").strip()
    if configured:
        path = Path(configured)
    else:
        configured_root = os.getenv("AGENTIC_CONFIG_DIR", "").strip()
        root = Path(configured_root).expanduser() if configured_root else Path()
        if not configured_root:
            root = Path(os.getenv("LOCALAPPDATA", Path.home())) / "AgenticGraphicMotionDesigner"
        path = root / "data" / "app.sqlite3"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path.resolve()

from __future__ import annotations

import json
from typing import Any

import httpx


class GoogleDriveClient:
    """Small Drive v3 REST client; no Google database or SDK is required."""

    files_url = "https://www.googleapis.com/drive/v3/files"
    upload_url = "https://www.googleapis.com/upload/drive/v3/files"

    def __init__(self, *, access_token: str = "", api_key: str = "") -> None:
        self._access_token = access_token
        self._api_key = api_key

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._access_token}"} if self._access_token else {}

    def _params(self, **values: Any) -> dict[str, Any]:
        return {**values, **({"key": self._api_key} if self._api_key else {})}

    def list_svg_files(self, folder_id: str) -> list[dict[str, Any]]:
        response = httpx.get(
            self.files_url,
            headers=self._headers(),
            params=self._params(
                q=f"'{folder_id}' in parents and trashed = false and mimeType = 'image/svg+xml'",
                spaces="drive",
                fields="files(id,name,description,modifiedTime,appProperties,webContentLink,size)",
                pageSize=1000,
            ),
            timeout=20,
        )
        response.raise_for_status()
        return list(response.json().get("files", []))

    def download(self, file_id: str) -> bytes:
        response = httpx.get(
            f"{self.files_url}/{file_id}",
            headers=self._headers(),
            params=self._params(alt="media"),
            timeout=30,
        )
        response.raise_for_status()
        return response.content

    def upload_svg(self, *, folder_id: str, filename: str, content: bytes, properties: dict[str, str]) -> dict[str, Any]:
        boundary = "agentic-motion-designer-boundary"
        metadata = json.dumps({
            "name": filename,
            "parents": [folder_id],
            "mimeType": "image/svg+xml",
            "appProperties": properties,
        }, separators=(",", ":"))
        body = (
            f"--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n"
            f"{metadata}\r\n--{boundary}\r\nContent-Type: image/svg+xml\r\n\r\n"
        ).encode("utf-8") + content + f"\r\n--{boundary}--\r\n".encode("ascii")
        response = httpx.post(
            self.upload_url,
            headers={**self._headers(), "Content-Type": f"multipart/related; boundary={boundary}"},
            params=self._params(uploadType="multipart", fields="id,name,appProperties,modifiedTime"),
            content=body,
            timeout=45,
        )
        response.raise_for_status()
        return dict(response.json())


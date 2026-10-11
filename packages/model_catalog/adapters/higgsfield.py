"""Higgsfield CLI model discovery and normalization adapter.

The adapter accepts raw provider records and normalizes only fields explicitly
present in the provider response. It does not contain a hardcoded model list.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from packages.model_catalog.domain.model import CatalogModel


def _first(record: Dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in record and record[key] not in (None, ""):
            return record[key]
    return None


def _extract_records(payload: Any) -> List[Dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        raise ValueError("provider catalog response must be a JSON object or list")

    for key in ("models", "items", "results", "data"):
        nested = payload.get(key)
        if isinstance(nested, list):
            return [item for item in nested if isinstance(item, dict)]
        if isinstance(nested, dict):
            return [
                dict(value, model_id=key_id)
                for key_id, value in nested.items()
                if isinstance(value, dict)
            ]

    # Some catalog APIs return a single model object.
    if _first(payload, "model_id", "id", "slug", "model") is not None:
        return [payload]
    raise ValueError("provider catalog response contains no model records")


class HiggsfieldCatalogAdapter:
    provider_id = "higgsfield"

    def __init__(
        self,
        *,
        command_runner: Optional[Callable[[List[str]], str]] = None,
        executable: Optional[str] = None,
    ) -> None:
        self._command_runner = command_runner or self._run_cli
        self._executable = executable

    def discover_raw(self) -> List[Dict[str, Any]]:
        executable = self._executable or self._resolve_executable()
        payload = self._command_runner(
            [executable, "model", "list", "--json"]
        )
        return _extract_records(json.loads(payload))

    def discover(self) -> List[Any]:
        normalized: List[Any] = []
        for raw in self.discover_raw():
            try:
                normalized.append(self.normalize(raw))
            except Exception:
                # Preserve the invalid raw record so ModelCatalogService can
                # reject and count it without discarding valid siblings.
                normalized.append(raw)
        return normalized

    def normalize(self, raw: Dict[str, Any]) -> CatalogModel:
        # The live Higgsfield CLI uses job_type as its stable model identifier.
        model_id = _first(raw, "model_id", "id", "slug", "model", "job_type")
        model_name = _first(raw, "model_name", "name", "display_name", "label")
        media_type = _first(raw, "media_type", "mediaType", "type", "media")
        operations = _first(raw, "supported_operations", "operations") or []
        inputs = _first(raw, "supported_input_types", "input_types", "inputs") or []
        outputs = _first(raw, "supported_output_formats", "output_formats", "outputs") or []
        capabilities = _first(raw, "capabilities", "supported_capabilities") or []
        # A successful model-list response establishes catalog availability;
        # it does not assert that a generation job will succeed.
        availability = _first(raw, "availability", "status") or "available"

        capability_metadata = dict(raw.get("capability_metadata") or {})
        if not any(key in raw for key in ("supported_operations", "operations", "output_formats", "outputs")):
            capability_metadata["live_provider_catalog"] = True

        # The live Higgsfield image catalog currently reports only display
        # name/job_type/type. Standard image formats are provider defaults;
        # Recraft V4.1 is the documented direct-SVG exception.
        if str(media_type).lower() == "image" and capability_metadata.get("live_provider_catalog") and not outputs:
            outputs = ["png", "jpg", "webp"]
            if str(model_id).lower() == "recraft_v4_1":
                outputs.append("svg")
                capability_metadata["native_editable_formats"] = ["svg"]
                native_editable = True
            else:
                native_editable = False
        else:
            native_editable = bool(raw.get("native_editable_support", False))

        return CatalogModel(
            model_id=model_id,
            model_name=model_name or model_id,
            provider=self.provider_id,
            media_type=media_type,
            supported_operations=operations,
            supported_input_types=inputs,
            supported_output_formats=outputs,
            capabilities=capabilities,
            editable_output_support=bool(raw.get("editable_output_support", False)),
            native_editable_support=native_editable,
            capability_metadata=capability_metadata,
            availability=availability,
        )

    def discover_normalized(self) -> List[CatalogModel]:
        return [self.normalize(raw) for raw in self.discover_raw()]

    def _resolve_executable(self) -> str:
        executable = (
            shutil.which("higgsfield.cmd")
            or shutil.which("higgsfield")
            or os.getenv("HIGGSFIELD_EXECUTABLE")
        )
        if not executable:
            known_windows_path = Path("C:/nvm4w/nodejs/higgsfield.cmd")
            if known_windows_path.exists():
                executable = str(known_windows_path)
        if not executable:
            raise FileNotFoundError(
                "Higgsfield CLI was not found; model discovery is unavailable."
            )
        return executable

    @staticmethod
    def _run_cli(command: List[str]) -> str:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            shell=False,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"Higgsfield model discovery failed: {result.stderr or result.stdout}"
            )
        return result.stdout

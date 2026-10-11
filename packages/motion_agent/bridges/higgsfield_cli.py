"""
Higgsfield CLI Bridge for Motion Agent

RESPONSIBILITY:

Motion Tool
    ↓
Higgsfield CLI
    ↓
Higgsfield video generation
"""

from __future__ import annotations

import json
import shutil
import subprocess

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


# ============================================================
# HIGGSFIELD CLI RESULT
# ============================================================

@dataclass
class HiggsfieldMotionCLIResult:

    success: bool

    provider: str

    data: Dict[str, Any]

    result_url: Optional[str]

    stdout: str

    stderr: str

    return_code: int


# ============================================================
# RESULT URL FINDER
# ============================================================

def _find_result_url(
    value: Any,
) -> Optional[str]:
    """
    Extract generated video URL from Higgsfield JSON output.
    """

    if isinstance(value, dict):

        for key in (
            "result_url",
            "resultUrl",
            "output_url",
            "outputUrl",
            "video_url",
            "videoUrl",
            "media_url",
            "mediaUrl",
            "url",
        ):

            candidate = value.get(key)

            if (
                isinstance(candidate, str)
                and candidate.startswith(("http://", "https://"))
            ):
                return candidate

        for nested_value in value.values():

            found = _find_result_url(nested_value)

            if found:
                return found

    elif isinstance(value, list):

        for item in value:

            found = _find_result_url(item)

            if found:
                return found

    return None


# ============================================================
# WINDOWS EXECUTABLE RESOLUTION
# ============================================================

def _resolve_higgsfield_executable() -> str:

    executable = (
        shutil.which("higgsfield.cmd")
        or shutil.which("higgsfield")
    )

    if not executable:

        raise FileNotFoundError(
            "Higgsfield CLI was not found on PATH. "
            "Expected 'higgsfield.cmd' or 'higgsfield'."
        )

    return executable


# ============================================================
# HIGGSFIELD MOTION CLI BRIDGE
# ============================================================

class HiggsfieldMotionCLI:

    provider_id = "higgsfield"


    # ========================================================
    # EXECUTE
    # ========================================================

    def execute(
        self,
        command: List[str],
        stdin_text: Optional[str] = None,
    ) -> HiggsfieldMotionCLIResult:

        if not command:

            raise ValueError(
                "Higgsfield CLI command is empty."
            )

        resolved_command = list(command)

        first_part = str(resolved_command[0]).lower()

        if first_part in ("higgsfield", "higgsfield.cmd", "higgs", "hf"):

            resolved_command[0] = _resolve_higgsfield_executable()

        print("[MOTION BRIDGE] Calling Higgsfield CLI")
        print("[MOTION BRIDGE] Executable:", resolved_command[0])

        result = subprocess.run(
            resolved_command,
            input=stdin_text,
            capture_output=True,
            text=True,
            shell=False,
        )

        stdout = (result.stdout or "").strip()
        stderr = (result.stderr or "").strip()

        if result.returncode != 0:

            raise RuntimeError(
                "Higgsfield CLI video generation failed. "
                f"Return code={result.returncode}. "
                f"Error={stderr or stdout}"
            )

        try:
            data = json.loads(stdout)
        except json.JSONDecodeError:
            data = {"raw_output": stdout}

        result_url = _find_result_url(data)

        return HiggsfieldMotionCLIResult(
            success=True,
            provider=self.provider_id,
            data=data,
            result_url=result_url,
            stdout=stdout,
            stderr=stderr,
            return_code=result.returncode,
        )
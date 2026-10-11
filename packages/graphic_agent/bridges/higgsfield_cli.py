"""
Higgsfield CLI Bridge for Graphic Agent

RESPONSIBILITY:

Graphic Tool
    ↓
Higgsfield CLI
    ↓
Higgsfield image generation

IMPORTANT:

This file contains transport/provider communication only.

NO:
- Manager logic
- Planner logic
- Graphic workflow logic
- tool selection
- prompt planning
- verification
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
class HiggsfieldGraphicCLIResult:

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
    Extract generated media URL from Higgsfield JSON.

    Supports nested dict/list responses without tying the
    tool layer to Higgsfield response structure.
    """

    if isinstance(
        value,
        dict,
    ):

        # Prefer explicit result/media fields first.
        for key in (
            "result_url",
            "resultUrl",
            "output_url",
            "outputUrl",
            "media_url",
            "mediaUrl",
            "url",
        ):

            candidate = value.get(
                key
            )

            if (
                isinstance(
                    candidate,
                    str,
                )
                and
                candidate.startswith(
                    (
                        "http://",
                        "https://",
                    )
                )
            ):

                return candidate


        # Recursively inspect nested values.
        for nested_value in value.values():

            found = _find_result_url(
                nested_value
            )

            if found:
                return found


    elif isinstance(
        value,
        list,
    ):

        for item in value:

            found = _find_result_url(
                item
            )

            if found:
                return found


    return None


# ============================================================
# WINDOWS-SAFE HIGGSFIELD CLI RESOLUTION
# ============================================================

def _resolve_higgsfield_executable() -> str:
    """
    Resolve installed Higgsfield CLI.

    Windows npm/nvm normally exposes:

        higgsfield.cmd
    """

    executable = (
        shutil.which(
            "higgsfield.cmd"
        )
        or
        shutil.which(
            "higgsfield"
        )
    )

    if not executable:

        raise FileNotFoundError(
            "Higgsfield CLI was not found. "
            "Expected 'higgsfield.cmd' or "
            "'higgsfield' on PATH."
        )

    return executable


# ============================================================
# HIGGSFIELD GRAPHIC CLI BRIDGE
# ============================================================

class HiggsfieldGraphicCLI:

    provider_id = "higgsfield"


    # ========================================================
    # EXECUTE
    # ========================================================

    def execute(
        self,
        command: List[str],
        stdin_text: Optional[str] = None,
    ) -> HiggsfieldGraphicCLIResult:
        """
        Execute a prepared Higgsfield CLI command.

        IMPORTANT:

        Long generation prompts should NOT be placed inside
        the Windows command line.

        Instead the Graphic Tool passes the prompt through
        stdin_text.

        Example equivalent CLI usage:

            echo "prompt" |
            higgsfield generate create nano_banana_2 --wait
        """

        if not command:

            raise ValueError(
                "Higgsfield CLI command is empty."
            )


        # ====================================================
        # RESOLVE WINDOWS EXECUTABLE
        # ====================================================

        resolved_command = list(
            command
        )


        first_command_part = str(
            resolved_command[0]
        ).lower()


        if first_command_part in (
            "higgsfield",
            "higgsfield.cmd",
            "higgs",
            "hf",
        ):

            resolved_command[0] = (
                _resolve_higgsfield_executable()
            )


        # ====================================================
        # DEBUG
        # ====================================================

        print(
            "[GRAPHIC BRIDGE] Calling Higgsfield CLI"
        )

        print(
            "[GRAPHIC BRIDGE] Executable:",
            resolved_command[0],
        )

        if stdin_text:

            print(
                "[GRAPHIC BRIDGE] Prompt transport = STDIN"
            )

            print(
                "[GRAPHIC BRIDGE] Prompt length =",
                len(stdin_text),
            )


        # ====================================================
        # EXECUTE HIGGSFIELD CLI
        # ====================================================
        #
        # IMPORTANT:
        #
        # input=stdin_text prevents huge prompts from being
        # inserted into the Windows command line.
        #
        # This fixes:
        #
        #     The command line is too long.
        # ====================================================

        result = subprocess.run(

            resolved_command,

            input=stdin_text,

            capture_output=True,

            text=True,

            check=False,

            shell=False,

        )


        stdout = (
            result.stdout
            or ""
        ).strip()

        stderr = (
            result.stderr
            or ""
        ).strip()


        # ====================================================
        # CLI FAILURE
        # ====================================================

        if result.returncode != 0:

            raise RuntimeError(
                "Higgsfield CLI failed. "
                f"Return code={result.returncode}. "
                f"Error={stderr or stdout}"
            )


        # ====================================================
        # JSON RESPONSE
        # ====================================================

        try:

            data = json.loads(
                stdout
            )

        except json.JSONDecodeError as exc:

            raise RuntimeError(
                "Higgsfield CLI did not return "
                "valid JSON output. "
                f"stdout={stdout!r} "
                f"stderr={stderr!r}"
            ) from exc


        # ====================================================
        # EXTRACT GENERATED RESULT URL
        # ====================================================

        result_url = _find_result_url(
            data
        )


        if not result_url:

            raise RuntimeError(
                "Higgsfield generation completed "
                "but no result URL was found. "
                f"Response={data!r}"
            )


        # ====================================================
        # SUCCESS
        # ====================================================

        return HiggsfieldGraphicCLIResult(

            success=True,

            provider=self.provider_id,

            data=data,

            result_url=result_url,

            stdout=stdout,

            stderr=stderr,

            return_code=result.returncode,

        )
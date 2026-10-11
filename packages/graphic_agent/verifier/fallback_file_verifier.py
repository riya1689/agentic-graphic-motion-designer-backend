"""
Graphic Agent JSX Fallback File Verifier

Only verifies file evidence.

No design business logic.
"""

from __future__ import annotations

from pathlib import Path


# ============================================================
# VERIFY JSX FILE
# ============================================================

def verify_jsx_file(
    file_path: str,
) -> bool:

    if not file_path:

        return False

    path = Path(
        file_path
    )

    if not path.exists():

        return False

    if not path.is_file():

        return False

    if path.suffix.lower() != ".jsx":

        return False

    if path.stat().st_size <= 0:

        return False

    return True
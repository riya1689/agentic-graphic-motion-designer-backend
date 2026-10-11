"""
Graphic Agent API Key Pool

Multiple Gemini API keys priority order-এ load করে।

.env example:

GRAPHIC_GEMINI_API_KEYS=key_1||key_2||key_3

IMPORTANT:
- key value কখনো terminal-এ print করা হবে না।
- order preserve করা হবে।
"""

from __future__ import annotations

import os
from typing import List


# ============================================================
# LOAD GRAPHIC GEMINI API KEYS
# ============================================================

def load_graphic_gemini_api_keys() -> List[str]:
    """
    GRAPHIC_GEMINI_API_KEYS environment variable থেকে
    priority order-এ API keys return করে।
    """

    raw_keys = os.getenv(
        "GRAPHIC_GEMINI_API_KEYS",
        "",
    ).strip()

    # --------------------------------------------------------
    # Backward compatibility:
    #
    # যদি multiple-key variable না থাকে,
    # previous single key variable try করবে।
    # --------------------------------------------------------

    if not raw_keys:

        single_key = os.getenv(
            "GRAPHIC_GEMINI_API_KEY",
            "",
        ).strip()

        if single_key:

            return [single_key]

        raise RuntimeError(
            "No Graphic Gemini API key found. "
            "Set GRAPHIC_GEMINI_API_KEYS or "
            "GRAPHIC_GEMINI_API_KEY in .env."
        )

    # --------------------------------------------------------
    # Parse:
    #
    # key1||key2||key3
    # --------------------------------------------------------

    keys = [

        key.strip()

        for key in raw_keys.split("||")

        if key.strip()
    ]

    if not keys:

        raise RuntimeError(
            "GRAPHIC_GEMINI_API_KEYS contains no valid keys."
        )

    return keys
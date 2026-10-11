"""
Manager Agent Registry

এই file-এর কাজ:
- registered agents load করা
- agent configuration খুঁজে বের করা
- future agent dynamically add করার foundation তৈরি করা

Manager workflow-এর ভিতরে agent URL hardcode করা হবে না।
"""

import json
from pathlib import Path
from typing import Any, Dict


# ============================================================
# REGISTRY FILE LOCATION
# ============================================================

REGISTRY_FILE = (
    Path(__file__).resolve().parent.parent
    / "registry"
    / "agents.json"
)


# ============================================================
# LOAD COMPLETE REGISTRY
# ============================================================

def load_agent_registry() -> Dict[str, Any]:
    """
    agents.json file load করে পুরো agent registry return করে।
    """

    if not REGISTRY_FILE.exists():
        raise FileNotFoundError(
            f"Agent registry not found: {REGISTRY_FILE}"
        )

    with open(REGISTRY_FILE, "r", encoding="utf-8") as file:
        registry = json.load(file)

    return registry


# ============================================================
# GET SINGLE AGENT CONFIGURATION
# ============================================================

def get_agent_config(agent_id: str) -> Dict[str, Any]:
    """
    একটি agent-এর configuration return করে।

    Example:
        get_agent_config("prompt_to_json_agent")
    """

    registry = load_agent_registry()

    agent_config = registry.get(agent_id)

    if not agent_config:
        raise ValueError(
            f"Agent '{agent_id}' is not registered."
        )

    if not agent_config.get("enabled", False):
        raise ValueError(
            f"Agent '{agent_id}' is currently disabled."
        )

    return agent_config
"""
Manager Agent Dispatcher

এই file-এর কাজ:
- Registry থেকে agent খুঁজে বের করা
- HTTP-এর মাধ্যমে task পাঠানো
- Agent response Manager-কে return করা

IMPORTANT:
Manager এখানে agent-এর internal code import করছে না।

অর্থাৎ:

Manager
   ↓ HTTP
Prompt-to-JSON Agent

এতে agents independently deploy করা যাবে।
"""

from typing import Any, Dict

import httpx

from packages.manager_agent.orchestrator.registry import (
    get_agent_config,
)


# ============================================================
# GENERIC AGENT DISPATCHER
# ============================================================

async def dispatch_to_agent(
    agent_id: str,
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    """
    যেকোনো registered agent-এর কাছে task পাঠায়।

    Manager agent-specific business logic জানে না।
    """

    # --------------------------------------------------------
    # STEP 1:
    # Registry থেকে agent configuration নাও
    # --------------------------------------------------------

    agent_config = get_agent_config(agent_id)

    base_url = agent_config["base_url"]
    execute_path = agent_config["execute_path"]

    endpoint = f"{base_url}{execute_path}"

    # --------------------------------------------------------
    # STEP 2:
    # Agent-এর কাছে HTTP request পাঠাও
    # --------------------------------------------------------


    timeout=httpx.Timeout(
        # Time allowed to establish the HTTP connection.
        connect=10.0,

        # Time allowed while waiting for the agent response.
        #
        # 5 minutes is safer for Planner / remote AI work.
        read=300.0,

        # Time allowed to upload/send request payload.
        write=30.0,

        # Time allowed to acquire a connection from pool.
        pool=30.0,
    )

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:

            response = await client.post(
                endpoint,
                json=payload,
            )

            # HTTP 4xx / 5xx হলে exception
            response.raise_for_status()

            return response.json()

    # ========================================================
    # ADDED:
    # RESPONSE TIMEOUT HANDLING
    # ========================================================
    #
    # Important:
    #
    # ReadTimeout means:
    #
    # connection হয়েছিল,
    # request agent-এর কাছে গিয়েছিল,
    # কিন্তু agent response দিতে বেশি সময় নিয়েছে।
    #
    # তাই এটাকে "Could not connect" বলা ভুল।
    # ========================================================

    except httpx.ReadTimeout as exc:

        raise RuntimeError(
            f"Agent '{agent_id}' response timed out "
            f"while waiting for {endpoint}. "
            "The agent may still be processing the task."
        ) from exc


    # ========================================================
    # ADDED:
    # CONNECTION TIMEOUT HANDLING
    # ========================================================

    except httpx.ConnectTimeout as exc:

        raise RuntimeError(
            f"Connection to agent '{agent_id}' timed out "
            f"at {endpoint}."
        ) from exc


    # ========================================================
    # EXISTING:
    # HTTP STATUS ERROR
    # ========================================================

    except httpx.HTTPStatusError as exc:

        raise RuntimeError(
            f"Agent '{agent_id}' returned HTTP error: "
            f"{exc.response.status_code} "
            f"{exc.response.text}"
        ) from exc


    # ========================================================
    # CHANGED:
    # GENERAL REQUEST / NETWORK ERROR
    # ========================================================
    #
    # This now handles actual remaining transport errors.
    # ReadTimeout and ConnectTimeout are already handled above.
    # ========================================================

    except httpx.RequestError as exc:

        raise RuntimeError(
            f"Request to agent '{agent_id}' failed "
            f"at {endpoint}. "
            f"Error: {str(exc)}"
        ) from exc
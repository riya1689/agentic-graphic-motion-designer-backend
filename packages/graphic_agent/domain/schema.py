"""
Graphic Agent Domain Schemas

Phase-1 purpose:

Manager থেকে আসা Planner plan-কে Graphic Agent-এর
internal structured task হিসেবে represent করা।

IMPORTANT:

এই phase-এ Planner plan-এর internal fields আমরা hardcode করছি না।

কারণ Planner Agent already তার own schema অনুযায়ী
final_output generate এবং verify করেছে।

Graphic Agent Phase-1 শুধু নিশ্চিত করবে:

    - job_id আছে
    - planner_plan এসেছে
    - plan empty না
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


# ============================================================
# GRAPHIC TASK
# ============================================================

class GraphicTask(BaseModel):
    """
    Graphic Agent-এর internal task representation.

    Manager API payload সরাসরি agent logic-এর everywhere
    pass না করে একটি domain model ব্যবহার করা হচ্ছে।
    """

    # Manager job ID
    job_id: str

    # Planner Agent-এর final verified execution plan
    planner_plan: Dict[str, Any] = Field(
        default_factory=dict
    )

    # Original user request context হিসেবে রাখা হচ্ছে
    original_user_request: str = ""

    selected_image_model: Optional[str] = None

    # Loop Engineering:
    # validation / repair loop bounded থাকবে।
    max_validation_attempts: int = 2
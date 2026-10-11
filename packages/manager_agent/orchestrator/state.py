"""
Manager Agent Workflow State

এই file-এর কাজ:
- একটি job-এর current অবস্থান track করা
- কোন agent pending/running/completed/failed তা track করা
- agent output store করা
- next agent track করা

এখানে কোনো LLM call নেই।
এখানে কোনো business logic নেই।
"""

from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


# ============================================================
# WORKFLOW STATUS
# ============================================================

class WorkflowStatus(str, Enum):
    CREATED = "created"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


# ============================================================
# INDIVIDUAL AGENT STATUS
# ============================================================

class AgentTaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


# ============================================================
# AGENT TASK STATE
# ============================================================

class AgentTaskState(BaseModel):
    """
    একটি নির্দিষ্ট agent-এর execution status।
    """

    status: AgentTaskStatus = AgentTaskStatus.PENDING

    # Agent execution-এর output
    output: Optional[Any] = None

    # Error হলে এখানে রাখা হবে
    error: Optional[str] = None


# ============================================================
# COMPLETE MANAGER JOB STATE
# ============================================================

class ManagerWorkflowState(BaseModel):
    """
    Manager একটি user request-এর জন্য এই state maintain করবে।
    """

    # Unique job ID
    job_id: str

    # User-এর original prompt
    original_prompt: str

    selected_image_model: Optional[str] = None
    selected_video_model: Optional[str] = None
    status: WorkflowStatus = WorkflowStatus.CREATED

    # পুরো workflow-এর status
    status: WorkflowStatus = WorkflowStatus.CREATED

    # বর্তমানে কোন stage চলছে
    current_stage: str = "manager_received"

    # বর্তমানে কোন agent কাজ করছে
    current_agent: Optional[str] = None

    # পরবর্তী agent কে হবে
    next_agent: Optional[str] = "prompt_to_json_agent"

    # প্রতিটি agent-এর execution tracking
    agent_tasks: Dict[str, AgentTaskState] = Field(
        default_factory=lambda: {
            "prompt_to_json_agent": AgentTaskState(),
            "planner_agent": AgentTaskState(),
            "graphic_agent": AgentTaskState(),
            "motion_agent": AgentTaskState(),
        }
    )

    # Agent-generated artifacts / outputs এখানে থাকবে
    artifacts: Dict[str, Any] = Field(default_factory=dict)
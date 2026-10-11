"""
Motion LLM Provider Contract

Motion Agent must not depend directly on Gemini.

Future:

Gemini
OpenAI
Claude
local model

can implement this interface.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict

from packages.motion_agent.compiler.schema import (
    MotionExecutionSpec,
)


class MotionLLMProvider(ABC):

    provider_id: str


    @abstractmethod
    def compile_execution_spec(
        self,
        *,
        job_id: str,
        planner_plan: Dict[str, Any],
        original_user_request: str,
    ) -> MotionExecutionSpec:
        """
        Convert Planner plan into generic MotionExecutionSpec.
        """

        raise NotImplementedError
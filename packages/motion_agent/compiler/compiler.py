"""
Motion Execution Compiler

This module coordinates:

Planner plan
    ↓
Motion LLM provider
    ↓
MotionExecutionSpec

It knows nothing about video-generation models.
"""

from __future__ import annotations

from typing import Any, Dict

from packages.motion_agent.compiler.schema import (
    MotionExecutionSpec,
)

from packages.motion_agent.llm.base import (
    MotionLLMProvider,
)


class MotionExecutionCompiler:

    def __init__(
        self,
        provider: MotionLLMProvider,
    ):

        self.provider = provider


    def compile(
        self,
        *,
        job_id: str,
        planner_plan: Dict[str, Any],
        original_user_request: str,
    ) -> MotionExecutionSpec:

        return self.provider.compile_execution_spec(

            job_id=job_id,

            planner_plan=planner_plan,

            original_user_request=(
                original_user_request
            ),

        )
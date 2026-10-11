"""Focused workflow state owned by the Orchestrator."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional

from packages.execution.domain.contracts import ExecutionResult
from packages.model_catalog.domain.model import CatalogModel
from packages.planner_integration.domain.contracts import ComplexityDecision, ExecutionPlan
from packages.request_contract.domain.schema import NormalizedRequest
from packages.verification.domain.contracts import VerificationResult


class WorkflowStage(str, Enum):
    UNDERSTANDING = "understanding"
    VALIDATING = "validating"
    ROUTING = "routing"
    DECIDING = "deciding"
    PLANNING = "planning"
    EXECUTING = "executing"
    VERIFYING = "verifying"
    REPAIRING = "repairing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class OrchestratorState:
    request_id: str
    raw_input: str
    request: Optional[NormalizedRequest] = None
    current_stage: WorkflowStage = WorkflowStage.UNDERSTANDING
    selected_model: Optional[CatalogModel] = None
    complexity: Optional[ComplexityDecision] = None
    plan: Optional[ExecutionPlan] = None
    execution_status: Optional[str] = None
    execution_result: Optional[ExecutionResult] = None
    verification_result: Optional[VerificationResult] = None
    retry_count: int = 0
    final_output: Optional[Dict[str, Any]] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None


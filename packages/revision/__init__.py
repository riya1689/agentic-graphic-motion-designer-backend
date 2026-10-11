"""Controlled, provider-neutral design revision capability."""

from .domain import (
    DesignTrace,
    RevisionDecision,
    RevisionPatch,
    RevisionRecord,
    RevisionRequest,
    RevisionResult,
    RevisionStatus,
)
from .application import RevisionPatchApplier, RevisionLoop

__all__ = [
    "RevisionDecision", "RevisionPatch", "RevisionRecord", "RevisionRequest",
    "RevisionResult", "RevisionStatus", "RevisionPatchApplier", "RevisionLoop",
    "DesignTrace",
]

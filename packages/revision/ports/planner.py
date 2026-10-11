from typing import Protocol

from packages.revision.domain import RevisionDecision, RevisionRequest


class RevisionPlannerPort(Protocol):
    def plan(self, request: RevisionRequest) -> RevisionDecision:
        ...

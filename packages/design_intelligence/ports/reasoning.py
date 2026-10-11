"""Provider-neutral design-reasoning port."""

from __future__ import annotations

from typing import Protocol

from packages.design_intelligence.domain.specification import DesignBrief, DesignSpecification


class DesignReasoningPort(Protocol):
    """External or deterministic reasoner used by the application boundary."""

    def reason(self, brief: DesignBrief) -> DesignSpecification:
        ...

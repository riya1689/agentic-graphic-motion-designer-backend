"""
Base Graphic Tool Contract

Every Graphic Agent tool should expose
a common execution interface.

Future tools:
    Nano Banana
    Photoshop
    Illustrator
    Canva
    Stitch
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict


class GraphicTool(ABC):

    tool_id: str

    @abstractmethod
    def execute(
        self,
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Execute a graphic tool.

        Must return a serializable dictionary.
        """
        raise NotImplementedError
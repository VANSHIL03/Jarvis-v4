"""
JARVIS v4 - Abstract Base Agent Class
"""

from abc import ABC, abstractmethod
from typing import Dict, Any

class BaseAgent(ABC):
    @property
    @abstractmethod
    def agent_name(self) -> str:
        """Returns the specialized agent name."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Returns description of sub-agent responsibilities."""
        pass

    @abstractmethod
    async def execute_task(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Executes assigned task action asynchronously."""
        pass

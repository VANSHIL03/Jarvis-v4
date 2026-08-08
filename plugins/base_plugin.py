"""
JARVIS v4 - Abstract Base Plugin Specification
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List

class BasePlugin(ABC):
    @property
    @abstractmethod
    def plugin_name(self) -> str:
        """Returns the unique name of the plugin."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Returns plugin capabilities description."""
        pass

    @abstractmethod
    def get_supported_commands(self) -> List[str]:
        """Returns list of supported command action names."""
        pass

    @abstractmethod
    def execute(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Executes specified command action with parameter dictionary."""
        pass

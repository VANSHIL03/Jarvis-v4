"""
JARVIS v4 Controlled Tool Registry Package

`build_registry()` is the single place the whole tool catalogue is assembled, so
main.py, the mobile server and the tests all get an identical registry instead of
each wiring up its own subset.
"""

from typing import Any, Dict, Optional

from tools.base import ToolCall, ToolParam, ToolResult, ToolSpec
from tools.registry import ToolRegistry

from tools.browser_tools import BROWSER_TOOLS
from tools.coding_tools import CODING_TOOLS
from tools.document_tools import DOCUMENT_TOOLS
from tools.file_tools import FILE_TOOLS
from tools.integration_tools import build_integration_tools
from tools.memory_tools import MEMORY_TOOLS
from tools.system_tools import SYSTEM_TOOLS
from tools.vision_tools import VISION_TOOLS
from tools.whatsapp_tools import build_whatsapp_tools


def build_registry(
    agents: Optional[Dict[str, Any]] = None,
    policy: Optional[Any] = None,
    db: Any = None,
) -> ToolRegistry:
    """
    Assembles every tool JARVIS can run.

    `agents` is main.py's live sub-agent dict; the WhatsApp and integration
    factories keep a reference to it rather than a copy, so a dict that is still
    being filled in is fine. `db` is the DatabaseManager whose contacts table
    decides whether a WhatsApp recipient is certain enough to skip confirmation
    (Section 13). Passing neither still produces a complete, valid registry --
    tools whose agent is missing fail cleanly at execution time instead of
    vanishing from the catalogue.
    """
    registry = ToolRegistry(policy=policy, agents=agents)

    registry.register_all(SYSTEM_TOOLS)
    registry.register_all(FILE_TOOLS)
    registry.register_all(BROWSER_TOOLS)
    registry.register_all(build_whatsapp_tools(agents, db))
    registry.register_all(VISION_TOOLS)
    registry.register_all(CODING_TOOLS)
    registry.register_all(MEMORY_TOOLS)
    registry.register_all(DOCUMENT_TOOLS)
    registry.register_all(build_integration_tools(agents))
    return registry


__all__ = [
    "ToolCall",
    "ToolParam",
    "ToolResult",
    "ToolSpec",
    "ToolRegistry",
    "build_registry",
    "BROWSER_TOOLS",
    "CODING_TOOLS",
    "DOCUMENT_TOOLS",
    "FILE_TOOLS",
    "MEMORY_TOOLS",
    "SYSTEM_TOOLS",
    "VISION_TOOLS",
    "build_integration_tools",
    "build_whatsapp_tools",
]

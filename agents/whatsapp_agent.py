"""
JARVIS v4 - WhatsApp UI Automation Agent
"""

from typing import Dict, Any
from agents.base_agent import BaseAgent
from plugins.whatsapp_plugin import WhatsAppPlugin

class WhatsAppAgent(BaseAgent):
    def __init__(self, plugin: WhatsAppPlugin):
        self.plugin = plugin

    @property
    def agent_name(self) -> str:
        return "whatsapp_agent"

    @property
    def description(self) -> str:
        return "Automates WhatsApp Desktop UI for messaging, reading unread chats, sending attachments and voice notes."

    async def execute_task(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        return self.plugin.execute(action, params)

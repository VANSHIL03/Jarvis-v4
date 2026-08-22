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
        return "Automates WhatsApp Desktop UI for messaging, voice/video calling, reading unread chats, sending attachments and voice notes."

    async def execute_task(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        action = (action or "").lower()

        if action in ["video_call", "voice_call", "end_call", "find_contact"]:
            res = self.plugin.execute(action, params)
            res.setdefault("speech_reply", self._call_speech(action, params, res))
            return res

        return self.plugin.execute(action, params)

    def _call_speech(self, action: str, params: Dict[str, Any], res: Dict[str, Any]) -> str:
        """Builds the Hinglish spoken confirmation for call outcomes."""
        asked = params.get("contact_name") or params.get("contact", "")
        contact = res.get("contact") or asked
        status = res.get("status")
        kind = "video call" if action == "video_call" else "call"

        if action == "end_call":
            return "Ji Sir, call end kar diya hai." if status == "success" else "Sir, koi active WhatsApp call nahi mila."

        if status == "success":
            if action == "find_contact":
                return f"Ji Sir, WhatsApp par '{contact}' mil gaya hai."
            return f"Ji Sir, {contact} ko WhatsApp {kind} laga raha hoon."

        if status == "ambiguous":
            names = ", ".join(res.get("candidates", [])[:4])
            return f"Sir, '{asked}' naam ke kai contacts hain: {names}. Kaun sa call karna hai?"

        if status == "not_found":
            return f"Sir, WhatsApp par '{asked}' naam ka koi contact nahi mila."

        return f"Sir, {kind} nahi lag paya. {res.get('message', '')}".strip()

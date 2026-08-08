"""
JARVIS v4 - Discord Integration Plugin
"""

import subprocess
from typing import Dict, Any, List
from plugins.base_plugin import BasePlugin

class DiscordPlugin(BasePlugin):
    @property
    def plugin_name(self) -> str:
        return "discord"

    @property
    def description(self) -> str:
        return "Launches Discord desktop client and handles quick navigation."

    def get_supported_commands(self) -> List[str]:
        return ["open_discord"]

    def execute(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        if action == "open_discord":
            subprocess.Popen(["start", "discord:"], shell=True)
            return {"status": "success", "message": "Discord client launched."}
        return {"status": "error", "message": f"Unknown action: '{action}'"}

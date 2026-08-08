"""
JARVIS v4 - Steam Gaming Plugin
"""

import subprocess
from typing import Dict, Any, List
from plugins.base_plugin import BasePlugin

class SteamPlugin(BasePlugin):
    @property
    def plugin_name(self) -> str:
        return "steam"

    @property
    def description(self) -> str:
        return "Launches Steam client and starts configured game titles."

    def get_supported_commands(self) -> List[str]:
        return ["open_steam", "launch_game"]

    def execute(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        if action == "open_steam":
            subprocess.Popen(["start", "steam:"], shell=True)
            return {"status": "success", "message": "Steam launched."}
        elif action == "launch_game":
            app_id = params.get("app_id", "")
            subprocess.Popen(["start", f"steam://rungameid/{app_id}"], shell=True)
            return {"status": "success", "message": f"Steam launched game ID {app_id}."}
        return {"status": "error", "message": f"Unknown Steam action: '{action}'"}

"""
JARVIS v4 - Gaming & Unity Game Dev Agent
"""

from typing import Dict, Any
from agents.base_agent import BaseAgent
from plugins.steam_plugin import SteamPlugin
from plugins.unity_plugin import UnityPlugin

class GamingAgent(BaseAgent):
    def __init__(self, steam_plugin: SteamPlugin, unity_plugin: UnityPlugin):
        self.steam = steam_plugin
        self.unity = unity_plugin

    @property
    def agent_name(self) -> str:
        return "gaming_agent"

    @property
    def description(self) -> str:
        return "Handles Steam game launches, gaming controls, and Unity engine project/C# script templates."

    async def execute_task(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        action = action.lower()
        if action in ["open_steam", "launch_game"]:
            return self.steam.execute(action, params)
        elif action in ["open_hub", "create_csharp_script"]:
            return self.unity.execute(action, params)

        return {"status": "error", "message": f"Unknown gaming action: '{action}'"}

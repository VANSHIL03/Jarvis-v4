"""
JARVIS v4 - Chrome Browser Plugin
"""

import subprocess
from typing import Dict, Any, List
from plugins.base_plugin import BasePlugin

class ChromePlugin(BasePlugin):
    @property
    def plugin_name(self) -> str:
        return "chrome"

    @property
    def description(self) -> str:
        return "Controls Google Chrome browser tabs, URLs, and incognito sessions."

    def get_supported_commands(self) -> List[str]:
        return ["open_url", "incognito"]

    def execute(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        url = params.get("url", "https://google.com")
        if action == "open_url":
            subprocess.Popen(["start", "chrome", url], shell=True)
            return {"status": "success", "message": f"Chrome opened {url}"}
        elif action == "incognito":
            subprocess.Popen(["start", "chrome", "--incognito", url], shell=True)
            return {"status": "success", "message": f"Chrome Incognito opened {url}"}
        return {"status": "error", "message": f"Unknown action '{action}'"}

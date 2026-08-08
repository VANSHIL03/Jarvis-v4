"""
JARVIS v4 - VSCode Workspace Plugin
"""

import subprocess
from typing import Dict, Any, List
from plugins.base_plugin import BasePlugin
from utils.logger import logger

class VSCodePlugin(BasePlugin):
    @property
    def plugin_name(self) -> str:
        return "vscode"

    @property
    def description(self) -> str:
        return "Launches VSCode, opens project workspaces, and executes editor commands."

    def get_supported_commands(self) -> List[str]:
        return ["open_project", "new_window"]

    def execute(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        if action == "open_project":
            project_path = params.get("path", ".")
            subprocess.Popen(["code", project_path], shell=True)
            return {"status": "success", "message": f"VSCode opened project at '{project_path}'."}
        elif action == "new_window":
            subprocess.Popen(["code", "-n"], shell=True)
            return {"status": "success", "message": "VSCode new window launched."}
        return {"status": "error", "message": f"Unknown VSCode action: '{action}'"}

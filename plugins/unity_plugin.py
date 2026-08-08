"""
JARVIS v4 - Unity Development Helper Plugin
"""

import subprocess
from typing import Dict, Any, List
from plugins.base_plugin import BasePlugin

class UnityPlugin(BasePlugin):
    @property
    def plugin_name(self) -> str:
        return "unity"

    @property
    def description(self) -> str:
        return "Launches Unity Hub and creates C# script templates."

    def get_supported_commands(self) -> List[str]:
        return ["open_hub", "create_csharp_script"]

    def execute(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        if action == "open_hub":
            subprocess.Popen(["start", "unityhub:"], shell=True)
            return {"status": "success", "message": "Unity Hub launched."}
        elif action == "create_csharp_script":
            file_path = params.get("path", "NewScript.cs")
            script_name = params.get("name", "NewScript")
            content = f"""using UnityEngine;

public class {script_name} : MonoBehaviour
{{
    void Start()
    {{
        // JARVIS initialized script
    }}

    void Update()
    {{
        
    }}
}}
"""
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            return {"status": "success", "message": f"Unity C# script created at '{file_path}'."}
        return {"status": "error", "message": f"Unknown Unity action: '{action}'"}

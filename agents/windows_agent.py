"""
JARVIS v4 - Windows System Control Agent
"""

from typing import Dict, Any
from agents.base_agent import BaseAgent
from automation.system import SystemControl
from automation.input_control import InputControl

class WindowsAgent(BaseAgent):
    def __init__(self, sys_control: SystemControl, input_control: InputControl):
        self.sys_control = sys_control
        self.input_control = input_control

    @property
    def agent_name(self) -> str:
        return "windows_agent"

    @property
    def description(self) -> str:
        return "Controls Windows 11 system app launcher, power, volume, brightness, and mouse/keyboard automation."

    async def execute_task(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        action = action.lower()
        if action == "launch_app":
            app = params.get("app_name", "")
            res = self.sys_control.launch_app(app)
            return {"status": "success" if res else "error", "app": app}

        elif action == "set_volume":
            level = params.get("level", 50)
            res = self.sys_control.set_volume(level)
            return {"status": "success" if res else "error", "level": level}

        elif action == "set_brightness":
            level = params.get("level", 50)
            res = self.sys_control.set_brightness(level)
            return {"status": "success" if res else "error", "level": level}

        elif action in ["shutdown_pc", "shutdown_laptop", "shutdown_system", "turn_off_pc", "turn_off_laptop"]:
            res = self.sys_control.shutdown_pc()
            return {"status": "success" if res else "error"}

        elif action in ["restart_pc", "restart_laptop", "restart_system", "reboot_pc", "reboot_laptop"]:
            res = self.sys_control.restart_pc()
            return {"status": "success" if res else "error"}

        elif action in ["lock_pc", "lock_laptop", "lock_system"]:
            res = self.sys_control.lock_pc()
            return {"status": "success" if res else "error"}

        elif action in ["sleep_pc", "sleep_laptop", "sleep_system"]:
            res = self.sys_control.sleep_pc()
            return {"status": "success" if res else "error"}

        elif action in ["get_system_specs", "get_specs", "system_specs", "specs"]:
            specs = self.sys_control.get_system_specs()
            speech = f"Ji Sir, aapke system ki real specs yeh hain: Processor {specs['cpu']}, GPU {specs['gpu']}, RAM {specs['ram']}, Operating System {specs['os']}."
            return {"status": "success", "specs": specs, "speech_reply": speech}

        elif action in ["get_storage", "storage_info", "drive_space", "free_space"]:
            storage = self.sys_control.get_storage_info()
            d_strs = [f"Drive {d['drive']} me {d['free_gb']} GB free hai ({d['total_gb']} GB total)" for d in storage['drives']]
            speech = f"Ji Sir, aapke system me {storage['free_all_gb']} GB free storage hai. " + ". ".join(d_strs) + "."
            return {"status": "success", "storage": storage, "speech_reply": speech}

        elif action in ["list_games", "detect_games", "scan_games", "get_games"]:
            games = self.sys_control.detect_installed_games()
            return {"status": "success", "installed_games": games}

        elif action in ["launch_game", "open_game", "play_game"]:
            game = params.get("game_name", params.get("app_name", ""))
            res = self.sys_control.launch_game(game)
            return {"status": "success" if res else "error", "game": game}

        elif action == "type_text":
            text = params.get("text", "")
            self.input_control.type_text(text)
            return {"status": "success", "typed": text}

        elif action in ["toggle_hotspot", "enable_hotspot", "turn_on_hotspot", "hotspot_on"]:
            enable = params.get("enable", True)
            res = self.sys_control.toggle_hotspot(enable=enable)
            state_text = "ON" if enable else "OFF"
            speech = f"Ji Sir, aapka Windows Mobile Hotspot {state_text} kar diya gaya hai."
            return {"status": res.get("status", "success"), "state": state_text, "speech_reply": speech}

        elif action in ["disable_hotspot", "turn_off_hotspot", "hotspot_off"]:
            res = self.sys_control.toggle_hotspot(enable=False)
            speech = "Ji Sir, aapka Windows Mobile Hotspot OFF kar diya gaya hai."
            return {"status": res.get("status", "success"), "state": "OFF", "speech_reply": speech}

        elif action == "take_screenshot":
            path = params.get("path", "screenshot.png")
            out = self.input_control.take_screenshot(path)
            return {"status": "success", "file_path": out}

        return {"status": "error", "message": f"Unknown windows action: '{action}'"}

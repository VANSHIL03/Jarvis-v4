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
            # Games are launched through the same Start-menu resolver as any other
            # app; SystemControl has no separate game launcher.
            res = self.sys_control.launch_app(game)
            return {"status": "success" if res else "error", "game": game}

        elif action in ["close_app", "close_application", "close_window", "kill_app"]:
            app = params.get("app_name", params.get("window", ""))
            res = self.sys_control.close_app(app)
            res.setdefault("speech_reply", (
                f"Ji Sir, {app} band kar diya hai."
                if res.get("status") == "success"
                else f"Sir, '{app}' chal hi nahi raha tha."
            ))
            return res

        elif action in ["focus_window", "switch_window", "activate_window", "bring_to_front"]:
            target = params.get("window", params.get("app_name", ""))
            res = self.sys_control.focus_window(target)
            res.setdefault("speech_reply", (
                f"Ji Sir, {target} saamne le aaya hoon."
                if res.get("status") == "success"
                else f"Sir, '{target}' ka koi open window nahi mila."
            ))
            return res

        elif action in ["minimize_window", "minimise_window", "minimize"]:
            target = params.get("window", params.get("app_name", ""))
            res = self.sys_control.minimize_window(target)
            res.setdefault("speech_reply", (
                f"Ji Sir, {target} minimize kar diya."
                if res.get("status") == "success"
                else f"Sir, '{target}' ka koi open window nahi mila."
            ))
            return res

        elif action in ["maximize_window", "maximise_window", "maximize"]:
            target = params.get("window", params.get("app_name", ""))
            res = self.sys_control.maximize_window(target)
            res.setdefault("speech_reply", (
                f"Ji Sir, {target} maximize kar diya."
                if res.get("status") == "success"
                else f"Sir, '{target}' ka koi open window nahi mila."
            ))
            return res

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

        elif action in ["toggle_wifi", "enable_wifi", "turn_on_wifi", "wifi_on"]:
            enable = params.get("enable", True)
            res = self.sys_control.toggle_wifi(enable=enable)
            state_text = "ON" if enable else "OFF"
            speech = f"Ji Sir, aapka Wi-Fi {state_text} kar diya gaya hai."
            return {"status": res.get("status", "success"), "state": state_text, "speech_reply": speech}

        elif action in ["disable_wifi", "turn_off_wifi", "wifi_off"]:
            res = self.sys_control.toggle_wifi(enable=False)
            speech = "Ji Sir, aapka Wi-Fi OFF kar diya gaya hai."
            return {"status": res.get("status", "success"), "state": "OFF", "speech_reply": speech}

        elif action in ["toggle_bluetooth", "enable_bluetooth", "turn_on_bluetooth", "bluetooth_on"]:
            enable = params.get("enable", True)
            res = self.sys_control.toggle_bluetooth(enable=enable)
            state_text = "ON" if enable else "OFF"
            speech = f"Ji Sir, aapka Bluetooth {state_text} kar diya gaya hai."
            return {"status": res.get("status", "success"), "state": state_text, "speech_reply": speech}

        elif action in ["disable_bluetooth", "turn_off_bluetooth", "bluetooth_off"]:
            res = self.sys_control.toggle_bluetooth(enable=False)
            speech = "Ji Sir, aapka Bluetooth OFF kar diya gaya hai."
            return {"status": res.get("status", "success"), "state": "OFF", "speech_reply": speech}

        elif action in ["toggle_airplane_mode", "enable_airplane_mode", "turn_on_airplane_mode", "airplane_mode_on", "flight_mode_on"]:
            enable = params.get("enable", True)
            res = self.sys_control.toggle_airplane_mode(enable=enable)
            state_text = "ON" if enable else "OFF"
            speech = f"Ji Sir, aapka Airplane Mode {state_text} kar diya gaya hai."
            return {"status": res.get("status", "success"), "state": state_text, "speech_reply": speech}

        elif action in ["disable_airplane_mode", "turn_off_airplane_mode", "airplane_mode_off", "flight_mode_off"]:
            res = self.sys_control.toggle_airplane_mode(enable=False)
            speech = "Ji Sir, aapka Airplane Mode OFF kar diya gaya hai."
            return {"status": res.get("status", "success"), "state": "OFF", "speech_reply": speech}

        elif action == "take_screenshot":
            path = params.get("path", "screenshot.png")
            out = self.input_control.take_screenshot(path)
            # take_screenshot returns "" when the grab fails; reporting success
            # with an empty path would tell the user a file exists that does not.
            if not out:
                return {
                    "status": "error",
                    "message": "Screenshot could not be captured.",
                    "speech_reply": "Sir, screenshot le nahi paya.",
                }
            return {
                "status": "success",
                "file_path": out,
                "path": out,
                "speech_reply": f"Ji Sir, screenshot save kar diya hai: {out}",
            }

        return {"status": "error", "message": f"Unknown windows action: '{action}'"}

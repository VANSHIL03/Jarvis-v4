"""
JARVIS v4 - WhatsApp Desktop UI Automation Plugin
"""

import time
import subprocess
from typing import Dict, Any, List
from plugins.base_plugin import BasePlugin
from utils.logger import logger

try:
    import pyautogui
except ImportError:
    pyautogui = None
    logger.warning("pyautogui not installed. WhatsApp UI automation disabled.")

class WhatsAppPlugin(BasePlugin):
    @property
    def plugin_name(self) -> str:
        return "whatsapp"

    @property
    def description(self) -> str:
        return "Automates WhatsApp Desktop UI for sending text, files, documents, and voice messages."

    def get_supported_commands(self) -> List[str]:
        return ["open_whatsapp", "send_message", "read_unread", "send_file", "send_voice_note"]

    def execute(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        action = action.lower()
        if action == "open_whatsapp":
            return self._open_whatsapp()
        elif action == "send_message":
            contact = params.get("contact_name") or params.get("contact", "")
            message = params.get("message", "")
            return self._send_message(contact, message)
        elif action == "read_unread":
            return self._read_unread()
        elif action == "send_file":
            contact = params.get("contact_name") or params.get("contact", "")
            file_path = params.get("file_path", "")
            return self._send_file(contact, file_path)
        else:
            return {"status": "error", "message": f"Unsupported action: '{action}'"}

    def _open_whatsapp(self) -> Dict[str, Any]:
        try:
            subprocess.Popen(["start", "whatsapp:"], shell=True)
            logger.info("WhatsApp Desktop app launch triggered.")
            return {"status": "success", "message": "WhatsApp Desktop opened."}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def _send_message(self, contact: str, message: str) -> Dict[str, Any]:
        self._open_whatsapp()
        time.sleep(2.0)
        if not pyautogui:
            return {"status": "error", "message": "pyautogui is required for WhatsApp UI automation."}
        try:
            pyautogui.hotkey('ctrl', 'f')
            time.sleep(0.3)
            pyautogui.write(contact, interval=0.03)
            time.sleep(0.8)
            pyautogui.press('enter')
            time.sleep(0.5)

            pyautogui.write(message, interval=0.02)
            time.sleep(0.3)
            pyautogui.press('enter')
            logger.info(f"WhatsApp message sent to '{contact}': '{message}'")
            return {"status": "success", "message": f"Message sent to {contact}."}
        except Exception as e:
            return {"status": "error", "message": f"Failed to send WhatsApp message: {e}"}

    def _read_unread(self) -> Dict[str, Any]:
        self._open_whatsapp()
        time.sleep(2.0)
        if pyautogui:
            pyautogui.hotkey('ctrl', 'shift', 'u')
        return {"status": "success", "message": "WhatsApp unread messages tab selected."}

    def _send_file(self, contact: str, file_path: str) -> Dict[str, Any]:
        self._send_message(contact, "")
        time.sleep(0.5)
        if pyautogui:
            pyautogui.hotkey('ctrl', 'shift', 'd')
            time.sleep(1.0)
            pyautogui.write(file_path, interval=0.02)
            pyautogui.press('enter')
            time.sleep(0.5)
            pyautogui.press('enter')
        return {"status": "success", "message": f"File '{file_path}' sent to {contact}."}

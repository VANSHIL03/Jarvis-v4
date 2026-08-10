"""
JARVIS v4 - Windows 11 System Automation
App launching, system power management, audio volume, display brightness.
"""

import os
import sys
import subprocess
import ctypes
import time
from typing import Dict, Any, Optional
from utils.logger import logger

try:
    import pyautogui
except ImportError:
    pyautogui = None

class SystemControl:
    def __init__(self):
        self.app_map = {
            "chrome": ["start", "chrome"],
            "edge": ["start", "msedge"],
            "vscode": ["code"],
            "notepad": ["notepad.exe"],
            "calculator": ["calc.exe"],
            "paint": ["mspaint.exe"],
            "cmd": ["start", "cmd"],
            "powershell": ["start", "powershell"],
            "settings": ["start", "ms-settings:"],
            "control panel": ["control.exe"],
            "file explorer": ["explorer.exe"],
            "downloads": ["explorer.exe", os.path.expanduser("~/Downloads")],
            "documents": ["explorer.exe", os.path.expanduser("~/Documents")]
        }

    def launch_app(self, app_name: str) -> bool:
        """Launches a desktop application by name or executable command."""
        name_clean = app_name.lower().strip()
        cmd = self.app_map.get(name_clean, [app_name])
        logger.info(f"Launching application: {name_clean} -> {cmd}")

        try:
            subprocess.Popen(cmd, shell=True)
            return True
        except Exception as e:
            logger.error(f"Failed to launch app '{app_name}': {e}")
            return False

    def set_volume(self, level_percent: int) -> bool:
        """Sets Windows master audio volume percentage (0-100)."""
        level_percent = max(0, min(100, level_percent))
        logger.info(f"Setting Windows audio volume to {level_percent}%")

        # 1. Primary method via pycaw + pythoncom COM thread initialization
        try:
            import pythoncom
            pythoncom.CoInitialize()
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
            from comtypes import CLSCTX_ALL
            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            volume = ctypes.cast(interface, ctypes.POINTER(IAudioEndpointVolume))
            volume.SetMasterVolumeLevelScalar(level_percent / 100.0, None)
            logger.info(f"Audio volume set to {level_percent}% via pycaw COM endpoint.")
            return True
        except Exception as e:
            logger.warning(f"pycaw COM adjustment failed: {e}. Trying Windows volume key simulation.")

        # 2. Fallback via Windows VK_VOLUME keys simulation
        try:
            VK_VOLUME_MUTE = 0xAD
            VK_VOLUME_DOWN = 0xAE
            VK_VOLUME_UP = 0xAF
            
            # Press volume down 50 times to set baseline to 0, then volume up (level/2) times
            for _ in range(50):
                ctypes.windll.user32.keybd_event(VK_VOLUME_DOWN, 0, 0, 0)
                ctypes.windll.user32.keybd_event(VK_VOLUME_DOWN, 0, 2, 0)
                time.sleep(0.01)

            steps_up = int((level_percent / 100.0) * 50)
            for _ in range(steps_up):
                ctypes.windll.user32.keybd_event(VK_VOLUME_UP, 0, 0, 0)
                ctypes.windll.user32.keybd_event(VK_VOLUME_UP, 0, 2, 0)
                time.sleep(0.01)

            logger.info(f"Audio volume set to {level_percent}% via Windows hardware keys.")
            return True
        except Exception as ex:
            logger.error(f"Volume adjustment failed: {ex}")
            return False

    def set_brightness(self, level_percent: int) -> bool:
        """Sets monitor brightness percentage (0-100)."""
        level_percent = max(0, min(100, level_percent))
        try:
            import screen_brightness_control as sbc
            sbc.set_brightness(level_percent)
            logger.info(f"Display brightness set to {level_percent}%")
            return True
        except Exception as e:
            logger.error(f"Failed to set brightness: {e}")
            return False

    def lock_pc(self) -> bool:
        """Locks Windows workstation immediately."""
        try:
            ctypes.windll.user32.LockWorkStation()
            logger.info("PC locked successfully.")
            return True
        except Exception as e:
            logger.error(f"Failed to lock PC: {e}")
            return False

    def sleep_pc(self) -> bool:
        """Puts Windows PC into sleep mode."""
        try:
            subprocess.run("rundll32.exe powrprof.dll,SetSuspendState 0,1,0", shell=True)
            return True
        except Exception as e:
            logger.error(f"Failed to put PC to sleep: {e}")
            return False

    def close_all_user_apps(self) -> bool:
        """Closes all non-critical user background applications safely before shutdown."""
        apps_to_close = [
            "chrome.exe", "msedge.exe", "code.exe", "notepad.exe", "spotify.exe",
            "discord.exe", "steam.exe", "winword.exe", "excel.exe", "powerpnt.exe",
            "vlc.exe", "calculator.exe", "mspaint.exe"
        ]
        logger.info("Closing user background applications prior to system shutdown...")
        for app in apps_to_close:
            try:
                subprocess.run(f"taskkill /f /im {app}", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                pass
        return True

    def restart_pc(self) -> bool:
        """Restarts Windows system with forced application termination."""
        try:
            self.close_all_user_apps()
            time.sleep(0.5)
            os.system("shutdown /r /f /t 3")
            logger.info("System restart initiated in 3 seconds (forced).")
            return True
        except Exception as e:
            logger.error(f"Failed to restart PC: {e}")
            return False

    def shutdown_pc(self) -> bool:
        """Closes all user applications first, then initiates forced Windows shutdown."""
        try:
            self.close_all_user_apps()
            time.sleep(0.5)
            os.system("shutdown /s /f /t 3")
            logger.info("System shutdown initiated in 3 seconds (forced).")
            return True
        except Exception as e:
            logger.error(f"Failed to shutdown PC: {e}")
            return False

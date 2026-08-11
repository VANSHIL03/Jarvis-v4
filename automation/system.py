"""
JARVIS v4 - Windows 11 System Automation
App launching, system power management, audio volume, display brightness.
"""

import os
import sys
import subprocess
import ctypes
import time
from pathlib import Path
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

    def detect_installed_games(self) -> list:
        """Scans Windows Registry, Steam, Epic, Riot, and Start Menu to detect installed games."""
        games = set()
        
        # 1. Steam Common Folders across drives
        steam_paths = [
            Path("C:/Program Files (x86)/Steam/steamapps/common"),
            Path("C:/Program Files/Steam/steamapps/common"),
            Path("D:/Steam/steamapps/common"),
            Path("D:/SteamLibrary/steamapps/common"),
            Path("E:/SteamLibrary/steamapps/common")
        ]
        for sp in steam_paths:
            if sp.exists():
                for folder in sp.iterdir():
                    if folder.is_dir() and not folder.name.startswith("."):
                        games.add(folder.name)

        # 2. Riot Games & Epic Games
        game_dirs = [Path("C:/Riot Games"), Path("C:/Program Files/Epic Games"), Path("D:/Epic Games")]
        for gd in game_dirs:
            if gd.exists():
                for folder in gd.iterdir():
                    if folder.is_dir():
                        games.add(folder.name)

        # 3. Windows Registry Installed Software
        import winreg
        def _scan_reg(root, key_path):
            try:
                with winreg.OpenKey(root, key_path) as k:
                    for i in range(winreg.QueryInfoKey(k)[0]):
                        sub = winreg.EnumKey(k, i)
                        with winreg.OpenKey(k, sub) as sk:
                            try:
                                name, _ = winreg.QueryValueEx(sk, "DisplayName")
                                if name and any(kw in name.lower() for kw in ['game', 'steam', 'epic', 'gta', 'valorant', 'minecraft', 'csgo', 'counter-strike', 'cyberpunk', 'pubg', 'fortnite', 'roblox', 'call of duty', 'forza', 'apex', 'genshin', 'fifa']):
                                    if not any(ign in name.lower() for ign in ['sdk', 'input', 'driver', 'redist']):
                                        games.add(name)
                            except Exception:
                                pass
            except Exception:
                pass

        _scan_reg(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall")
        _scan_reg(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall")
        _scan_reg(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Uninstall")

        result = sorted(list(games))
        logger.info(f"Detected {len(result)} installed games: {result}")
        return result

    def launch_game(self, game_name: str) -> bool:
        """Launches requested game by app name or executable search."""
        logger.info(f"Attempting to launch game: '{game_name}'")
        if self.launch_app(game_name):
            return True
        try:
            os.system(f'start "" "{game_name}"')
            return True
        except Exception as e:
            logger.error(f"Failed to launch game '{game_name}': {e}")
            return False

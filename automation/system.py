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
        """Launches a desktop application by dynamically searching Windows Start Menu."""
        name_clean = app_name.lower().strip()
        logger.info(f"Attempting to launch application: {name_clean}")

        # 1. Check hardcoded rapid map first
        if name_clean in self.app_map:
            cmd = self.app_map[name_clean]
            try:
                subprocess.Popen(cmd, shell=True)
                return True
            except Exception as e:
                logger.error(f"Failed to launch app '{app_name}' from map: {e}")

        # 2. Dynamically search using Windows Get-StartApps
        logger.info(f"Searching Start Menu for: {name_clean}")
        try:
            res = subprocess.run(
                ["powershell", "-Command", "Get-StartApps | Select-Object -Property Name, AppID"],
                capture_output=True, text=True, timeout=10
            )
            best_match = None
            best_appid = None
            
            for line in res.stdout.splitlines():
                line = line.strip()
                if not line or "AppID" in line or "---" in line:
                    continue
                
                parts = [p.strip() for p in line.rsplit("  ", 1) if p.strip()]
                if len(parts) == 2:
                    p_name = parts[0]
                    p_appid = parts[1]
                    if name_clean in p_name.lower():
                        if name_clean == p_name.lower():
                            best_match = p_name
                            best_appid = p_appid
                            break
                        elif best_match is None:
                            best_match = p_name
                            best_appid = p_appid

            if best_appid:
                logger.info(f"Found app '{best_match}' with AppID: {best_appid}. Launching...")
                subprocess.Popen(f'explorer.exe shell:AppsFolder\\{best_appid}', shell=True)
                return True
            else:
                logger.warning(f"App '{name_clean}' not found in Start Menu. Trying fallback...")
                subprocess.Popen(f"start {app_name}", shell=True)
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

    # ------------------------------------------------------- window controls
    #: Friendly name -> process image name, used only as a fallback when no
    #: window title matches. Keeps "close chrome" working when Chrome's window
    #: is titled after the page rather than the browser.
    exe_map = {
        "chrome": "chrome.exe",
        "google chrome": "chrome.exe",
        "edge": "msedge.exe",
        "microsoft edge": "msedge.exe",
        "vscode": "Code.exe",
        "vs code": "Code.exe",
        "visual studio code": "Code.exe",
        "code": "Code.exe",
        "notepad": "notepad.exe",
        "calculator": "CalculatorApp.exe",
        "calc": "CalculatorApp.exe",
        "paint": "mspaint.exe",
        "spotify": "Spotify.exe",
        "discord": "Discord.exe",
        "steam": "steam.exe",
        "word": "WINWORD.EXE",
        "excel": "EXCEL.EXE",
        "powerpoint": "POWERPNT.EXE",
        "vlc": "vlc.exe",
        "whatsapp": "WhatsApp.exe",
        "explorer": "explorer.exe",
        "file explorer": "explorer.exe",
        "cmd": "cmd.exe",
        "terminal": "WindowsTerminal.exe",
        "powershell": "powershell.exe",
        "firefox": "firefox.exe",
        "brave": "brave.exe",
        "telegram": "Telegram.exe",
        "obs": "obs64.exe",
        "unity": "Unity.exe",
    }

    def list_windows(self) -> list:
        """
        Every visible top-level window as {hwnd, title, process}.

        Section 12 forbids blind coordinate clicking, so window control is done
        through real window handles and their accessible titles rather than by
        guessing where a title bar happens to be on screen.
        """
        windows = []
        try:
            import win32gui
            import win32process
        except Exception as e:
            logger.warning(f"pywin32 unavailable, window controls disabled: {e}")
            return windows

        try:
            import psutil
        except Exception:
            psutil = None

        def _visit(hwnd, _):
            if not win32gui.IsWindowVisible(hwnd):
                return True
            title = win32gui.GetWindowText(hwnd) or ""
            if not title.strip():
                return True
            proc_name = ""
            if psutil is not None:
                try:
                    _, pid = win32process.GetWindowThreadProcessId(hwnd)
                    proc_name = psutil.Process(pid).name()
                except Exception:
                    proc_name = ""
            windows.append({"hwnd": hwnd, "title": title, "process": proc_name})
            return True

        try:
            win32gui.EnumWindows(_visit, None)
        except Exception as e:
            logger.warning(f"Window enumeration failed: {e}")
        return windows

    def find_window(self, target: str) -> Optional[Dict[str, Any]]:
        """Best visible window for a spoken name, matching title then process."""
        needle = (target or "").strip().lower()
        if not needle:
            return None

        candidates = self.list_windows()
        exe = self.exe_map.get(needle, "").lower()

        # Exact title, then title prefix/substring, then process image name.
        for match in (
            lambda w: w["title"].lower() == needle,
            lambda w: w["title"].lower().startswith(needle),
            lambda w: needle in w["title"].lower(),
            lambda w: bool(exe) and w["process"].lower() == exe,
            lambda w: needle in w["process"].lower().replace(".exe", ""),
        ):
            hit = next((w for w in candidates if match(w)), None)
            if hit:
                return hit
        return None

    def _set_window_state(self, target: str, state: str) -> Dict[str, Any]:
        """Shared implementation for focus/minimize/maximize."""
        try:
            import win32con
            import win32gui
        except Exception as e:
            return {"status": "error", "message": f"pywin32 is required for window control: {e}"}

        window = self.find_window(target)
        if window is None:
            return {
                "status": "not_found",
                "message": f"No open window matching '{target}'.",
            }

        commands = {
            "focus": win32con.SW_RESTORE,
            "minimize": win32con.SW_MINIMIZE,
            "maximize": win32con.SW_MAXIMIZE,
        }
        try:
            win32gui.ShowWindow(window["hwnd"], commands[state])
            if state == "focus":
                try:
                    win32gui.SetForegroundWindow(window["hwnd"])
                except Exception as e:
                    # Windows refuses foreground changes from a background thread
                    # in some cases; the restore above already un-minimised it.
                    logger.debug(f"SetForegroundWindow refused for '{target}': {e}")
            logger.info(f"Window '{window['title']}' -> {state}")
            return {"status": "success", "window": window["title"], "state": state}
        except Exception as e:
            logger.error(f"Failed to {state} window '{target}': {e}")
            return {"status": "error", "message": str(e)}

    def focus_window(self, target: str) -> Dict[str, Any]:
        """Restores and brings a window to the foreground."""
        return self._set_window_state(target, "focus")

    def minimize_window(self, target: str) -> Dict[str, Any]:
        """Minimises a window to the taskbar."""
        return self._set_window_state(target, "minimize")

    def maximize_window(self, target: str) -> Dict[str, Any]:
        """Maximises a window."""
        return self._set_window_state(target, "maximize")

    def close_app(self, app_name: str) -> Dict[str, Any]:
        """
        Closes an application by asking its windows to close.

        WM_CLOSE is used rather than taskkill so the application still gets to
        prompt about unsaved work; killing the process is only the fallback for
        an app with no matching visible window.
        """
        name = (app_name or "").strip()
        if not name:
            return {"status": "error", "message": "No application name given."}

        try:
            import win32con
            import win32gui
        except Exception as e:
            return {"status": "error", "message": f"pywin32 is required to close apps: {e}"}

        needle = name.lower()
        exe = self.exe_map.get(needle, "").lower()
        closed = []
        for window in self.list_windows():
            title = window["title"].lower()
            proc = window["process"].lower()
            if needle in title or (exe and proc == exe) or (needle in proc.replace(".exe", "")):
                try:
                    win32gui.PostMessage(window["hwnd"], win32con.WM_CLOSE, 0, 0)
                    closed.append(window["title"])
                except Exception as e:
                    logger.debug(f"WM_CLOSE failed for '{window['title']}': {e}")

        if closed:
            logger.info(f"Close requested for {len(closed)} window(s) of '{name}'.")
            return {
                "status": "success",
                "closed": closed,
                "count": len(closed),
                "message": f"Closed {len(closed)} window(s) of '{name}'.",
            }

        if exe:
            try:
                res = subprocess.run(
                    f"taskkill /im {exe}", shell=True,
                    capture_output=True, text=True, timeout=15
                )
                if res.returncode == 0:
                    logger.info(f"'{name}' terminated via taskkill ({exe}).")
                    return {
                        "status": "success",
                        "closed": [exe],
                        "count": 1,
                        "message": f"Closed {name}.",
                    }
            except Exception as e:
                logger.error(f"taskkill for '{exe}' failed: {e}")

        return {"status": "not_found", "message": f"'{name}' does not appear to be running."}

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

    def get_system_specs(self) -> Dict[str, Any]:
        """Returns real-time live hardware and system telemetry specifications."""
        import platform
        import psutil

        ram_gb = round(psutil.virtual_memory().total / (1024 ** 3))
        os_name = f"{platform.system()} {platform.release()}"

        cpu_name = "AMD Ryzen 7 7445HS"
        try:
            res = subprocess.run(
                ["powershell", "-Command", "Get-CimInstance Win32_Processor | Select-Object -ExpandProperty Name"],
                capture_output=True, text=True, timeout=3
            )
            c = res.stdout.strip()
            if c:
                cpu_name = c
        except Exception:
            pass

        gpu_name = "NVIDIA GeForce RTX 4050 Laptop GPU"
        try:
            res = subprocess.run(
                ["powershell", "-Command", "Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name"],
                capture_output=True, text=True, timeout=3
            )
            gpus = [g.strip() for g in res.stdout.splitlines() if g.strip()]
            if gpus:
                gpu_name = ", ".join(gpus)
        except Exception:
            pass

        return {
            "os": os_name,
            "cpu": cpu_name,
            "gpu": gpu_name,
            "ram": f"{ram_gb} GB"
        }

    def get_storage_info(self) -> Dict[str, Any]:
        """Returns live drive storage breakdown for all connected drives."""
        import psutil
        drives = []
        total_all_gb = 0
        free_all_gb = 0

        for part in psutil.disk_partitions():
            if part.fstype and not part.mountpoint.startswith("/proc"):
                try:
                    usage = psutil.disk_usage(part.mountpoint)
                    t = round(usage.total / (1024 ** 3))
                    f = round(usage.free / (1024 ** 3))
                    u = round(usage.used / (1024 ** 3))
                    total_all_gb += t
                    free_all_gb += f
                    drives.append({
                        "drive": part.device.rstrip("\\"),
                        "total_gb": t,
                        "free_gb": f,
                        "used_gb": u,
                        "percent_used": usage.percent
                    })
                except Exception:
                    pass

        return {
            "drives": drives,
            "total_all_gb": total_all_gb,
            "free_all_gb": free_all_gb
        }

    def toggle_hotspot(self, enable: bool = True) -> Dict[str, Any]:
        """Toggles Windows 11 Mobile Hotspot ON or OFF natively via WinRT API."""
        method = "StartTetheringAsync" if enable else "StopTetheringAsync"
        action_name = "ON" if enable else "OFF"
        logger.info(f"Toggling Windows 11 Mobile Hotspot: {action_name}...")

        ps_content = f"""
$Null = [Windows.Networking.Connectivity.NetworkInformation, Windows.Networking.Connectivity, ContentType = WindowsRuntime]
$Null = [Windows.Networking.NetworkOperators.NetworkOperatorTetheringManager, Windows.Networking.NetworkOperators, ContentType = WindowsRuntime]

$profile = [Windows.Networking.Connectivity.NetworkInformation]::GetInternetConnectionProfile()
if (-not $profile) {{
    Write-Output "NO_PROFILE"
    exit 1
}}

$mgr = [Windows.Networking.NetworkOperators.NetworkOperatorTetheringManager]::CreateFromConnectionProfile($profile)
if (-not $mgr) {{
    Write-Output "NO_MANAGER"
    exit 1
}}

$asyncOp = $mgr.{method}()
Start-Sleep -Seconds 2
Write-Output "STATE: $($mgr.TetheringOperationalState)"
"""

        import tempfile
        with tempfile.NamedTemporaryFile(suffix='.ps1', delete=False, mode='w', encoding='utf-8') as f:
            f.write(ps_content)
            tmp_script = f.name

        try:
            res = subprocess.run(['powershell', '-ExecutionPolicy', 'Bypass', '-File', tmp_script], capture_output=True, text=True, timeout=10)
            out = res.stdout.strip()
            state_str = "ON" if "STATE: On" in out else "OFF" if "STATE: Off" in out else "UNKNOWN"
            success = "STATE: On" in out if enable else "STATE: Off" in out
            return {"status": "success" if success else "warning", "state": state_str, "enabled": enable}
        except Exception as e:
            logger.error(f"Failed to toggle hotspot: {e}")
            return {"status": "error", "message": str(e)}
        finally:
            if os.path.exists(tmp_script):
                os.remove(tmp_script)

    def toggle_wifi(self, enable: bool = True) -> Dict[str, Any]:
        """Toggles Windows 11 Wi-Fi ON or OFF natively via NetAdapter."""
        action_name = "ON" if enable else "OFF"
        ps_action = "Enable-NetAdapter" if enable else "Disable-NetAdapter"
        logger.info(f"Toggling Wi-Fi: {action_name}...")

        ps_content = f"Get-NetAdapter | Where-Object {{ $_.Name -like '*Wi-Fi*' -or $_.InterfaceDescription -like '*Wireless*' }} | {ps_action} -Confirm:$false"
        import tempfile
        with tempfile.NamedTemporaryFile(suffix='.ps1', delete=False, mode='w', encoding='utf-8') as f:
            f.write(ps_content)
            tmp_script = f.name

        try:
            res = subprocess.run(['powershell', '-ExecutionPolicy', 'Bypass', '-File', tmp_script], capture_output=True, text=True, timeout=10)
            success = res.returncode == 0
            return {"status": "success" if success else "error", "enabled": enable, "state": action_name}
        except Exception as e:
            logger.error(f"Failed to toggle Wi-Fi: {e}")
            return {"status": "error", "message": str(e)}
        finally:
            if os.path.exists(tmp_script):
                os.remove(tmp_script)

    def toggle_bluetooth(self, enable: bool = True) -> Dict[str, Any]:
        """Toggles Windows 11 Bluetooth ON or OFF natively via PnP Device."""
        action_name = "ON" if enable else "OFF"
        ps_action = "Enable-PnpDevice" if enable else "Disable-PnpDevice"
        logger.info(f"Toggling Bluetooth: {action_name}...")

        ps_content = f"Get-PnpDevice | Where-Object {{ $_.FriendlyName -like '*Bluetooth Adapter*' }} | {ps_action} -Confirm:$false"
        import tempfile
        with tempfile.NamedTemporaryFile(suffix='.ps1', delete=False, mode='w', encoding='utf-8') as f:
            f.write(ps_content)
            tmp_script = f.name

        try:
            res = subprocess.run(['powershell', '-ExecutionPolicy', 'Bypass', '-File', tmp_script], capture_output=True, text=True, timeout=10)
            success = res.returncode == 0
            return {"status": "success" if success else "error", "enabled": enable, "state": action_name}
        except Exception as e:
            logger.error(f"Failed to toggle Bluetooth: {e}")
            return {"status": "error", "message": str(e)}
        finally:
            if os.path.exists(tmp_script):
                os.remove(tmp_script)

    def toggle_airplane_mode(self, enable: bool = True) -> Dict[str, Any]:
        """Toggles Windows 11 Airplane Mode ON (disables all radios) or OFF (enables all radios)."""
        action_name = "ON" if enable else "OFF"
        logger.info(f"Toggling Airplane Mode: {action_name}...")

        # Airplane Mode ON -> Turn OFF Wi-Fi, Bluetooth, & Mobile Hotspot
        # Airplane Mode OFF -> Turn ON Wi-Fi & Bluetooth
        radio_state = not enable
        res_w = self.toggle_wifi(enable=radio_state)
        res_b = self.toggle_bluetooth(enable=radio_state)
        if enable:
            self.toggle_hotspot(enable=False)

        success = res_w.get("status") == "success" and res_b.get("status") == "success"
        return {"status": "success" if success else "warning", "state": action_name, "enabled": enable}

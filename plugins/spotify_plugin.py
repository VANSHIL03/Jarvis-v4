"""
JARVIS v4 - Spotify Plugin
"""

import subprocess
from typing import Dict, Any, List
from plugins.base_plugin import BasePlugin

try:
    import pyautogui
except ImportError:
    pyautogui = None

class SpotifyPlugin(BasePlugin):
    @property
    def plugin_name(self) -> str:
        return "spotify"

    @property
    def description(self) -> str:
        return "Controls Spotify app playback, play/pause, next track, volume."

    def get_supported_commands(self) -> List[str]:
        return ["play_pause", "next_track", "prev_track", "open_spotify"]

    def execute(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        if action == "open_spotify":
            subprocess.Popen(["start", "spotify:"], shell=True)
            return {"status": "success", "message": "Spotify app opened."}
        elif action == "play_pause" and pyautogui:
            pyautogui.press("playpause")
            return {"status": "success", "message": "Toggled playback."}
        elif action == "next_track" and pyautogui:
            pyautogui.press("nexttrack")
            return {"status": "success", "message": "Skipped to next track."}
        elif action == "prev_track" and pyautogui:
            pyautogui.press("prevtrack")
            return {"status": "success", "message": "Previous track."}
        return {"status": "error", "message": f"Action '{action}' unavailable or pyautogui missing."}

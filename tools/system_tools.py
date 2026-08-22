"""
JARVIS v4 - System Control Tools

Windows app launching, window management, volume/brightness, screenshots, power
actions and the radio toggles -- every one declared, permission-tagged and bound
to the existing WindowsAgent rather than reimplemented.

Two things here are load-bearing for Section 16 and Section 19:

  * The power actions are ordinary registry entries. There is no bypass: an
    earlier build short-circuited shutdown/restart/lock/sleep past the safety
    check, so "shutdown my laptop" powered the machine off with no question
    asked. shutdown_pc and restart_pc are DANGEROUS and carry a confirmation
    question; lock and sleep stay auto-allowed (instantly reversible, nothing
    lost) but still travel the same gate, so raising them in permissions.json
    is all it takes to have JARVIS ask.
  * close_app is LOW_RISK and closes windows politely via WM_CLOSE, so the app
    itself gets to prompt about unsaved work. Asking the user twice for
    something that harmless is the behaviour Section 16 explicitly warns off.
"""

from __future__ import annotations

from typing import List

from security.permissions import PermissionLevel as P
from tools.base import ToolParam, ToolSpec

CATEGORY = "system"

_LEVEL = ToolParam(
    "level", "integer", required=True,
    description="Target value, 0-100.",
)
_ENABLE = ToolParam(
    "enable", "boolean", default=True,
    description="True to switch on, False to switch off.",
)
_WINDOW = ToolParam(
    "window", "string", required=True,
    description="Window title or app name, e.g. 'chrome', 'Untitled - Notepad'.",
)


def _window_tool(name: str, action: str, description: str) -> ToolSpec:
    """focus/minimize/maximize differ only in wording, so build them uniformly."""
    return ToolSpec(
        name=name,
        description=description,
        permission=P.SAFE,
        category=CATEGORY,
        agent="windows_agent",
        action=action,
        parameters=(_WINDOW,),
        aliases={"app_name": "window", "app": "window", "title": "window", "target": "window"},
    )


SYSTEM_TOOLS: List[ToolSpec] = [
    ToolSpec(
        name="open_app",
        description="Launch a Windows application by name (chrome, notepad, vscode, spotify...).",
        permission=P.SAFE,
        category=CATEGORY,
        agent="windows_agent",
        action="launch_app",
        parameters=(
            ToolParam("app_name", "string", required=True, description="Application name."),
        ),
        aliases={"app": "app_name", "name": "app_name", "application": "app_name", "program": "app_name"},
        legacy_actions=("open_app", "open_application", "start_app", "launch_application"),
    ),
    ToolSpec(
        name="close_app",
        description="Close a running application's windows gracefully (the app may prompt to save).",
        permission=P.LOW_RISK,
        category=CATEGORY,
        agent="windows_agent",
        action="close_app",
        parameters=(
            ToolParam("app_name", "string", required=True, description="Application or window name."),
        ),
        aliases={"app": "app_name", "window": "app_name", "name": "app_name", "target": "app_name"},
        confirm_template="Sir, {app_name} band kar doon? Haan ya na bataiye.",
        legacy_actions=("close_application", "close_window", "kill_app", "quit_app"),
    ),
    _window_tool("focus_window", "focus_window", "Bring an open window to the foreground."),
    _window_tool("minimize_window", "minimize_window", "Minimize an open window."),
    _window_tool("maximize_window", "maximize_window", "Maximize an open window."),
    ToolSpec(
        name="set_volume",
        description="Set the system output volume to a percentage (0-100).",
        permission=P.LOW_RISK,
        category=CATEGORY,
        agent="windows_agent",
        action="set_volume",
        parameters=(_LEVEL,),
        aliases={"volume": "level", "value": "level", "percent": "level", "percentage": "level"},
        legacy_actions=("volume", "change_volume", "adjust_volume"),
    ),
    ToolSpec(
        name="set_brightness",
        description="Set the display brightness to a percentage (0-100).",
        permission=P.LOW_RISK,
        category=CATEGORY,
        agent="windows_agent",
        action="set_brightness",
        parameters=(_LEVEL,),
        aliases={"brightness": "level", "value": "level", "percent": "level", "percentage": "level"},
        legacy_actions=("brightness", "change_brightness", "adjust_brightness"),
    ),
    ToolSpec(
        name="screenshot",
        description="Capture the screen to an image file.",
        permission=P.SAFE,
        category=CATEGORY,
        agent="windows_agent",
        action="take_screenshot",
        parameters=(
            ToolParam("path", "string", default="screenshot.png", description="Output image path."),
        ),
        aliases={"file_path": "path", "output": "path", "save_to": "path"},
        legacy_actions=("take_screenshot", "capture_screen", "screen_capture"),
    ),
    ToolSpec(
        name="type_text",
        description="Type text into the focused window using the keyboard.",
        permission=P.LOW_RISK,
        category=CATEGORY,
        agent="windows_agent",
        action="type_text",
        parameters=(
            ToolParam("text", "string", required=True, description="Text to type."),
        ),
        aliases={"message": "text", "content": "text"},
    ),

    # ------------------------------------------------------------- power
    ToolSpec(
        name="shutdown_pc",
        description="Shut the computer down. Always asks first.",
        permission=P.DANGEROUS,
        category=CATEGORY,
        agent="windows_agent",
        action="shutdown_pc",
        confirm_template="Sir, laptop abhi shutdown karna hai? Haan ya na bataiye.",
        legacy_actions=("shutdown", "shutdown_laptop", "shutdown_system", "turn_off_pc", "turn_off_laptop"),
    ),
    ToolSpec(
        name="restart_pc",
        description="Restart the computer. Always asks first.",
        permission=P.DANGEROUS,
        category=CATEGORY,
        agent="windows_agent",
        action="restart_pc",
        confirm_template="Sir, laptop restart karna hai? Haan ya na bataiye.",
        legacy_actions=("restart", "restart_laptop", "restart_system", "reboot_pc", "reboot_laptop"),
    ),
    ToolSpec(
        name="lock_pc",
        description="Lock the computer (sign-in screen).",
        permission=P.LOW_RISK,
        category=CATEGORY,
        agent="windows_agent",
        action="lock_pc",
        confirm_template="Sir, laptop lock kar doon? Haan ya na bataiye.",
        legacy_actions=("lock", "lock_laptop", "lock_system", "lock_screen"),
    ),
    ToolSpec(
        name="sleep_pc",
        description="Put the computer to sleep.",
        permission=P.LOW_RISK,
        category=CATEGORY,
        agent="windows_agent",
        action="sleep_pc",
        confirm_template="Sir, laptop sleep mode me daal doon? Haan ya na bataiye.",
        legacy_actions=("sleep", "sleep_laptop", "sleep_system", "suspend_pc"),
    ),

    # ------------------------------------------------------------- status
    ToolSpec(
        name="system_specs",
        description="Report the real CPU, GPU, RAM and OS of this machine.",
        permission=P.SAFE,
        category=CATEGORY,
        agent="windows_agent",
        action="get_system_specs",
        legacy_actions=("get_specs", "specs", "get_system_specs", "system_info"),
    ),
    ToolSpec(
        name="storage_info",
        description="Report free and total space on every drive.",
        permission=P.SAFE,
        category=CATEGORY,
        agent="windows_agent",
        action="get_storage",
        legacy_actions=("storage_info", "drive_space", "free_space", "get_storage_info"),
    ),
    ToolSpec(
        name="list_games",
        description="List games installed on this PC (Steam, Epic, Riot, standalone).",
        permission=P.SAFE,
        category=CATEGORY,
        agent="windows_agent",
        action="list_games",
        legacy_actions=("detect_games", "scan_games", "get_games"),
    ),
    ToolSpec(
        name="launch_game",
        description="Launch an installed game by name.",
        permission=P.SAFE,
        category=CATEGORY,
        agent="windows_agent",
        action="launch_game",
        parameters=(
            ToolParam("game_name", "string", required=True, description="Game name."),
        ),
        aliases={"game": "game_name", "app_name": "game_name", "name": "game_name"},
        legacy_actions=("open_game", "play_game"),
    ),

    # -------------------------------------------------------------- radios
    ToolSpec(
        name="toggle_wifi",
        description="Turn Wi-Fi on or off.",
        permission=P.LOW_RISK,
        category=CATEGORY,
        agent="windows_agent",
        action="toggle_wifi",
        parameters=(_ENABLE,),
        aliases={"state": "enable", "on": "enable", "value": "enable"},
        legacy_actions=("enable_wifi", "disable_wifi", "wifi_on", "wifi_off", "turn_on_wifi", "turn_off_wifi"),
    ),
    ToolSpec(
        name="toggle_bluetooth",
        description="Turn Bluetooth on or off.",
        permission=P.LOW_RISK,
        category=CATEGORY,
        agent="windows_agent",
        action="toggle_bluetooth",
        parameters=(_ENABLE,),
        aliases={"state": "enable", "on": "enable", "value": "enable"},
        legacy_actions=(
            "enable_bluetooth", "disable_bluetooth", "bluetooth_on", "bluetooth_off",
            "turn_on_bluetooth", "turn_off_bluetooth",
        ),
    ),
    ToolSpec(
        name="toggle_airplane_mode",
        description="Turn Airplane (flight) mode on or off.",
        permission=P.LOW_RISK,
        category=CATEGORY,
        agent="windows_agent",
        action="toggle_airplane_mode",
        parameters=(_ENABLE,),
        aliases={"state": "enable", "on": "enable", "value": "enable"},
        legacy_actions=(
            "enable_airplane_mode", "disable_airplane_mode", "airplane_mode_on",
            "airplane_mode_off", "flight_mode_on", "flight_mode_off",
        ),
    ),
    ToolSpec(
        name="toggle_hotspot",
        description="Turn the Windows Mobile Hotspot on or off.",
        permission=P.LOW_RISK,
        category=CATEGORY,
        agent="windows_agent",
        action="toggle_hotspot",
        parameters=(_ENABLE,),
        aliases={"state": "enable", "on": "enable", "value": "enable"},
        legacy_actions=(
            "enable_hotspot", "disable_hotspot", "hotspot_on", "hotspot_off",
            "turn_on_hotspot", "turn_off_hotspot",
        ),
    ),
]

__all__ = ["SYSTEM_TOOLS"]

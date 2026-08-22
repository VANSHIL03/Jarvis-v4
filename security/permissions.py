"""
JARVIS v4 - Tool Permission Levels & User-Configurable Policy

Implements the four-tier permission model:

    SAFE       -> open Notepad, create folder, read document
    LOW_RISK   -> move files, download files, adjust volume
    SENSITIVE  -> send WhatsApp message, send email, execute generated code
    DANGEROUS  -> delete files, shutdown, restart, format drive

SAFE and LOW_RISK execute immediately. SENSITIVE and DANGEROUS require explicit
user confirmation before execution. Every level and confirmation requirement can
be overridden per-tool by the user through data/permissions.json.
"""

from __future__ import annotations

import json
from enum import IntEnum
from pathlib import Path
from typing import Any, Dict, Optional

from config.settings import settings
from utils.logger import logger


class PermissionLevel(IntEnum):
    """Risk tier of a tool. Ordered so comparisons express escalating risk."""

    SAFE = 0
    LOW_RISK = 1
    SENSITIVE = 2
    DANGEROUS = 3

    @classmethod
    def parse(cls, value: Any, default: "PermissionLevel" = None) -> "PermissionLevel":
        """Coerces an int, name string, or PermissionLevel into a PermissionLevel."""
        if isinstance(value, cls):
            return value
        if isinstance(value, bool):
            # bool is an int subclass; reject it explicitly to avoid True -> LOW_RISK
            return default if default is not None else cls.SAFE
        if isinstance(value, int):
            try:
                return cls(value)
            except ValueError:
                pass
        if isinstance(value, str):
            key = value.strip().upper().replace("-", "_").replace(" ", "_")
            if key in cls.__members__:
                return cls.__members__[key]
        return default if default is not None else cls.SAFE

    @property
    def label(self) -> str:
        return self.name

    def __str__(self) -> str:  # keeps log lines readable
        return self.name


#: Levels at or below this execute without asking the user.
DEFAULT_AUTO_ALLOW_MAX = PermissionLevel.LOW_RISK


class PermissionPolicy:
    """
    Decides whether a tool may run unattended, and lets the user retune that.

    Overrides live in data/permissions.json:

        {
          "auto_allow_max": "LOW_RISK",
          "tools": {
            "send_message":  {"requires_confirmation": false},
            "set_volume":    {"permission": "SAFE"},
            "delete_file":   {"permission": "DANGEROUS"}
          }
        }

    A missing file means "use the built-in defaults" -- never an error.
    """

    def __init__(self, config_path: Optional[Path] = None, auto_load: bool = True):
        self.config_path = Path(config_path or getattr(
            settings, "PERMISSIONS_FILE", settings.DATA_DIR / "permissions.json"
        ))
        self.auto_allow_max: PermissionLevel = DEFAULT_AUTO_ALLOW_MAX
        self.tool_overrides: Dict[str, Dict[str, Any]] = {}
        if auto_load:
            self.load()

    # ------------------------------------------------------------------ load
    def load(self) -> bool:
        """Loads user overrides from disk. Returns True if a config was applied."""
        if not self.config_path.exists():
            logger.info("No permissions.json found; using built-in permission defaults.")
            return False

        try:
            raw = json.loads(self.config_path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.error(f"permissions.json is unreadable ({e}). Falling back to defaults.")
            return False

        if not isinstance(raw, dict):
            logger.error("permissions.json must contain a JSON object. Using defaults.")
            return False

        self.auto_allow_max = PermissionLevel.parse(
            raw.get("auto_allow_max"), DEFAULT_AUTO_ALLOW_MAX
        )

        tools = raw.get("tools") or {}
        if isinstance(tools, dict):
            self.tool_overrides = {
                str(name): dict(cfg)
                for name, cfg in tools.items()
                if isinstance(cfg, dict)
            }

        logger.info(
            f"Permission policy loaded: auto_allow_max={self.auto_allow_max.name}, "
            f"{len(self.tool_overrides)} tool override(s)."
        )
        return True

    def save(self) -> bool:
        """Persists the current policy so the user can hand-edit it afterwards."""
        payload = {
            "auto_allow_max": self.auto_allow_max.name,
            "tools": self.tool_overrides,
        }
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            self.config_path.write_text(
                json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            return True
        except Exception as e:
            logger.error(f"Failed to write permissions.json: {e}")
            return False

    # ----------------------------------------------------------- evaluation
    def level_for(self, tool_name: str, declared: PermissionLevel) -> PermissionLevel:
        """Effective permission level for a tool, honouring user overrides."""
        override = self.tool_overrides.get(tool_name, {})
        if "permission" in override:
            return PermissionLevel.parse(override["permission"], declared)
        return declared

    def requires_confirmation(
        self,
        tool_name: str,
        declared: PermissionLevel,
        spec_default: Optional[bool] = None,
    ) -> bool:
        """
        True when the user must approve this tool before it runs.

        Precedence: user override > tool's own declaration > level threshold.
        """
        override = self.tool_overrides.get(tool_name, {})
        if "requires_confirmation" in override:
            return bool(override["requires_confirmation"])
        if spec_default is not None:
            return bool(spec_default)
        return self.level_for(tool_name, declared) > self.auto_allow_max

    # ------------------------------------------------------------ mutation
    def set_tool_permission(self, tool_name: str, level: Any) -> PermissionLevel:
        """Reassigns a tool's risk tier at runtime (used by the settings UI)."""
        parsed = PermissionLevel.parse(level)
        self.tool_overrides.setdefault(tool_name, {})["permission"] = parsed.name
        logger.info(f"Permission override: {tool_name} -> {parsed.name}")
        return parsed

    def set_tool_confirmation(self, tool_name: str, required: bool) -> bool:
        """Turns the confirmation prompt for a single tool on or off."""
        self.tool_overrides.setdefault(tool_name, {})["requires_confirmation"] = bool(required)
        logger.info(f"Confirmation override: {tool_name} -> {bool(required)}")
        return bool(required)

    def clear_overrides(self, tool_name: Optional[str] = None):
        """Drops one tool's overrides, or all of them."""
        if tool_name is None:
            self.tool_overrides.clear()
        else:
            self.tool_overrides.pop(tool_name, None)

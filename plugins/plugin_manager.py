"""
JARVIS v4 - Dynamic Plugin Discovery & Execution Manager
"""

import importlib
import pkgutil
from typing import Dict, Any, List, Optional
from plugins.base_plugin import BasePlugin
from utils.logger import logger

class PluginManager:
    def __init__(self):
        self.plugins: Dict[str, BasePlugin] = {}
        self.load_plugins()

    def register_plugin(self, plugin: BasePlugin):
        """Registers a plugin instance."""
        self.plugins[plugin.plugin_name.lower()] = plugin
        logger.info(f"Registered plugin: '{plugin.plugin_name}' ({len(plugin.get_supported_commands())} actions)")

    def load_plugins(self):
        """Discovers and instantiates built-in plugins from plugins package."""
        from plugins.whatsapp_plugin import WhatsAppPlugin
        from plugins.vscode_plugin import VSCodePlugin
        from plugins.chrome_plugin import ChromePlugin
        from plugins.spotify_plugin import SpotifyPlugin
        from plugins.discord_plugin import DiscordPlugin
        from plugins.steam_plugin import SteamPlugin
        from plugins.unity_plugin import UnityPlugin

        builtin_classes = [
            WhatsAppPlugin, VSCodePlugin, ChromePlugin, SpotifyPlugin,
            DiscordPlugin, SteamPlugin, UnityPlugin
        ]

        for cls in builtin_classes:
            try:
                instance = cls()
                self.register_plugin(instance)
            except Exception as e:
                logger.error(f"Error instantiating plugin '{cls.__name__}': {e}")

    def execute_plugin_command(self, plugin_name: str, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Routes execution to target plugin."""
        name_clean = plugin_name.lower().strip()
        if name_clean not in self.plugins:
            return {"status": "error", "message": f"Plugin '{plugin_name}' not registered."}

        plugin = self.plugins[name_clean]
        try:
            return plugin.execute(action, params)
        except Exception as e:
            logger.error(f"Error executing command on plugin '{plugin_name}': {e}")
            return {"status": "error", "message": str(e)}

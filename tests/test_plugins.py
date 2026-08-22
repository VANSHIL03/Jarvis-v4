"""
JARVIS v4 Unit Tests - Plugin Discovery Subsystem
"""

import pytest
from plugins.plugin_manager import PluginManager

def test_plugin_manager_registration():
    pm = PluginManager()
    assert "whatsapp" in pm.plugins
    assert "vscode" in pm.plugins
    assert "chrome" in pm.plugins
    assert "spotify" in pm.plugins
    assert "discord" in pm.plugins
    assert "steam" in pm.plugins
    assert "unity" in pm.plugins

def test_plugin_execution_unsupported():
    pm = PluginManager()
    res = pm.execute_plugin_command("whatsapp", "invalid_action", {})
    assert res["status"] == "error"

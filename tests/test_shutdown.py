"""
Tests for the power-control surface of automation/system.py.

The previous version of this file called ``SystemControl.close_all_user_apps()``
for real, so a plain ``pytest`` run issued ``taskkill /f /im chrome.exe`` (plus
Code, Discord, Steam, Word, Excel...) and destroyed the developer's unsaved work
as a side effect of running the suite. Nothing about that is a test: the function
swallows every exception and unconditionally returns True, so the assertion could
not fail either way.

What is worth testing is the part that has logic: the command each app produces,
that shutdown and restart close apps before pulling the plug, and that the whole
family sits behind the permission gate. All of that is checked here against a
patched subprocess, so the suite never touches a real process.

The genuinely destructive variants still exist, marked ``destructive``, and
pytest.ini excludes that marker by default -- they run only when asked for
explicitly with ``pytest -m destructive``.
"""

import os
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from automation.system import SystemControl
from security.permissions import PermissionLevel
from security.safety import SafetyManager


# --------------------------------------------------------------------------
# Non-destructive: nothing below is allowed to touch a real process
# --------------------------------------------------------------------------
def test_close_all_user_apps_issues_taskkill_per_app():
    """Builds one forced taskkill per app, and reports success."""
    sys_control = SystemControl()

    with patch("automation.system.subprocess.run") as mock_run:
        assert sys_control.close_all_user_apps() is True

    commands = [call.args[0] for call in mock_run.call_args_list]
    assert commands, "no taskkill command was issued"
    for command in commands:
        assert command.startswith("taskkill /f /im ")
        assert command.endswith(".exe")

    # A representative sample rather than the full hardcoded list, so adding an
    # app to the list does not break this test.
    assert "taskkill /f /im chrome.exe" in commands
    assert "taskkill /f /im code.exe" in commands


def test_close_all_user_apps_survives_a_failing_taskkill():
    """One app refusing to die must not abort the rest of the sweep."""
    sys_control = SystemControl()

    with patch("automation.system.subprocess.run", side_effect=OSError("access denied")) as mock_run:
        assert sys_control.close_all_user_apps() is True

    assert mock_run.call_count > 1, "gave up after the first failure"


def test_shutdown_pc_closes_apps_then_shuts_down():
    """Unsaved work gets a chance to be flushed before the machine goes down."""
    sys_control = SystemControl()
    order = []

    with patch.object(sys_control, "close_all_user_apps", side_effect=lambda: order.append("close") or True), \
         patch("automation.system.time.sleep"), \
         patch("automation.system.os.system", side_effect=lambda cmd: order.append(cmd) or 0):
        assert sys_control.shutdown_pc() is True

    assert order[0] == "close", "shutdown fired before closing apps"
    assert order[1] == "shutdown /s /f /t 3"


def test_restart_pc_closes_apps_then_restarts():
    sys_control = SystemControl()
    order = []

    with patch.object(sys_control, "close_all_user_apps", side_effect=lambda: order.append("close") or True), \
         patch("automation.system.time.sleep"), \
         patch("automation.system.os.system", side_effect=lambda cmd: order.append(cmd) or 0):
        assert sys_control.restart_pc() is True

    assert order[0] == "close"
    assert order[1] == "shutdown /r /f /t 3"


def test_shutdown_pc_reports_failure_honestly():
    """A raising os.system must return False, not a cheerful True."""
    sys_control = SystemControl()

    with patch.object(sys_control, "close_all_user_apps", return_value=True), \
         patch("automation.system.time.sleep"), \
         patch("automation.system.os.system", side_effect=OSError("nope")):
        assert sys_control.shutdown_pc() is False


# --------------------------------------------------------------------------
# The safety contract: power actions may not run unasked
# --------------------------------------------------------------------------
@pytest.mark.parametrize("tool", ["shutdown_pc", "restart_pc"])
def test_power_actions_require_confirmation(tool):
    """
    Section 16: shutdown and restart are DANGEROUS and always ask first.

    security/safety.py used to hardcode these four names to "not dangerous",
    which is the exact inverse of the specification. This test is what stops that
    bypass from being reintroduced.
    """
    safety = SafetyManager()
    decision = safety.evaluate(tool)

    assert decision.known, f"'{tool}' is not a registered tool"
    assert decision.level is PermissionLevel.DANGEROUS
    assert decision.needs_confirmation is True
    assert decision.question, "gated action has no question to ask"
    assert safety.is_dangerous_action(tool) is True


@pytest.mark.parametrize("tool", ["lock_pc", "sleep_pc"])
def test_lock_and_sleep_go_through_the_policy(tool):
    """
    Lock and sleep are gate-free but not bypass-free.

    They are auto-allowed because Section 16 also says not to nag about harmless
    actions -- losing nothing but the lock screen. The distinction that matters
    is that the answer now comes from the policy (and can be overridden in
    data/permissions.json), instead of from a hardcoded early return.
    """
    safety = SafetyManager()
    decision = safety.evaluate(tool)

    assert decision.known, f"'{tool}' is not a registered tool"
    assert decision.level <= PermissionLevel.LOW_RISK
    assert decision.needs_confirmation is False


@pytest.mark.asyncio
@pytest.mark.parametrize("tool", ["shutdown_pc", "restart_pc"])
async def test_power_action_executes_nothing_before_confirmation(tool):
    """The registry must refuse the call outright, not run it and report back."""
    from tools import build_registry

    class ExplodingWindowsAgent:
        async def execute_task(self, action, params):
            raise AssertionError(f"'{action}' executed without confirmation!")

    registry = build_registry(agents={"windows_agent": ExplodingWindowsAgent()})
    result = await registry.execute(tool, {}, confirmed=False)

    assert result.ok is False
    assert result.blocked is True
    assert result.awaiting_confirmation is True


# --------------------------------------------------------------------------
# Destructive: excluded from a default run by pytest.ini
# --------------------------------------------------------------------------
@pytest.mark.destructive
def test_close_all_user_apps_for_real():
    """
    Actually terminates the listed applications on this machine.

    Run only with ``pytest -m destructive``, and only when you have nothing open
    that you care about.
    """
    sys_control = SystemControl()
    assert sys_control.close_all_user_apps() is True

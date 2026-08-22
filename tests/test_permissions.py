"""
Tests for the four-tier permission model (Sections 15, 16 and 19).

Two properties matter here and they pull in opposite directions:

  * a destructive tool must never run without the user saying yes, and
  * a harmless tool must never nag ("For harmless actions, do not unnecessarily
    ask" -- Section 16).

Most of these tests therefore come in pairs: one asserting that something is
gated, one asserting that its innocent neighbour is not. The regression this
guards against is the old security/safety.py, which decided both questions by
looking for substrings in ``f"{action} {params}"`` -- so it blocked
``search_google("how to send email")`` while waving ``shutdown_pc`` straight
through via a hardcoded bypass.
"""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from security.permissions import (
    DEFAULT_AUTO_ALLOW_MAX,
    PermissionLevel,
    PermissionPolicy,
)
from security.safety import SafetyManager
from tools import build_registry


class RecordingAgent:
    def __init__(self):
        self.calls = []

    async def execute_task(self, action, params):
        self.calls.append((action, dict(params)))
        return {"status": "success"}


class ExplodingAgent:
    """Any call at all is a test failure."""

    async def execute_task(self, action, params):
        raise AssertionError(f"'{action}' executed without confirmation!")


AGENT_NAMES = (
    "memory_agent", "coding_agent", "browser_agent", "windows_agent",
    "whatsapp_agent", "vision_agent", "email_agent", "file_agent",
    "gaming_agent", "git_agent", "n8n_agent", "document_agent",
)


@pytest.fixture
def isolated_policy(tmp_path):
    """A policy whose config file lives in tmp_path, never the real data dir."""
    return PermissionPolicy(config_path=tmp_path / "permissions.json")


@pytest.fixture
def registry(isolated_policy):
    return build_registry(
        agents={name: ExplodingAgent() for name in AGENT_NAMES},
        policy=isolated_policy,
    )


@pytest.fixture
def safety(registry, isolated_policy):
    return SafetyManager(policy=isolated_policy).attach(registry=registry)


# --------------------------------------------------------------------------
# The tier model itself
# --------------------------------------------------------------------------
def test_levels_are_ordered_by_risk():
    assert PermissionLevel.SAFE < PermissionLevel.LOW_RISK
    assert PermissionLevel.LOW_RISK < PermissionLevel.SENSITIVE
    assert PermissionLevel.SENSITIVE < PermissionLevel.DANGEROUS


def test_level_parse_accepts_loose_input():
    """LLM output and old JSON both need to land on a real tier."""
    assert PermissionLevel.parse("dangerous") is PermissionLevel.DANGEROUS
    assert PermissionLevel.parse("LOW_RISK") is PermissionLevel.LOW_RISK
    assert PermissionLevel.parse("low risk") is PermissionLevel.LOW_RISK
    assert PermissionLevel.parse(3) is PermissionLevel.DANGEROUS
    assert PermissionLevel.parse(None) is PermissionLevel.SAFE
    assert PermissionLevel.parse("nonsense", PermissionLevel.SAFE) is PermissionLevel.SAFE
    assert PermissionLevel.parse("", PermissionLevel.DANGEROUS) is PermissionLevel.DANGEROUS


def test_default_auto_allow_stops_below_sensitive():
    """SENSITIVE and above always ask. That is the whole point of the tiers."""
    assert DEFAULT_AUTO_ALLOW_MAX == PermissionLevel.LOW_RISK
    assert DEFAULT_AUTO_ALLOW_MAX < PermissionLevel.SENSITIVE


# --------------------------------------------------------------------------
# Which tools are gated
# --------------------------------------------------------------------------
GATED = ["shutdown_pc", "restart_pc", "delete_file", "run_code"]
UNGATED = ["open_app", "set_volume", "screenshot", "search_google", "read_file"]


@pytest.mark.parametrize("tool", GATED)
def test_destructive_tools_require_confirmation(safety, tool):
    decision = safety.evaluate(tool, _sample_params(tool))
    assert decision.known, f"'{tool}' is not registered"
    assert decision.needs_confirmation is True, f"'{tool}' would run unasked"
    assert decision.level >= PermissionLevel.SENSITIVE
    assert decision.question.strip(), f"'{tool}' is gated but has nothing to ask"
    assert decision.allowed_now is False


@pytest.mark.parametrize("tool", UNGATED)
def test_harmless_tools_do_not_ask(safety, tool):
    """Section 16: do not nag. Opening Notepad is not a decision."""
    decision = safety.evaluate(tool, _sample_params(tool))
    assert decision.known, f"'{tool}' is not registered"
    assert decision.needs_confirmation is False, f"'{tool}' asks unnecessarily"
    assert decision.allowed_now is True
    assert decision.question == ""


def _sample_params(tool):
    return {
        "delete_file": {"path": "C:/tmp/x.txt"},
        "read_file": {"path": "C:/tmp/x.txt"},
        "run_code": {"code": "print(1)"},
        "open_app": {"app_name": "notepad"},
        "set_volume": {"level": 40},
        "search_google": {"query": "how to send email"},
    }.get(tool, {})


def test_the_old_substring_false_positive_is_gone(safety):
    """
    "send email" inside a search query used to trip the keyword matcher.

    Danger is a property of the tool now, not of the text of its arguments.
    """
    decision = safety.evaluate("search_google", {"query": "how to send email and delete file"})
    assert decision.needs_confirmation is False


def test_the_old_power_action_bypass_is_gone(safety):
    """
    security/safety.py hardcoded these four to "not dangerous". That is inverted.

    All four must now be *evaluated by the policy*; shutdown and restart come out
    gated, lock and sleep come out auto-allowed because they cost nothing.
    """
    for tool in ("shutdown_pc", "restart_pc"):
        assert safety.evaluate(tool).needs_confirmation is True
    for tool in ("lock_pc", "sleep_pc"):
        decision = safety.evaluate(tool)
        assert decision.known
        assert decision.level <= PermissionLevel.LOW_RISK


# --------------------------------------------------------------------------
# Enforcement: the gate is not advisory
# --------------------------------------------------------------------------
@pytest.mark.asyncio
@pytest.mark.parametrize("tool", GATED)
async def test_gated_tool_executes_nothing_without_confirmation(registry, tool):
    """
    Default-deny. The sub-agent behind every tool here raises on any call, so a
    pass proves the gate refused *before* dispatch rather than after.
    """
    result = await registry.execute(tool, _sample_params(tool), confirmed=False)
    assert result.ok is False
    assert result.blocked is True
    assert result.awaiting_confirmation is True
    assert result.message.strip(), "blocked with no explanation"
    assert (result.data or {}).get("question"), "blocked with no question to ask"


@pytest.mark.asyncio
async def test_confirmed_true_lets_the_call_through(isolated_policy):
    agents = {name: RecordingAgent() for name in AGENT_NAMES}
    registry = build_registry(agents=agents, policy=isolated_policy)

    result = await registry.execute("shutdown_pc", {}, confirmed=True)
    assert result.ok is True
    assert agents["windows_agent"].calls, "confirmed call never reached the agent"


@pytest.mark.asyncio
async def test_held_params_are_the_normalised_ones(registry):
    """
    The question and the eventual execution must describe the same call.

    A fast-path that says folder_path is normalised to path *before* the question
    is rendered, so "delete C:/tmp/x.txt?" cannot become a call with no path.
    """
    result = await registry.execute("delete_file", {"file_path": "C:/tmp/x.txt"}, confirmed=False)
    assert result.awaiting_confirmation is True
    assert result.data["params"] == {"path": "C:/tmp/x.txt"}
    assert "C:/tmp/x.txt" in result.data["question"]


# --------------------------------------------------------------------------
# User overrides
# --------------------------------------------------------------------------
def test_user_can_raise_a_tools_permission(isolated_policy):
    """Someone who wants to be asked before Notepad opens is allowed to be."""
    assert isolated_policy.requires_confirmation("open_app", PermissionLevel.SAFE) is False
    isolated_policy.set_tool_permission("open_app", PermissionLevel.DANGEROUS)
    assert isolated_policy.level_for("open_app", PermissionLevel.SAFE) is PermissionLevel.DANGEROUS
    assert isolated_policy.requires_confirmation("open_app", PermissionLevel.SAFE) is True


def test_user_can_lower_a_tools_permission(isolated_policy):
    isolated_policy.set_tool_confirmation("send_message", False)
    assert isolated_policy.requires_confirmation(
        "send_message", PermissionLevel.SENSITIVE
    ) is False


def test_clear_overrides_restores_the_defaults(isolated_policy):
    isolated_policy.set_tool_permission("open_app", PermissionLevel.DANGEROUS)
    isolated_policy.clear_overrides("open_app")
    assert isolated_policy.level_for("open_app", PermissionLevel.SAFE) is PermissionLevel.SAFE


def test_overrides_round_trip_through_disk(tmp_path):
    path = tmp_path / "permissions.json"
    first = PermissionPolicy(config_path=path)
    first.set_tool_permission("open_app", PermissionLevel.DANGEROUS)
    first.auto_allow_max = PermissionLevel.SAFE
    assert first.save() is True

    second = PermissionPolicy(config_path=path)
    assert second.auto_allow_max is PermissionLevel.SAFE
    assert second.level_for("open_app", PermissionLevel.SAFE) is PermissionLevel.DANGEROUS


def test_a_missing_config_file_is_not_an_error(tmp_path):
    policy = PermissionPolicy(config_path=tmp_path / "absent.json")
    assert policy.load() is False
    assert policy.auto_allow_max == DEFAULT_AUTO_ALLOW_MAX


def test_a_corrupt_config_file_falls_back_to_defaults(tmp_path):
    """
    A truncated JSON file must not make everything auto-allowed.

    Failing open here would be the worst possible outcome of a bad edit.
    """
    path = tmp_path / "permissions.json"
    path.write_text("{ this is not json", encoding="utf-8")

    policy = PermissionPolicy(config_path=path)
    assert policy.auto_allow_max == DEFAULT_AUTO_ALLOW_MAX
    assert policy.requires_confirmation("shutdown_pc", PermissionLevel.DANGEROUS) is True


def test_a_json_array_is_rejected(tmp_path):
    path = tmp_path / "permissions.json"
    path.write_text(json.dumps(["not", "an", "object"]), encoding="utf-8")
    policy = PermissionPolicy(config_path=path)
    assert policy.auto_allow_max == DEFAULT_AUTO_ALLOW_MAX


@pytest.mark.asyncio
async def test_an_override_is_enforced_at_execution_time(tmp_path):
    """An override that the registry ignores would be decorative."""
    policy = PermissionPolicy(config_path=tmp_path / "permissions.json")
    policy.set_tool_permission("open_app", PermissionLevel.DANGEROUS)

    registry = build_registry(
        agents={name: ExplodingAgent() for name in AGENT_NAMES}, policy=policy
    )
    result = await registry.execute("open_app", {"app_name": "notepad"}, confirmed=False)
    assert result.blocked is True


# --------------------------------------------------------------------------
# Backwards-compatible wrappers kept for existing callers
# --------------------------------------------------------------------------
def test_is_dangerous_action_still_answers_the_legacy_questions(safety):
    """tests/test_agents.py has asserted this pair since before the registry."""
    assert safety.is_dangerous_action("delete_file", {"path": "C:/tmp/x.txt"}) is True
    assert safety.is_dangerous_action("set_volume", {"level": 50}) is False


def test_check_and_confirm_defaults_to_deny(safety):
    """
    No console, no callback, no approval.

    The old implementation called input() here, which would have frozen the Qt
    worker thread with nowhere to type. Denying is the only safe answer.
    """
    assert safety.check_and_confirm("open_app", {"app_name": "notepad"}) is True
    assert safety.check_and_confirm("shutdown_pc") is False


def test_check_and_confirm_honours_a_legacy_callback(safety):
    asked = []
    safety.set_confirmation_callback(lambda question: asked.append(question) or True)
    assert safety.check_and_confirm("shutdown_pc") is True
    assert asked and "shutdown" in asked[0].lower()


def test_a_raising_callback_denies_rather_than_crashes(safety):
    def boom(question):
        raise RuntimeError("dialog closed")

    safety.set_confirmation_callback(boom)
    assert safety.check_and_confirm("shutdown_pc") is False


def test_an_unregistered_action_is_never_silently_allowed(safety):
    """
    Nothing outside the registry can execute, but the answer should still be
    conservative rather than a cheerful "safe".
    """
    decision = safety.evaluate("format_c_drive_now", {})
    assert decision.known is False
    assert safety.permission_for("format_c_drive_now") is PermissionLevel.DANGEROUS

"""
Structural tests for the controlled tool registry (Section 19).

The registry is the only way anything executes in JARVIS: the LLM picks a name
out of a fixed catalogue and supplies named parameters, and the registry
validates them before a sub-agent is touched. That makes its structural
invariants worth asserting directly -- a tool bound to a sub-agent that does not
exist, or an alias pointing at a parameter that was never declared, is a runtime
failure that no amount of prompt engineering can recover from.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from security.permissions import PermissionLevel, PermissionPolicy
from tools import build_registry
from tools.base import ToolParam, ToolResult, ToolSpec
from tools.registry import ToolRegistry


AGENT_NAMES = (
    "memory_agent", "coding_agent", "browser_agent", "windows_agent",
    "whatsapp_agent", "vision_agent", "email_agent", "file_agent",
    "gaming_agent", "git_agent", "n8n_agent", "document_agent",
)


class RecordingAgent:
    """Stands in for a sub-agent and records what it was asked to do."""

    def __init__(self):
        self.calls = []

    async def execute_task(self, action, params):
        self.calls.append((action, dict(params)))
        return {"status": "success", "speech_reply": f"{action} done"}


@pytest.fixture
def agents():
    return {name: RecordingAgent() for name in AGENT_NAMES}


@pytest.fixture
def registry(agents):
    return build_registry(agents=agents, policy=PermissionPolicy())


# --------------------------------------------------------------------------
# Every tool is executable
# --------------------------------------------------------------------------
def test_registry_is_not_empty(registry):
    assert len(registry) > 0
    assert len(registry.all()) == len(registry.names())


def test_every_spec_resolves_to_something_runnable(registry):
    """A tool with neither a handler nor a live agent binding can never run."""
    unrunnable = [
        spec.name for spec in registry.all()
        if spec.handler is None and not (spec.agent and spec.action)
    ]
    assert unrunnable == []


def test_no_tool_is_bound_to_an_unknown_agent(registry):
    """Catches a typo like agent='whatsap_agent' at test time, not at 2am by voice."""
    unknown = [
        f"{spec.name} -> {spec.agent}" for spec in registry.all()
        if spec.handler is None and spec.agent not in AGENT_NAMES
    ]
    assert unknown == []


def test_registry_audit_reports_no_structural_problems(registry):
    assert registry.audit() == []


def test_tool_names_are_unique_and_well_formed(registry):
    names = registry.names()
    assert len(names) == len(set(names)), "duplicate tool name"
    for name in names:
        assert name == name.strip().lower(), f"'{name}' is not normalised"
        assert " " not in name, f"'{name}' contains a space"


# --------------------------------------------------------------------------
# Descriptions and schemas are valid
# --------------------------------------------------------------------------
def test_every_tool_has_a_usable_description(registry):
    """The description is the model's only clue about when to pick the tool."""
    for spec in registry.all():
        assert spec.description.strip(), f"{spec.name} has no description"
        assert len(spec.description) >= 15, f"{spec.name}: description too terse"


def test_every_tool_declares_a_category(registry):
    for spec in registry.all():
        assert spec.category.strip(), f"{spec.name} has no category"
    assert len(registry.by_category()) > 1


def test_parameter_types_are_from_the_supported_set(registry):
    """An unsupported type silently falls through coerce() as a raw string."""
    supported = {"string", "integer", "number", "boolean", "array", "object"}
    for spec in registry.all():
        for param in spec.parameters:
            assert param.type in supported, f"{spec.name}.{param.name}: '{param.type}'"
            assert param.name == param.name.strip()


def test_gated_tools_have_a_question_to_ask(registry):
    """A tool that needs confirmation but cannot phrase the question is a dead end."""
    for spec in registry.all():
        if spec.permission >= PermissionLevel.SENSITIVE:
            assert spec.confirm_template, f"{spec.name} is gated with no confirm_template"


def test_confirmation_question_renders_without_leftover_placeholders(registry):
    """{path}-style placeholders must be filled, not spoken aloud verbatim."""
    for spec in registry.all():
        if not spec.confirm_template:
            continue
        params = {p.name: f"<{p.name}>" for p in spec.parameters}
        question = registry.confirmation_question(spec, params)
        assert question.strip()
        assert "{" not in question, f"{spec.name}: unrendered placeholder in {question!r}"


def test_describe_for_llm_lists_tools_and_respects_the_budget(registry):
    text = registry.describe_for_llm(max_chars=6000)
    assert len(text) <= 6100          # allows the truncation marker
    assert "open_app" in text
    assert "[system]" in text or "[systems]" in text

    tiny = registry.describe_for_llm(max_chars=200)
    assert len(tiny) <= 300
    assert "truncated" in tiny


# --------------------------------------------------------------------------
# Parameter normalisation
# --------------------------------------------------------------------------
def test_aliases_map_to_canonical_names(registry):
    """
    The fast-path speaks folder_path; the tool declares path.

    This is defect #4 from the wiring review: the regex router emitted
    folder_path while create_folder declared path, so the folder name was
    dropped on the floor and an empty-path call reached the file agent.
    """
    spec = registry.get("create_folder")
    assert spec is not None
    clean, missing = registry.normalize_params(spec, {"folder_path": "C:/tmp/demo"})
    assert clean["path"] == "C:/tmp/demo"
    assert "folder_path" not in clean
    assert missing == []


def test_every_declared_alias_points_at_a_real_param(registry):
    for spec in registry.all():
        for alias, canonical in spec.aliases.items():
            assert canonical in spec.param_map, \
                f"{spec.name}: alias '{alias}' -> undeclared '{canonical}'"
            assert alias not in spec.param_map, \
                f"{spec.name}: '{alias}' is both an alias and a real param"


def test_unknown_params_are_dropped(registry):
    """
    An invented parameter must not reach the sub-agent.

    Local models routinely hallucinate extras ("force": true, "silent": true).
    Passing those through as **kwargs would raise TypeError inside the agent.
    """
    spec = registry.get("open_app")
    clean, _ = registry.normalize_params(
        spec, {"app_name": "notepad", "force": True, "wait_ms": 500, "": "x"}
    )
    assert clean == {"app_name": "notepad"}


def test_params_are_coerced_to_their_declared_type(registry):
    """LLMs emit "50" and "50%" for an integer volume."""
    spec = registry.get("set_volume")
    for raw in ("50", "50%", 50.4):
        clean, missing = registry.normalize_params(spec, {"level": raw})
        assert clean["level"] == 50, f"{raw!r} -> {clean['level']!r}"
        assert missing == []


def test_missing_required_params_are_reported_not_guessed(registry):
    spec = registry.get("open_app")
    clean, missing = registry.normalize_params(spec, {})
    assert "app_name" in missing
    assert "app_name" not in clean


@pytest.mark.asyncio
async def test_missing_required_param_fails_before_the_agent_runs(registry, agents):
    result = await registry.execute("open_app", {}, confirmed=True)
    assert result.ok is False
    assert "app_name" in result.message
    assert agents["windows_agent"].calls == [], "agent ran with an incomplete call"


def test_defaults_fill_in_for_omitted_optional_params(registry):
    """A declared default belongs in the call, not in each agent's own fallback."""
    for spec in registry.all():
        defaults = {p.name: p.default for p in spec.parameters
                    if not p.required and p.default is not None}
        if not defaults:
            continue
        clean, _ = registry.normalize_params(spec, {})
        for name, default in defaults.items():
            assert clean.get(name) == default, f"{spec.name}.{name}"
        break


# --------------------------------------------------------------------------
# Legacy (agent, action) resolution -- how the regex fast-path still works
# --------------------------------------------------------------------------
def test_legacy_agent_action_pairs_resolve(registry):
    """
    The ~1,000-line regex router emits {"agent","action"} and must keep working.

    It was written before the registry existed, so every one of its delegations
    is resolved through this map rather than by tool name.
    """
    cases = [
        ("windows_agent", "open_app", "open_app"),
        ("file_agent", "create_folder", "create_folder"),
        ("browser_agent", "search_google", "search_google"),
        ("whatsapp_agent", "send_message", "send_message"),
        ("memory_agent", "remember", "remember"),
    ]
    for agent, action, expected in cases:
        spec = registry.resolve_legacy(agent, action)
        assert spec is not None, f"{agent}/{action} does not resolve"
        assert spec.name == expected


def test_resolve_legacy_returns_none_for_nonsense(registry):
    assert registry.resolve_legacy("nope_agent", "nope_action") is None


def test_get_is_case_and_whitespace_insensitive(registry):
    assert registry.get("  OPEN_APP  ") is registry.get("open_app")
    assert registry.get("does_not_exist") is None
    assert "open_app" in registry
    assert "does_not_exist" not in registry


# --------------------------------------------------------------------------
# Execution and result shape
# --------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_execute_delegates_with_canonical_params(registry, agents):
    """
    The agent is called with its own action name and canonical params.

    Tool name and sub-agent action name are deliberately allowed to differ --
    open_app reads better in a prompt than the agent's launch_app -- so the
    binding is asserted from the spec rather than assumed to match.
    """
    spec = registry.get("open_app")
    result = await registry.execute(spec, {"app_name": "notepad"}, confirmed=True)
    assert result.ok is True
    assert agents["windows_agent"].calls == [(spec.action, {"app_name": "notepad"})]


@pytest.mark.asyncio
async def test_a_raising_agent_returns_a_failed_result_not_an_exception(registry):
    """
    A crashing tool must degrade to ToolResult(ok=False), not kill the turn.

    An exception escaping here would propagate out of process_user_request and
    take down the Qt worker thread mid-sentence.
    """
    class Exploding:
        async def execute_task(self, action, params):
            raise RuntimeError("disk on fire")

    registry.bind_agents({**registry.agents, "windows_agent": Exploding()})
    result = await registry.execute("open_app", {"app_name": "notepad"}, confirmed=True)

    assert isinstance(result, ToolResult)
    assert result.ok is False
    assert result.message, "a failure with no message tells the user nothing"


@pytest.mark.asyncio
async def test_agent_error_status_is_reported_as_failure(registry):
    """
    Defect #3: agents return {"status": "error"} but the planner read ["success"].

    Because "success" was absent, `res.get("success") is False` was never true and
    every failure was announced to the user as a success. ok is now derived from
    whichever convention the agent used.
    """
    class Failing:
        async def execute_task(self, action, params):
            return {"status": "error", "message": "Notepad not found"}

    registry.bind_agents({**registry.agents, "windows_agent": Failing()})
    result = await registry.execute("open_app", {"app_name": "nope"}, confirmed=True)

    assert result.ok is False
    assert result.message == "Notepad not found"
    assert result.to_dict()["status"] == "error"


@pytest.mark.asyncio
async def test_unknown_tool_name_fails_cleanly(registry):
    result = await registry.execute("format_c_drive", {}, confirmed=True)
    assert result.ok is False
    assert result.message


@pytest.mark.asyncio
async def test_result_dict_keeps_the_keys_the_uis_read(registry):
    """
    ui/main_window.py reads item["result"], the phone reads item.result.*.

    Renaming these would blank both UIs without failing anything else, so the
    contract is pinned here.
    """
    result = await registry.execute("open_app", {"app_name": "notepad"}, confirmed=True)
    data = result.to_dict()
    for key in ("tool", "ok", "status", "message", "permission",
                "blocked", "awaiting_confirmation", "result"):
        assert key in data, f"missing '{key}'"
    assert isinstance(data["result"], dict)


# --------------------------------------------------------------------------
# Registration mechanics
# --------------------------------------------------------------------------
def test_duplicate_registration_is_rejected_unless_replacing():
    reg = ToolRegistry(policy=PermissionPolicy())
    spec = ToolSpec(
        name="demo_tool",
        description="A demonstration tool used only by the test suite.",
        parameters=(ToolParam("value", "string", required=True),),
        handler=lambda value: value,
    )
    reg.register(spec)
    with pytest.raises(ValueError):
        reg.register(spec)
    assert reg.register(spec, replace=True) is spec
    assert len(reg) == 1


def test_spec_requires_an_execution_binding():
    with pytest.raises(ValueError):
        ToolSpec(name="orphan", description="No handler and no agent binding at all.")


def test_spec_requires_a_name():
    with pytest.raises(ValueError):
        ToolSpec(name="", description="Nameless.", handler=lambda: None)


def test_signature_shows_required_and_optional_params(registry):
    sig = registry.get("set_volume").signature()
    assert sig.startswith("set_volume(")
    assert "level" in sig

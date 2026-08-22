"""
Tests for the two-turn confirmation flow (Sections 13 and 16).

The old gate called ``input()``. Every request into JARVIS arrives on a Qt worker
thread, from the voice pipeline, or from the phone's web server -- none of which
has a console, so the prompt would have blocked forever and taken the assistant
down mid-sentence. Confirmation is conversational instead: the turn ends with a
question, the held action sits in the broker, and the *next* utterance decides.

Three properties are load-bearing and each has tests below:

  * nothing executes before the answer. Not partially, not optimistically.
  * a reply that is neither yes nor no drops the held action rather than guessing.
  * the action that runs is the one the user was asked about, unchanged.
"""

import os
import sys
import time
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from security.confirmation import (
    ConfirmationBroker,
    ConfirmationDecision,
    classify_reply,
)
from security.permissions import PermissionPolicy
from security.safety import SafetyManager
from tools import build_registry


AGENT_NAMES = (
    "memory_agent", "coding_agent", "browser_agent", "windows_agent",
    "whatsapp_agent", "vision_agent", "email_agent", "file_agent",
    "gaming_agent", "git_agent", "n8n_agent", "document_agent",
)


class RecordingAgent:
    def __init__(self):
        self.calls = []

    async def execute_task(self, action, params):
        self.calls.append((action, dict(params)))
        return {"status": "success", "speech_reply": f"Ji Sir, {action} ho gaya."}


@pytest.fixture
def broker():
    return ConfirmationBroker(ttl_seconds=120.0)


@pytest.fixture
def agents():
    return {name: RecordingAgent() for name in AGENT_NAMES}


@pytest.fixture
def planner(agents, tmp_path):
    """
    A real PlannerAgent with a stubbed LLM and memory.

    The point of testing through the planner rather than the broker alone is that
    the planner is where the two routes converge: the regex fast-path and the LLM
    plan must reach the same gate, and only an end-to-end call proves it.
    """
    from agents.planner_agent import PlannerAgent

    llm = MagicMock()

    async def never_called(**kwargs):
        raise AssertionError("the fast-path should have handled this without the LLM")

    llm.generate_response = never_called

    memory = MagicMock()
    memory.get_all_facts.return_value = []
    memory.retrieve_relevant_memory.return_value = []
    memory.get_dialogue_context.return_value = []
    memory.db = None

    policy = PermissionPolicy(config_path=tmp_path / "permissions.json")
    safety = SafetyManager(policy=policy, broker=ConfirmationBroker())
    registry = build_registry(agents=agents, policy=policy)

    agent = PlannerAgent(llm, memory, safety, agents, registry=registry)
    agent.registry.bind_agents(agents)
    return agent


# --------------------------------------------------------------------------
# Reply classification: Hinglish and English
# --------------------------------------------------------------------------
AFFIRMATIONS = [
    "yes", "Yes.", "yeah", "yep", "sure", "ok", "okay", "confirm", "proceed",
    "haan", "haan ji", "ji haan", "ha", "bilkul", "kar do", "kardo", "karo",
    "theek hai", "zaroor", "go ahead", "do it", "yes please", "haan sir",
]

NEGATIONS = [
    "no", "No!", "nope", "nah", "nahi", "nahin", "na", "mat karo", "rehne do",
    "cancel", "cancel karo", "stop", "abort", "abhi nahi", "never mind",
    "forget it", "no thanks", "nahi sir", "ruko",
]

UNRELATED = [
    "what time is it",
    "open notepad",
    "kal ka weather batao",
    "play some music on youtube",
    "mera naam Vanshil hai",
]


@pytest.mark.parametrize("reply", AFFIRMATIONS)
def test_affirmations_are_recognised(broker, reply):
    broker.request(tool="shutdown_pc", params={}, question="Shutdown?", session_id="s")
    decision, pending = broker.resolve(reply, "s")
    assert decision is ConfirmationDecision.AFFIRM, f"{reply!r} was not read as yes"
    assert pending is not None and pending.tool == "shutdown_pc"


@pytest.mark.parametrize("reply", NEGATIONS)
def test_negations_are_recognised(broker, reply):
    broker.request(tool="shutdown_pc", params={}, question="Shutdown?", session_id="s")
    decision, _ = broker.resolve(reply, "s")
    assert decision is ConfirmationDecision.DENY, f"{reply!r} was not read as no"


@pytest.mark.parametrize("reply", UNRELATED)
def test_unrelated_input_is_not_guessed_at(broker, reply):
    """
    Ambiguity resolves to "drop it", never to "run it".

    Reading "open notepad" as consent to a shutdown is the one outcome that must
    be impossible, so anything that is not clearly yes or no is UNRELATED.
    """
    broker.request(tool="shutdown_pc", params={}, question="Shutdown?", session_id="s")
    decision, _ = broker.resolve(reply, "s")
    assert decision is ConfirmationDecision.UNRELATED, f"{reply!r} -> {decision}"


def test_classify_reply_needs_no_pending_state():
    assert classify_reply("haan") is ConfirmationDecision.AFFIRM
    assert classify_reply("nahi") is ConfirmationDecision.DENY
    assert classify_reply("what time is it") is ConfirmationDecision.UNRELATED
    assert classify_reply("") is ConfirmationDecision.UNRELATED


def test_a_negation_inside_a_sentence_is_not_read_as_consent():
    """"nahi nahi ruko" must never be a yes."""
    for reply in ("nahi nahi", "no no stop", "arre nahi sir"):
        assert classify_reply(reply) is ConfirmationDecision.DENY, reply


# --------------------------------------------------------------------------
# Broker mechanics
# --------------------------------------------------------------------------
def test_resolve_with_nothing_pending_returns_none(broker):
    decision, pending = broker.resolve("haan", "s")
    assert decision is ConfirmationDecision.NONE
    assert pending is None


def test_an_answered_confirmation_is_consumed(broker):
    """A yes must not be reusable -- one approval, one execution."""
    broker.request(tool="shutdown_pc", params={}, question="Shutdown?", session_id="s")
    assert broker.has_pending("s") is True

    broker.resolve("haan", "s")
    assert broker.has_pending("s") is False
    assert broker.resolve("haan", "s")[0] is ConfirmationDecision.NONE


def test_a_denied_confirmation_is_consumed(broker):
    broker.request(tool="shutdown_pc", params={}, question="Shutdown?", session_id="s")
    broker.resolve("nahi", "s")
    assert broker.has_pending("s") is False


def test_unrelated_input_drops_the_pending_action(broker):
    """
    The held action is discarded, not carried forward.

    Keeping it would mean an unrelated "haan" ten minutes later fires a shutdown
    the user has long since forgotten about.
    """
    broker.request(tool="shutdown_pc", params={}, question="Shutdown?", session_id="s")
    broker.resolve("open notepad", "s")
    assert broker.has_pending("s") is False


def test_a_new_request_replaces_the_previous_pending_action(broker):
    broker.request(tool="shutdown_pc", params={}, question="Shutdown?", session_id="s")
    broker.request(tool="delete_file", params={"path": "x"}, question="Delete?", session_id="s")

    pending = broker.peek("s")
    assert pending.tool == "delete_file"
    decision, resolved = broker.resolve("haan", "s")
    assert decision is ConfirmationDecision.AFFIRM
    assert resolved.tool == "delete_file"


def test_sessions_do_not_leak_into_each_other(broker):
    broker.request(tool="shutdown_pc", params={}, question="Shutdown?", session_id="a")
    assert broker.has_pending("b") is False
    assert broker.resolve("haan", "b")[0] is ConfirmationDecision.NONE
    assert broker.has_pending("a") is True


def test_clear_removes_a_pending_action_without_running_it(broker):
    broker.request(tool="shutdown_pc", params={}, question="Shutdown?", session_id="s")
    broker.clear("s")
    assert broker.has_pending("s") is False


def test_peek_does_not_consume(broker):
    broker.request(tool="shutdown_pc", params={}, question="Shutdown?", session_id="s")
    assert broker.peek("s").tool == "shutdown_pc"
    assert broker.peek("s").tool == "shutdown_pc"
    assert broker.has_pending("s") is True


# --------------------------------------------------------------------------
# Expiry
# --------------------------------------------------------------------------
def test_an_expired_confirmation_is_not_executed():
    """
    A forgotten question must not fire later.

    Approving something the user has moved on from is worse than asking again --
    "haan" said to a different question is not consent.
    """
    broker = ConfirmationBroker(ttl_seconds=0.05)
    broker.request(tool="shutdown_pc", params={}, question="Shutdown?", session_id="s")
    time.sleep(0.1)

    decision, pending = broker.resolve("haan", "s")
    assert decision is ConfirmationDecision.EXPIRED
    assert pending is not None, "no context left to explain the expiry"
    assert broker.has_pending("s") is False


def test_has_pending_is_false_once_expired():
    broker = ConfirmationBroker(ttl_seconds=0.05)
    broker.request(tool="shutdown_pc", params={}, question="Shutdown?", session_id="s")
    assert broker.has_pending("s") is True
    time.sleep(0.1)
    assert broker.has_pending("s") is False


def test_include_expired_sees_the_record_peek_would_have_purged():
    """
    The caller that is about to interpret a reply needs to know a record existed.

    Plain has_pending() answers "may this still be approved?" and purges on the
    way past; include_expired answers "was something asked?", which is what
    decides whether the next utterance is an answer or a new command.
    """
    broker = ConfirmationBroker(ttl_seconds=0.05)
    broker.request(tool="shutdown_pc", params={}, question="Shutdown?", session_id="s")
    time.sleep(0.1)

    assert broker.has_pending("s", include_expired=True) is True
    assert broker.has_pending("s") is False, "expired record still answerable"
    assert broker.has_pending("s", include_expired=True) is False, "peek did not purge"


def test_an_unrelated_reply_after_expiry_is_not_reported_as_a_timeout():
    """An expired record plus a new command is just a new command."""
    broker = ConfirmationBroker(ttl_seconds=0.05)
    broker.request(tool="shutdown_pc", params={}, question="Shutdown?", session_id="s")
    time.sleep(0.1)

    decision, pending = broker.resolve("open notepad", "s")
    assert decision is ConfirmationDecision.UNRELATED
    assert pending is not None and pending.tool == "shutdown_pc"
    assert broker.has_pending("s", include_expired=True) is False


def test_expiry_and_cancellation_replies_name_the_action(broker):
    pending = broker.request(
        tool="shutdown_pc", params={}, question="Shutdown?", session_id="s"
    )
    assert broker.cancellation_reply(pending).strip()
    assert broker.expiry_reply(pending).strip()


def test_ttl_comes_from_settings_when_not_given():
    """Phase 14 made the window configurable rather than hardcoded."""
    from config.settings import settings

    saved = settings.CONFIRMATION_TTL_SECONDS
    try:
        settings.CONFIRMATION_TTL_SECONDS = 42.0
        assert ConfirmationBroker().ttl == 42.0
        assert ConfirmationBroker(ttl_seconds=5.0).ttl == 5.0, "explicit arg ignored"
    finally:
        settings.CONFIRMATION_TTL_SECONDS = saved


# --------------------------------------------------------------------------
# End to end through the planner: the part that actually matters
# --------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_shutdown_asks_and_executes_nothing(planner, agents):
    """
    The Section 18 manual check, automated.

    "shutdown my laptop" must produce a question and zero side effects.
    """
    response = await planner.process_user_request("shutdown my laptop", session_id="t")

    assert agents["windows_agent"].calls == [], "something ran before confirmation"
    assert "haan" in response["speech_reply"].lower() or "?" in response["speech_reply"]
    assert planner.safety.has_pending("t") is True

    results = response["execution_results"]
    assert results and results[0]["awaiting_confirmation"] is True
    assert results[0]["ok"] is False


@pytest.mark.asyncio
async def test_the_optimistic_fast_path_line_is_suppressed_while_gated(planner):
    """
    The regex router writes its speech_reply before anything runs.

    Those lines are phrased as done deals ("Ji Sir, shutdown kar raha hoon"), so
    a gated turn has to replace the reply with the question -- otherwise JARVIS
    announces a shutdown that has not happened and then asks about it.
    """
    response = await planner.process_user_request("shutdown my laptop", session_id="t")
    pending = planner.safety.peek_pending("t")

    assert pending is not None
    assert response["speech_reply"] == pending.question


@pytest.mark.asyncio
async def test_haan_executes_the_held_action_once(planner, agents):
    await planner.process_user_request("shutdown my laptop", session_id="t")
    response = await planner.process_user_request("haan", session_id="t")

    calls = agents["windows_agent"].calls
    assert len(calls) == 1, f"expected exactly one call, got {calls}"
    assert response["speech_reply"]
    assert planner.safety.has_pending("t") is False


@pytest.mark.asyncio
async def test_nahi_cancels_and_executes_nothing(planner, agents):
    await planner.process_user_request("shutdown my laptop", session_id="t")
    response = await planner.process_user_request("nahi", session_id="t")

    assert agents["windows_agent"].calls == []
    assert "cancel" in response["speech_reply"].lower()
    assert planner.safety.has_pending("t") is False


@pytest.mark.asyncio
async def test_an_unrelated_reply_drops_the_gate_and_runs_the_new_request(planner, agents):
    """
    The new instruction is honoured and the old one is not.

    This is the subtle one: falling through must not carry the shutdown along,
    and must not swallow the request the user actually just made.
    """
    await planner.process_user_request("shutdown my laptop", session_id="t")
    await planner.process_user_request("open notepad", session_id="t")

    calls = agents["windows_agent"].calls
    assert calls, "the new request was swallowed by the confirmation handler"
    assert all("shutdown" not in action for action, _ in calls), calls
    assert planner.safety.has_pending("t") is False


def _age_out(planner, session_id):
    """
    Backdates the held action past its window, as real elapsed time would.

    Cheaper and more deterministic than sleeping, and it leaves the record in
    place -- which is the interesting state, because reading it through peek()
    purges it.
    """
    pending = planner.safety.peek_pending(session_id)
    assert pending is not None, "nothing was held"
    pending.created_at -= pending.ttl + 1.0
    return pending


@pytest.mark.asyncio
async def test_an_expired_gate_does_not_execute_on_a_late_haan(planner, agents):
    """
    A "haan" that arrives after the window gets an explanation, not a shutdown.

    Regression: process_user_request gated on has_pending(), which purged the
    expired record as a side effect of reading it. resolve_reply() therefore
    never saw an expired pending, the EXPIRED branch and expiry_reply() were
    unreachable, and a late "haan" was re-parsed as a brand-new command -- so the
    user got a confused answer instead of "that timed out, nothing ran".
    """
    await planner.process_user_request("shutdown my laptop", session_id="t")
    _age_out(planner, "t")

    response = await planner.process_user_request("haan", session_id="t")

    assert agents["windows_agent"].calls == [], "an expired action ran anyway"
    assert "time out" in response["speech_reply"].lower(), response["speech_reply"]
    assert planner.safety.has_pending("t", include_expired=True) is False


@pytest.mark.asyncio
async def test_an_expired_gate_does_not_hijack_the_next_real_command(planner, agents):
    """
    The other half: an expired record must not turn a new request into a lecture.

    Telling Sir that a shutdown timed out when he asked for Notepad would be a
    worse bug than the one above.
    """
    await planner.process_user_request("shutdown my laptop", session_id="t")
    _age_out(planner, "t")

    response = await planner.process_user_request("open notepad", session_id="t")

    calls = agents["windows_agent"].calls
    assert calls, "the new request was swallowed by the expired confirmation"
    assert all("shutdown" not in action for action, _ in calls), calls
    assert "time out" not in response["speech_reply"].lower(), response["speech_reply"]


@pytest.mark.asyncio
async def test_a_late_nahi_is_also_answered(planner, agents):
    await planner.process_user_request("shutdown my laptop", session_id="t")
    _age_out(planner, "t")

    response = await planner.process_user_request("nahi", session_id="t")
    assert agents["windows_agent"].calls == []
    assert response["speech_reply"].strip()


@pytest.mark.asyncio
async def test_an_ungated_request_runs_without_asking(planner, agents):
    """Section 16's other half: opening Notepad must not prompt."""
    response = await planner.process_user_request("open notepad", session_id="t")

    assert agents["windows_agent"].calls, "an auto-allowed tool did not run"
    assert planner.safety.has_pending("t") is False
    assert response["execution_results"][0]["ok"] is True


@pytest.mark.asyncio
async def test_a_gate_stops_later_delegations_in_the_same_plan(planner, agents):
    """
    Nothing after a gated step runs either.

    A plan is a sequence; executing step 2 while step 1 waits for approval would
    apply half a plan the user never agreed to.
    """
    plan = {
        "thought": "test",
        "speech_reply": "Ji Sir, kar diya.",
        "delegations": [
            {"agent": "windows_agent", "action": "shutdown_pc", "params": {}},
            {"agent": "windows_agent", "action": "open_app", "params": {"app_name": "notepad"}},
        ],
    }
    results, reply, gated = await planner._execute_delegations(
        plan["delegations"], session_id="t", user_input="test", speech_reply=plan["speech_reply"]
    )

    assert gated is True
    assert len(results) == 1, "kept going past the gate"
    assert agents["windows_agent"].calls == []
    assert reply != plan["speech_reply"], "still claiming the plan is done"


@pytest.mark.asyncio
async def test_the_executed_call_is_the_one_that_was_described(planner, agents):
    """
    Section 13 in spirit: never act on something other than what was confirmed.

    The question quotes a path; the execution must use that same path, not a
    re-parse of the original utterance.
    """
    result = await planner.registry.execute(
        "delete_file", {"file_path": "C:/tmp/report.txt"}, confirmed=False
    )
    pending = planner.safety.hold_for_confirmation(result, session_id="t")

    assert "C:/tmp/report.txt" in pending.question
    assert pending.params == {"path": "C:/tmp/report.txt"}

    await planner.process_user_request("haan", session_id="t")
    assert agents["file_agent"].calls, "confirmed delete never reached the agent"
    action, params = agents["file_agent"].calls[0]
    assert params["path"] == "C:/tmp/report.txt"


@pytest.mark.asyncio
async def test_gui_and_phone_share_one_pending_state(planner, agents):
    """
    Both front-ends call process_user_request without a session_id.

    That is deliberate: they share "default", so a question asked out loud can be
    answered by tapping yes on the phone.
    """
    await planner.process_user_request("shutdown my laptop")
    assert planner.safety.has_pending("default") is True

    await planner.process_user_request("haan")
    assert len(agents["windows_agent"].calls) == 1


@pytest.mark.asyncio
async def test_confirmation_never_blocks_on_input(planner, monkeypatch):
    """
    The regression this whole design exists to prevent.

    A stray input() would hang the Qt worker thread with no console attached, so
    any call to it during a gated turn is a hard failure.
    """
    def forbidden(*args, **kwargs):
        raise AssertionError("input() was called; this would freeze the worker thread")

    monkeypatch.setattr("builtins.input", forbidden)

    await planner.process_user_request("shutdown my laptop", session_id="t")
    await planner.process_user_request("haan", session_id="t")

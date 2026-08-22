"""
JARVIS v4 - WhatsApp call routing & contact-matching tests.
Pure logic only: the real PlannerAgent fast-path is exercised with stubbed sub-agents,
so no WhatsApp window is touched and no call is ever placed.
"""

import re
import types
import pytest

from agents.planner_agent import PlannerAgent
from automation.whatsapp_call import WhatsAppCallController, _normalize
from security.safety import SafetyManager


class _StubMemory:
    def get_all_facts(self):
        return []

    def store_user_fact(self, *a, **kw):
        return True


def _planner() -> PlannerAgent:
    """
    Builds a PlannerAgent with inert collaborators - fast-paths need no LLM.

    The safety manager is the real one rather than a stub: the planner wires the
    tool registry into it at construction, and a bare SimpleNamespace would only
    prove that the stub was accepted. It executes nothing here -- these tests call
    _fast_path_match, which classifies intent and returns.
    """
    return PlannerAgent(
        llm_client=types.SimpleNamespace(),
        memory_manager=_StubMemory(),
        safety_manager=SafetyManager(),
        agents={},
    )


VIDEO_UTTERANCES = [
    "Video Call Mummy on whatsapp",
    "video call mummy",
    "jarvis mummy ko video call kro",
    "mummy ko video call karo",
    "mummy ko whatsapp pe video call kro",
    "whatsapp pe mummy ko video call karo",
    "make a video call to mummy on whatsapp",
    "start a whatsapp video call with mummy",
    "mummy ko video call lagao",
    "mummy ko videocall kar do",
]

VOICE_UTTERANCES = [
    "call mummy on whatsapp",
    "mummy ko call kro",
    "mummy ko call lagao",
    "voice call mummy",
    "audio call mummy on whatsapp",
    "whatsapp call to mummy",
]

END_UTTERANCES = ["end call", "hang up", "call kaat do", "call band karo", "cut the call"]


@pytest.mark.parametrize("phrase", VIDEO_UTTERANCES)
def test_video_call_routes_to_video_call_action(phrase):
    matched, plan = _planner()._fast_path_match(phrase)
    assert matched, f"no fast-path matched: {phrase!r}"
    delegation = plan["delegations"][0]
    assert delegation["agent"] == "whatsapp_agent"
    assert delegation["action"] == "video_call", f"{phrase!r} routed to {delegation['action']}"
    assert delegation["params"]["contact_name"].lower() == "mummy"


@pytest.mark.parametrize("phrase", VOICE_UTTERANCES)
def test_voice_call_routes_to_voice_call_action(phrase):
    matched, plan = _planner()._fast_path_match(phrase)
    assert matched, f"no fast-path matched: {phrase!r}"
    delegation = plan["delegations"][0]
    assert delegation["action"] == "voice_call", f"{phrase!r} routed to {delegation['action']}"
    assert delegation["params"]["contact_name"].lower() == "mummy"


@pytest.mark.parametrize("phrase", END_UTTERANCES)
def test_end_call_utterances(phrase):
    matched, plan = _planner()._fast_path_match(phrase)
    assert matched
    assert plan["delegations"][0]["action"] == "end_call"


def test_call_intent_never_becomes_a_text_message():
    """Regression: the messaging fast-path used to swallow 'video call kro' as message text."""
    for phrase in VIDEO_UTTERANCES + VOICE_UTTERANCES:
        _, plan = _planner()._fast_path_match(phrase)
        actions = [d["action"] for d in plan.get("delegations", [])]
        assert "send_message" not in actions, f"{phrase!r} was routed as a message: {actions}"


def test_multi_word_contact_names_survive_extraction():
    for phrase, expected in [
        ("video call pinki mummy on whatsapp", "pinki mummy"),
        ("abhishek mummy ko video call kro", "abhishek mummy"),
        ("call fr.aman singh 2 on whatsapp", "fr.aman singh 2"),
    ]:
        matched, plan = _planner()._fast_path_match(phrase)
        assert matched, phrase
        assert plan["delegations"][0]["params"]["contact_name"].lower() == expected


def test_messaging_still_works():
    matched, plan = _planner()._fast_path_match("mummy ko message bhejo hello")
    assert matched
    assert plan["delegations"][0]["action"] == "send_message"


def test_non_call_phrases_are_not_hijacked():
    for phrase in ["show me my call history", "what do you call this", "recall my last note"]:
        _, plan = _planner()._fast_path_match(phrase)
        actions = [d["action"] for d in plan.get("delegations", [])]
        assert "video_call" not in actions and "voice_call" not in actions, phrase


# ----------------------------------------------------------------- contact matching

def _candidates(*rows):
    """Builds the candidate shape _pick() consumes from real search-result labels."""
    return [
        {"label": label, "norm": _normalize(label), "section": section,
         "blocked": blocked, "element": None}
        for label, section, blocked in rows
    ]


def test_exact_match_wins_over_similar_contacts():
    """Live search for 'mummy' really does return all of these rows."""
    picked, _ = WhatsAppCallController()._pick("Mummy", _candidates(
        ("Mummy", "Chats", False),
        ("Pinki Mummy", "Contacts", False),
        ("Abhishek Mummy", "Contacts", False),
        ("Pinki Mummy Whatsapp", "Contacts", False),
        ("Lalla Ki Mummy", "Contacts", True),
    ))
    assert picked is not None and picked["label"] == "Mummy"


def test_blocked_contacts_are_never_picked():
    picked, _ = WhatsAppCallController()._pick("Lalla Ki Mummy", _candidates(
        ("Lalla Ki Mummy", "Contacts", True),
    ))
    assert picked is None


def test_ambiguous_prefix_refuses_to_pick():
    picked, shortlist = WhatsAppCallController()._pick("pinki mummy", _candidates(
        ("Pinki Mummy", "Contacts", False),
        ("Pinki Mummy Whatsapp", "Contacts", False),
    ))
    assert picked is not None and picked["label"] == "Pinki Mummy"

    picked2, shortlist2 = WhatsAppCallController()._pick("pinki", _candidates(
        ("Pinki Mummy", "Contacts", False),
        ("Pinki Mummy Whatsapp", "Contacts", False),
    ))
    assert picked2 is None
    assert len(shortlist2) == 2


def test_emoji_and_case_are_normalized():
    assert _normalize("Lalla Ki Mummy \U0001F92E \U0001F92E") == "lalla ki mummy"
    assert _normalize("  MUMMY  ") == "mummy"


def test_unmatched_contact_returns_nothing():
    picked, shortlist = WhatsAppCallController()._pick("papa", _candidates(
        ("Mummy", "Chats", False),
    ))
    assert picked is None and not shortlist

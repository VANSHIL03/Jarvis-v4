"""
JARVIS v4 - Two-Turn Confirmation Broker

Section 16/20 require explicit approval before destructive or consequential
actions. The obvious implementation -- ``input()`` -- cannot work here: the
request arrives from a Qt worker thread, from the voice pipeline, or from the
phone web server, none of which have a console. A blocking prompt would simply
freeze JARVIS.

So confirmation is conversational instead, which is also how the spec words it:

    Sir : "Shut down my laptop."
    JARVIS: "Sir, laptop abhi shutdown karna hai? Haan ya na bataiye."   # nothing runs
    Sir : "haan"
          -> the pending tool executes

The pending action lives here, keyed by session, with a TTL. Replying with
neither yes nor no drops it and the input is handled as a fresh request, so a
forgotten pending confirmation can never wedge the assistant.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional, Tuple

from config.settings import settings
from utils.logger import logger

DEFAULT_TTL_SECONDS = 120.0


class ConfirmationDecision(Enum):
    """How the user's reply was understood."""

    NONE = "none"            # nothing was pending
    AFFIRM = "affirm"        # go ahead
    DENY = "deny"            # cancel it
    UNRELATED = "unrelated"  # neither; pending dropped, treat as a new request
    EXPIRED = "expired"      # pending timed out before a reply arrived


# Multi-word forms collapsed before matching, so "kar do" and "kardo" behave the
# same and "abhi nahi" is not read as the filler "abhi" plus a stray token.
_PHRASE_COLLAPSE = {
    "kar do": "kardo",
    "kar de": "kardo",
    "kar dijiye": "kardo",
    "kar dijiyega": "kardo",
    "ji haan": "haan",
    "haan ji": "haan",
    "ji han": "haan",
    "han ji": "haan",
    "theek hai": "theekhai",
    "thik hai": "theekhai",
    "sahi hai": "theekhai",
    "go ahead": "proceed",
    "do it": "proceed",
    "aage badho": "proceed",
    "start karo": "proceed",
    "yes please": "haan",
    "abhi nahi": "abhinahi",
    "mat karo": "matkaro",
    "mat karna": "matkaro",
    "nahi karna": "matkaro",
    "nahi chahiye": "matkaro",
    "rehne do": "rehnedo",
    "chhod do": "rehnedo",
    "chod do": "rehnedo",
    "cancel karo": "cancel",
    "cancel kar do": "cancel",
    "ruk jao": "ruko",
    "band karo": "cancel",
    "never mind": "cancel",
    "nevermind": "cancel",
    "forget it": "cancel",
    "koi nahi": "cancel",
    "no thanks": "nahi",
    "nahi nahi": "nahi",
}

_AFFIRM_EXACT = {
    "yes", "yeah", "yep", "yup", "ya", "yess", "y",
    "haan", "haa", "ha", "han", "hanji", "ji", "jee",
    "ok", "okay", "okey", "k", "sure", "confirm", "confirmed",
    "kardo", "karo", "theekhai", "bilkul", "proceed", "chalo",
    "zaroor", "definitely", "absolutely", "affirmative", "haanji",
}

_DENY_EXACT = {
    "no", "nope", "nah", "nahi", "nahin", "na", "naa", "nai",
    "matkaro", "cancel", "ruko", "stop", "rehnedo", "abhinahi",
    "abort", "negative", "dont", "don't",
}

# Words that carry no decision on their own and may pad a reply.
_FILLERS = {
    "sir", "please", "pls", "bhai", "boss", "jarvis", "abhi", "now",
    "thanks", "thank", "you", "hi", "hey", "acha", "achha", "arre", "haa",
}

_STRONG_AFFIRM = {
    "yes", "yeah", "yep", "yup", "haan", "haa", "ha", "han", "hanji", "ji",
    "ok", "okay", "sure", "confirm", "kardo", "karo", "theekhai", "bilkul",
    "proceed", "zaroor",
}

_STRONG_DENY = {
    "no", "nope", "nah", "nahi", "nahin", "nai", "matkaro", "cancel",
    "ruko", "stop", "rehnedo", "abhinahi", "abort",
}

_PUNCT_RE = re.compile(r"[^\w\s'-]+", re.UNICODE)


def _normalize(text: str) -> str:
    cleaned = _PUNCT_RE.sub(" ", (text or "").lower())
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    for phrase, token in _PHRASE_COLLAPSE.items():
        if phrase in cleaned:
            cleaned = cleaned.replace(phrase, token)
    return re.sub(r"\s+", " ", cleaned).strip()


def classify_reply(text: str) -> ConfirmationDecision:
    """
    Reads a short reply as yes, no, or neither.

    Deliberately conservative: only a reply that is *essentially nothing but* an
    answer counts. "haan notepad kholo" is a new command, not approval to shut
    the laptop down, so it comes back UNRELATED and the pending action is
    discarded without running.
    """
    norm = _normalize(text)
    if not norm:
        return ConfirmationDecision.UNRELATED

    if norm in _DENY_EXACT:
        return ConfirmationDecision.DENY
    if norm in _AFFIRM_EXACT:
        return ConfirmationDecision.AFFIRM

    tokens = norm.split()
    meaningful = [t for t in tokens if t not in _FILLERS]

    if not meaningful:
        # Only fillers, e.g. "sir please" -- not an answer.
        return ConfirmationDecision.UNRELATED

    joined = " ".join(meaningful)
    if joined in _DENY_EXACT:
        return ConfirmationDecision.DENY
    if joined in _AFFIRM_EXACT:
        return ConfirmationDecision.AFFIRM

    if len(meaningful) > 4:
        return ConfirmationDecision.UNRELATED

    deny_hits = {t for t in meaningful if t in _STRONG_DENY}
    affirm_hits = {t for t in meaningful if t in _STRONG_AFFIRM}
    other = [t for t in meaningful if t not in _STRONG_DENY and t not in _STRONG_AFFIRM]

    if other:
        # Carries content beyond yes/no ("haan gaana chala do") -> new request.
        return ConfirmationDecision.UNRELATED
    if deny_hits and not affirm_hits:
        return ConfirmationDecision.DENY
    if affirm_hits and not deny_hits:
        return ConfirmationDecision.AFFIRM
    if deny_hits and affirm_hits:
        # Contradictory ("haan nahi") -- refuse to execute anything.
        return ConfirmationDecision.DENY
    return ConfirmationDecision.UNRELATED


@dataclass
class PendingConfirmation:
    """One action held back until the user approves it."""

    tool: str
    params: Dict[str, Any] = field(default_factory=dict)
    question: str = ""
    session_id: str = "default"
    created_at: float = field(default_factory=time.time)
    ttl: float = DEFAULT_TTL_SECONDS
    original_input: str = ""
    on_confirm_reply: str = ""   # spoken line to use once it actually runs

    def is_expired(self, now: Optional[float] = None) -> bool:
        return ((now or time.time()) - self.created_at) > self.ttl

    def age(self, now: Optional[float] = None) -> float:
        return (now or time.time()) - self.created_at

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tool": self.tool,
            "params": dict(self.params),
            "question": self.question,
            "session_id": self.session_id,
            "age_seconds": round(self.age(), 1),
            "ttl": self.ttl,
        }


class ConfirmationBroker:
    """
    Holds at most one pending confirmation per session.

    A second gated request replaces the first: asking about a shutdown and then
    asking about a delete should leave the delete pending, not a stale shutdown.
    """

    def __init__(self, ttl_seconds: Optional[float] = None):
        self.ttl = float(
            ttl_seconds
            if ttl_seconds is not None
            else getattr(settings, "CONFIRMATION_TTL_SECONDS", DEFAULT_TTL_SECONDS)
        )
        self._pending: Dict[str, PendingConfirmation] = {}

    # ------------------------------------------------------------- request
    def request(
        self,
        tool: str,
        params: Optional[Dict[str, Any]] = None,
        question: str = "",
        session_id: str = "default",
        original_input: str = "",
        on_confirm_reply: str = "",
    ) -> PendingConfirmation:
        """Stores an action as pending and returns it, so the caller can ask."""
        if session_id in self._pending:
            previous = self._pending[session_id]
            logger.info(
                f"Replacing unanswered confirmation for '{previous.tool}' "
                f"with '{tool}' (session={session_id})."
            )
        pending = PendingConfirmation(
            tool=tool,
            params=dict(params or {}),
            question=question,
            session_id=session_id,
            ttl=self.ttl,
            original_input=original_input,
            on_confirm_reply=on_confirm_reply,
        )
        self._pending[session_id] = pending
        logger.info(f"Confirmation pending: {tool} (session={session_id})")
        return pending

    # -------------------------------------------------------------- state
    def has_pending(self, session_id: str = "default") -> bool:
        return self.peek(session_id) is not None

    def peek(self, session_id: str = "default") -> Optional[PendingConfirmation]:
        """Returns the live pending action, silently discarding an expired one."""
        pending = self._pending.get(session_id)
        if pending is None:
            return None
        if pending.is_expired():
            logger.info(
                f"Confirmation for '{pending.tool}' expired after "
                f"{pending.ttl:.0f}s; discarded without executing."
            )
            self._pending.pop(session_id, None)
            return None
        return pending

    def clear(self, session_id: Optional[str] = None):
        if session_id is None:
            self._pending.clear()
        else:
            self._pending.pop(session_id, None)

    # ------------------------------------------------------------ resolve
    def resolve(
        self, user_input: str, session_id: str = "default"
    ) -> Tuple[ConfirmationDecision, Optional[PendingConfirmation]]:
        """
        Interprets an incoming utterance against the pending action.

        Returns the decision and, for AFFIRM/DENY/UNRELATED, the pending action
        that was removed. The caller executes it only on AFFIRM.
        """
        raw = self._pending.get(session_id)
        if raw is None:
            return ConfirmationDecision.NONE, None

        if raw.is_expired():
            self._pending.pop(session_id, None)
            logger.info(f"Confirmation for '{raw.tool}' expired; nothing executed.")
            return ConfirmationDecision.EXPIRED, raw

        decision = classify_reply(user_input)

        if decision is ConfirmationDecision.AFFIRM:
            self._pending.pop(session_id, None)
            logger.info(f"User CONFIRMED '{raw.tool}' params={raw.params}")
            return decision, raw

        if decision is ConfirmationDecision.DENY:
            self._pending.pop(session_id, None)
            logger.info(f"User DENIED '{raw.tool}'; not executed.")
            return decision, raw

        # Neither yes nor no: abandon the pending action and handle the new input.
        self._pending.pop(session_id, None)
        logger.info(
            f"Unrelated reply while '{raw.tool}' was pending; dropped it and "
            "treating the input as a new request."
        )
        return ConfirmationDecision.UNRELATED, raw

    # ----------------------------------------------------- spoken replies
    @staticmethod
    def cancellation_reply(pending: PendingConfirmation) -> str:
        return f"Theek hai Sir, {ConfirmationBroker._describe(pending)} cancel kar diya."

    @staticmethod
    def expiry_reply(pending: PendingConfirmation) -> str:
        return (
            f"Sir, {ConfirmationBroker._describe(pending)} ka confirmation "
            "time out ho gaya tha, isliye kuch nahi kiya."
        )

    @staticmethod
    def _describe(pending: PendingConfirmation) -> str:
        """Short human phrase for the held action, used in spoken replies."""
        phrases = {
            "shutdown_pc": "shutdown",
            "restart_pc": "restart",
            "delete_file": "delete",
            "send_message": "message bhejna",
            "send_file": "file bhejna",
            "send_email": "email bhejna",
            "voice_call": "call",
            "video_call": "video call",
            "run_code": "code run karna",
            "forget": "memory delete karna",
            "forget_about": "memory delete karna",
            "push_to_github": "GitHub push",
        }
        return phrases.get(pending.tool, f"'{pending.tool}'")


__all__ = [
    "ConfirmationBroker",
    "ConfirmationDecision",
    "PendingConfirmation",
    "classify_reply",
]

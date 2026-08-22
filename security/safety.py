"""
JARVIS v4 - Safety Gate

The old implementation of this module decided what was dangerous by looking for
substrings in ``f"{action} {params}"``. That approach was wrong in both
directions at once:

  * it missed real danger -- ``delete_folder`` does not contain "delete file",
    and a path of ``C:/Users/vansh/Documents`` with any action name at all
    matched nothing, so destructive calls sailed through;
  * it invented danger that was not there -- "send email" matched the innocent
    ``search_google(query="how to send email")``;
  * and it carried an explicit hardcoded bypass that returned False for
    ``shutdown_pc``, ``restart_pc``, ``lock_pc`` and ``sleep_pc``, which is the
    exact opposite of what Section 16 asks for. That bypass is gone.

Danger is now a property the tool itself declares (``ToolSpec.permission``), that
the user can retune (``PermissionPolicy`` / data/permissions.json), and that is
enforced at the single execution path (``ToolRegistry.execute`` refuses to run a
gated tool without ``confirmed=True``). This module is the seam the rest of
JARVIS talks to: it answers "does this call need approval, and what should I ask?"
and it holds the pending action until the user replies.

The console ``input()`` fallback is also gone. Requests arrive from a Qt worker
thread, the voice pipeline, or the phone's web server -- none of which have a
console, and all of which would freeze behind a blocking prompt. Confirmation is
conversational instead (see security/confirmation.py), so the same two-turn
"haan ya na" flow works from the GUI, voice, typed text and the mobile server.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional, Tuple

from config.settings import settings
from security.confirmation import (
    ConfirmationBroker,
    ConfirmationDecision,
    PendingConfirmation,
)
from security.permissions import PermissionLevel, PermissionPolicy
from utils.logger import logger


@dataclass
class SafetyDecision:
    """What the gate concluded about one specific call."""

    tool: str
    params: Dict[str, Any] = field(default_factory=dict)
    level: PermissionLevel = PermissionLevel.SAFE
    needs_confirmation: bool = False
    question: str = ""
    known: bool = True   # False when no ToolSpec matched the requested name

    @property
    def allowed_now(self) -> bool:
        """True when the call may run immediately, with nothing to ask."""
        return not self.needs_confirmation

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tool": self.tool,
            "params": dict(self.params),
            "permission": self.level.name,
            "needs_confirmation": self.needs_confirmation,
            "question": self.question,
            "known_tool": self.known,
        }


class SafetyManager:
    """
    Permission gate plus pending-confirmation state.

    Constructed with no arguments it builds its own default registry and policy,
    which keeps existing callers (and the unit tests) working. main.py hands it
    the live registry and broker through :meth:`attach` so that the GUI, the
    voice loop and the mobile server all share one pending-confirmation state --
    approving on the phone must satisfy a question asked by voice.
    """

    def __init__(
        self,
        registry: Optional[Any] = None,
        policy: Optional[PermissionPolicy] = None,
        broker: Optional[ConfirmationBroker] = None,
    ):
        self._registry = registry
        self.policy = policy or getattr(registry, "policy", None) or PermissionPolicy()
        self.broker = broker or ConfirmationBroker()

        # Retained only so an unregistered action name still gets a sensible
        # answer from the legacy is_dangerous_action() wrapper. It is never
        # consulted for a tool the registry knows about.
        self.dangerous_keywords = list(
            getattr(settings, "DANGEROUS_COMMAND_KEYWORDS", []) or []
        )

        # Legacy hook: a UI/voice callback that returns True/False for a question.
        # Kept for backwards compatibility; must not block. Prefer the
        # conversational flow (request_confirmation + resolve_reply).
        self.confirmation_callback: Optional[Callable[[str], bool]] = None

    # ------------------------------------------------------------- plumbing
    def attach(
        self,
        registry: Optional[Any] = None,
        broker: Optional[ConfirmationBroker] = None,
        policy: Optional[PermissionPolicy] = None,
    ) -> "SafetyManager":
        """Wires in the live registry/broker/policy built by main.py."""
        if registry is not None:
            self._registry = registry
            if policy is None and getattr(registry, "policy", None) is not None:
                self.policy = registry.policy
        if broker is not None:
            self.broker = broker
        if policy is not None:
            self.policy = policy
        return self

    @property
    def registry(self) -> Any:
        """
        The tool registry, built on first use if nobody attached one.

        Imported lazily: security.permissions is imported *by* the tools
        package, so a module-level import here would be circular, and building
        the full catalogue on ``import security`` would be wasteful.
        """
        if self._registry is None:
            from tools import build_registry

            self._registry = build_registry(policy=self.policy)
            logger.debug(
                f"SafetyManager built a default tool registry "
                f"({len(self._registry)} tools)."
            )
        return self._registry

    def set_confirmation_callback(self, callback: Callable[[str], bool]):
        """
        Registers a legacy synchronous approve/deny callback.

        Only useful for a caller that genuinely can block (a modal dialog on the
        GUI thread). Voice, text and the mobile server must use the
        conversational flow instead.
        """
        self.confirmation_callback = callback

    # ------------------------------------------------------------ evaluation
    def resolve_spec(self, tool: Any, agent: Optional[str] = None) -> Optional[Any]:
        """Finds the ToolSpec for a tool name, or for a legacy (agent, action) pair."""
        registry = self.registry
        if hasattr(tool, "name") and hasattr(tool, "permission"):
            return tool

        name = str(tool or "").strip()
        if not name:
            return None

        spec = registry.get(name)
        if spec is not None:
            return spec
        return registry.resolve_legacy(agent or "", name)

    def evaluate(
        self,
        tool: Any,
        params: Optional[Dict[str, Any]] = None,
        agent: Optional[str] = None,
    ) -> SafetyDecision:
        """
        Decides whether one call needs approval, and what to ask.

        This is the primary mechanism. It reads the tool's declared permission
        level, applies the user's overrides, and honours any per-call
        ``confirm_when`` gate (that is how an uncertain WhatsApp recipient is
        always confirmed while a known contact is not).
        """
        registry = self.registry
        spec = self.resolve_spec(tool, agent)
        raw = dict(params or {})

        if spec is None:
            name = getattr(tool, "name", None) or str(tool or "")
            dangerous = self._keyword_fallback(name, raw)
            logger.warning(
                f"Safety gate asked about unregistered action '{name}'; "
                f"falling back to keyword heuristic (dangerous={dangerous}). "
                "Nothing can execute outside the registry regardless."
            )
            return SafetyDecision(
                tool=name,
                params=raw,
                level=PermissionLevel.DANGEROUS if dangerous else PermissionLevel.SAFE,
                needs_confirmation=dangerous,
                question=(
                    f"Sir, '{name}' chalana hai? Haan ya na bataiye."
                    if dangerous else ""
                ),
                known=False,
            )

        # Normalise so the question renders with canonical names -- a fast-path
        # that passes folder_path still produces "'C:/x' delete karna hai?".
        try:
            clean, _missing = registry.normalize_params(spec, raw)
        except Exception:
            clean = raw

        level = registry.level_for(spec)
        needs = bool(registry.needs_confirmation(spec, clean))
        return SafetyDecision(
            tool=spec.name,
            params=clean,
            level=level,
            needs_confirmation=needs,
            question=registry.confirmation_question(spec, clean) if needs else "",
            known=True,
        )

    def permission_for(
        self, tool: Any, agent: Optional[str] = None
    ) -> PermissionLevel:
        """Effective risk tier of a tool after user overrides."""
        spec = self.resolve_spec(tool, agent)
        if spec is None:
            return PermissionLevel.DANGEROUS
        return self.registry.level_for(spec)

    def _keyword_fallback(self, action_name: str, params: Dict[str, Any]) -> bool:
        """Legacy substring check, used only for names the registry does not know."""
        haystack = f"{action_name} {params}".lower().replace("_", " ")
        return any(kw.lower() in haystack for kw in self.dangerous_keywords)

    # ------------------------------------------------- conversational flow
    def request_confirmation(
        self,
        tool: Any,
        params: Optional[Dict[str, Any]] = None,
        session_id: str = "default",
        original_input: str = "",
        question: str = "",
        on_confirm_reply: str = "",
        agent: Optional[str] = None,
    ) -> PendingConfirmation:
        """
        Holds a call back until the user answers, and returns what to ask.

        Nothing is executed here -- that is the point. The caller speaks
        ``pending.question`` and returns; the next utterance goes through
        :meth:`resolve_reply`.
        """
        decision = self.evaluate(tool, params, agent=agent)
        return self.broker.request(
            tool=decision.tool,
            params=decision.params,
            question=question or decision.question,
            session_id=session_id,
            original_input=original_input,
            on_confirm_reply=on_confirm_reply,
        )

    def hold_for_confirmation(
        self,
        result: Any,
        session_id: str = "default",
        original_input: str = "",
        on_confirm_reply: str = "",
    ) -> PendingConfirmation:
        """
        Holds a ToolResult that came back ``awaiting_confirmation``.

        The registry has already normalised the parameters and rendered the
        question, so this stores them verbatim rather than re-deriving them --
        the action that eventually runs is byte-for-byte the one the user was
        asked about.
        """
        data = getattr(result, "data", None) or {}
        return self.broker.request(
            tool=getattr(result, "tool", "") or "",
            params=data.get("params") or {},
            question=data.get("question") or getattr(result, "message", "") or "",
            session_id=session_id,
            original_input=original_input,
            on_confirm_reply=on_confirm_reply,
        )

    def has_pending(
        self, session_id: str = "default", include_expired: bool = False
    ) -> bool:
        """
        Whether this session owes an answer.

        Pass ``include_expired=True`` before routing an utterance into
        :meth:`resolve_reply`, so a reply that arrived just after the window
        closed is answered ("that timed out, nothing ran") rather than silently
        re-parsed as a new command.
        """
        return self.broker.has_pending(session_id, include_expired=include_expired)

    def peek_pending(self, session_id: str = "default") -> Optional[PendingConfirmation]:
        return self.broker.peek(session_id)

    def clear_pending(self, session_id: Optional[str] = None):
        self.broker.clear(session_id)

    def resolve_reply(
        self, user_input: str, session_id: str = "default"
    ) -> Tuple[ConfirmationDecision, Optional[PendingConfirmation]]:
        """
        Interprets an utterance against the pending action.

        Returns (decision, pending). The caller executes the pending tool only
        on ``ConfirmationDecision.AFFIRM``, and passes ``confirmed=True`` to
        ``ToolRegistry.execute`` when it does.
        """
        return self.broker.resolve(user_input, session_id)

    def cancellation_reply(self, pending: PendingConfirmation) -> str:
        return self.broker.cancellation_reply(pending)

    def expiry_reply(self, pending: PendingConfirmation) -> str:
        return self.broker.expiry_reply(pending)

    # ------------------------------------------------ backwards-compatible API
    def is_dangerous_action(
        self,
        action_name: str,
        params: Optional[Dict[str, Any]] = None,
        agent: Optional[str] = None,
    ) -> bool:
        """
        Whether this call is gated behind user approval.

        Backwards-compatible wrapper kept for existing callers and tests. The
        answer now comes from the tool's declared permission level rather than
        from substring matching, and there is no longer any bypass for power
        actions: shutdown and restart are DANGEROUS and report True.
        """
        return bool(self.evaluate(action_name, params, agent=agent).needs_confirmation)

    def check_and_confirm(
        self,
        action_name: str,
        params: Optional[Dict[str, Any]] = None,
        agent: Optional[str] = None,
    ) -> bool:
        """
        Legacy synchronous gate: True means "you may proceed now".

        Default-deny. A gated action returns False unless a legacy confirmation
        callback approves it, because the alternative -- blocking on ``input()``
        -- would hang the Qt worker thread with no console to type into. Callers
        that want the real two-turn flow should use :meth:`evaluate` plus
        :meth:`request_confirmation`.
        """
        if not settings.SAFETY_CONFIRMATION_REQUIRED:
            return True

        decision = self.evaluate(action_name, params, agent=agent)
        if not decision.needs_confirmation:
            return True

        logger.warning(
            f"SAFETY GATE: '{decision.tool}' [{decision.level.name}] "
            "requires confirmation before it may run."
        )

        if self.confirmation_callback is not None:
            try:
                approved = bool(self.confirmation_callback(decision.question))
            except Exception as e:
                logger.error(f"Confirmation callback raised ({e}); denying.")
                return False
            logger.info(
                f"Confirmation callback {'APPROVED' if approved else 'REJECTED'} "
                f"'{decision.tool}'."
            )
            return approved

        logger.warning(
            f"No confirmation channel available for '{decision.tool}'; refusing to "
            "run it. Use request_confirmation() for the conversational flow."
        )
        return False


__all__ = ["SafetyManager", "SafetyDecision"]

"""
JARVIS v4 - Controlled Tool Registry

The single execution path for every capability JARVIS has. Nothing else may
invoke automation directly: the LLM (and the regex fast-paths) name a tool, and
this registry validates the arguments, applies the permission gate, dispatches
to the bound sub-agent and normalises the outcome.

Two properties are deliberate and load-bearing:

  * Default-deny -- a tool that needs confirmation and is called without
    ``confirmed=True`` is refused, not executed. Skipping the confirmation flow
    is structurally impossible rather than merely discouraged.
  * Uniform results -- every call returns a ToolResult whose ``ok`` flag is
    authoritative, so a failing sub-agent can never be reported as a success.
"""

from __future__ import annotations

import inspect
from typing import Any, Dict, Iterable, List, Optional, Tuple, Union

from security.permissions import PermissionLevel, PermissionPolicy
from tools.base import ToolCall, ToolParam, ToolResult, ToolSpec
from utils.logger import logger

SpecOrName = Union[str, ToolSpec]


class ToolRegistry:
    """Holds every ToolSpec and is the only place tools are executed."""

    def __init__(
        self,
        policy: Optional[PermissionPolicy] = None,
        agents: Optional[Dict[str, Any]] = None,
    ):
        self.policy = policy or PermissionPolicy()
        self.agents: Dict[str, Any] = dict(agents or {})
        self._tools: Dict[str, ToolSpec] = {}
        # ("windows_agent", "launch_app") -> "open_app"
        self._legacy: Dict[Tuple[str, str], str] = {}

    # --------------------------------------------------------- registration
    def register(self, spec: ToolSpec, replace: bool = False) -> ToolSpec:
        """Adds one tool. Duplicate names are rejected unless replace=True."""
        if spec.name in self._tools and not replace:
            raise ValueError(f"Tool '{spec.name}' is already registered.")
        self._tools[spec.name] = spec

        if spec.agent and spec.action:
            self._legacy[(spec.agent, spec.action)] = spec.name
        for legacy_action in spec.legacy_actions:
            if spec.agent:
                self._legacy[(spec.agent, legacy_action)] = spec.name
        return spec

    def register_all(self, specs: Iterable[ToolSpec], replace: bool = False) -> int:
        count = 0
        for spec in specs:
            self.register(spec, replace=replace)
            count += 1
        return count

    def bind_agents(self, agents: Dict[str, Any]):
        """Attaches the live sub-agent instances built by main.py."""
        self.agents.update(agents or {})

    # -------------------------------------------------------------- lookup
    def get(self, name: str) -> Optional[ToolSpec]:
        if not name:
            return None
        return self._tools.get(str(name).strip().lower())

    def all(self) -> List[ToolSpec]:
        return list(self._tools.values())

    def names(self) -> List[str]:
        return sorted(self._tools.keys())

    def __contains__(self, name: object) -> bool:
        return isinstance(name, str) and str(name).strip().lower() in self._tools

    def __len__(self) -> int:
        return len(self._tools)

    def by_category(self) -> Dict[str, List[ToolSpec]]:
        grouped: Dict[str, List[ToolSpec]] = {}
        for spec in self._tools.values():
            grouped.setdefault(spec.category, []).append(spec)
        for specs in grouped.values():
            specs.sort(key=lambda s: s.name)
        return grouped

    def resolve_legacy(self, agent: str, action: str) -> Optional[ToolSpec]:
        """
        Maps an old-style {"agent", "action"} delegation onto a tool.

        Keeps a model (or a saved plan) that still emits the previous format
        working, instead of silently dropping the request.
        """
        if not action:
            return None
        action = str(action).strip().lower()
        agent = str(agent or "").strip().lower()

        name = self._legacy.get((agent, action))
        if name:
            return self._tools.get(name)

        # The action may already be a tool name.
        direct = self._tools.get(action)
        if direct is not None:
            return direct

        # Unknown/misnamed agent but a unique action across the registry.
        matches = {n for (_, a), n in self._legacy.items() if a == action}
        if len(matches) == 1:
            return self._tools.get(next(iter(matches)))
        return None

    def resolve(self, tool: SpecOrName) -> Optional[ToolSpec]:
        return tool if isinstance(tool, ToolSpec) else self.get(tool)

    # ----------------------------------------------------------- arguments
    def normalize_params(
        self, spec: ToolSpec, params: Optional[Dict[str, Any]]
    ) -> Tuple[Dict[str, Any], List[str]]:
        """
        Cleans loosely-typed arguments into the tool's declared schema.

        Applies aliases, coerces types, fills defaults and drops unknown keys.
        Returns (clean_params, missing_required).
        """
        raw = dict(params or {})
        declared = spec.param_map

        # Aliases first: folder_path -> path, contact_name -> contact, ...
        aliased: Dict[str, Any] = {}
        for key, value in raw.items():
            canonical = spec.aliases.get(key, key)
            if canonical in aliased and aliased[canonical] not in (None, ""):
                continue  # an explicit canonical value wins over an alias
            aliased[canonical] = value

        clean: Dict[str, Any] = {}
        for name, param in declared.items():
            if name in aliased and aliased[name] is not None:
                clean[name] = param.coerce(aliased[name])
            elif param.default is not None:
                clean[name] = param.default

        dropped = [k for k in aliased if k not in declared]
        if dropped:
            logger.debug(f"Tool '{spec.name}': ignoring unknown param(s) {dropped}")

        missing = [
            name for name in spec.required_params
            if clean.get(name) in (None, "", [], {})
        ]
        return clean, missing

    # ---------------------------------------------------------- permission
    def level_for(self, tool: SpecOrName) -> PermissionLevel:
        spec = self.resolve(tool)
        if spec is None:
            return PermissionLevel.DANGEROUS  # unknown => treat as worst case
        return self.policy.level_for(spec.name, spec.permission)

    def needs_confirmation(
        self, tool: SpecOrName, params: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Whether this exact call must be approved by the user first.

        Beyond the level threshold, a tool may add a dynamic gate via
        ``confirm_when`` -- that is how an ambiguous WhatsApp contact is always
        confirmed while a known contact is not.
        """
        spec = self.resolve(tool)
        if spec is None:
            return True

        if self.policy.requires_confirmation(
            spec.name, spec.permission, spec.requires_confirmation
        ):
            return True

        if spec.confirm_when is not None:
            try:
                return bool(spec.confirm_when(dict(params or {})))
            except Exception as e:
                logger.warning(
                    f"confirm_when for '{spec.name}' raised ({e}); asking to be safe."
                )
                return True
        return False

    def confirmation_question(
        self, tool: SpecOrName, params: Optional[Dict[str, Any]] = None
    ) -> str:
        spec = self.resolve(tool)
        if spec is None:
            return "Sir, ye action confirm karein? Haan ya na bataiye."
        return spec.confirmation_question(params or {})

    # ------------------------------------------------------------- execute
    async def execute(
        self,
        tool: SpecOrName,
        params: Optional[Dict[str, Any]] = None,
        *,
        confirmed: bool = False,
    ) -> ToolResult:
        """
        Runs one tool. Never raises -- failures come back as ok=False.

        A gated tool without ``confirmed=True`` returns blocked=True and is not
        executed, so the confirmation flow cannot be bypassed by a caller that
        forgets to ask.
        """
        spec = self.resolve(tool)
        if spec is None:
            name = tool if isinstance(tool, str) else getattr(tool, "name", "?")
            logger.warning(f"Unknown tool requested: '{name}'")
            return ToolResult(
                ok=False,
                tool=str(name),
                message=f"Sir, '{name}' naam ka koi tool available nahi hai.",
            )

        level = self.level_for(spec)
        clean, missing = self.normalize_params(spec, params)

        if missing:
            return ToolResult(
                ok=False,
                tool=spec.name,
                permission=level,
                data={"missing": missing},
                message=(
                    f"Sir, '{spec.name}' ke liye {', '.join(missing)} "
                    "ki jankari missing hai."
                ),
            )

        if not confirmed and self.needs_confirmation(spec, clean):
            question = self.confirmation_question(spec, clean)
            logger.info(f"Tool '{spec.name}' gated ({level.name}); awaiting confirmation.")
            return ToolResult(
                ok=False,
                tool=spec.name,
                permission=level,
                blocked=True,
                awaiting_confirmation=True,
                data={"params": clean, "question": question},
                message=question,
            )

        logger.info(f"Executing tool '{spec.name}' [{level.name}] params={clean}")
        try:
            payload = await self._dispatch(spec, clean)
        except Exception as e:
            logger.error(f"Tool '{spec.name}' raised: {e}", exc_info=True)
            return ToolResult(
                ok=False,
                tool=spec.name,
                permission=level,
                data={"error": str(e), "params": clean},
                message=f"Sir, '{spec.name}' execute karte waqt problem aa gayi: {e}",
            )

        result = ToolResult.from_agent_payload(spec.name, payload, permission=level)
        if not result.ok:
            logger.warning(f"Tool '{spec.name}' failed: {result.message or result.data}")
        return result

    async def execute_call(
        self, call: ToolCall, *, confirmed: bool = False
    ) -> ToolResult:
        return await self.execute(call.tool, call.params, confirmed=confirmed)

    async def _dispatch(self, spec: ToolSpec, params: Dict[str, Any]) -> Any:
        """Invokes the tool's handler, or the sub-agent it is bound to."""
        if spec.handler is not None:
            outcome = spec.handler(**params)
            if inspect.isawaitable(outcome):
                outcome = await outcome
            return outcome

        agent = self.agents.get(spec.agent)
        if agent is None:
            raise RuntimeError(
                f"Sub-agent '{spec.agent}' is not available for tool '{spec.name}'."
            )
        outcome = agent.execute_task(spec.action, params)
        if inspect.isawaitable(outcome):
            outcome = await outcome
        return outcome

    # ----------------------------------------------------- LLM description
    def describe_for_llm(self, max_chars: int = 6000) -> str:
        """
        Renders the tool catalogue for the planner prompt.

        Grouped by category and truncated on a whole-line boundary so the prompt
        never blows the context budget with a half-written signature.
        """
        lines: List[str] = []
        for category, specs in sorted(self.by_category().items()):
            lines.append(f"[{category}]")
            for spec in specs:
                gate = "" if spec.permission <= self.policy.auto_allow_max else \
                    f" <needs confirmation: {self.policy.level_for(spec.name, spec.permission).name}>"
                lines.append(f"- {spec.signature()} — {spec.description}{gate}")
            lines.append("")

        out: List[str] = []
        used = 0
        for line in lines:
            cost = len(line) + 1
            if used + cost > max_chars:
                out.append("- … (tool list truncated)")
                break
            out.append(line)
            used += cost
        return "\n".join(out).strip()

    def describe_tool(self, tool: SpecOrName) -> str:
        """Detailed description of one tool, for clarification replies."""
        spec = self.resolve(tool)
        if spec is None:
            return ""
        parts = [f"{spec.signature()} — {spec.description}"]
        for p in spec.parameters:
            flag = "required" if p.required else "optional"
            default = f", default={p.default!r}" if p.default is not None else ""
            desc = f" — {p.description}" if p.description else ""
            parts.append(f"    {p.name} ({p.type}, {flag}{default}){desc}")
        parts.append(
            f"    permission: {self.level_for(spec).name}, "
            f"confirmation: {self.needs_confirmation(spec)}"
        )
        return "\n".join(parts)

    def audit(self) -> List[str]:
        """
        Structural problems a unit test should fail on.

        Catches the two mistakes that are easy to make while adding tools:
        binding to a sub-agent that was never registered, and marking a
        confirmation-gated tool without giving it a question to ask.
        """
        problems: List[str] = []
        for spec in self._tools.values():
            if spec.handler is None:
                if not spec.agent or not spec.action:
                    problems.append(f"{spec.name}: no handler and no agent/action binding")
                elif self.agents and spec.agent not in self.agents:
                    problems.append(f"{spec.name}: bound to unknown agent '{spec.agent}'")
            if spec.permission >= PermissionLevel.SENSITIVE and not spec.confirm_template:
                problems.append(f"{spec.name}: {spec.permission.name} but no confirm_template")
            for alias, canonical in spec.aliases.items():
                if canonical not in spec.param_map:
                    problems.append(
                        f"{spec.name}: alias '{alias}' points at undeclared param '{canonical}'"
                    )
        return problems


__all__ = ["ToolRegistry", "ToolSpec", "ToolParam", "ToolCall", "ToolResult"]

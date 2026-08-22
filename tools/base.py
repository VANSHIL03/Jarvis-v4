"""
JARVIS v4 - Tool Contract Primitives

Every capability JARVIS exposes is described by a ToolSpec carrying its name,
description, parameter schema, permission level and confirmation requirement.
The LLM never executes anything directly: it names a tool, the registry
validates the arguments, the permission gate decides, and only then does the
bound sub-agent run.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Mapping, Optional, Tuple

from security.permissions import PermissionLevel


@dataclass(frozen=True)
class ToolParam:
    """One argument of a tool, with enough type info to coerce LLM output."""

    name: str
    type: str = "string"          # string | integer | number | boolean | array | object
    required: bool = False
    default: Any = None
    description: str = ""

    def coerce(self, value: Any) -> Any:
        """Best-effort conversion of a loosely-typed value into this param's type."""
        if value is None:
            return None
        try:
            if self.type == "integer":
                if isinstance(value, bool):
                    return int(value)
                if isinstance(value, str):
                    cleaned = value.strip().rstrip("%").strip()
                    return int(float(cleaned))
                return int(value)
            if self.type == "number":
                if isinstance(value, str):
                    return float(value.strip().rstrip("%").strip())
                return float(value)
            if self.type == "boolean":
                if isinstance(value, bool):
                    return value
                if isinstance(value, (int, float)):
                    return bool(value)
                return str(value).strip().lower() in (
                    "true", "yes", "on", "1", "enable", "enabled", "haan", "ha", "ji"
                )
            if self.type == "array":
                if isinstance(value, (list, tuple)):
                    return list(value)
                return [value]
            if self.type == "object":
                return value if isinstance(value, dict) else {"value": value}
            # string
            if isinstance(value, str):
                return value
            return str(value)
        except (TypeError, ValueError):
            # Keep the raw value; the tool itself reports a useful error.
            return value


@dataclass(frozen=True)
class ToolSpec:
    """
    Declarative description of a single tool.

    A tool executes either through `handler` (a callable) or by delegating to an
    existing sub-agent via `agent` + `action`. Delegation is preferred: the
    eleven sub-agents already implement the behaviour, and this layer adds the
    schema, the permission gate and a uniform result shape on top of them.
    """

    name: str
    description: str
    permission: PermissionLevel = PermissionLevel.SAFE
    parameters: Tuple[ToolParam, ...] = ()
    category: str = "general"

    # Execution binding (exactly one of these is expected)
    agent: Optional[str] = None
    action: Optional[str] = None
    handler: Optional[Callable[..., Any]] = None

    # None -> derive from the permission level via PermissionPolicy
    requires_confirmation: Optional[bool] = None

    # Incoming parameter name -> canonical name, e.g. {"folder_path": "path"}.
    aliases: Mapping[str, str] = field(default_factory=dict)

    # Spoken confirmation question. Supports {param} placeholders.
    confirm_template: str = ""

    # Extra dynamic gate: return True to demand confirmation for these arguments
    # even when the permission level alone would not. Used so an ambiguous
    # WhatsApp contact is always confirmed while a known one is not.
    confirm_when: Optional[Callable[[Dict[str, Any]], bool]] = None

    # Legacy {"agent": ..., "action": ...} pairs that should resolve to this tool.
    legacy_actions: Tuple[str, ...] = ()

    def __post_init__(self):
        if not self.name:
            raise ValueError("ToolSpec.name is required")
        if self.handler is None and not (self.agent and self.action):
            raise ValueError(
                f"Tool '{self.name}' has no executable binding: "
                "provide handler=, or both agent= and action=."
            )

    @property
    def param_map(self) -> Dict[str, ToolParam]:
        return {p.name: p for p in self.parameters}

    @property
    def required_params(self) -> List[str]:
        return [p.name for p in self.parameters if p.required]

    def signature(self) -> str:
        """Compact single-line signature used in the LLM tool catalogue."""
        parts = []
        for p in self.parameters:
            token = f"{p.name}:{p.type}"
            parts.append(token if p.required else f"{token}?")
        return f"{self.name}({', '.join(parts)})"

    def confirmation_question(self, params: Optional[Dict[str, Any]] = None) -> str:
        """Renders the Hinglish confirmation question for these arguments."""
        params = params or {}
        if self.confirm_template:
            try:
                return self.confirm_template.format(**{
                    k: ("" if v is None else v) for k, v in params.items()
                })
            except (KeyError, IndexError):
                return self.confirm_template
        detail = ", ".join(f"{k}={v}" for k, v in params.items() if v not in (None, ""))
        suffix = f" ({detail})" if detail else ""
        return f"Sir, '{self.name}'{suffix} execute karna hai? Haan ya na bataiye."


@dataclass
class ToolCall:
    """A request to run one tool. Produced by fast-paths and by the LLM alike."""

    tool: str
    params: Dict[str, Any] = field(default_factory=dict)

    def to_delegation(self) -> Dict[str, Any]:
        """Legacy {"agent","action","params"} view, for logs and the mobile UI."""
        return {"tool": self.tool, "action": self.tool, "params": dict(self.params)}


@dataclass
class ToolResult:
    """
    Uniform outcome of every tool execution.

    `ok` is the single source of truth for success. Sub-agents historically
    returned {"status": "error"} while the planner checked res["success"], so
    failures were reported to the user as successes; normalising here removes
    that whole failure mode.
    """

    ok: bool
    tool: str = ""
    data: Dict[str, Any] = field(default_factory=dict)
    message: str = ""
    permission: PermissionLevel = PermissionLevel.SAFE
    blocked: bool = False           # refused by the permission gate, not attempted
    awaiting_confirmation: bool = False

    @property
    def speech_reply(self) -> str:
        """Spoken line supplied by the sub-agent, if any."""
        if isinstance(self.data, dict):
            return self.data.get("speech_reply", "") or ""
        return ""

    @classmethod
    def from_agent_payload(
        cls,
        tool: str,
        payload: Any,
        permission: PermissionLevel = PermissionLevel.SAFE,
    ) -> "ToolResult":
        """
        Interprets whatever a sub-agent returned.

        Recognises both conventions already in the codebase: {"status": "success"
        | "error"} and {"success": True | False}.
        """
        if isinstance(payload, dict):
            ok = True
            status = str(payload.get("status", "")).lower()
            if status in ("error", "failed", "failure", "not_found", "security_rejected"):
                ok = False
            elif status in ("ambiguous", "needs_clarification"):
                ok = False
            if payload.get("success") is False:
                ok = False
            elif payload.get("success") is True and not status:
                ok = True
            return cls(
                ok=ok,
                tool=tool,
                data=payload,
                message=str(payload.get("message", "") or ""),
                permission=permission,
            )
        if isinstance(payload, bool):
            return cls(ok=payload, tool=tool, data={"result": payload}, permission=permission)
        return cls(ok=True, tool=tool, data={"result": payload}, permission=permission)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tool": self.tool,
            "ok": self.ok,
            "status": "success" if self.ok else ("blocked" if self.blocked else "error"),
            "message": self.message,
            "permission": self.permission.name,
            "blocked": self.blocked,
            "awaiting_confirmation": self.awaiting_confirmation,
            "result": self.data,
        }

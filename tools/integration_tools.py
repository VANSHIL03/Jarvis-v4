"""
JARVIS v4 - Integration Tools (email, git, gaming, n8n)

The eight themed modules cover the eight sub-agents the specification names. This
ninth module exists for the remaining four -- email_agent, git_agent,
gaming_agent and n8n_agent -- because once the registry is the only execution
path, a capability nobody registers is a capability JARVIS silently loses. These
already work today, so they are declared rather than dropped.

Two security decisions are worth reading before editing anything here:

  * Section 14 forbids exposing passwords or tokens to the LLM. EmailAgent's
    send_email expects `sender_email` and `sender_password` in its params, so this
    module does NOT bind it directly: the schema advertises only recipient,
    subject and body, and a handler injects the credentials from the environment
    on the way to the agent. The password therefore never appears in a tool
    schema, in an LLM completion, or in the registry's params log line (Section
    27). push_to_github is the same story -- the GitHub token lives in settings
    and never becomes a parameter.
  * n8n workflows can publish to LinkedIn, Instagram, YouTube and Reddit or fire
    off a WhatsApp message. Reading a mailbox through the same tool is harmless.
    Rather than gate everything (friction on "any new emails?") or nothing (a
    public post with no confirmation), run_workflow inspects the intent and asks
    only when the workflow would push something outward.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from security.permissions import PermissionLevel as P
from tools.base import ToolParam, ToolSpec
from utils.logger import logger

CATEGORY_MAIL = "email"
CATEGORY_DEV = "developer"
CATEGORY_GAMING = "gaming"
CATEGORY_WORKFLOW = "workflows"

#: Verbs that mean "this leaves the machine and other people will see it".
_PUBLISHING_MARKERS = (
    "post", "publish", "upload", "tweet", "share", "send", "message",
    "comment", "reply", "story", "reel", "commit", "push",
)


def _email_credentials() -> Tuple[str, str]:
    """
    Reads the mailbox credentials from the environment.

    Deliberately a plain function that returns them to the caller and nowhere
    else: they are never logged, never put into tool parameters, and never shown
    to the model.
    """
    import os

    from config.settings import settings

    address = (os.getenv("EMAIL_ADDRESS", "") or getattr(settings, "EMAIL_ADDRESS", "") or "").strip()
    password = os.getenv("EMAIL_PASSWORD", "") or getattr(settings, "EMAIL_PASSWORD", "") or ""
    return address, password


def _is_publishing(intent: str) -> bool:
    text = str(intent or "").lower()
    return any(marker in text for marker in _PUBLISHING_MARKERS)


def build_integration_tools(agents: Optional[Dict[str, Any]] = None) -> List[ToolSpec]:
    """Builds the email / git / gaming / n8n specs against main.py's agent dict."""
    agents = agents if agents is not None else {}

    async def _send_email(recipient: str = "", subject: str = "", body: str = "") -> Dict[str, Any]:
        """Sends mail with credentials injected here, never carried in the schema."""
        recipient = str(recipient or "").strip()
        if not recipient:
            return {
                "status": "error",
                "message": "No recipient given.",
                "speech_reply": "Sir, email kisko bhejna hai wo bataiye.",
            }

        address, password = _email_credentials()
        if not address or not password:
            # Say what is missing without echoing anything secret.
            return {
                "status": "error",
                "message": "Email credentials are not configured.",
                "speech_reply": (
                    "Sir, email bhejne ke liye .env file me EMAIL_ADDRESS aur "
                    "EMAIL_PASSWORD set karna padega."
                ),
            }

        agent = agents.get("email_agent")
        if agent is None:
            return {
                "status": "error",
                "message": "Email agent is not available.",
                "speech_reply": "Sir, email agent available nahi hai.",
            }

        res = await agent.execute_task(
            "send_email",
            {
                "sender_email": address,
                "sender_password": password,
                "recipient": recipient,
                "subject": subject,
                "body": body,
            },
        )
        res = res if isinstance(res, dict) else {"status": "error", "message": str(res)}
        res.pop("sender_password", None)  # nothing downstream should echo it back
        if res.get("status") == "success":
            res.setdefault("speech_reply", f"Ji Sir, {recipient} ko email bhej diya hai.")
        else:
            res.setdefault(
                "speech_reply",
                f"Sir, {recipient} ko email nahi ja paya. {res.get('message', '')}".strip(),
            )
        return res

    def _workflow_publishes(params: Dict[str, Any]) -> bool:
        """Confirm an n8n workflow only when it would put something out in public."""
        intent = params.get("user_intent") or ""
        publishing = _is_publishing(intent)
        if publishing:
            logger.info("n8n workflow looks outward-facing; asking before running it.")
        return publishing

    return [
        # ------------------------------------------------------------- email
        ToolSpec(
            name="send_email",
            description=(
                "Send an email. Uses the mailbox configured in .env -- never ask "
                "the user for a password and never pass one to this tool."
            ),
            permission=P.SENSITIVE,
            category=CATEGORY_MAIL,
            handler=_send_email,
            agent="email_agent",
            action="send_email",
            parameters=(
                ToolParam("recipient", "string", required=True, description="Recipient email address."),
                ToolParam("subject", "string", default="", description="Subject line."),
                ToolParam("body", "string", default="", description="Message body."),
            ),
            aliases={
                "to": "recipient", "recipient_email": "recipient", "email": "recipient", "address": "recipient",
                "title": "subject", "text": "body", "message": "body", "content": "body",
            },
            confirm_template="Sir, {recipient} ko '{subject}' subject ke saath email bhej doon? Haan ya na bataiye.",
            legacy_actions=("email", "compose_email", "mail"),
        ),
        ToolSpec(
            name="check_email",
            description="Read the unread emails in the configured inbox.",
            permission=P.LOW_RISK,
            category=CATEGORY_MAIL,
            agent="email_agent",
            action="fetch_unread",
            confirm_template="Sir, aapka inbox check kar loon? Haan ya na bataiye.",
            legacy_actions=("fetch_unread", "read_email", "unread_email", "check_inbox"),
        ),

        # --------------------------------------------------------------- git
        ToolSpec(
            name="push_to_github",
            description=(
                "Initialise, commit and push a project folder to GitHub using the "
                "configured token. Publishes code, so it always asks first."
            ),
            permission=P.SENSITIVE,
            category=CATEGORY_DEV,
            agent="git_agent",
            action="push_to_github",
            parameters=(
                ToolParam("folder_path", "string", default=".", description="Project folder to push."),
                ToolParam("repo_name", "string", default=None, description="Repository name (default: folder name)."),
                ToolParam("repo_url", "string", default=None, description="Existing remote URL, if any."),
                ToolParam("commit_message", "string", default="Pushed by J.A.R.V.I.S. v4", description="Commit message."),
                ToolParam("private", "boolean", default=False, description="Create the repo as private."),
            ),
            aliases={
                "path": "folder_path", "folder": "folder_path", "project": "folder_path",
                "dir": "folder_path", "directory": "folder_path",
                "repo": "repo_name", "name": "repo_name", "repository": "repo_name",
                "url": "repo_url", "remote": "repo_url",
                "message": "commit_message", "commit": "commit_message",
            },
            confirm_template=(
                "Sir, '{folder_path}' ko GitHub par push kar doon? Ye code online "
                "chala jayega. Haan ya na bataiye."
            ),
            legacy_actions=("push_folder", "push_repo", "push", "github_push"),
        ),

        # ------------------------------------------------------------ gaming
        ToolSpec(
            name="open_steam",
            description="Open the Steam client.",
            permission=P.SAFE,
            category=CATEGORY_GAMING,
            agent="gaming_agent",
            action="open_steam",
            legacy_actions=("launch_steam", "steam"),
        ),
        ToolSpec(
            name="launch_steam_game",
            description="Launch a Steam game by its numeric AppID.",
            permission=P.SAFE,
            category=CATEGORY_GAMING,
            agent="gaming_agent",
            action="launch_game",
            parameters=(
                ToolParam("app_id", "string", required=True, description="Steam AppID, e.g. '730'."),
            ),
            aliases={"appid": "app_id", "id": "app_id", "steam_id": "app_id", "game_id": "app_id"},
            legacy_actions=("steam_game", "run_steam_game"),
        ),
        ToolSpec(
            name="open_unity_hub",
            description="Open Unity Hub.",
            permission=P.SAFE,
            category=CATEGORY_GAMING,
            agent="gaming_agent",
            action="open_hub",
            legacy_actions=("unity_hub", "open_unity", "launch_unity"),
        ),
        ToolSpec(
            name="create_csharp_script",
            description="Write a Unity C# MonoBehaviour script template.",
            permission=P.LOW_RISK,
            category=CATEGORY_GAMING,
            agent="gaming_agent",
            action="create_csharp_script",
            parameters=(
                ToolParam("name", "string", default="NewScript", description="Class name."),
                ToolParam("path", "string", default="NewScript.cs", description="Output .cs path."),
            ),
            aliases={
                "script_name": "name", "class_name": "name",
                "file_path": "path", "save_to": "path", "folder_path": "path",
            },
            confirm_template="Sir, '{name}' naam ka Unity C# script bana doon? Haan ya na bataiye.",
            legacy_actions=("unity_script", "create_unity_script", "new_csharp_script"),
        ),

        # ---------------------------------------------------------- n8n / SaaS
        ToolSpec(
            name="run_workflow",
            description=(
                "Run a matching n8n workflow (Gmail, Drive, Sheets, Discord, "
                "Telegram, LinkedIn, backups...). Anything that posts or sends "
                "outward is confirmed first."
            ),
            permission=P.LOW_RISK,
            category=CATEGORY_WORKFLOW,
            agent="n8n_agent",
            action="execute_workflow",
            parameters=(
                ToolParam("user_intent", "string", required=True, description="What the workflow should accomplish."),
                ToolParam("payload", "object", default=None, description="Extra data for the workflow."),
            ),
            aliases={
                "intent": "user_intent", "task": "user_intent", "query": "user_intent",
                "text": "user_intent", "description": "user_intent",
                "data": "payload", "body": "payload",
            },
            confirm_template="Sir, ye workflow chalaun: '{user_intent}'? Haan ya na bataiye.",
            confirm_when=_workflow_publishes,
            legacy_actions=("run_n8n", "workflow", "n8n", "execute_n8n_workflow"),
        ),
        ToolSpec(
            name="list_workflows",
            description="List the n8n workflows available on this machine.",
            permission=P.SAFE,
            category=CATEGORY_WORKFLOW,
            agent="n8n_agent",
            action="discover_workflows",
            legacy_actions=("discover_workflows", "show_workflows", "get_workflows"),
        ),
        ToolSpec(
            name="create_workflow",
            description="Generate a new n8n workflow from a description.",
            permission=P.LOW_RISK,
            category=CATEGORY_WORKFLOW,
            agent="n8n_agent",
            action="create_workflow",
            parameters=(
                ToolParam("description", "string", required=True, description="What the workflow should do."),
            ),
            aliases={"prompt": "description", "text": "description", "task": "description", "user_intent": "description"},
            confirm_template="Sir, naya n8n workflow bana doon: '{description}'? Haan ya na bataiye.",
            legacy_actions=("new_workflow", "make_workflow", "auto_create_workflow"),
        ),
    ]


__all__ = ["build_integration_tools"]

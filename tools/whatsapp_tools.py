"""
JARVIS v4 - WhatsApp Tools

Section 13 is the whole reason this module has a factory instead of a flat list
of specs: "never send a message to the wrong person because of an uncertain
contact match." Getting that right needs the contacts database at spec-build
time, so `build_whatsapp_tools(agents, db)` closes over both.

The asymmetry between messaging and calling is deliberate:

  * send_message types the name into WhatsApp's search box and presses Enter.
    Nothing verifies which chat opened, so an uncertain name is exactly the
    wrong-recipient risk Section 13 names. Every recipient that is not a single
    exact contact is therefore confirmed first, with the recipient AND the
    message read back, and a name matching several contacts is refused outright
    with "which one?" -- JARVIS never picks between two Rahuls.
  * voice_call / video_call go through WhatsAppCallController, which resolves the
    contact against the real WhatsApp UI (exact beats prefix beats fuzzy),
    verifies the opened chat header, and returns `ambiguous` without dialling
    when a name matches more than one person. That guarantee is stronger than a
    yes/no prompt, so calls to a known contact are not gated -- Section 16 says
    not to ask when asking adds nothing.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from security.permissions import PermissionLevel as P
from tools.base import ToolParam, ToolSpec
from utils.logger import logger

CATEGORY = "whatsapp"

_CONTACT = ToolParam(
    "contact", "string", required=True,
    description="Contact name as saved in WhatsApp.",
)
_CONTACT_ALIASES = {
    "contact_name": "contact",
    "name": "contact",
    "to": "contact",
    "recipient": "contact",
    "person": "contact",
    "who": "contact",
}


def _known_names(db: Any, contact: str) -> List[str]:
    """Contact names from the local database that could be this person."""
    if db is None or not contact:
        return []
    try:
        rows = db.find_contacts(contact)
    except Exception as e:
        logger.warning(f"Contact lookup for '{contact}' failed: {e}")
        return []
    names: List[str] = []
    for row in rows or []:
        name = str((row or {}).get("contact_name", "") or "").strip()
        if name and name not in names:
            names.append(name)
    return names


def _is_exact(db: Any, contact: str) -> bool:
    if db is None or not contact:
        return False
    try:
        return bool(db.has_exact_contact(contact))
    except Exception as e:
        logger.warning(f"Exact contact check for '{contact}' failed: {e}")
        return False


def build_whatsapp_tools(
    agents: Optional[Dict[str, Any]] = None,
    db: Any = None,
) -> List[ToolSpec]:
    """
    Builds the WhatsApp tool specs.

    `agents` is main.py's live sub-agent dict (read at call time, so it may still
    be filling up when this runs) and `db` is the DatabaseManager holding the
    contacts table. With no database every recipient counts as uncertain, which
    fails safe: JARVIS asks before sending rather than guessing.
    """
    agents = agents if agents is not None else {}

    # ------------------------------------------------------ recipient safety
    def _recipient_uncertain(params: Dict[str, Any]) -> bool:
        """
        Section 13 gate: does this recipient need explicit approval first?

        False for a single exact contact (policy allows an exact match to
        proceed) and -- counter-intuitively -- also False when the name matches
        several contacts, because the handler below refuses that case and asks
        *which* contact. "Which Rahul?" is a better question than "send it,
        yes or no?", and nothing is sent either way.
        """
        contact = str(params.get("contact") or "").strip()
        if not contact:
            return False  # the missing-parameter error fires before this matters
        if len(_known_names(db, contact)) > 1:
            return False
        return not _is_exact(db, contact)

    async def _send_message(contact: str = "", message: str = "") -> Dict[str, Any]:
        """Resolves the recipient, then delegates the typing to WhatsAppAgent."""
        contact = str(contact or "").strip()
        message = str(message or "")

        if not contact:
            return {
                "status": "error",
                "message": "No recipient given.",
                "speech_reply": "Sir, message kisko bhejna hai wo bataiye.",
            }
        if not message.strip():
            return {
                "status": "error",
                "contact": contact,
                "message": "No message text given.",
                "speech_reply": f"Sir, {contact} ko kya likhna hai wo bataiye.",
            }

        matches = _known_names(db, contact)
        if len(matches) > 1:
            exact = [n for n in matches if n.lower() == contact.lower()]
            if len(exact) == 1:
                contact = exact[0]
            else:
                shortlist = matches[:4]
                spoken = " aur ".join(
                    [", ".join(shortlist[:-1]), shortlist[-1]]
                ) if len(shortlist) > 1 else shortlist[0]
                # Never guess between contacts (Section 13). Nothing is typed.
                return {
                    "status": "ambiguous",
                    "contact": contact,
                    "candidates": matches,
                    "message": f"'{contact}' matches {len(matches)} contacts; nothing was sent.",
                    "speech_reply": (
                        f"Sir, mujhe {spoken} mile hain. Kaun se '{contact}' ko "
                        "message bhejna hai?"
                    ),
                }
        elif len(matches) == 1:
            contact = matches[0]  # use the saved spelling, not the spoken one

        agent = agents.get("whatsapp_agent")
        if agent is None:
            return {
                "status": "error",
                "message": "WhatsApp agent is not available.",
                "speech_reply": "Sir, WhatsApp automation available nahi hai.",
            }

        res = await agent.execute_task(
            "send_message", {"contact_name": contact, "message": message}
        )
        res = res if isinstance(res, dict) else {"status": "error", "message": str(res)}
        res.setdefault("contact", contact)
        if res.get("status") == "success":
            res.setdefault(
                "speech_reply", f"Ji Sir, {contact} ko message bhej diya hai."
            )
        else:
            res.setdefault(
                "speech_reply",
                f"Sir, {contact} ko message nahi ja paya. {res.get('message', '')}".strip(),
            )
        return res

    return [
        ToolSpec(
            name="open_whatsapp",
            description="Open the WhatsApp Desktop app.",
            permission=P.SAFE,
            category=CATEGORY,
            agent="whatsapp_agent",
            action="open_whatsapp",
            legacy_actions=("whatsapp", "launch_whatsapp", "start_whatsapp"),
        ),
        ToolSpec(
            name="send_message",
            description=(
                "Send a WhatsApp message. Confirms the recipient and text first "
                "unless the contact is an exact match, and refuses to choose "
                "between contacts with similar names."
            ),
            permission=P.LOW_RISK,
            category=CATEGORY,
            # Execution goes through the handler above -- ToolRegistry._dispatch
            # prefers `handler` over the agent binding. The agent/action pair is
            # declared anyway so a legacy {"agent": "whatsapp_agent", "action":
            # "send_message"} delegation resolves to *this* guarded tool instead
            # of reaching the plugin with an unverified recipient.
            handler=_send_message,
            agent="whatsapp_agent",
            action="send_message",
            parameters=(
                _CONTACT,
                ToolParam("message", "string", required=True, description="Message text to send."),
            ),
            aliases={**_CONTACT_ALIASES, "text": "message", "body": "message", "msg": "message", "content": "message"},
            confirm_template="Sir, {contact} ko ye message bhejun: '{message}'? Haan ya na bataiye.",
            confirm_when=_recipient_uncertain,
            legacy_actions=("send_whatsapp", "whatsapp_message", "message", "send_text"),
        ),
        ToolSpec(
            name="send_file",
            description="Send a file or document to a WhatsApp contact.",
            permission=P.SENSITIVE,
            category=CATEGORY,
            agent="whatsapp_agent",
            action="send_file",
            parameters=(
                _CONTACT,
                ToolParam("file_path", "string", required=True, description="File to attach."),
            ),
            aliases={**_CONTACT_ALIASES, "path": "file_path", "file": "file_path", "document": "file_path", "attachment": "file_path"},
            confirm_template="Sir, {contact} ko '{file_path}' bhej doon? Haan ya na bataiye.",
            legacy_actions=("send_document", "send_attachment", "whatsapp_file", "share_file"),
        ),
        ToolSpec(
            name="voice_call",
            description="Place a WhatsApp voice call. Refuses to dial when the name matches several contacts.",
            permission=P.LOW_RISK,
            category=CATEGORY,
            agent="whatsapp_agent",
            action="voice_call",
            parameters=(_CONTACT,),
            aliases=_CONTACT_ALIASES,
            confirm_template="Sir, {contact} ko voice call laga doon? Haan ya na bataiye.",
            legacy_actions=("call", "audio_call", "whatsapp_call", "phone_call"),
        ),
        ToolSpec(
            name="video_call",
            description="Place a WhatsApp video call. Refuses to dial when the name matches several contacts.",
            permission=P.LOW_RISK,
            category=CATEGORY,
            agent="whatsapp_agent",
            action="video_call",
            parameters=(_CONTACT,),
            aliases=_CONTACT_ALIASES,
            confirm_template="Sir, {contact} ko video call laga doon? Haan ya na bataiye.",
            legacy_actions=("videocall", "whatsapp_video_call", "facetime"),
        ),
        ToolSpec(
            name="end_call",
            description="Hang up the WhatsApp call that is in progress.",
            permission=P.LOW_RISK,
            category=CATEGORY,
            agent="whatsapp_agent",
            action="end_call",
            legacy_actions=("hang_up", "cut_call", "disconnect_call", "hangup"),
        ),
        ToolSpec(
            name="find_contact",
            description="Check which WhatsApp contact a name resolves to, without calling or messaging.",
            permission=P.SAFE,
            category=CATEGORY,
            agent="whatsapp_agent",
            action="find_contact",
            parameters=(_CONTACT,),
            aliases=_CONTACT_ALIASES,
            legacy_actions=("resolve_contact", "check_contact", "lookup_contact"),
        ),
        ToolSpec(
            name="read_unread",
            description="Open the WhatsApp unread-messages filter.",
            permission=P.SAFE,
            category=CATEGORY,
            agent="whatsapp_agent",
            action="read_unread",
            legacy_actions=("unread_messages", "check_whatsapp", "read_messages"),
        ),
    ]


__all__ = ["build_whatsapp_tools"]

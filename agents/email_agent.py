"""
JARVIS v4 - Email Transport Agent
"""

from typing import Dict, Any
from agents.base_agent import BaseAgent
from automation.email_client import EmailClient

class EmailAgent(BaseAgent):
    def __init__(self, email_client: EmailClient):
        self.email_client = email_client

    @property
    def agent_name(self) -> str:
        return "email_agent"

    @property
    def description(self) -> str:
        return "Handles reading unread emails, composing messages, searching, replying, and sending emails."

    async def execute_task(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        action = action.lower()
        if action == "send_email":
            sender = params.get("sender_email", "")
            pwd = params.get("sender_password", "")
            recipient = params.get("recipient", "")
            subj = params.get("subject", "")
            body = params.get("body", "")
            success = self.email_client.send_email(sender, pwd, recipient, subj, body)
            return {"status": "success" if success else "error", "recipient": recipient}

        elif action == "fetch_unread":
            user = params.get("email", "")
            pwd = params.get("password", "")
            emails = self.email_client.fetch_unread_emails(user, pwd)
            return {"status": "success", "unread_emails": emails}

        return {"status": "error", "message": f"Unknown email action: '{action}'"}

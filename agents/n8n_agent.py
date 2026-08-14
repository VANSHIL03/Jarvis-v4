"""
JARVIS v4 - n8n Workflow Automation Agent
Specialized Antigravity Agent for executing SaaS workflows (WhatsApp, Email, Drive, GitHub, Discord, Telegram, Sheets, Notion, Slack, Backup, etc.) via local n8n.
"""

from typing import Dict, Any, Optional
from agents.base_agent import BaseAgent
from ai.llm_client import LocalLLMClient
from automation.n8n_client import N8nClient
from automation.n8n_workflow_manager import N8nWorkflowManager
from utils.logger import logger


class N8nAgent(BaseAgent):
    """Antigravity agent responsible for n8n workflow execution, discovery, and dynamic creation."""

    def __init__(self, llm_client: LocalLLMClient, workflow_manager: Optional[N8nWorkflowManager] = None):
        self.llm = llm_client
        self.manager = workflow_manager or N8nWorkflowManager()

    @property
    def agent_name(self) -> str:
        return "n8n_agent"

    @property
    def description(self) -> str:
        return "Executes SaaS & cloud workflow automations (WhatsApp, Email, Drive, GitHub, Backup, Discord, Telegram, Sheets, Slack, Notion, etc.) using local n8n."

    async def execute_task(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        action = action.lower().strip()
        logger.info(f"N8nAgent executing action '{action}' with params: {params}")

        if action == "discover_workflows":
            workflows = await self.manager.discover_workflows(force_refresh=True)
            return {
                "status": "success",
                "count": len(workflows),
                "workflows": [wf.model_dump() for wf in workflows]
            }

        elif action in (
            "execute_workflow", "send_whatsapp", "send_email", "read_gmail", "check_emails", "upload_google_drive",
            "github_push", "backup_folder", "send_discord_alert", "send_telegram",
            "update_google_sheets", "manage_calendar", "post_slack", "notion_add",
            "dropbox_upload", "onedrive_upload"
        ):
            intent = params.get("user_intent", f"Execute {action}")
            payload = params.get("payload", params)

            res = await self.manager.execute_matched_task(intent, payload)
            if res.success:
                return {
                    "status": "success",
                    "workflow_name": res.workflow_name,
                    "execution_id": res.execution_id,
                    "data": res.data
                }
            else:
                return {
                    "status": "error",
                    "message": res.error_message or "n8n workflow execution failed.",
                    "workflow_name": res.workflow_name
                }

        elif action == "create_workflow":
            desc = params.get("description", "Auto generated task")
            wf = await self.manager.auto_create_workflow(desc)
            if wf:
                return {"status": "success", "workflow_id": wf.id, "name": wf.name}
            return {"status": "error", "message": "Failed to create n8n workflow."}

        return {"status": "error", "message": f"Unknown n8n action: '{action}'"}

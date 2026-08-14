"""
JARVIS v4 - n8n Workflow Discovery, Auto-Matching, Auto-Creation & Memory Manager
Indexes local n8n workflows, matches user intent to appropriate workflows, auto-generates missing workflows,
and tracks execution statistics and memory.
"""

import time
import json
import asyncio
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path

from automation.n8n_client import N8nClient, N8nWorkflow, N8nExecutionResult
from memory.memory_manager import MemoryManager
from utils.logger import logger


class N8nWorkflowManager:
    """Manages workflow discovery, semantic intent matching, auto-generation, and execution memory."""

    def __init__(
        self,
        n8n_client: Optional[N8nClient] = None,
        memory_manager: Optional[MemoryManager] = None
    ):
        self.client = n8n_client or N8nClient()
        self.memory = memory_manager
        self.cached_workflows: Dict[str, N8nWorkflow] = {}
        self.workflow_index: Dict[str, Dict[str, Any]] = {}
        self.last_discovery_time: float = 0.0
        self.cache_ttl_seconds: float = 300.0  # 5 minutes

        # Default built-in workflow definitions map (for zero-config local triggers)
        self.builtin_service_map: Dict[str, Dict[str, Any]] = {
            "whatsapp": {"tags": ["whatsapp", "messaging", "chat"], "webhook": "whatsapp-send", "service": "WhatsApp"},
            "email": {"tags": ["email", "gmail", "mail", "send email"], "webhook": "email-send", "service": "Email"},
            "read_gmail": {"tags": ["read email", "check email", "inbox", "gmail padho", "unread email", "latest emails", "read gmail", "my email", "my gmail"], "webhook": "gmail-read", "service": "Gmail Reader"},
            "google_drive": {"tags": ["drive", "google drive", "gdrive", "upload"], "webhook": "gdrive-upload", "service": "Google Drive"},
            "github_push": {"tags": ["github", "git push", "repo"], "webhook": "github-push", "service": "GitHub"},
            "backup_folder": {"tags": ["backup", "zip", "archive", "folder backup"], "webhook": "backup-folder", "service": "Backup"},
            "discord": {"tags": ["discord", "discord alert", "notification"], "webhook": "discord-notify", "service": "Discord"},
            "telegram": {"tags": ["telegram", "telegram message", "bot"], "webhook": "telegram-send", "service": "Telegram"},
            "google_sheets": {"tags": ["sheets", "excel", "google sheets", "spreadsheet"], "webhook": "sheets-append", "service": "Google Sheets"},
            "calendar": {"tags": ["calendar", "google calendar", "schedule", "event"], "webhook": "calendar-create", "service": "Calendar"},
            "slack": {"tags": ["slack", "slack message", "channel"], "webhook": "slack-post", "service": "Slack"},
            "notion": {"tags": ["notion", "notes", "database"], "webhook": "notion-add", "service": "Notion"},
            "dropbox": {"tags": ["dropbox", "cloud storage"], "webhook": "dropbox-upload", "service": "Dropbox"},
            "onedrive": {"tags": ["onedrive", "microsoft drive"], "webhook": "onedrive-upload", "service": "OneDrive"},
            "grok_ai": {"tags": ["grok", "grok ai", "xai", "ask grok", "grok query", "grok search"], "webhook": "grok-ai-query", "service": "Grok AI (xAI)"},
        }

    async def discover_workflows(self, force_refresh: bool = False) -> List[N8nWorkflow]:
        """Discovers all available workflows from local n8n instance and indexes metadata."""
        now = time.time()
        if not force_refresh and self.cached_workflows and (now - self.last_discovery_time) < self.cache_ttl_seconds:
            return list(self.cached_workflows.values())

        workflows = await self.client.list_workflows()
        self.cached_workflows.clear()
        self.workflow_index.clear()

        for wf in workflows:
            self.cached_workflows[wf.id] = wf
            tag_names = [t.get("name", "").lower() for t in wf.tags if isinstance(t, dict)]

            self.workflow_index[wf.id] = {
                "id": wf.id,
                "name": wf.name,
                "description": wf.description or wf.name,
                "active": wf.active,
                "tags": tag_names,
                "nodes": [n.get("name") for n in wf.nodes if isinstance(n, dict)],
                "trigger_type": "webhook" if any("webhook" in str(n.get("type", "")).lower() for n in wf.nodes) else "manual"
            }

        self.last_discovery_time = now
        logger.info(f"Discovered and indexed {len(self.cached_workflows)} n8n workflows.")
        return workflows

    async def match_workflow(self, user_intent: str) -> Optional[Tuple[str, str, Dict[str, Any]]]:
        """
        Matches user intent string against discovered n8n workflows and built-in automation maps.
        Returns Tuple of (workflow_id_or_webhook, service_name, default_params).
        """
        await self.discover_workflows()
        clean = user_intent.lower().strip()

        # 1. Match against discovered active n8n workflows by name or tags
        for wf_id, meta in self.workflow_index.items():
            wf_name = meta["name"].lower()
            if wf_name in clean or any(t in clean for t in meta["tags"]):
                logger.info(f"Matched user intent '{user_intent}' to n8n workflow '{meta['name']}' ({wf_id})")
                return (wf_id, meta["name"], {})

        # 2. Match against built-in SaaS service mappings
        for key, s_info in self.builtin_service_map.items():
            if any(t in clean for t in s_info["tags"]):
                logger.info(f"Matched user intent '{user_intent}' to built-in n8n trigger '{s_info['webhook']}' ({s_info['service']})")
                return (s_info["webhook"], s_info["service"], {"service_key": key})

        return None

    async def execute_matched_task(self, user_intent: str, payload: Dict[str, Any]) -> N8nExecutionResult:
        """Executes matched workflow or auto-generates a new n8n workflow if none exists."""
        start_time = time.time()
        match = await self.match_workflow(user_intent)

        if match:
            wf_target, service_name, _ = match
            logger.info(f"Executing n8n automation for service '{service_name}' via target '{wf_target}'")

            # Check if target is UUID workflow_id or webhook string
            if len(wf_target) == 36 and "-" in wf_target:
                res = await self.client.execute_workflow(wf_target, payload)
            else:
                res = await self.client.trigger_webhook(wf_target, payload)
        else:
            # Auto-Creation Flow: Generate workflow dynamically
            logger.info(f"No existing n8n workflow matched for '{user_intent}'. Auto-generating n8n workflow...")
            gen_wf = await self.auto_create_workflow(user_intent)
            if gen_wf:
                res = await self.client.execute_workflow(gen_wf.id, payload)
                service_name = gen_wf.name
            else:
                # Fallback to dynamic webhook trigger
                slug = user_intent.lower().replace(" ", "-")[:30]
                res = await self.client.trigger_webhook(f"auto-{slug}", payload)
                service_name = "Auto Webhook"

        elapsed = round(time.time() - start_time, 2)
        res.workflow_name = res.workflow_name or service_name

        # Memory Logging
        self._record_execution_memory(
            intent=user_intent,
            service=service_name,
            success=res.success,
            latency=elapsed,
            error=res.error_message
        )

        return res

    async def auto_create_workflow(self, task_description: str) -> Optional[N8nWorkflow]:
        """Generates valid n8n JSON workflow schema for a given task description and creates it on n8n server."""
        try:
            workflow_name = f"JARVIS_Auto_{task_description.title().replace(' ', '')[:24]}"
            webhook_path = f"jarvis-auto-{int(time.time())}"

            # Basic n8n Webhook -> Code -> Output Workflow JSON Template
            workflow_definition = {
                "name": workflow_name,
                "nodes": [
                    {
                        "parameters": {
                            "httpMethod": "POST",
                            "path": webhook_path,
                            "options": {}
                        },
                        "id": "node-webhook-1",
                        "name": "Webhook",
                        "type": "n8n-nodes-base.webhook",
                        "typeVersion": 1,
                        "position": [250, 300]
                    },
                    {
                        "parameters": {
                            "mode": "runOnceForEachItem",
                            "jsCode": f"// JARVIS Auto-Generated Workflow Code for {task_description}\nreturn $input.item;"
                        },
                        "id": "node-code-2",
                        "name": "Execute Action",
                        "type": "n8n-nodes-base.code",
                        "typeVersion": 1,
                        "position": [450, 300]
                    }
                ],
                "connections": {
                    "Webhook": {
                        "main": [
                            [
                                {
                                    "node": "Execute Action",
                                    "type": "main",
                                    "index": 0
                                }
                            ]
                        ]
                    }
                },
                "active": True,
                "settings": {"executionOrder": "v1"}
            }

            new_wf = await self.client.create_workflow(workflow_definition)
            if new_wf:
                await self.client.activate_workflow(new_wf.id)
                await self.discover_workflows(force_refresh=True)
                return new_wf
        except Exception as e:
            logger.error(f"Failed to auto-create n8n workflow for '{task_description}': {e}")
        return None

    def _record_execution_memory(
        self,
        intent: str,
        service: str,
        success: bool,
        latency: float,
        error: Optional[str] = None
    ):
        """Records workflow execution telemetry and preferences into SQLite MemoryManager."""
        if not self.memory:
            return
        try:
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            fact_key = f"n8n_exec_{int(time.time())}"
            fact_value = f"Task: '{intent}' | Service: {service} | Status: {'SUCCESS' if success else 'FAILED'} | Time: {latency}s"
            if error:
                fact_value += f" | Error: {error}"

            self.memory.store_user_fact(fact_key, fact_value, category="n8n_history")
            logger.info(f"Logged n8n execution memory: {fact_value}")
        except Exception as e:
            logger.warning(f"Could not record n8n execution memory: {e}")

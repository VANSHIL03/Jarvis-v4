"""
JARVIS v4 - Async n8n REST API & Webhook Client
Connects Antigravity AI framework to a locally hosted n8n instance (http://localhost:5678).
Provides workflow discovery, execution, creation, status tracking, and error recovery.
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
import httpx

from config.settings import settings
from utils.logger import logger


# ─── Pydantic Schemas for n8n API ───

class N8nWorkflow(BaseModel):
    id: str
    name: str
    active: bool = False
    createdAt: Optional[str] = None
    updatedAt: Optional[str] = None
    tags: List[Dict[str, Any]] = Field(default_factory=list)
    nodes: List[Dict[str, Any]] = Field(default_factory=list)
    connections: Dict[str, Any] = Field(default_factory=dict)
    description: Optional[str] = None


class N8nExecution(BaseModel):
    id: str
    finished: bool = False
    mode: str = "trigger"
    retryOf: Optional[str] = None
    retrySuccessId: Optional[str] = None
    status: str = "unknown"  # success, error, running, waiting
    startedAt: Optional[str] = None
    stoppedAt: Optional[str] = None
    workflowId: Optional[str] = None
    data: Dict[str, Any] = Field(default_factory=dict)


class N8nExecutionResult(BaseModel):
    success: bool
    execution_id: Optional[str] = None
    workflow_id: Optional[str] = None
    workflow_name: Optional[str] = None
    data: Dict[str, Any] = Field(default_factory=dict)
    error_message: Optional[str] = None
    logs: Optional[str] = None


# ─── Async n8n Client Implementation ───

class N8nClient:
    """Production-ready Async Client for local n8n workflow engine."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        webhook_base_url: Optional[str] = None,
        timeout: Optional[float] = None,
        max_retries: Optional[int] = None
    ):
        self.base_url = (base_url or settings.N8N_BASE_URL).rstrip("/")
        self.api_key = api_key or settings.N8N_API_KEY
        self.webhook_base_url = (webhook_base_url or settings.N8N_WEBHOOK_BASE_URL).rstrip("/")
        self.timeout = timeout or settings.N8N_TIMEOUT_SECONDS
        self.max_retries = max_retries or settings.N8N_MAX_RETRIES

    def _get_headers(self) -> Dict[str, str]:
        """Builds HTTP headers for n8n REST API authentication."""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        if self.api_key:
            headers["X-N8N-API-KEY"] = self.api_key
        return headers

    async def check_health(self) -> bool:
        """Checks if local n8n server is online and responding."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                res = await client.get(f"{self.base_url}/healthz")
                if res.status_code == 200:
                    return True
                # Fallback check root / API endpoint
                res = await client.get(f"{self.base_url}/api/v1/workflows", headers=self._get_headers())
                return res.status_code in (200, 401, 403)
        except Exception as e:
            logger.debug(f"n8n health check failed ({self.base_url}): {e}")
            return False

    async def list_workflows(self) -> List[N8nWorkflow]:
        """Retrieves all workflows from local n8n instance via REST API."""
        url = f"{self.base_url}/api/v1/workflows"
        for attempt in range(1, self.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    res = await client.get(url, headers=self._get_headers())
                    res.raise_for_status()
                    data = res.json()
                    items = data.get("data", data if isinstance(data, list) else [])
                    workflows = [N8nWorkflow(**item) for item in items]
                    logger.info(f"Retrieved {len(workflows)} n8n workflows from local server.")
                    return workflows
            except Exception as e:
                logger.warning(f"Attempt {attempt}/{self.max_retries} failed to list n8n workflows: {e}")
                if attempt < self.max_retries:
                    await asyncio.sleep(1.0 * attempt)
        return []

    async def get_workflow(self, workflow_id: str) -> Optional[N8nWorkflow]:
        """Fetches detailed workflow schema by ID."""
        url = f"{self.base_url}/api/v1/workflows/{workflow_id}"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                res = await client.get(url, headers=self._get_headers())
                res.raise_for_status()
                return N8nWorkflow(**res.json())
        except Exception as e:
            logger.error(f"Error fetching n8n workflow '{workflow_id}': {e}")
            return None

    async def trigger_webhook(
        self,
        webhook_path: str,
        payload: Dict[str, Any],
        method: str = "POST"
    ) -> N8nExecutionResult:
        """Triggers an n8n webhook workflow with payload data."""
        clean_path = webhook_path.lstrip("/")
        if clean_path.startswith("webhook/"):
            clean_path = clean_path.replace("webhook/", "", 1)

        urls_to_try = [
            f"{self.webhook_base_url}/{clean_path}",
            f"{self.base_url}/webhook-test/{clean_path}"
        ]

        for target_url in urls_to_try:
            for attempt in range(1, self.max_retries + 1):
                try:
                    async with httpx.AsyncClient(timeout=self.timeout) as client:
                        if method.upper() == "GET":
                            res = await client.get(target_url, params=payload)
                        else:
                            res = await client.post(target_url, json=payload, headers={"Content-Type": "application/json"})

                        if res.status_code in (200, 201, 202):
                            result_data = res.json() if res.headers.get("content-type", "").startswith("application/json") else {"raw_response": res.text}
                            logger.info(f"n8n webhook '{webhook_path}' triggered successfully at {target_url}.")
                            return N8nExecutionResult(
                                success=True,
                                data=result_data
                            )
                        else:
                            error_text = f"HTTP {res.status_code}: {res.text}"
                            logger.warning(f"Webhook attempt {attempt} for {target_url} error: {error_text}")
                except Exception as e:
                    logger.warning(f"Webhook trigger attempt {attempt}/{self.max_retries} failed for {target_url}: {e}")
                    if attempt < self.max_retries:
                        await asyncio.sleep(0.5 * attempt)

        return N8nExecutionResult(
            success=False,
            error_message=f"n8n webhook '{webhook_path}' is not published or active yet. In n8n UI, click 'Publish' (top right) or add a Webhook node with path '{clean_path}'."
        )

    async def execute_workflow(
        self,
        workflow_id: str,
        payload: Dict[str, Any]
    ) -> N8nExecutionResult:
        """Executes a workflow by ID via REST API trigger endpoint or webhook fallback."""
        url = f"{self.base_url}/api/v1/workflows/{workflow_id}/execute"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                res = await client.post(url, json={"data": payload}, headers=self._get_headers())
                if res.status_code in (200, 201):
                    res_data = res.json()
                    execution_id = res_data.get("id") or res_data.get("executionId")
                    return N8nExecutionResult(
                        success=True,
                        execution_id=execution_id,
                        workflow_id=workflow_id,
                        data=res_data
                    )
        except Exception as e:
            logger.debug(f"Direct REST execution for workflow '{workflow_id}' failed ({e}). Trying webhook fallback...")

        # Webhook fallback if workflow_id maps to a webhook endpoint
        return await self.trigger_webhook(f"jarvis-{workflow_id}", payload)

    async def get_execution_status(self, execution_id: str) -> Optional[N8nExecution]:
        """Queries execution status and logs for a given execution ID."""
        url = f"{self.base_url}/api/v1/executions/{execution_id}"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                res = await client.get(url, headers=self._get_headers())
                res.raise_for_status()
                return N8nExecution(**res.json())
        except Exception as e:
            logger.error(f"Error checking execution status for '{execution_id}': {e}")
            return None

    async def create_workflow(self, workflow_data: Dict[str, Any]) -> Optional[N8nWorkflow]:
        """Creates a new workflow in n8n using JSON workflow definition."""
        url = f"{self.base_url}/api/v1/workflows"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                res = await client.post(url, json=workflow_data, headers=self._get_headers())
                res.raise_for_status()
                wf = N8nWorkflow(**res.json())
                logger.info(f"Created new n8n workflow '{wf.name}' (ID: {wf.id})")
                return wf
        except Exception as e:
            logger.error(f"Failed to auto-create n8n workflow: {e}")
            return None

    async def activate_workflow(self, workflow_id: str) -> bool:
        """Activates an n8n workflow so it can listen for triggers."""
        url = f"{self.base_url}/api/v1/workflows/{workflow_id}/activate"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                res = await client.post(url, headers=self._get_headers())
                return res.status_code in (200, 201)
        except Exception as e:
            logger.error(f"Failed to activate workflow '{workflow_id}': {e}")
            return False

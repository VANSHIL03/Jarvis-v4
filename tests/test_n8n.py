import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from automation.n8n_client import N8nClient, N8nWorkflow, N8nExecutionResult
from automation.n8n_workflow_manager import N8nWorkflowManager
from agents.n8n_agent import N8nAgent
from agents.planner_agent import PlannerAgent

@pytest.mark.asyncio
async def test_n8n_client_health():
    client = N8nClient()
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value.status_code = 200
        is_healthy = await client.check_health()
        assert is_healthy is True

@pytest.mark.asyncio
async def test_n8n_workflow_manager_match():
    memory = MagicMock()
    client = AsyncMock()
    client.list_workflows.return_value = [
        N8nWorkflow(id="wf-12345678-1234-1234-1234-123456789012", name="Backup Documents", active=True)
    ]
    manager = N8nWorkflowManager(n8n_client=client, memory_manager=memory)

    # Match workflow by name
    match = await manager.match_workflow("Backup Documents")
    assert match is not None
    assert match[0] == "wf-12345678-1234-1234-1234-123456789012"
    assert match[1] == "Backup Documents"

@pytest.mark.asyncio
async def test_n8n_agent_execute_action():
    llm = MagicMock()
    manager = AsyncMock()
    manager.execute_matched_task.return_value = N8nExecutionResult(
        success=True,
        workflow_name="Google Drive Upload",
        execution_id="exec-99",
        data={"file": "doc.pdf"}
    )
    agent = N8nAgent(llm_client=llm, workflow_manager=manager)

    res = await agent.execute_task("upload_google_drive", {"user_intent": "Upload file to Google Drive", "file": "doc.pdf"})
    assert res["status"] == "success"
    assert res["workflow_name"] == "Google Drive Upload"

def test_planner_tool_router_classification():
    llm = MagicMock()
    memory = MagicMock()
    safety = MagicMock()
    planner = PlannerAgent(llm, memory, safety, {})

    # n8n Workflow Classification
    is_fp, result = planner._fast_path_match("Backup my Documents folder to n8n")
    assert is_fp is True
    assert result["delegations"][0]["agent"] == "n8n_agent"

    # Local Windows Tool Classification
    is_fp_win, res_win = planner._fast_path_match("open notepad")
    assert is_fp_win is True
    assert res_win["delegations"][0]["agent"] == "windows_agent"

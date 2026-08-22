"""
JARVIS v4 Unit Tests - Multi-Agent System Subsystem
"""

import pytest
import asyncio
from ai.llm_client import LocalLLMClient
from memory.memory_manager import MemoryManager
from security.safety import SafetyManager
from agents.coding_agent import CodingAgent
from agents.planner_agent import PlannerAgent

@pytest.mark.asyncio
async def test_coding_agent_sandbox():
    llm = LocalLLMClient()
    coding_agent = CodingAgent(llm)
    res = await coding_agent.execute_task(
        "run_python_sandbox",
        {"code": "print(10 + 20)"}
    )
    assert res["status"] == "success"
    assert "30" in res["stdout"]

def test_safety_manager_interceptor():
    safety = SafetyManager()
    assert safety.is_dangerous_action("delete_file", {"path": "C:/Windows"}) is True
    assert safety.is_dangerous_action("set_volume", {"level": 50}) is False

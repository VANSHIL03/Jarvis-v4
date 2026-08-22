"""
JARVIS v4 - Git & GitHub Sub-Agent Unit Tests
"""

import pytest
from unittest.mock import MagicMock
from agents.git_agent import GitAgent
from automation.git_control import GitControl


@pytest.mark.asyncio
async def test_git_agent_push():
    mock_git_control = MagicMock()
    mock_git_control.push_folder_to_github.return_value = {
        "success": True,
        "message": "Pushed to GitHub",
        "repo_url": "https://github.com/user/repo.git"
    }

    agent = GitAgent(git_control=mock_git_control)
    res = await agent.execute_task("push_to_github", {"folder_path": "."})

    assert res["success"] is True
    assert "Pushed to GitHub" in res["message"]
    mock_git_control.push_folder_to_github.assert_called_once()

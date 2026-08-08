"""
JARVIS v4 - Git & GitHub Automation Agent
Specialized sub-agent for initializing git repositories, committing changes, and pushing projects to GitHub.
"""

from typing import Dict, Any
from automation.git_control import GitControl
from utils.logger import logger


class GitAgent:
    def __init__(self, git_control: GitControl = None):
        self.git_control = git_control or GitControl()

    async def execute_task(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Executes Git and GitHub operations based on requested action."""
        action = action.lower().strip()
        logger.info(f"GitAgent executing action '{action}' with params {params}")

        if action in ["push_to_github", "push_folder", "push_repo", "push"]:
            folder_path = params.get("folder_path", ".")
            repo_name = params.get("repo_name")
            repo_url = params.get("repo_url")
            commit_message = params.get("commit_message", "Pushed by J.A.R.V.I.S. v4")
            private = params.get("private", False)

            res = self.git_control.push_folder_to_github(
                folder_path=folder_path,
                repo_name=repo_name,
                repo_url=repo_url,
                commit_message=commit_message,
                private=private
            )
            return res

        else:
            return {"status": "error", "message": f"Unknown GitAgent action '{action}'."}

"""
JARVIS v4 - Git & GitHub Automation Module
Handles local Git repository operations and GitHub remote creation & pushes.
"""

import os
import subprocess
import json
import urllib.request
import urllib.error
from pathlib import Path
from typing import Dict, Any, Optional
from config.settings import settings
from utils.logger import logger


class GitControl:
    def __init__(self):
        pass

    def _run_git(self, args: list[str], cwd: str) -> tuple[int, str, str]:
        """Helper to run a git command in a target directory."""
        try:
            res = subprocess.run(
                ["git"] + args,
                cwd=cwd,
                capture_output=True,
                text=True,
                check=False
            )
            return res.returncode, res.stdout.strip(), res.stderr.strip()
        except Exception as e:
            return 1, "", str(e)

    def create_remote_repo(self, repo_name: str, private: bool = False, token: Optional[str] = None) -> tuple[bool, str]:
        """Creates a new repository on GitHub using the REST API."""
        gh_token = token or settings.GITHUB_TOKEN or os.getenv("GITHUB_TOKEN", "")
        if not gh_token:
            return False, "GitHub API Token is required to create a new remote repository. Please set your GitHub Token in Settings."

        url = "https://api.github.com/user/repos"
        headers = {
            "Authorization": f"token {gh_token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "JARVIS-v4-Assistant"
        }
        payload = json.dumps({
            "name": repo_name,
            "private": private,
            "auto_init": False
        }).encode("utf-8")

        try:
            req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                clone_url = data.get("clone_url", "")
                return True, clone_url
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8")
            if e.code == 422: # Repo might already exist
                user_res = self.get_authenticated_user(gh_token)
                if user_res:
                    return True, f"https://github.com/{user_res}/{repo_name}.git"
            return False, f"GitHub API error ({e.code}): {err_body}"
        except Exception as e:
            return False, f"Failed to connect to GitHub API: {e}"

    def get_authenticated_user(self, token: str) -> Optional[str]:
        """Fetches the authenticated user's GitHub username."""
        url = "https://api.github.com/user"
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "JARVIS-v4-Assistant"
        }
        try:
            req = urllib.request.Request(url, headers=headers, method="GET")
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data.get("login")
        except Exception:
            return None

    def push_folder_to_github(
        self,
        folder_path: str = ".",
        repo_name: Optional[str] = None,
        repo_url: Optional[str] = None,
        commit_message: str = "Pushed by J.A.R.V.I.S. v4",
        private: bool = False
    ) -> Dict[str, Any]:
        """Initializes git, commits all files, creates remote repo if needed, and pushes code to GitHub."""
        target_dir = Path(folder_path).resolve()
        if not target_dir.exists() or not target_dir.is_dir():
            return {"success": False, "message": f"Target folder '{folder_path}' does not exist."}

        cwd = str(target_dir)
        folder_name = repo_name or target_dir.name

        logger.info(f"GitControl: Preparing to push '{folder_name}' at '{cwd}' to GitHub...")

        # 1. Git Init
        git_dir = target_dir / ".git"
        if not git_dir.exists():
            code, out, err = self._run_git(["init"], cwd)
            if code != 0:
                return {"success": False, "message": f"Failed to initialize Git repository: {err}"}

        # Set default branch to main and configure user info if missing
        self._run_git(["config", "user.name", "VANSHIL03"], cwd)
        self._run_git(["config", "user.email", "vanshilgupta4@gmail.com"], cwd)
        self._run_git(["branch", "-M", "main"], cwd)

        # 2. Add files & Commit
        self._run_git(["add", "."], cwd)
        code, out, err = self._run_git(["commit", "-m", commit_message], cwd)
        # Note: if nothing to commit, code might be non-zero, which is okay

        # 3. Handle Remote URL
        final_remote_url = repo_url
        if not final_remote_url:
            # Check if origin remote already exists
            code, out, _ = self._run_git(["remote", "get-url", "origin"], cwd)
            if code == 0 and out:
                final_remote_url = out
            else:
                # Create remote repo on GitHub via API if token is present
                gh_token = settings.GITHUB_TOKEN or os.getenv("GITHUB_TOKEN", "")
                if gh_token:
                    ok, res_url = self.create_remote_repo(folder_name, private=private, token=gh_token)
                    if ok:
                        final_remote_url = res_url
                    else:
                        return {"success": False, "message": f"Failed to create GitHub repository: {res_url}"}

        if not final_remote_url:
            return {
                "success": False,
                "message": "No remote URL found and GitHub Token is missing. Please configure your GitHub Token in Settings or provide a remote repository URL."
            }

        # Inject auth token into HTTPS remote URL if token is present and URL is HTTPS
        gh_token = settings.GITHUB_TOKEN or os.getenv("GITHUB_TOKEN", "")
        push_url = final_remote_url
        if gh_token and final_remote_url.startswith("https://github.com/"):
            push_url = final_remote_url.replace("https://github.com/", f"https://{gh_token}@github.com/")

        # Set origin remote
        self._run_git(["remote", "remove", "origin"], cwd)
        self._run_git(["remote", "add", "origin", push_url], cwd)

        # 4. Push to origin main
        code, out, err = self._run_git(["push", "-u", "origin", "main", "--force"], cwd)
        if code != 0:
            # Try master if main fails
            code2, out2, err2 = self._run_git(["push", "-u", "origin", "master", "--force"], cwd)
            if code2 != 0:
                return {"success": False, "message": f"Git push failed: {err} / {err2}"}

        clean_url = final_remote_url.replace(f"{gh_token}@", "") if gh_token else final_remote_url
        return {
            "success": True,
            "message": f"Successfully pushed '{folder_name}' to GitHub repository: {clean_url}",
            "repo_url": clean_url
        }

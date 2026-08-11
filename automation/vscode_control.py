"""
JARVIS v4 - VS Code Project Creator & Direct Coding Automation
Creates project folders at target locations, generates code files, and launches VS Code.
"""

import os
import sys
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional
from utils.logger import logger


class VSCodeControl:
    def __init__(self):
        self.default_base = Path.home() / "Desktop"

    def create_project_and_code(
        self,
        folder_name: str,
        target_dir: Optional[str] = None,
        language: str = "python",
        code_content: str = "",
        file_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """Creates target project directory, writes code file, and opens VS Code in that directory."""
        try:
            base_dir = Path(target_dir) if target_dir and Path(target_dir).exists() else self.default_base
            project_path = base_dir / folder_name
            project_path.mkdir(parents=True, exist_ok=True)
            logger.info(f"Created project folder: {project_path}")

            # Map extension
            ext_map = {
                "python": ("py", "main.py"),
                "html": ("html", "index.html"),
                "css": ("css", "style.css"),
                "javascript": ("js", "app.js"),
                "js": ("js", "app.js"),
                "java": ("java", "Main.java"),
                "cpp": ("cpp", "main.cpp"),
                "c++": ("cpp", "main.cpp"),
                "c#": ("cs", "Game.cs"),
                "react": ("jsx", "App.jsx"),
                "unity": ("cs", "PlayerController.cs")
            }

            ext, default_fn = ext_map.get(language.lower(), ("py", "main.py"))
            target_fn = file_name if file_name else default_fn
            code_file_path = project_path / target_fn

            with open(code_file_path, "w", encoding="utf-8") as f:
                f.write(code_content if code_content else f"# JARVIS Generated Project - {folder_name}\nprint('Hello Sir!')\n")

            logger.info(f"Created code file: {code_file_path}")

            # Launch VS Code in project folder
            vscode_launched = self.open_in_vscode(project_path, code_file_path)

            return {
                "status": "success",
                "project_path": str(project_path),
                "code_file": str(code_file_path),
                "vscode_launched": vscode_launched,
                "folder_name": folder_name,
                "language": language
            }
        except Exception as e:
            logger.error(f"Failed to create VS Code project: {e}")
            return {"status": "error", "message": str(e)}

    def open_in_vscode(self, folder_path: Path, file_path: Optional[Path] = None) -> bool:
        """Launches VS Code in folder and opens target file."""
        try:
            cmd = ["code", str(folder_path)]
            if file_path:
                cmd.append(str(file_path))

            subprocess.Popen(cmd, shell=True)
            logger.info(f"VS Code launched for: {folder_path}")
            return True
        except Exception as e:
            logger.warning(f"Could not launch VS Code directly ({e}). Opening File Explorer fallback.")
            try:
                subprocess.Popen(["explorer.exe", str(folder_path)])
                return False
            except Exception:
                return False

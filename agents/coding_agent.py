"""
JARVIS v4 - Coding & Programming Assistant Agent
Handles code generation (Python, Java, C++, HTML, JS, React, Unity C#), debugging, and sandbox execution.
"""

import sys
import subprocess
import tempfile
from typing import Dict, Any
from agents.base_agent import BaseAgent
from ai.llm_client import LocalLLMClient
from utils.logger import logger

class CodingAgent(BaseAgent):
    def __init__(self, llm_client: LocalLLMClient):
        self.llm = llm_client

    @property
    def agent_name(self) -> str:
        return "coding_agent"

    @property
    def description(self) -> str:
        return "Writes, explains, debugs, and executes Python, Java, C++, JS, React, and Unity C# code."

    async def execute_task(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        action = action.lower()
        if action == "generate_code":
            language = params.get("language", "python")
            prompt = params.get("prompt", "")
            sys_prompt = f"You are an expert {language} software developer. Generate clean, efficient, production quality code with comments."
            code = await self.llm.generate_response(prompt=prompt, system_prompt=sys_prompt)
            return {"status": "success", "language": language, "code": code}

        elif action == "explain_code":
            code = params.get("code", "")
            prompt = f"Explain the following code step-by-step:\n```\n{code}\n```"
            explanation = await self.llm.generate_response(prompt=prompt)
            return {"status": "success", "explanation": explanation}

        elif action == "debug_code":
            code = params.get("code", "")
            error_msg = params.get("error", "")
            prompt = f"Debug this code:\n```\n{code}\n```\nStack Trace / Error:\n{error_msg}\nProvide corrected code and explanation."
            fix = await self.llm.generate_response(prompt=prompt)
            return {"status": "success", "debug_result": fix}

        elif action == "run_python_sandbox":
            code = params.get("code", "")
            return self._run_python_sandbox(code)

        return {"status": "error", "message": f"Unknown coding action: '{action}'"}

    def _run_python_sandbox(self, code: str) -> Dict[str, Any]:
        """Executes Python snippet safely in temporary subprocess sandbox."""
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False, encoding="utf-8") as tmp:
            tmp.write(code)
            tmp_path = tmp.name

        try:
            res = subprocess.run(
                [sys.executable, tmp_path],
                capture_output=True,
                text=True,
                timeout=10
            )
            return {
                "status": "success" if res.returncode == 0 else "error",
                "stdout": res.stdout,
                "stderr": res.stderr,
                "exit_code": res.returncode
            }
        except subprocess.TimeoutExpired:
            return {"status": "error", "stderr": "Execution timed out after 10 seconds."}
        except Exception as e:
            return {"status": "error", "stderr": str(e)}

"""
JARVIS v4 - Coding & Programming Assistant Agent
Handles code generation (Python, Java, C++, HTML, JS, React, Unity C#), debugging, and sandbox execution.
"""

import sys
import subprocess
import tempfile
from typing import Dict, Any, Optional
from agents.base_agent import BaseAgent
from ai.llm_client import LocalLLMClient
from automation.vscode_control import VSCodeControl
from utils.logger import logger

class CodingAgent(BaseAgent):
    def __init__(self, llm_client: LocalLLMClient):
        self.llm = llm_client
        self.vscode = VSCodeControl()

    @property
    def agent_name(self) -> str:
        return "coding_agent"

    @property
    def description(self) -> str:
        return "Writes, explains, debugs, executes code, and creates VS Code project folders."

    async def execute_task(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        action = action.lower()
        if action in ("create_vscode_project", "create_project"):
            folder_name = params.get("folder_name", "JARVIS_Project")
            target_dir = params.get("target_dir")
            language = params.get("language", "python")
            prompt = params.get("prompt", f"Create a production quality {language} project")
            sys_prompt = f"You are an expert {language} software developer. Generate complete, clean, working production code with comments."
            code = await self.llm.generate_response(prompt=prompt, system_prompt=sys_prompt)
            code_lower = code.lower()
            if "offline standby mode" in code_lower or "error communicating" in code_lower or "returned status" in code_lower or not code.strip():
                code = self._get_fallback_code(prompt, language)

            res = self.vscode.create_project_and_code(
                folder_name=folder_name,
                target_dir=target_dir,
                language=language,
                code_content=code
            )
            notepad_file = self._open_in_notepad(code, language)
            res["code"] = code
            res["notepad_path"] = notepad_file
            res["speech_reply"] = f"Ji Sir, maine '{folder_name}' folder me aapka {language.capitalize()} code write karke Notepad aur VS Code me khol diya hai!"
            return res

        elif action in ("generate_code", "write_code", "code"):
            language = params.get("language", "python")
            prompt = params.get("prompt", params.get("user_input", "Write clean python code"))
            sys_prompt = f"You are an expert {language} software developer. Generate clean, efficient, working code with comments."
            code = await self.llm.generate_response(prompt=prompt, system_prompt=sys_prompt)
            code_lower = code.lower()
            if "offline standby mode" in code_lower or "error communicating" in code_lower or "returned status" in code_lower or not code.strip():
                code = self._get_fallback_code(prompt, language)

            notepad_path = self._open_in_notepad(code, language)
            return {
                "status": "success",
                "language": language,
                "code": code,
                "notepad_path": notepad_path,
                "speech_reply": f"Ji Sir, maine aapka {language.capitalize()} code write kar diya hai aur ise Notepad me open kar diya hai! Code aapke GUI feed par bhi hai."
            }

        elif action == "explain_code":
            code = params.get("code", "")
            prompt = f"Explain the following code step-by-step:\n```\n{code}\n```"
            explanation = await self.llm.generate_response(prompt=prompt)
            return {
                "status": "success",
                "explanation": explanation,
                "speech_reply": f"Sir, yeh raha aapke code ka step-by-step explanation: {explanation[:200]}..."
            }

        elif action == "debug_code":
            code = params.get("code", "")
            error_msg = params.get("error", "")
            prompt = f"Debug this code:\n```\n{code}\n```\nStack Trace / Error:\n{error_msg}\nProvide corrected code and explanation."
            fix = await self.llm.generate_response(prompt=prompt)
            notepad_path = self._open_in_notepad(fix, "txt")
            return {
                "status": "success",
                "debug_result": fix,
                "notepad_path": notepad_path,
                "speech_reply": "Ji Sir, maine code ko debug karke corrected code Notepad me open kar diya hai."
            }

        elif action in ("run_python_sandbox", "run_code", "execute_code", "run_python"):
            code = params.get("code", "")
            if not str(code).strip():
                return {
                    "status": "error",
                    "message": "No code supplied to run.",
                    "speech_reply": "Sir, run karne ke liye code to dijiye.",
                }
            language = str(params.get("language", "python")).lower()
            if language not in ("", "python", "py", "python3"):
                # Only Python has a sandboxed runner here. Silently running it
                # through the Python interpreter would be worse than refusing.
                return {
                    "status": "error",
                    "language": language,
                    "message": f"Sandboxed execution is only available for Python, not {language}.",
                    "speech_reply": (
                        f"Sir, main sirf Python code hi safely run kar sakta hoon, "
                        f"{language} nahi."
                    ),
                }
            return self._run_python_sandbox(code, timeout=int(params.get("timeout", 10) or 10))

        elif action in ("open_vscode", "open_in_vscode", "launch_vscode", "open_editor"):
            folder = params.get("folder_path") or params.get("path") or ""
            file_path = params.get("file_path") or None
            if not folder and file_path:
                from pathlib import Path as _Path
                folder = str(_Path(file_path).parent)
            if not folder:
                from pathlib import Path as _Path
                folder = str(_Path.home() / "Desktop")
            ok = self.vscode.open_in_vscode(folder, file_path=file_path)
            return {
                "status": "success" if ok else "error",
                "folder_path": folder,
                "file_path": file_path or "",
                "speech_reply": (
                    f"Ji Sir, VS Code me '{folder}' khol diya hai."
                    if ok else "Sir, VS Code open nahi ho paya - kya wo installed hai?"
                ),
            }

        return {"status": "error", "message": f"Unknown coding action: '{action}'"}

    def _get_fallback_code(self, prompt: str, language: str) -> str:
        """Generates instant working code templates when Ollama LLM server is offline."""
        prompt_lower = prompt.lower()
        if "snake" in prompt_lower:
            return '''# Snake Game in Python (Pygame)
import pygame, sys, random
pygame.init()
WIDTH, HEIGHT = 600, 400
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("JARVIS Snake Game")
clock = pygame.time.Clock()
snake = [(100, 100), (90, 100), (80, 100)]
direction = (10, 0)
food = (200, 200)

while True:
    for event in pygame.event.get():
        if event.type == pygame.QUIT: pygame.quit(); sys.exit()
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_UP and direction != (0, 10): direction = (0, -10)
            elif event.key == pygame.K_DOWN and direction != (0, -10): direction = (0, 10)
            elif event.key == pygame.K_LEFT and direction != (10, 0): direction = (-10, 0)
            elif event.key == pygame.K_RIGHT and direction != (-10, 0): direction = (10, 0)

    new_head = (snake[0][0] + direction[0], snake[0][1] + direction[1])
    snake.insert(0, new_head)
    if new_head == food:
        food = (random.randint(0, (WIDTH-10)//10)*10, random.randint(0, (HEIGHT-10)//10)*10)
    else:
        snake.pop()

    screen.fill((10, 15, 25))
    for segment in snake:
        pygame.draw.rect(screen, (0, 255, 170), (*segment, 10, 10))
    pygame.draw.rect(screen, (255, 50, 80), (*food, 10, 10))
    pygame.display.flip()
    clock.tick(15)
'''
        elif "calculator" in prompt_lower:
            return '''# Simple Calculator in Python
def calculate():
    print("=== JARVIS Calculator ===")
    num1 = float(input("Enter first number: "))
    op = input("Enter operator (+, -, *, /): ")
    num2 = float(input("Enter second number: "))

    if op == '+': result = num1 + num2
    elif op == '-': result = num1 - num2
    elif op == '*': result = num1 * num2
    elif op == '/': result = num1 / num2 if num2 != 0 else "Error (Division by zero)"
    else: result = "Invalid operator"

    print(f"Result: {result}")

if __name__ == "__main__":
    calculate()
'''
        elif language.lower() in ("html", "webpage", "website"):
            return '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>JARVIS Generated Webpage</title>
    <style>
        body { background-color: #080c16; color: #00d2ff; font-family: 'Segoe UI', sans-serif; text-align: center; padding: 50px; }
        .card { background: rgba(0, 180, 255, 0.1); border: 1px solid #00d2ff; padding: 20px; border-radius: 12px; display: inline-block; }
    </style>
</head>
<body>
    <div class="card">
        <h1>Welcome Sir</h1>
        <p>This webpage was created automatically by J.A.R.V.I.S. v4</p>
    </div>
</body>
</html>
'''
        else:
            return f'''# JARVIS v4 - {language.capitalize()} Program
# Prompt: {prompt}

def main():
    print("Greetings Sir! Executing {language.capitalize()} code generated by JARVIS.")

if __name__ == "__main__":
    main()
'''

    def _open_in_notepad(self, code: str, language: str = "txt") -> Optional[str]:
        """Saves generated code into a file and opens it in Notepad."""
        try:
            ext_map = {
                "python": "py", "py": "py",
                "java": "java",
                "cpp": "cpp", "c++": "cpp", "c": "c",
                "c#": "cs", "csharp": "cs", "cs": "cs",
                "html": "html", "css": "css",
                "javascript": "js", "js": "js",
                "typescript": "ts", "ts": "ts", "react": "jsx",
                "sql": "sql", "xml": "xml", "json": "json",
                "php": "php", "go": "go", "golang": "go",
                "rust": "rs", "rs": "rs",
                "kotlin": "kt", "kt": "kt",
                "swift": "swift", "ruby": "rb", "rb": "rb",
                "shell": "sh", "bash": "sh", "powershell": "ps1", "bat": "bat",
                "yaml": "yml", "yml": "yml", "markdown": "md", "md": "md",
                "unity": "cs"
            }
            ext = ext_map.get(language.lower(), "txt")
            with tempfile.NamedTemporaryFile(suffix=f".{ext}", prefix="JARVIS_Code_", delete=False, mode="w", encoding="utf-8") as tmp:
                tmp.write(code)
                code_file = tmp.name

            subprocess.Popen(["notepad.exe", code_file])
            logger.info(f"Opened generated code in Notepad: {code_file}")
            return code_file
        except Exception as e:
            logger.warning(f"Could not open Notepad for generated code: {e}")
            return None

    def _run_python_sandbox(self, code: str, timeout: int = 10) -> Dict[str, Any]:
        """
        Executes a Python snippet in a throwaway subprocess.

        Section 15 forbids running untrusted code with unrestricted privileges,
        so the child is constrained in four ways: it starts in its own empty temp
        directory (a stray open("out.txt","w") cannot touch the project), runs
        under -I so PYTHONPATH and the user site-dir cannot inject code, gets an
        environment with credential-shaped variables stripped (Section 14), and
        is killed on timeout. This is a guard rail, not a jail -- generated code
        still runs as this user, which is why run_code is confirmation-gated.
        """
        import os
        import shutil

        workdir = tempfile.mkdtemp(prefix="JARVIS_Run_")
        script = os.path.join(workdir, "snippet.py")
        try:
            with open(script, "w", encoding="utf-8") as handle:
                handle.write(code)

            child_env = {
                k: v for k, v in os.environ.items()
                if not any(
                    marker in k.upper()
                    for marker in ("TOKEN", "SECRET", "PASSWORD", "PASSWD", "API_KEY", "APIKEY", "CREDENTIAL")
                )
            }
            child_env["PYTHONIOENCODING"] = "utf-8"

            res = subprocess.run(
                [sys.executable, "-I", script],
                capture_output=True,
                text=True,
                timeout=max(1, int(timeout)),
                cwd=workdir,
                env=child_env,
            )
            stdout = (res.stdout or "")[:8000]
            stderr = (res.stderr or "")[:4000]
            ok = res.returncode == 0
            return {
                "status": "success" if ok else "error",
                "stdout": stdout,
                "stderr": stderr,
                "exit_code": res.returncode,
                "message": "" if ok else f"Code exit code {res.returncode} ke saath fail hua.",
                "speech_reply": (
                    f"Ji Sir, code chal gaya. Output: {stdout.strip()[:200]}"
                    if ok else
                    f"Sir, code error de raha hai: {stderr.strip()[:200]}"
                ),
            }
        except subprocess.TimeoutExpired:
            return {
                "status": "error",
                "stderr": f"Execution timed out after {timeout} seconds.",
                "message": "Execution timed out.",
                "speech_reply": f"Sir, code {timeout} second me khatam nahi hua, isliye main use rok diya.",
            }
        except Exception as e:
            return {"status": "error", "stderr": str(e), "message": str(e)}
        finally:
            shutil.rmtree(workdir, ignore_errors=True)

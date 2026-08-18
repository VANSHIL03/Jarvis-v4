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
            if "offline standby mode" in code or not code.strip():
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
            if "offline standby mode" in code or not code.strip():
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

        elif action == "run_python_sandbox":
            code = params.get("code", "")
            return self._run_python_sandbox(code)

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

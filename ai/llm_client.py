"""
JARVIS v4 - Async Local LLM Client (Ollama / CUDA Accelerated)
"""

import httpx
import json
from typing import List, Dict, Any, AsyncGenerator, Optional
from config.settings import settings
from utils.logger import logger

class LocalLLMClient:
    def __init__(self):
        self.base_url = settings.OLLAMA_BASE_URL
        self.default_model = settings.DEFAULT_MODEL
        self.fallback_model = settings.FALLBACK_MODEL
        self.client = httpx.AsyncClient(timeout=60.0)

    async def is_server_available(self) -> bool:
        """Checks if local Ollama server is running."""
        for url in [self.base_url, "http://127.0.0.1:11434", "http://localhost:11434"]:
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    resp = await client.get(f"{url}/api/version")
                    if resp.status_code == 200:
                        self.base_url = url
                        return True
            except Exception:
                pass
        return False

    async def generate_response(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        messages: Optional[List[Dict[str, str]]] = None,
        temperature: float = 0.3
    ) -> str:
        """Generates a text completion asynchronously from the local Ollama LLM."""
        if not await self.is_server_available():
            logger.warning("Ollama server unreachable at http://localhost:11434. Returning simulated offline response.")
            return "I am currently running in offline standby mode. Ollama service is not responding at localhost:11434."

        payload = {
            "model": self.default_model,
            "options": {
                "temperature": temperature,
                "num_predict": settings.LLM_MAX_TOKENS
            },
            "stream": False
        }

        if messages:
            endpoint = f"{self.base_url}/api/chat"
            formatted_messages = []
            if system_prompt:
                formatted_messages.append({"role": "system", "content": system_prompt})
            formatted_messages.extend(messages)
            payload["messages"] = formatted_messages
        else:
            endpoint = f"{self.base_url}/api/generate"
            payload["prompt"] = prompt
            if system_prompt:
                payload["system"] = system_prompt

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(endpoint, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    if "message" in data:
                        return data["message"]["content"]
                    return data.get("response", "")
                else:
                    logger.error(f"Ollama error {resp.status_code}: {resp.text}")
                    return f"Local LLM service returned status {resp.status_code}."
        except Exception as e:
            logger.error(f"Exception calling local LLM: {e}")
            return f"Error communicating with local AI model: {e}"

    async def generate_stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        """Streams response tokens from local LLM."""
        if not await self.is_server_available():
            yield "Ollama service unavailable."
            return

        payload = {
            "model": self.default_model,
            "prompt": prompt,
            "system": system_prompt or "",
            "stream": True
        }

        try:
            async with self.client.stream("POST", f"{self.base_url}/api/generate", json=payload) as response:
                async for chunk in response.aiter_lines():
                    if chunk:
                        data = json.loads(chunk)
                        token = data.get("response", "")
                        yield token
        except Exception as e:
            logger.error(f"Error during stream generation: {e}")
            yield f" [Error: {e}]"

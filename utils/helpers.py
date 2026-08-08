"""
JARVIS v4 - Helper Utilities
"""

import json
import re
import asyncio
from typing import Any, Dict, Optional
from utils.logger import logger

def parse_json_safely(text: str) -> Optional[Dict[str, Any]]:
    """Extracts and parses JSON object from LLM response text."""
    if not text:
        return None
        
    try:
        # Direct parse attempt
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Extract JSON inside markdown codeblocks
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # Extract raw curly braces block
    match_curly = re.search(r"\{.*\}", text, re.DOTALL)
    if match_curly:
        try:
            return json.loads(match_curly.group(0))
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse extracted JSON block: {e}")

    return None

def strip_thought_tags(text: str) -> tuple[str, str]:
    """Separates internal <thought> reasoning from the final response text."""
    thought = ""
    match = re.search(r"<thought>(.*?)</thought>", text, re.DOTALL)
    if match:
        thought = match.group(1).strip()
        cleaned_text = re.sub(r"<thought>.*?</thought>", "", text, flags=re.DOTALL).strip()
    else:
        cleaned_text = text.strip()
    
    return thought, cleaned_text

def run_async_in_thread(coro):
    """Utility to safely run async coroutine from synchronous threads."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()

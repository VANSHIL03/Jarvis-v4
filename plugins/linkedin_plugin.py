"""
JARVIS v4 - LinkedIn Automation Plugin
Provides local browser automation fallback for posting & interacting on LinkedIn.
"""

from typing import Dict, Any, List
from plugins.base_plugin import BasePlugin
from utils.logger import logger


class LinkedInPlugin(BasePlugin):
    def __init__(self):
        super().__init__()

    @property
    def plugin_name(self) -> str:
        return "linkedin"

    @property
    def description(self) -> str:
        return "LinkedIn Browser Automation & Posting Plugin"

    def get_supported_commands(self) -> List[str]:
        return ["post_update", "open_linkedin"]

    def execute(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        action = action.lower().strip()
        logger.info(f"LinkedInPlugin executing action '{action}' with params: {params}")

        if action in ("open_linkedin", "open"):
            import webbrowser
            webbrowser.open("https://www.linkedin.com/feed/")
            return {"status": "success", "message": "Opened LinkedIn feed in browser."}

        elif action in ("post_update", "post"):
            text = params.get("text", params.get("post_text", params.get("content", "")))
            import webbrowser
            from urllib.parse import quote
            url = f"https://www.linkedin.com/feed/?shareActive=true&text={quote(text)}" if text else "https://www.linkedin.com/feed/"
            webbrowser.open(url)
            return {
                "status": "success",
                "message": f"Opened LinkedIn post composer with message: '{text}'"
            }

        return {"status": "error", "message": f"Unknown LinkedIn action '{action}'"}

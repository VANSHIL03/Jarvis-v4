"""
JARVIS v4 - Browser Automation Agent
"""

from typing import Dict, Any
from agents.base_agent import BaseAgent
from automation.browser import PlaywrightBrowser

class BrowserAgent(BaseAgent):
    def __init__(self, browser: PlaywrightBrowser):
        self.browser = browser

    @property
    def agent_name(self) -> str:
        return "browser_agent"

    @property
    def description(self) -> str:
        return "Handles web browsing, Google search, YouTube music playback, Wikipedia, form filling, and downloads."

    async def execute_task(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        action = action.lower()
        if action == "open_url":
            url = params.get("url", "")
            success = await self.browser.open_url(url)
            return {"status": "success" if success else "error", "url": url}

        elif action == "search_google":
            query = params.get("query", "")
            snippet = await self.browser.search_google(query)
            return {"status": "success", "query": query, "result": snippet}

        elif action == "play_youtube":
            term = params.get("search_term", "")
            success = await self.browser.play_youtube(term)
            return {"status": "success" if success else "error", "search_term": term}

        return {"status": "error", "message": f"Unknown browser action: '{action}'"}

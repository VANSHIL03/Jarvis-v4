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
        if action in ["open_url", "open_website", "open_site", "browse"]:
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

        elif action in ["pause_video", "pause"]:
            success = await self.browser.youtube_control("pause")
            return {"status": "success" if success else "error", "action": "pause"}

        elif action in ["resume_video", "resume", "play_video"]:
            success = await self.browser.youtube_control("resume")
            return {"status": "success" if success else "error", "action": "resume"}

        elif action in ["skip_video", "skip", "forward"]:
            success = await self.browser.youtube_control("skip")
            return {"status": "success" if success else "error", "action": "skip_10s"}

        elif action in ["rewind_video", "rewind", "back"]:
            success = await self.browser.youtube_control("rewind")
            return {"status": "success" if success else "error", "action": "rewind_10s"}

        elif action in ["next_video", "next"]:
            success = await self.browser.youtube_control("next")
            return {"status": "success" if success else "error", "action": "next_video"}

        elif action in ["open_maps", "search_maps", "find_location"]:
            location = params.get("location", "") or params.get("query", "")
            success = await self.browser.open_maps(location)
            return {"status": "success" if success else "error", "location": location}

        elif action in ["navigate_maps", "get_distance", "maps_directions", "navigate"]:
            destination = params.get("destination", "") or params.get("location", "")
            origin = params.get("origin", "")
            success = await self.browser.get_maps_directions(destination, origin)
            return {"status": "success" if success else "error", "destination": destination, "origin": origin}

        elif action in ["download", "download_file", "save_file"]:
            url = params.get("url", "")
            save_dir = params.get("save_dir", "")
            file_name = params.get("file_name", "")
            res = await self.browser.download_file(url, save_dir=save_dir, file_name=file_name)
            if res.get("status") == "success":
                res.setdefault(
                    "speech_reply",
                    f"Ji Sir, file download ho gayi: {res.get('path', '')}",
                )
            return res

        return {"status": "error", "message": f"Unknown browser action: '{action}'"}

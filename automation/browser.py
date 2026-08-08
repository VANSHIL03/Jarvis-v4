"""
JARVIS v4 - Async Playwright Web Browser Automation
"""

import asyncio
import re
import urllib.parse
import webbrowser
import httpx
from typing import Optional, Dict, Any
from utils.logger import logger

class PlaywrightBrowser:
    def __init__(self):
        self._browser = None
        self._page = None

    async def _ensure_browser(self):
        if self._browser is None:
            try:
                from playwright.async_api import async_playwright
                p = await async_playwright().start()
                self._browser = await p.chromium.launch(headless=False)
                self._page = await self._browser.new_page()
                logger.info("Playwright Chromium browser launched successfully.")
            except Exception as e:
                logger.warning(f"Playwright browser launch failed ({e}). Falling back to default system browser.")

    async def open_url(self, url: str) -> bool:
        """Opens URL in Playwright browser or system default browser."""
        if not url.startswith("http"):
            url = f"https://{url}"

        await self._ensure_browser()
        if self._page:
            try:
                await self._page.goto(url)
                return True
            except Exception as e:
                logger.error(f"Playwright navigation error: {e}")

        # System browser fallback
        webbrowser.open(url)
        return True

    async def search_google(self, query: str) -> str:
        """Searches Google for query and extracts top snippet result."""
        encoded = urllib.parse.quote(query)
        url = f"https://www.google.com/search?q={encoded}"
        await self.open_url(url)
        if self._page:
            try:
                await self._page.wait_for_timeout(2000)
                snippet = await self._page.locator("div.g").first.text_content()
                return snippet if snippet else "Google search executed."
            except Exception:
                pass
        return "Search executed."

    async def _fetch_youtube_watch_url(self, search_term: str) -> Optional[str]:
        """Fetches direct YouTube watch URL (https://www.youtube.com/watch?v=...) for query."""
        try:
            encoded = urllib.parse.quote(search_term)
            search_url = f"https://www.youtube.com/results?search_query={encoded}"
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(search_url, headers=headers)
                if resp.status_code == 200:
                    matches = re.findall(r"watch\?v=([a-zA-Z0-9_-]{11})", resp.text)
                    if matches:
                        video_id = matches[0]
                        watch_url = f"https://www.youtube.com/watch?v={video_id}"
                        logger.info(f"Resolved direct YouTube video watch URL: {watch_url}")
                        return watch_url
        except Exception as e:
            logger.warning(f"Error resolving YouTube watch URL: {e}")
        return None

    async def play_youtube(self, search_term: str) -> bool:
        """Searches and plays video directly on YouTube."""
        # 1. Resolve direct video watch URL
        watch_url = await self._fetch_youtube_watch_url(search_term)
        if not watch_url:
            encoded = urllib.parse.quote(search_term)
            watch_url = f"https://www.youtube.com/results?search_query={encoded}"

        # 2. Navigate directly to video watch page
        logger.info(f"Playing YouTube video at: {watch_url}")
        await self.open_url(watch_url)

        if self._page and "watch?v=" in watch_url:
            try:
                # Try auto-play click if paused
                await self._page.wait_for_timeout(2000)
                play_btn = self._page.locator("button.ytp-play-button")
                if await play_btn.is_visible():
                    await play_btn.click()
            except Exception:
                pass

        return True

    async def close_browser(self):
        """Closes Playwright browser instance."""
        if self._browser:
            await self._browser.close()
            self._browser = None
            self._page = None

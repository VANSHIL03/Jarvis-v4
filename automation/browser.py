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

        try:
            await self._ensure_browser()
            if self._page:
                await self._page.goto(url)
                return True
        except Exception as e:
            logger.warning(f"Playwright navigation failed ({e}). Opening in default system browser.")
            self._browser = None
            self._page = None

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
                        watch_url = f"https://www.youtube.com/watch?v={video_id}&autoplay=1"
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

    async def youtube_control(self, command: str) -> bool:
        """Controls active YouTube video playback (pause, resume, 10s skip, 10s rewind, next video)."""
        cmd = command.lower()

        # Method 1: Playwright Page active control
        if self._page and "youtube.com" in self._page.url:
            try:
                if cmd in ["pause", "stop", "resume", "play"]:
                    await self._page.keyboard.press("k")
                    logger.info(f"YouTube Playwright control: toggled play/pause ('{cmd}')")
                    return True
                elif cmd in ["skip", "forward"]:
                    await self._page.keyboard.press("l")  # 10s skip forward
                    logger.info("YouTube Playwright control: skipped 10 seconds forward")
                    return True
                elif cmd in ["rewind", "back"]:
                    await self._page.keyboard.press("j")  # 10s rewind backward
                    logger.info("YouTube Playwright control: rewound 10 seconds backward")
                    return True
                elif cmd in ["next"]:
                    await self._page.keyboard.press("Shift+N")  # Next video
                    logger.info("YouTube Playwright control: triggered next video")
                    return True
            except Exception as e:
                logger.debug(f"Playwright YouTube control failed: {e}")

        # Method 2: Global PyAutoGUI media/keyboard shortcut fallback (system browser / Chrome)
        try:
            import pyautogui
            if cmd in ["pause", "stop", "resume", "play"]:
                pyautogui.press('k')
                logger.info("PyAutoGUI YouTube control: pressed 'k'")
            elif cmd in ["skip", "forward"]:
                pyautogui.press('l')
                logger.info("PyAutoGUI YouTube control: pressed 'l' (10s skip)")
            elif cmd in ["rewind", "back"]:
                pyautogui.press('j')
                logger.info("PyAutoGUI YouTube control: pressed 'j' (10s rewind)")
            elif cmd in ["next"]:
                pyautogui.hotkey('shift', 'n')
                logger.info("PyAutoGUI YouTube control: pressed Shift+N (Next Video)")
            return True
        except Exception as e:
            logger.error(f"PyAutoGUI YouTube control error: {e}")
            return False

    async def open_maps(self, query: str) -> bool:
        """Opens Google Maps and searches for target location."""
        encoded = urllib.parse.quote(query)
        maps_url = f"https://www.google.com/maps/search/{encoded}"
        logger.info(f"Opening Google Maps search for '{query}': {maps_url}")
        return await self.open_url(maps_url)

    async def get_maps_directions(self, destination: str, origin: str = "") -> bool:
        """Opens Google Maps navigation directions from origin/current location to destination."""
        dest_encoded = urllib.parse.quote(destination)
        if origin:
            orig_encoded = urllib.parse.quote(origin)
            dir_url = f"https://www.google.com/maps/dir/{orig_encoded}/{dest_encoded}"
        else:
            dir_url = f"https://www.google.com/maps/dir/?api=1&destination={dest_encoded}"
        logger.info(f"Opening Google Maps directions to '{destination}': {dir_url}")
        return await self.open_url(dir_url)

    async def download_file(self, url: str, save_dir: str = "", file_name: str = "") -> Dict[str, Any]:
        """
        Streams a file from `url` into the Downloads folder.

        httpx is used rather than a browser download so the bytes never touch a
        page context and the saved path is known exactly -- the caller has to be
        able to tell the user where the file went.
        """
        from pathlib import Path

        if not url:
            return {"status": "error", "message": "No URL given to download."}
        if not url.startswith("http"):
            url = f"https://{url}"

        target_dir = Path(save_dir) if save_dir else (Path.home() / "Downloads")
        name = file_name or urllib.parse.unquote(url.split("?")[0].rstrip("/").split("/")[-1])
        if not name or "." not in name:
            name = name or "download"
        target = target_dir / name

        try:
            target_dir.mkdir(parents=True, exist_ok=True)
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            written = 0
            async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
                async with client.stream("GET", url, headers=headers) as resp:
                    if resp.status_code >= 400:
                        return {
                            "status": "error",
                            "url": url,
                            "http_status": resp.status_code,
                            "message": f"Server ne {resp.status_code} return kiya.",
                        }
                    with open(target, "wb") as handle:
                        async for chunk in resp.aiter_bytes(65536):
                            handle.write(chunk)
                            written += len(chunk)
            logger.info(f"Downloaded {written} bytes to {target}")
            return {"status": "success", "url": url, "path": str(target), "bytes": written}
        except Exception as e:
            logger.error(f"Download failed for '{url}': {e}")
            return {"status": "error", "url": url, "message": str(e)}

    async def close_browser(self):
        """Closes Playwright browser instance."""
        if self._browser:
            await self._browser.close()
            self._browser = None
            self._page = None

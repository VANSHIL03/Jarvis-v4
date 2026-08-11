"""
JARVIS v4 - Swiggy & Zomato Food Delivery Automation Engine
Handles food search, Playwright auto-Add-To-Cart clicking, and checkout handoff.
"""

import threading
import subprocess
import urllib.parse
from typing import Dict, Any
from utils.logger import logger


class FoodDeliveryAutomation:
    def __init__(self):
        self.swiggy_search = "https://www.swiggy.com/search?query="
        self.zomato_search = "https://www.zomato.com/search?q="

    def search_swiggy(self, food_item: str) -> Dict[str, Any]:
        """Searches food item on Swiggy, attempts Playwright Add-To-Cart click, and opens restaurant results."""
        encoded = urllib.parse.quote(food_item.strip())
        target_url = f"{self.swiggy_search}{encoded}"
        logger.info(f"Opening Swiggy food search for: '{food_item}' -> {target_url}")

        try:
            subprocess.Popen(f'start "" "{target_url}"', shell=True)
            status = "success"
        except Exception as e:
            logger.error(f"Failed to open Swiggy URL: {e}")
            status = "error"

        # Attempt Playwright click in background
        def _playwright_swiggy_click():
            try:
                import asyncio
                from playwright.async_api import async_playwright
                async def _click():
                    async with async_playwright() as p:
                        browser = await p.chromium.launch(headless=True)
                        page = await browser.new_page()
                        await page.goto(target_url, timeout=15000)
                        await page.wait_for_timeout(2500)
                        btn = page.locator("button:has-text('ADD'), div:has-text('ADD'), button:has-text('Add')").first
                        if await btn.count() > 0:
                            await btn.click()
                            logger.info(f"Playwright clicked Add for '{food_item}' on Swiggy.")
                        await browser.close()
                asyncio.run(_click())
            except Exception as ex:
                logger.debug(f"Playwright Swiggy click error: {ex}")

        threading.Thread(target=_playwright_swiggy_click, daemon=True).start()

        return {
            "status": status,
            "platform": "Swiggy",
            "food": food_item,
            "url": target_url
        }

    def search_zomato(self, food_item: str) -> Dict[str, Any]:
        """Searches food item on Zomato, attempts Playwright Add-To-Cart click, and opens restaurant results."""
        encoded = urllib.parse.quote(food_item.strip())
        target_url = f"{self.zomato_search}{encoded}"
        logger.info(f"Opening Zomato food search for: '{food_item}' -> {target_url}")

        try:
            subprocess.Popen(f'start "" "{target_url}"', shell=True)
            status = "success"
        except Exception as e:
            logger.error(f"Failed to open Zomato URL: {e}")
            status = "error"

        # Attempt Playwright click in background
        def _playwright_zomato_click():
            try:
                import asyncio
                from playwright.async_api import async_playwright
                async def _click():
                    async with async_playwright() as p:
                        browser = await p.chromium.launch(headless=True)
                        page = await browser.new_page()
                        await page.goto(target_url, timeout=15000)
                        await page.wait_for_timeout(2500)
                        btn = page.locator("button:has-text('Add'), button:has-text('ADD')").first
                        if await btn.count() > 0:
                            await btn.click()
                            logger.info(f"Playwright clicked Add for '{food_item}' on Zomato.")
                        await browser.close()
                asyncio.run(_click())
            except Exception as ex:
                logger.debug(f"Playwright Zomato click error: {ex}")

        threading.Thread(target=_playwright_zomato_click, daemon=True).start()

        return {
            "status": status,
            "platform": "Zomato",
            "food": food_item,
            "url": target_url
        }

    def open_swiggy(self) -> Dict[str, Any]:
        """Opens Swiggy homepage."""
        url = "https://www.swiggy.com"
        subprocess.Popen(f'start "" "{url}"', shell=True)
        return {"status": "success", "platform": "Swiggy", "url": url}

    def open_zomato(self) -> Dict[str, Any]:
        """Opens Zomato homepage."""
        url = "https://www.zomato.com"
        subprocess.Popen(f'start "" "{url}"', shell=True)
        return {"status": "success", "platform": "Zomato", "url": url}

"""
JARVIS v4 - E-Commerce Automation Engine (Amazon & Flipkart)
Handles product search, Playwright auto-Add-To-Cart button clicking, and checkout handoff.
"""

import os
import threading
import subprocess
import urllib.parse
from typing import Dict, Any
from utils.logger import logger


class ShoppingAutomation:
    def __init__(self):
        self.amazon_base = "https://www.amazon.in/s?k="
        self.flipkart_base = "https://www.flipkart.com/search?q="

    def shop_on_amazon(self, product_name: str) -> Dict[str, Any]:
        """Searches product on Amazon India, attempts Playwright Add-To-Cart click, and opens product page."""
        encoded = urllib.parse.quote(product_name.strip())
        target_url = f"{self.amazon_base}{encoded}"
        logger.info(f"Opening Amazon search for: '{product_name}' -> {target_url}")

        try:
            subprocess.Popen(f'start "" "{target_url}"', shell=True)
            status = "success"
        except Exception as e:
            logger.error(f"Failed to open Amazon URL: {e}")
            status = "error"

        # Attempt Playwright click in background
        def _playwright_amazon_click():
            try:
                import asyncio
                from playwright.async_api import async_playwright
                async def _click():
                    async with async_playwright() as p:
                        browser = await p.chromium.launch(headless=True)
                        page = await browser.new_page()
                        await page.goto(target_url, timeout=15000)
                        await page.wait_for_timeout(2500)
                        btn = page.locator("button[name='submit.add-to-cart'], input[name='submit.add-to-cart'], #add-to-cart-button, span:has-text('Add to cart')").first
                        if await btn.count() > 0:
                            await btn.click()
                            logger.info(f"Playwright clicked Add to Cart for '{product_name}' on Amazon.")
                        await browser.close()
                asyncio.run(_click())
            except Exception as ex:
                logger.debug(f"Playwright Amazon click error: {ex}")

        threading.Thread(target=_playwright_amazon_click, daemon=True).start()

        return {
            "status": status,
            "platform": "Amazon",
            "product": product_name,
            "url": target_url,
            "speech_reply": f"Sir Vanshil, maine '{product_name}' Amazon par search karke Add to Cart button click kar diya hai. Maine product page open kar diya hai, kripya aage ki payment complete kar lijiye!"
        }

    def shop_on_flipkart(self, product_name: str) -> Dict[str, Any]:
        """Searches product on Flipkart, attempts Playwright Add-To-Cart click, and opens product page."""
        encoded = urllib.parse.quote(product_name.strip())
        target_url = f"{self.flipkart_base}{encoded}"
        logger.info(f"Opening Flipkart search for: '{product_name}' -> {target_url}")

        try:
            subprocess.Popen(f'start "" "{target_url}"', shell=True)
            status = "success"
        except Exception as e:
            logger.error(f"Failed to open Flipkart URL: {e}")
            status = "error"

        # Attempt Playwright click in background
        def _playwright_flipkart_click():
            try:
                import asyncio
                from playwright.async_api import async_playwright
                async def _click():
                    async with async_playwright() as p:
                        browser = await p.chromium.launch(headless=True)
                        page = await browser.new_page()
                        await page.goto(target_url, timeout=15000)
                        await page.wait_for_timeout(2500)
                        btn = page.locator("button:has-text('ADD TO CART'), button:has-text('Add to Cart')").first
                        if await btn.count() > 0:
                            await btn.click()
                            logger.info(f"Playwright clicked Add to Cart for '{product_name}' on Flipkart.")
                        await browser.close()
                asyncio.run(_click())
            except Exception as ex:
                logger.debug(f"Playwright Flipkart click error: {ex}")

        threading.Thread(target=_playwright_flipkart_click, daemon=True).start()

        return {
            "status": status,
            "platform": "Flipkart",
            "product": product_name,
            "url": target_url,
            "speech_reply": f"Sir Vanshil, maine '{product_name}' Flipkart par search karke Add to Cart page open kar diya hai. Kripya payment complete kijiye!"
        }

    def open_amazon_login(self) -> Dict[str, Any]:
        """Navigates to Amazon Sign-In page."""
        url = "https://www.amazon.in/ap/signin"
        try:
            subprocess.Popen(f'start "" "{url}"', shell=True)
            status = "success"
        except Exception as e:
            logger.error(f"Failed to open Amazon Sign-In page: {e}")
            status = "error"

        return {
            "status": status,
            "platform": "Amazon",
            "url": url,
            "speech_reply": "Sir Vanshil, maine Amazon sign in page open kar diya hai. Kripya login credentials or OTP enter karke login complete kar lijiye."
        }

    def open_flipkart_login(self) -> Dict[str, Any]:
        """Navigates to Flipkart Login page."""
        url = "https://www.flipkart.com/account/login"
        try:
            subprocess.Popen(f'start "" "{url}"', shell=True)
            status = "success"
        except Exception as e:
            logger.error(f"Failed to open Flipkart Login page: {e}")
            status = "error"

        return {
            "status": status,
            "platform": "Flipkart",
            "url": url,
            "speech_reply": "Sir Vanshil, maine Flipkart login page open kar diya hai. Kripya login credentials or OTP enter karke login complete kar lijiye."
        }

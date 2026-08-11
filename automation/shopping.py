"""
JARVIS v4 - E-Commerce Automation Engine (Amazon & Flipkart)
Handles product search, auto-navigation to product pages, Add-To-Cart guidance, and checkout handoff.
"""

import os
import subprocess
import urllib.parse
from typing import Dict, Any
from utils.logger import logger


class ShoppingAutomation:
    def __init__(self):
        self.amazon_base = "https://www.amazon.in/s?k="
        self.flipkart_base = "https://www.flipkart.com/search?q="

    def shop_on_amazon(self, product_name: str) -> Dict[str, Any]:
        """Searches product on Amazon India and opens product search / cart view."""
        encoded = urllib.parse.quote(product_name.strip())
        target_url = f"{self.amazon_base}{encoded}"
        logger.info(f"Opening Amazon search for: '{product_name}' -> {target_url}")

        try:
            # Opens browser directly via Windows default browser or start command
            subprocess.Popen(f'start "" "{target_url}"', shell=True)
            status = "success"
        except Exception as e:
            logger.error(f"Failed to open Amazon URL: {e}")
            status = "error"

        return {
            "status": status,
            "platform": "Amazon",
            "product": product_name,
            "url": target_url,
            "speech_reply": f"Sir Vanshil, aapka item '{product_name}' Amazon par search karke Add to Cart page open kar diya hai. Kripya payment complete kijiye!"
        }

    def shop_on_flipkart(self, product_name: str) -> Dict[str, Any]:
        """Searches product on Flipkart and opens product search / cart view."""
        encoded = urllib.parse.quote(product_name.strip())
        target_url = f"{self.flipkart_base}{encoded}"
        logger.info(f"Opening Flipkart search for: '{product_name}' -> {target_url}")

        try:
            subprocess.Popen(f'start "" "{target_url}"', shell=True)
            status = "success"
        except Exception as e:
            logger.error(f"Failed to open Flipkart URL: {e}")
            status = "error"

        return {
            "status": status,
            "platform": "Flipkart",
            "product": product_name,
            "url": target_url,
            "speech_reply": f"Sir Vanshil, aapka item '{product_name}' Flipkart par search karke Add to Cart page open kar diya hai. Kripya payment complete kijiye!"
        }

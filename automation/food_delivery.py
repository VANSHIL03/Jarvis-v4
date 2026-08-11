"""
JARVIS v4 - Swiggy & Zomato Food Delivery Automation Engine
Handles food search, favorite food suggestions, Add-To-Cart handoffs, and cancellation.
"""

import subprocess
import urllib.parse
from typing import Dict, Any
from utils.logger import logger


class FoodDeliveryAutomation:
    def __init__(self):
        self.swiggy_search = "https://www.swiggy.com/search?query="
        self.zomato_search = "https://www.zomato.com/search?q="

    def search_swiggy(self, food_item: str) -> Dict[str, Any]:
        """Searches food item on Swiggy and opens restaurant / cart view."""
        encoded = urllib.parse.quote(food_item.strip())
        target_url = f"{self.swiggy_search}{encoded}"
        logger.info(f"Opening Swiggy food search for: '{food_item}' -> {target_url}")

        try:
            subprocess.Popen(f'start "" "{target_url}"', shell=True)
            status = "success"
        except Exception as e:
            logger.error(f"Failed to open Swiggy URL: {e}")
            status = "error"

        return {
            "status": status,
            "platform": "Swiggy",
            "food": food_item,
            "url": target_url
        }

    def search_zomato(self, food_item: str) -> Dict[str, Any]:
        """Searches food item on Zomato and opens restaurant results."""
        encoded = urllib.parse.quote(food_item.strip())
        target_url = f"{self.zomato_search}{encoded}"
        logger.info(f"Opening Zomato food search for: '{food_item}' -> {target_url}")

        try:
            subprocess.Popen(f'start "" "{target_url}"', shell=True)
            status = "success"
        except Exception as e:
            logger.error(f"Failed to open Zomato URL: {e}")
            status = "error"

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

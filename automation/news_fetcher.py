"""
JARVIS v4 - Real-Time Daily News Fetcher Engine
Fetches live headlines from Google News RSS by category (Gaming, Government, Health, Tech, Sports, etc.) in Hindi or Hinglish.
"""

import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from typing import List, Dict, Any
from utils.logger import logger


class NewsFetcher:
    def __init__(self):
        self.category_keywords = {
            "gaming": "gaming esports video games",
            "government": "government politics sarkaari news",
            "politics": "politics election government",
            "health": "health medical wellness swasthya",
            "tech": "technology tech AI smartphones",
            "sports": "sports cricket football khel",
            "business": "business economy finance share market",
            "entertainment": "entertainment bollywood movies cinema"
        }

    def fetch_top_headlines(self, category: str = "general", lang: str = "hi", count: int = 4) -> List[str]:
        """Fetches category-specific real-time news headlines from Google News RSS feed."""
        headlines = []
        cat_lower = category.lower().strip()
        search_query = self.category_keywords.get(cat_lower, cat_lower) if cat_lower != "general" else ""

        if search_query:
            encoded_q = urllib.parse.quote(search_query)
            url = f"https://news.google.com/rss/search?q={encoded_q}&hl={lang}&gl=IN&ceid=IN:{lang}"
        else:
            url = f"https://news.google.com/rss?hl={lang}&gl=IN&ceid=IN:{lang}"

        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            xml_data = urllib.request.urlopen(req, timeout=5.0).read()
            root = ET.fromstring(xml_data)
            for elem in root.findall(".//item")[:count]:
                title = elem.find("title")
                if title is not None and title.text:
                    clean_title = title.text.split(" - ")[0].strip()
                    headlines.append(clean_title)
            logger.info(f"Successfully fetched {len(headlines)} headlines for category '{category}' ({lang}).")
        except Exception as e:
            logger.error(f"Failed to fetch news headlines for category '{category}': {e}")

        return headlines

    def get_hinglish_news_bulletin(self, salutation: str = "Sir Vanshil", category: str = "general", lang: str = "hi") -> Dict[str, Any]:
        """Returns category-tailored Hindi / Hinglish news bulletin."""
        headlines = self.fetch_top_headlines(category=category, lang=lang, count=4)
        cat_title = category.capitalize() if category.lower() != "general" else "Daily"

        if not headlines:
            return {
                "speech_reply": f"Ji {salutation}, abhi {cat_title} news feed reach nahi ho raha hai. Main browser mein Google News open kar raha hoon.",
                "headlines": [],
                "url": "https://news.google.com"
            }

        bulletin_lines = [f"Ji {salutation}, aaj ki main {cat_title} news headlines yeh hain:"]
        for idx, item in enumerate(headlines, 1):
            bulletin_lines.append(f"{idx}. {item}")

        bulletin_lines.append("Main browser mein Google News open kar raha hoon.")
        spoken_text = " ".join(bulletin_lines)

        encoded_q = urllib.parse.quote(category) if category.lower() != "general" else ""
        web_url = f"https://news.google.com/search?q={encoded_q}" if encoded_q else "https://news.google.com"

        return {
            "speech_reply": spoken_text,
            "headlines": headlines,
            "url": web_url
        }

"""
JARVIS v4 - Real-Time Daily News Fetcher
Fetches live headlines from Google News RSS and formats spoken Hinglish news bulletins.
"""

import urllib.request
import xml.etree.ElementTree as ET
from typing import List, Dict, Any
from utils.logger import logger


class NewsFetcher:
    def __init__(self):
        self.rss_url = "https://news.google.com/rss?hl=en-IN&gl=IN&ceid=IN:en"

    def fetch_top_headlines(self, count: int = 4) -> List[str]:
        """Fetches top real-time news headlines from Google News RSS feed."""
        headlines = []
        try:
            req = urllib.request.Request(self.rss_url, headers={"User-Agent": "Mozilla/5.0"})
            xml_data = urllib.request.urlopen(req, timeout=5.0).read()
            root = ET.fromstring(xml_data)
            for elem in root.findall(".//item")[:count]:
                title = elem.find("title")
                if title is not None and title.text:
                    # Clean source attribution suffix
                    clean_title = title.text.split(" - ")[0].strip()
                    headlines.append(clean_title)
            logger.info(f"Successfully fetched {len(headlines)} live headlines.")
        except Exception as e:
            logger.error(f"Failed to fetch news headlines: {e}")
        return headlines

    def get_hinglish_news_bulletin(self, salutation: str = "Sir Vanshil") -> Dict[str, Any]:
        """Returns structured Hinglish news bulletin with spoken reply and headlines."""
        headlines = self.fetch_top_headlines(4)
        if not headlines:
            return {
                "speech_reply": f"Ji {salutation}, abhi news feed reach nahi ho raha hai. Main browser mein Google News open kar raha hoon.",
                "headlines": []
            }

        bulletin_lines = [f"Ji {salutation}, aaj ki main daily news headlines yeh hain:"]
        for idx, item in enumerate(headlines, 1):
            bulletin_lines.append(f"{idx}. {item}")

        bulletin_lines.append("Main browser mein Google News open kar raha hoon.")
        spoken_text = " ".join(bulletin_lines)

        return {
            "speech_reply": spoken_text,
            "headlines": headlines
        }

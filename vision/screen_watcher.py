"""
JARVIS v4 - Real-Time Autonomous Screen Perception & Vision Companion Engine
Continuously monitors user's active screen, active window title, and visible text/errors.
"""

import time
import threading
from typing import Dict, Any, Optional, Callable
from PIL import ImageGrab
from vision.ocr import ScreenOCR
from utils.logger import logger


class ScreenWatcher:
    def __init__(self, ocr_engine: Optional[ScreenOCR] = None):
        self.ocr = ocr_engine or ScreenOCR()
        self._running = False
        self._last_analysis = {}
        self._analysis_callback: Optional[Callable[[Dict[str, Any]], None]] = None

    def set_callback(self, callback: Callable[[Dict[str, Any]], None]):
        self._analysis_callback = callback

    def get_active_window_title(self) -> str:
        """Returns the title of the user's currently focused foreground window."""
        try:
            import ctypes
            hwnd = ctypes.windll.user32.GetForegroundWindow()
            length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
            buff = ctypes.create_unicode_buffer(length + 1)
            ctypes.windll.user32.GetWindowTextW(hwnd, buff, length + 1)
            return buff.value or "Desktop"
        except Exception:
            return "Desktop"

    def analyze_current_screen(self) -> Dict[str, Any]:
        """Captures screen, extracts window title, and runs OCR to understand user state."""
        window_title = self.get_active_window_title()
        ocr_text = self.ocr.extract_text_from_screen()

        # Categorize user activity
        activity = "General Desktop Activity"
        w_lower = window_title.lower()
        if any(k in w_lower for k in ["code", "visual studio", "pycharm", "sublime", "notepad++", "git"]):
            activity = "Coding & Development"
        elif any(k in w_lower for k in ["chrome", "edge", "firefox", "browser"]):
            activity = "Web Browsing"
        elif any(k in w_lower for k in ["youtube", "vlc", "spotify", "netflix"]):
            activity = "Media Playback"
        elif any(k in w_lower for k in ["game", "steam", "valorant", "gta", "minecraft"]):
            activity = "Gaming Session"
        elif any(k in w_lower for k in ["word", "excel", "powerpoint", "document", "pdf"]):
            activity = "Document Editing"

        summary = {
            "window_title": window_title,
            "activity": activity,
            "ocr_text": ocr_text[:600] if ocr_text else "",
            "timestamp": time.time()
        }
        self._last_analysis = summary
        logger.info(f"Screen Analysis: Active Window='{window_title}', Activity='{activity}'")
        return summary

    def get_screen_speech_summary(self, salutation: str = "Sir Vanshil") -> str:
        """Generates natural human-like speech description of what JARVIS sees on screen."""
        res = self.analyze_current_screen()
        w_title = res["window_title"]
        act = res["activity"]
        text_snippet = res["ocr_text"]

        if act == "Coding & Development":
            if any(e in text_snippet.lower() for e in ["error", "exception", "failed", "traceback", "syntaxerror"]):
                return f"Ji {salutation}, main dekh sakta hoon aap '{w_title}' mein code kar rahe hain aur screen par error traceback dikh raha hai. Kya main ise fix karne mein aapki madad karoon?"
            return f"Ji {salutation}, main dekh sakta hoon aap '{w_title}' mein code kar rahe hain. Main aapke code aur functions ko optimize kar sakta hoon!"

        elif act == "Gaming Session":
            return f"Ji {salutation}, main dekh raha hoon aap '{w_title}' game khel rahe hain. System performance aur GPU FPS nominal hain, enjoy your gaming session!"

        elif act == "Web Browsing":
            return f"Ji {salutation}, main dekh sakta hoon aap browser par '{w_title}' view kar rahe hain. Bataiye main is baare mein kya information search karoon?"

        return f"Ji {salutation}, main aapke screen par '{w_title}' dekh raha hoon. Main aapki kya help kar sakta hoon?"

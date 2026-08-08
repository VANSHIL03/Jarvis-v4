"""
JARVIS v4 - Keyboard & Mouse Input Automation
Uses PyAutoGUI, PIL, and PyWinAuto for desktop automation.
"""

import os
import time
from datetime import datetime
from typing import Optional, Tuple
from utils.logger import logger

try:
    import pyautogui
    pyautogui.FAILSAFE = True
    pyautogui.PAUSE = 0.1
except ImportError:
    pyautogui = None
    logger.warning("pyautogui not installed. Input automation running in simulation mode.")

class InputControl:
    def type_text(self, text: str, interval: float = 0.02):
        """Types out string sequence like a human typist."""
        logger.info(f"Auto-typing text: '{text[:30]}...'")
        if pyautogui:
            pyautogui.write(text, interval=interval)

    def press_key(self, key_name: str):
        """Presses a single key (e.g. 'enter', 'tab', 'escape')."""
        if pyautogui:
            pyautogui.press(key_name)

    def press_hotkey(self, *keys):
        """Executes hotkey combination (e.g. 'ctrl', 'c' or 'win', 'r')."""
        logger.info(f"Hotkey combination: {keys}")
        if pyautogui:
            pyautogui.hotkey(*keys)

    def mouse_click(self, x: Optional[int] = None, y: Optional[int] = None, button: str = "left", clicks: int = 1):
        """Performs mouse click at current or specified screen coordinates."""
        if pyautogui:
            if x is not None and y is not None:
                pyautogui.click(x=x, y=y, button=button, clicks=clicks)
            else:
                pyautogui.click(button=button, clicks=clicks)

    def take_screenshot(self, output_path: Optional[str] = None) -> str:
        """Takes full screen capture, saves image in Pictures/Screenshots, and opens viewer."""
        try:
            from PIL import ImageGrab
            screenshots_dir = os.path.join(os.path.expanduser("~"), "Pictures", "Screenshots")
            os.makedirs(screenshots_dir, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_name = f"JARVIS_Screenshot_{timestamp}.png"
            full_path = output_path or os.path.join(screenshots_dir, file_name)

            img = ImageGrab.grab()
            img.save(full_path)
            logger.info(f"Screenshot saved to: {full_path}")
            
            # Automatically open screenshot in Windows Photos viewer
            os.startfile(full_path)
            return full_path
        except Exception as e:
            logger.error(f"Error taking screenshot: {e}")
            return ""

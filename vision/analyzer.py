"""
JARVIS v4 - Multimodal Screen & Scene Analyzer
"""

from typing import Dict, Any
from vision.camera import CameraFeed
from vision.ocr import ScreenOCR
from utils.logger import logger

class VisionAnalyzer:
    def __init__(self):
        self.camera = CameraFeed()
        self.ocr = ScreenOCR()

    def analyze_workspace(self) -> Dict[str, Any]:
        """Provides complete visual context of screen text and webcam presence."""
        screen_text = self.ocr.extract_text_from_screen()
        camera_summary = self.camera.describe_scene()

        return {
            "screen_text_summary": screen_text[:500] if screen_text else "No screen text detected",
            "camera_status": camera_summary.get("status"),
            "user_present": camera_summary.get("face_count", 0) > 0,
            "face_count": camera_summary.get("face_count", 0)
        }

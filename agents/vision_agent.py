"""
JARVIS v4 - Vision & Multimodal Agent
"""

from typing import Dict, Any
from agents.base_agent import BaseAgent
from vision.analyzer import VisionAnalyzer

class VisionAgent(BaseAgent):
    def __init__(self, vision_analyzer: VisionAnalyzer):
        self.vision = vision_analyzer

    @property
    def agent_name(self) -> str:
        return "vision_agent"

    @property
    def description(self) -> str:
        return "Handles webcam camera feed, facial recognition, screen OCR reading, and image analysis."

    async def execute_task(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        action = action.lower()
        if action == "analyze_workspace":
            result = self.vision.analyze_workspace()
            return {"status": "success", "workspace_summary": result}

        elif action == "read_screen_ocr":
            text = self.vision.ocr.extract_text_from_screen()
            return {"status": "success", "ocr_text": text}

        elif action == "detect_faces":
            faces = self.vision.camera.detect_faces()
            return {"status": "success", "faces_count": len(faces), "faces": faces}

        return {"status": "error", "message": f"Unknown vision action: '{action}'"}

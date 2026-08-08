"""
JARVIS v4 - OpenCV Camera Feed & Facial Recognition
"""

import cv2
import numpy as np
from typing import Dict, Any, Optional, List
from config.settings import settings
from utils.logger import logger

class CameraFeed:
    def __init__(self, camera_index: int = None):
        self.camera_index = camera_index if camera_index is not None else settings.WEBCAM_INDEX
        self.face_cascade = None
        try:
            if hasattr(cv2, "CascadeClassifier") and hasattr(cv2, "data"):
                cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
                self.face_cascade = cv2.CascadeClassifier(cascade_path)
                logger.info("OpenCV Haar cascade face classifier loaded.")
        except Exception as e:
            logger.warning(f"Face cascade classifier initialization failed ({e}). Camera feed active without face detection.")

    def capture_frame(self) -> Optional[np.ndarray]:
        """Captures a single frame from webcam."""
        try:
            cap = cv2.VideoCapture(self.camera_index)
            if not cap.isOpened():
                logger.warning(f"Webcam at index {self.camera_index} cannot be opened.")
                return None

            ret, frame = cap.read()
            cap.release()
            return frame if ret else None
        except Exception as e:
            logger.error(f"Error capturing camera frame: {e}")
            return None

    def detect_faces(self, frame: Optional[np.ndarray] = None) -> List[Dict[str, int]]:
        """Detects faces in frame and returns bounding box coordinates."""
        if not self.face_cascade:
            return []

        if frame is None:
            frame = self.capture_frame()
            if frame is None:
                return []

        try:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = self.face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))
            return [{"x": int(x), "y": int(y), "w": int(w), "h": int(h)} for (x, y, w, h) in faces]
        except Exception as e:
            logger.error(f"Error detecting faces: {e}")
            return []

    def describe_scene(self) -> Dict[str, Any]:
        """Analyzes camera feed scene."""
        frame = self.capture_frame()
        if frame is None:
            return {"status": "camera_unavailable", "face_count": 0}

        faces = self.detect_faces(frame)
        h, w, _ = frame.shape
        return {
            "status": "active",
            "resolution": f"{w}x{h}",
            "face_count": len(faces),
            "faces": faces
        }

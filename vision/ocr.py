"""
JARVIS v4 - Screen Capture & Optical Character Recognition (EasyOCR)
"""

import numpy as np
from PIL import ImageGrab
from typing import List, Dict, Any, Optional
from utils.logger import logger

class ScreenOCR:
    def __init__(self):
        self.reader = None
        self._init_reader()

    def _init_reader(self):
        try:
            import easyocr
            self.reader = easyocr.Reader(['en'], gpu=True)
            logger.info("EasyOCR initialized with GPU acceleration.")
        except Exception as e:
            logger.warning(f"EasyOCR GPU init failed ({e}). OCR fallback active.")

    def capture_screen(self, bbox: Optional[tuple] = None) -> np.ndarray:
        """Captures primary display screen or region safely."""
        try:
            img = ImageGrab.grab(bbox=bbox)
            return np.array(img)
        except Exception as e:
            logger.warning(f"Screen capture failed ({e}). Returning empty image buffer.")
            return np.zeros((100, 100, 3), dtype=np.uint8)

    def extract_text_from_screen(self, bbox: Optional[tuple] = None) -> str:
        """Extracts text from full screen or specified region."""
        img_np = self.capture_screen(bbox=bbox)

        if self.reader:
            try:
                results = self.reader.readtext(img_np, detail=0)
                return " ".join(results)
            except Exception as e:
                logger.error(f"EasyOCR extraction error: {e}")

        # Tesseract fallback attempt
        try:
            import pytesseract
            from PIL import Image
            img_pil = Image.fromarray(img_np)
            return pytesseract.image_to_string(img_pil).strip()
        except Exception:
            return "[OCR text extraction unavailable]"

    def locate_text_on_screen(self, target_text: str) -> Optional[Dict[str, int]]:
        """Locates screen coordinates of a specific word or phrase."""
        img_np = self.capture_screen()
        if not self.reader:
            return None

        try:
            results = self.reader.readtext(img_np)
            for bbox, text, prob in results:
                if target_text.lower() in text.lower():
                    # bbox: [[x1, y1], [x2, y1], [x2, y2], [x1, y2]]
                    center_x = int((bbox[0][0] + bbox[1][0]) / 2)
                    center_y = int((bbox[0][1] + bbox[2][1]) / 2)
                    return {"x": center_x, "y": center_y, "matched_text": text, "confidence": float(prob)}
        except Exception as e:
            logger.error(f"Error locating text on screen: {e}")

        return None

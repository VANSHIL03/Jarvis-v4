"""
JARVIS v4 - Computer Vision & OCR Document Analysis Module
Extracts text from images, offer letters, certificates, and documents using PIL + Tesseract OCR and LLM reasoning.
"""

import os
from pathlib import Path
from typing import Dict, Any, Optional
from PIL import Image, ImageEnhance, ImageFilter
from ai.llm_client import LocalLLMClient
from utils.logger import logger

try:
    import pytesseract
except ImportError:
    pytesseract = None
    logger.warning("pytesseract package not found.")


class VisionAnalyzer:
    def __init__(self, llm_client: Optional[LocalLLMClient] = None):
        self.llm = llm_client or LocalLLMClient()

    def _preprocess_image(self, image_path: str) -> Image.Image:
        """Preprocesses image with contrast enhancement and grayscale for clean OCR."""
        img = Image.open(image_path)
        if img.mode != 'L':
            img = img.convert('L')
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(1.8)
        return img

    def extract_text(self, image_path: str) -> str:
        """Extracts plain text content from image or document file using Tesseract OCR."""
        if not os.path.exists(image_path):
            logger.error(f"Image file not found: {image_path}")
            return ""

        if not pytesseract:
            logger.warning("pytesseract unavailable for OCR text extraction.")
            return f"Image file attached: '{Path(image_path).name}'."

        try:
            img = self._preprocess_image(image_path)
            extracted = pytesseract.image_to_string(img)
            text = extracted.strip()
            if not text:
                raw_img = Image.open(image_path)
                text = pytesseract.image_to_string(raw_img).strip()

            logger.info(f"Extracted {len(text)} characters of OCR text from '{Path(image_path).name}'.")
            return text
        except Exception as e:
            logger.warning(f"OCR extraction exception ({e}). Returning filename.")
            return f"Document/Image file: '{Path(image_path).name}'."

    async def analyze_image_with_prompt(
        self,
        image_path: str,
        user_prompt: str,
        action_type: str = "analyze"
    ) -> Dict[str, Any]:
        """Analyzes uploaded image/document using OCR text extraction + LLM reasoning."""
        ocr_text = self.extract_text(image_path)
        file_name = Path(image_path).name

        system_prompt = (
            "You are JARVIS, an elite AI assistant equipped with computer vision and document OCR capabilities. "
            "Analyze the provided image text and fulfill the user's specific request with precision and clarity."
        )

        full_prompt = (
            f"Uploaded File: {file_name}\n\n"
            f"Extracted Document Text:\n```\n{ocr_text if ocr_text else 'Image file attached (no plain text OCR extracted).'}\n```\n\n"
            f"User Instructions: {user_prompt}\n\n"
            "Provide a comprehensive, professional analysis or response based on the document content."
        )

        response_text = await self.llm.generate_response(prompt=full_prompt, system_prompt=system_prompt)
        return {
            "status": "success",
            "image_path": image_path,
            "ocr_text": ocr_text,
            "analysis": response_text
        }

    async def generate_linkedin_post_from_document(
        self,
        image_path: str,
        user_prompt: str
    ) -> Dict[str, Any]:
        """Extracts offer letter/certificate details and generates an inspiring, high-impact LinkedIn post."""
        ocr_text = self.extract_text(image_path)
        file_name = Path(image_path).name

        system_prompt = (
            "You are a professional personal branding strategist and career advisor. "
            "Generate an engaging, inspiring, and polished LinkedIn announcement post for an offer letter, "
            "internship/job offer, or certification document. Include relevant emojis, hashtags, and professional gratitude."
        )

        prompt = (
            f"Document File: {file_name}\n"
            f"Document OCR Content:\n```\n{ocr_text}\n```\n\n"
            f"User Request: {user_prompt}\n\n"
            "Generate a complete, ready-to-publish LinkedIn post announcement. "
            "Highlight the achievement, company/role (if visible), key excitement, and gratitude."
        )

        post_content = await self.llm.generate_response(prompt=prompt, system_prompt=system_prompt)

        # Fallback template if LLM is offline
        if "offline standby mode" in post_content or not post_content.strip():
            post_content = (
                "🚀 Excited to share a new milestone!\n\n"
                "I am thrilled to announce that I have received a new opportunity! "
                "Looking forward to learning, growing, and making a meaningful impact in this next chapter. "
                "Grateful to everyone who supported me along the way! 💡✨\n\n"
                "#NewBeginnings #CareerGrowth #Achievement #Gratitude #ProfessionalJourney"
            )

        return {
            "status": "success",
            "image_path": image_path,
            "post_content": post_content,
            "ocr_text": ocr_text
        }

"""
JARVIS v4 - Vision & Image Analysis Agent
Processes screenshots, photos, offer letters, and documents to generate descriptions, summaries, and social media posts.
"""

from typing import Dict, Any
from agents.base_agent import BaseAgent
from ai.vision import VisionAnalyzer
from plugins.linkedin_plugin import LinkedInPlugin
from utils.logger import logger


class VisionAgent(BaseAgent):
    def __init__(self, vision_analyzer: VisionAnalyzer = None):
        self.vision = vision_analyzer or VisionAnalyzer()
        self.linkedin_plugin = LinkedInPlugin()
        # Screen OCR and the webcam are built on first use: EasyOCR loads a GPU
        # model and cv2 opens a device, neither of which should happen just
        # because JARVIS started.
        self._ocr = None
        self._camera_feed = None

    @property
    def agent_name(self) -> str:
        return "vision_agent"

    @property
    def description(self) -> str:
        return "Analyzes uploaded screenshots, offer letters, documents, and photos to generate descriptions, summaries, and automated posts."

    async def _get_fresh_vision(self) -> VisionAnalyzer:
        """Returns fresh VisionAnalyzer instance dynamically to bypass stale bytecode caches."""
        from ai.vision import VisionAnalyzer
        return VisionAnalyzer()

    def _screen_ocr(self):
        """
        Lazily constructs the screen OCR reader.

        An injected workspace analyzer already owns a ScreenOCR; reusing it
        matters on a 6 GB GPU, where a second EasyOCR reader would duplicate the
        model in VRAM.
        """
        if self._ocr is None:
            existing = getattr(self.vision, "ocr", None)
            if existing is not None and hasattr(existing, "extract_text_from_screen"):
                self._ocr = existing
            else:
                from vision.ocr import ScreenOCR
                self._ocr = ScreenOCR()
        return self._ocr

    def _camera(self):
        """Lazily constructs the webcam feed, reusing the analyzer's if it has one."""
        if self._camera_feed is None:
            existing = getattr(self.vision, "camera", None)
            if existing is not None and hasattr(existing, "capture_frame"):
                self._camera_feed = existing
            else:
                from vision.camera import CameraFeed
                self._camera_feed = CameraFeed()
        return self._camera_feed

    @staticmethod
    def _capture_dir():
        from config.settings import settings
        out = settings.DATA_DIR / "captures"
        out.mkdir(parents=True, exist_ok=True)
        return out

    def _save_frame(self, frame, prefix: str) -> str:
        """Writes a numpy frame to data/captures and returns the path."""
        import time as _time
        path = self._capture_dir() / f"{prefix}_{int(_time.time())}.png"
        try:
            import cv2
            cv2.imwrite(str(path), frame)
        except Exception:
            from PIL import Image
            Image.fromarray(frame).save(str(path))
        return str(path)

    async def execute_task(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        action = action.lower()

        # ---- live screen / webcam actions: these have no attached image ----
        if action in ["read_screen", "read_my_screen", "screen_text", "ocr_screen"]:
            try:
                text = self._screen_ocr().extract_text_from_screen()
            except Exception as e:
                logger.error(f"read_screen failed: {e}")
                return {
                    "status": "error",
                    "message": str(e),
                    "speech_reply": "Sir, screen padhne me problem aa gayi.",
                }
            text = (text or "").strip()
            if not text or text.startswith("[OCR"):
                return {
                    "status": "error",
                    "text": text,
                    "message": "No readable text found on screen.",
                    "speech_reply": "Sir, screen par mujhe koi readable text nahi mila.",
                }
            return {
                "status": "success",
                "text": text,
                "chars": len(text),
                "speech_reply": f"Sir, screen par ye likha hai: {text[:300]}",
            }

        elif action in ["describe_screen", "what_is_on_my_screen", "explain_screen"]:
            prompt = params.get("user_prompt") or params.get("prompt") or (
                "Describe what is currently on this Windows screen, and what the "
                "user appears to be doing."
            )
            try:
                frame = self._screen_ocr().capture_screen()
                shot = self._save_frame(frame, "screen")
            except Exception as e:
                logger.error(f"Screen capture for describe_screen failed: {e}")
                return {
                    "status": "error",
                    "message": str(e),
                    "speech_reply": "Sir, screen capture nahi ho payi.",
                }

            vision = self.vision
            if not hasattr(vision, "analyze_image_with_prompt"):
                vision = await self._get_fresh_vision()
                self.vision = vision

            description = ""
            try:
                res = await vision.analyze_image_with_prompt(shot, prompt)
                description = res.get("analysis", res.get("description", ""))
            except Exception as e:
                logger.warning(f"Vision model unavailable for describe_screen ({e}); using OCR only.")

            if not description:
                ocr_text = self._screen_ocr().extract_text_from_screen()
                description = f"Screen text: {(ocr_text or '').strip()[:1500]}"

            return {
                "status": "success",
                "image_path": shot,
                "description": description,
                "message": description,
                "speech_reply": f"Sir, aapki screen par ye chal raha hai: {description[:250]}",
            }

        elif action in ["locate_text", "find_on_screen", "locate_on_screen"]:
            target = params.get("text") or params.get("target_text") or params.get("query") or ""
            if not target:
                return {
                    "status": "error",
                    "message": "No text given to locate.",
                    "speech_reply": "Sir, screen par kya dhoondhna hai wo bataiye.",
                }
            try:
                hit = self._screen_ocr().locate_text_on_screen(target)
            except Exception as e:
                logger.error(f"locate_text failed: {e}")
                return {"status": "error", "message": str(e)}
            if not hit:
                return {
                    "status": "not_found",
                    "target": target,
                    "message": f"'{target}' not found on screen.",
                    "speech_reply": f"Sir, screen par '{target}' nahi mila.",
                }
            return {
                "status": "success",
                "target": target,
                "location": hit,
                "speech_reply": (
                    f"Ji Sir, '{hit.get('matched_text', target)}' mil gaya - "
                    f"x {hit.get('x')}, y {hit.get('y')} par."
                ),
            }

        elif action in ["webcam_capture", "take_photo", "capture_webcam", "camera_capture"]:
            frame = self._camera().capture_frame()
            if frame is None:
                return {
                    "status": "error",
                    "message": "Webcam unavailable or blocked.",
                    "speech_reply": "Sir, webcam access nahi ho raha - kya wo kisi aur app me use ho raha hai?",
                }
            try:
                saved = self._save_frame(frame, "webcam")
            except Exception as e:
                logger.error(f"Failed to save webcam frame: {e}")
                return {"status": "error", "message": str(e)}
            faces = self._camera().detect_faces(frame)
            return {
                "status": "success",
                "image_path": saved,
                "path": saved,
                "face_count": len(faces),
                "speech_reply": f"Ji Sir, photo le liya hai: {saved}",
            }

        image_path = params.get("image_path", params.get("file_path", ""))
        user_prompt = params.get("user_prompt", params.get("prompt", "Analyze this screenshot and describe its contents."))

        if not image_path:
            return {
                "status": "error",
                "speech_reply": "Sir, kripya pehle koi screenshot ya photo attach karein.",
                "message": "No image path provided."
            }

        vision = self.vision
        if not hasattr(vision, "analyze_image_with_prompt") or not hasattr(vision, "generate_linkedin_post_from_document"):
            vision = await self._get_fresh_vision()
            self.vision = vision

        if action in ["analyze_screenshot", "describe_image", "analyze_photo", "analyze_image"]:
            if hasattr(vision, "analyze_image_with_prompt"):
                res = await vision.analyze_image_with_prompt(image_path, user_prompt)
            else:
                ocr = vision.extract_text(image_path) if hasattr(vision, "extract_text") else ""
                res = {"analysis": f"Attached screenshot: {image_path}. Extracted OCR: {ocr}"}

            description = res.get("analysis", res.get("description", ""))
            speech = f"Ji Sir, maine aapke screenshot ko analyze kar liya hai. Yeh raha aapka description: {description[:180]}..."
            return {
                "status": "success",
                "image_path": image_path,
                "description": description,
                "speech_reply": speech,
                "message": description
            }

        elif action in ["generate_linkedin_post", "create_linkedin_description", "post_offer_letter"]:
            if hasattr(vision, "generate_linkedin_post_from_document"):
                res = await vision.generate_linkedin_post_from_document(image_path, user_prompt)
            elif hasattr(vision, "generate_linkedin_post"):
                res = await vision.generate_linkedin_post(image_path, user_prompt)
            elif hasattr(vision, "analyze_image_with_prompt"):
                res = await vision.analyze_image_with_prompt(image_path, f"Generate a LinkedIn post description for this document: {user_prompt}")
                res["post_content"] = res.get("analysis", "")
            else:
                fresh = await self._get_fresh_vision()
                res = await fresh.generate_linkedin_post_from_document(image_path, user_prompt)

            post_content = res.get("post_content", res.get("analysis", res.get("description", "")))

            # Trigger LinkedIn browser share composer
            plugin_res = self.linkedin_plugin.execute("post_update", {"text": post_content})

            speech = "Ji Sir, maine aapke screenshot ka LinkedIn post description write karke image aur text dono ko Clipboard me copy kar diya hai, aur LinkedIn share composer open kar diya hai!"
            return {
                "status": "success",
                "image_path": image_path,
                "description": post_content,
                "speech_reply": speech,
                "message": post_content,
                "browser_opened": plugin_res.get("status") == "success"
            }

        return {"status": "error", "message": f"Unknown vision action: '{action}'"}

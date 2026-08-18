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

    @property
    def agent_name(self) -> str:
        return "vision_agent"

    @property
    def description(self) -> str:
        return "Analyzes uploaded screenshots, offer letters, documents, and photos to generate descriptions, summaries, and automated posts."

    async def execute_task(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        action = action.lower()
        image_path = params.get("image_path", params.get("file_path", ""))
        user_prompt = params.get("user_prompt", params.get("prompt", "Analyze this screenshot and describe its contents."))

        if not image_path:
            return {
                "status": "error",
                "speech_reply": "Sir, kripya pehle koi screenshot ya photo attach karein.",
                "message": "No image path provided."
            }

        if action in ["analyze_screenshot", "describe_image", "analyze_photo", "analyze_image"]:
            res = await self.vision.analyze_image_with_prompt(image_path, user_prompt)
            description = res.get("analysis", "")
            speech = f"Ji Sir, maine aapke screenshot ko analyze kar liya hai. Yeh raha aapka description: {description[:180]}..."
            return {
                "status": "success",
                "image_path": image_path,
                "description": description,
                "speech_reply": speech,
                "message": description
            }

        elif action in ["generate_linkedin_post", "create_linkedin_description", "post_offer_letter"]:
            res = await self.vision.generate_linkedin_post_from_document(image_path, user_prompt)
            post_content = res.get("post_content", "")

            # Trigger LinkedIn browser share composer
            plugin_res = self.linkedin_plugin.execute("post_update", {"text": post_content})

            speech = "Ji Sir, maine aapke screenshot ka LinkedIn post description write kar diya hai aur LinkedIn share composer browser me open kar diya hai!"
            return {
                "status": "success",
                "image_path": image_path,
                "description": post_content,
                "speech_reply": speech,
                "message": post_content,
                "browser_opened": plugin_res.get("status") == "success"
            }

        return {"status": "error", "message": f"Unknown vision action: '{action}'"}

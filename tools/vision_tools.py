"""
JARVIS v4 - Vision Tools

Screen reading, screen description, image analysis, on-screen text location and
webcam capture -- all bound to the existing VisionAgent, which reuses the already
loaded EasyOCR reader rather than building a second one (a 6 GB GPU cannot afford
two copies of the model).

Levels here are about privacy rather than damage. Reading the screen or an image
touches whatever personal data happens to be in view, so those sit at LOW_RISK:
auto-allowed, but explicitly marked, and raising them in permissions.json makes
JARVIS ask. webcam_capture is SENSITIVE and always asks -- switching a camera on
is a boundary that should never be crossed silently, however the request was
phrased.

locate_text exists so automation can find a button by its label instead of
clicking a memorised coordinate, which is what Section 12 asks for.
"""

from __future__ import annotations

from typing import List

from security.permissions import PermissionLevel as P
from tools.base import ToolParam, ToolSpec

CATEGORY = "vision"

_PROMPT = ToolParam(
    "prompt", "string", default="",
    description="What to look for or explain (optional).",
)
_PROMPT_ALIASES = {"user_prompt": "prompt", "question": "prompt", "instruction": "prompt", "query": "prompt"}

_IMAGE = ToolParam(
    "image_path", "string", required=True,
    description="Path to the image or screenshot file.",
)
_IMAGE_ALIASES = {"path": "image_path", "file_path": "image_path", "image": "image_path", "photo": "image_path"}


VISION_TOOLS: List[ToolSpec] = [
    ToolSpec(
        name="read_screen",
        description="Read the text currently visible on screen using OCR.",
        permission=P.LOW_RISK,
        category=CATEGORY,
        agent="vision_agent",
        action="read_screen",
        confirm_template="Sir, screen ka text padh loon? Haan ya na bataiye.",
        legacy_actions=("read_my_screen", "screen_text", "ocr_screen", "read_display"),
    ),
    ToolSpec(
        name="describe_screen",
        description="Look at the screen and explain what is happening on it.",
        permission=P.LOW_RISK,
        category=CATEGORY,
        agent="vision_agent",
        action="describe_screen",
        parameters=(_PROMPT,),
        aliases=_PROMPT_ALIASES,
        confirm_template="Sir, screen dekh kar bata doon kya chal raha hai? Haan ya na bataiye.",
        legacy_actions=("what_is_on_my_screen", "explain_screen", "see_screen"),
    ),
    ToolSpec(
        name="analyze_image",
        description="Analyse an image or screenshot file and describe its contents.",
        permission=P.LOW_RISK,
        category=CATEGORY,
        agent="vision_agent",
        action="analyze_image",
        parameters=(_IMAGE, _PROMPT),
        aliases={**_IMAGE_ALIASES, **_PROMPT_ALIASES},
        confirm_template="Sir, '{image_path}' analyze kar doon? Haan ya na bataiye.",
        legacy_actions=("analyze_screenshot", "describe_image", "analyze_photo", "read_image"),
    ),
    ToolSpec(
        name="locate_text",
        description="Find where a piece of text appears on screen and return its coordinates.",
        permission=P.SAFE,
        category=CATEGORY,
        agent="vision_agent",
        action="locate_text",
        parameters=(
            ToolParam("text", "string", required=True, description="Text or label to find on screen."),
        ),
        aliases={"target_text": "text", "query": "text", "label": "text", "target": "text"},
        legacy_actions=("find_on_screen", "locate_on_screen", "find_text"),
    ),
    ToolSpec(
        name="webcam_capture",
        description="Take a photo with the webcam and report how many faces are in it.",
        permission=P.SENSITIVE,
        category=CATEGORY,
        agent="vision_agent",
        action="webcam_capture",
        confirm_template="Sir, webcam on karke photo le loon? Haan ya na bataiye.",
        legacy_actions=("take_photo", "capture_webcam", "camera_capture", "click_photo"),
    ),
    ToolSpec(
        name="generate_linkedin_post",
        description=(
            "Turn a document or screenshot (offer letter, certificate) into a "
            "LinkedIn post draft and open the share composer with it."
        ),
        permission=P.LOW_RISK,
        category=CATEGORY,
        agent="vision_agent",
        action="generate_linkedin_post",
        parameters=(_IMAGE, _PROMPT),
        aliases={**_IMAGE_ALIASES, **_PROMPT_ALIASES},
        confirm_template="Sir, is document se LinkedIn post banaun? Haan ya na bataiye.",
        legacy_actions=("create_linkedin_description", "post_offer_letter", "linkedin_post"),
    ),
]

__all__ = ["VISION_TOOLS"]

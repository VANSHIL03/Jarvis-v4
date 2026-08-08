"""
JARVIS v4 - Security & Safety Confirmation Interceptor
Prevents unauthorized or accidental execution of dangerous system operations.
"""

from typing import Dict, Any, Callable, Optional
from config.settings import settings
from utils.logger import logger

class SafetyManager:
    def __init__(self):
        self.dangerous_keywords = settings.DANGEROUS_COMMAND_KEYWORDS
        self.confirmation_callback: Optional[Callable[[str], bool]] = None

    def set_confirmation_callback(self, callback: Callable[[str], bool]):
        """Registers UI or voice confirmation dialog callback."""
        self.confirmation_callback = callback

    def is_dangerous_action(self, action_name: str, params: Dict[str, Any]) -> bool:
        """Determines if a requested sub-agent action involves destructive parameters."""
        action_str = f"{action_name} {params}".lower().replace("_", " ")
        for kw in self.dangerous_keywords:
            if kw.lower() in action_str:
                return True
        return False

    def check_and_confirm(self, action_name: str, params: Dict[str, Any]) -> bool:
        """Evaluates safety rules and prompts user if action is deemed dangerous."""
        if not settings.SAFETY_CONFIRMATION_REQUIRED:
            return True

        if not self.is_dangerous_action(action_name, params):
            return True

        warning_msg = f"Action '{action_name}' with parameters {params} requires confirmation."
        logger.warning(f"SECURITY GUARD TRIGGERED: {warning_msg}")

        if self.confirmation_callback:
            approved = self.confirmation_callback(warning_msg)
            logger.info(f"User confirmation result: {'APPROVED' if approved else 'REJECTED'}")
            return approved

        # Console fallback
        print(f"\n[SECURITY WARNING] {warning_msg}")
        resp = input("Type 'YES' to authorize execution: ").strip()
        return resp.upper() == "YES"

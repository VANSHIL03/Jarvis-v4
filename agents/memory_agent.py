"""
JARVIS v4 - Memory Agent
"""

from typing import Dict, Any
from agents.base_agent import BaseAgent
from memory.memory_manager import MemoryManager

class MemoryAgent(BaseAgent):
    def __init__(self, memory_manager: MemoryManager):
        self.memory = memory_manager

    @property
    def agent_name(self) -> str:
        return "memory_agent"

    @property
    def description(self) -> str:
        return "Manages database persistence, semantic vector memory search, user facts, and self-learning corrections."

    async def execute_task(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        action = action.lower()
        if action in ["store_fact", "update_user_preference", "set_fact", "update_fact"]:
            key = params.get("key") or params.get("key_name") or params.get("preference_name") or "user_preference"
            val = params.get("value") or params.get("value_data") or params.get("preference_value") or ""
            cat = params.get("category", "user")
            self.memory.store_user_fact(key, val, cat)
            return {"status": "success", "message": f"Stored fact {key} = {val}"}

        elif action == "store_correction":
            trigger = params.get("trigger", "")
            wrong = params.get("wrong", "")
            corrected = params.get("corrected", "")
            self.memory.store_correction(trigger, wrong, corrected)
            return {"status": "success", "message": f"Correction registered for '{trigger}'"}

        elif action == "retrieve_memory":
            query = params.get("query", "")
            memories = self.memory.retrieve_relevant_memory(query)
            return {"status": "success", "memories": memories}

        elif action == "get_dialogue_history":
            turns = params.get("turns", 6)
            history = self.memory.get_dialogue_context(turns=turns)
            return {"status": "success", "history": history}

        return {"status": "error", "message": f"Unknown memory action: '{action}'"}

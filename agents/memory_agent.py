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
            res = self.memory.store_user_fact(key, val, cat)
            # store_user_fact refuses credentials outright (Section 6). Reporting
            # that as a success would tell the user a password was saved.
            if not res.get("stored", False):
                return {
                    "status": "error",
                    "reason": res.get("reason", "refused"),
                    "message": f"Fact '{key}' store nahi kiya gaya.",
                    "speech_reply": res.get("speech_reply", ""),
                }
            return {
                "status": "success",
                "key": res.get("key", key),
                "category": res.get("category", cat),
                "message": f"Stored fact {key} = {val}",
            }

        elif action in ["remember", "remember_this", "save_memory"]:
            text = params.get("text") or params.get("value") or params.get("fact") or ""
            res = self.memory.remember(
                text,
                category=params.get("category"),
                explicit=bool(params.get("explicit", True)),
            )
            return {
                "status": "success" if res.get("stored") else "error",
                "reason": res.get("reason", ""),
                "key": res.get("key", ""),
                "category": res.get("category", ""),
                "speech_reply": res.get("speech_reply", ""),
                "message": "" if res.get("stored") else f"Not stored ({res.get('reason', 'refused')}).",
            }

        elif action in ["recall", "what_do_you_remember", "remember_about"]:
            query = params.get("query") or params.get("topic") or ""
            res = self.memory.recall(query, top_k=int(params.get("top_k", 5) or 5))
            return {"status": "success", **res}

        elif action in ["list_memories", "show_memories", "list_all_memories"]:
            res = self.memory.list_memories(
                mask_sensitive=bool(params.get("mask_sensitive", True))
            )
            return {"status": "success", **res}

        elif action in ["forget_about", "forget_topic", "forget_everything_about"]:
            topic = params.get("topic") or params.get("query") or ""
            res = self.memory.forget_about(topic)
            return {
                "status": "success" if res.get("deleted") else "not_found",
                **res,
            }

        elif action in ["forget", "forget_this", "forget_last", "forget_key"]:
            key = params.get("key") or params.get("key_name") or ""
            res = self.memory.forget_key(key) if key else self.memory.forget_last()
            return {"status": "success" if res.get("deleted") else "not_found", **res}

        elif action in ["forget_everything", "wipe_memory", "delete_all_memories"]:
            res = self.memory.forget_everything()
            return {"status": "success", **res}

        elif action in ["do_not_remember", "dont_remember", "do_not_store"]:
            res = self.memory.do_not_remember(
                session_id=params.get("session_id", "default")
            )
            return {"status": "success", **res}

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

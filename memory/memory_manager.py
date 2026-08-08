"""
JARVIS v4 - Unified Memory & Self-Learning Manager
"""

from typing import List, Dict, Any, Optional
from memory.db import DatabaseManager
from memory.vector_store import VectorStore
from utils.logger import logger

class MemoryManager:
    def __init__(self):
        self.db = DatabaseManager()
        self.vector_store = VectorStore()

    def record_turn(self, session_id: str, role: str, content: str, thought: Optional[str] = None):
        """Records a user prompt or assistant response into SQLite and vector memory."""
        self.db.add_conversation(session_id, role, content, thought)
        if role.lower() == "user":
            self.vector_store.add_text(content, {"type": "conversation", "role": role, "session_id": session_id})

    def get_dialogue_context(self, session_id: str = "default", turns: int = 6) -> List[Dict[str, Any]]:
        """Fetches short-term dialogue turns."""
        return self.db.get_recent_conversations(session_id=session_id, limit=turns)

    def retrieve_relevant_memory(self, query: str, top_k: int = 3) -> List[str]:
        """Retrieves semantically relevant memories from vector database."""
        results = self.vector_store.search(query, top_k=top_k)
        return [res["text"] for res in results if res["score"] > 0.3]

    def store_user_fact(self, key_name: str, value_data: str, category: str = "user"):
        """Stores a structured fact in database and vector memory."""
        self.db.set_fact(category, key_name, value_data)
        fact_str = f"User Preference - {key_name}: {value_data}"
        self.vector_store.add_text(fact_str, {"type": "fact", "category": category})
        logger.info(f"Learned user fact: {fact_str}")

    def store_correction(self, trigger_phrase: str, wrong_behavior: str, corrected_behavior: str):
        """Stores a self-learning correction rule."""
        self.db.add_correction(trigger_phrase, wrong_behavior, corrected_behavior)
        rule_str = f"Correction Rule: When user says '{trigger_phrase}', do NOT '{wrong_behavior}'. Instead: '{corrected_behavior}'."
        self.vector_store.add_text(rule_str, {"type": "correction", "trigger": trigger_phrase})
        logger.info(f"Self-learning rule registered: {rule_str}")

    def get_all_facts(self) -> List[Dict[str, Any]]:
        """Retrieves all user facts from SQLite."""
        return self.db.get_facts()

    def get_corrections(self) -> List[Dict[str, Any]]:
        """Retrieves self-learning corrections from SQLite."""
        return self.db.get_corrections()

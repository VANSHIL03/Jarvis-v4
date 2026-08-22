"""
JARVIS v4 - Unified Memory & Self-Learning Manager

Storage is deliberately selective. Section 6 requires JARVIS to decide what is
worth keeping instead of hoarding every sentence, and to never store
credentials at all -- so every write passes through two gates:

    1. SecretScanner  -- passwords, tokens, cards, keys are refused outright,
                         even when the user explicitly asks.
    2. MemoryCategory -- EPHEMERAL is never persisted, SHORT_TERM/TASK expire,
                         SENSITIVE is masked when displayed.

The same scanner guards the conversation embeddings, because a password spoken
in passing would otherwise land in the FAISS index by way of record_turn().
"""

from typing import List, Dict, Any, Optional
from memory.db import DatabaseManager
from memory.vector_store import VectorStore
from memory.categories import (
    DISPLAY_LABELS,
    MemoryCategory,
    classify_fact,
    is_masked_when_shown,
    is_persisted,
    requires_explicit_request,
    ttl_days,
)
from memory.redaction import scanner
from utils.logger import logger


class MemoryManager:
    def __init__(self):
        self.db = DatabaseManager()
        self.vector_store = VectorStore()
        # One-shot suppression set by "do not remember this".
        self._skip_next_embedding = False
        self.purge_expired()

    # ------------------------------------------------------------ dialogue
    def record_turn(self, session_id: str, role: str, content: str, thought: Optional[str] = None):
        """
        Records a dialogue turn into SQLite and, for user turns, vector memory.

        The embedded copy is redacted first: conversation text is indexed for
        semantic recall, so an unredacted "my password is ..." would become
        permanently searchable. The stored dialogue row is redacted too, since
        Section 27 applies to anything written to disk.
        """
        safe_content = scanner.redact(content) if content else content
        self.db.add_conversation(session_id, role, safe_content, thought)

        if role.lower() != "user":
            return

        if self._skip_next_embedding:
            self._skip_next_embedding = False
            logger.info("Turn not added to vector memory (user asked not to remember it).")
            return

        self.vector_store.add_text(
            safe_content,
            {"type": "conversation", "role": role, "session_id": session_id},
        )

    def get_dialogue_context(self, session_id: str = "default", turns: int = 6) -> List[Dict[str, Any]]:
        """Fetches short-term dialogue turns."""
        return self.db.get_recent_conversations(session_id=session_id, limit=turns)

    def retrieve_relevant_memory(self, query: str, top_k: int = 3) -> List[str]:
        """Retrieves semantically relevant memories from vector database."""
        results = self.vector_store.search(query, top_k=top_k)
        return [
            res["text"] for res in results
            if res["score"] > 0.3 and not (res.get("metadata") or {}).get("sensitive")
        ]

    # -------------------------------------------------------------- writes
    def remember(
        self,
        text: str,
        category: Any = None,
        explicit: bool = True,
        source: str = "user",
    ) -> Dict[str, Any]:
        """
        Stores a free-form memory, or refuses and explains why.

        Returns a dict with `stored`, a Hinglish `speech_reply`, and the
        resolved category. Refusal is a normal outcome here, not an error.
        """
        text = (text or "").strip()
        if not text:
            return {
                "stored": False,
                "reason": "empty",
                "speech_reply": "Sir, kya yaad rakhna hai wo bataiye.",
            }

        matches = scanner.scan(text)
        if matches:
            logger.warning(
                "Refused to store a memory containing "
                f"{scanner.describe(matches)} (value not logged)."
            )
            return {
                "stored": False,
                "reason": "sensitive",
                "detected": sorted({m.name for m in matches}),
                "category": MemoryCategory.SENSITIVE.value,
                "speech_reply": scanner.refusal_reply(text),
            }

        resolved = MemoryCategory.parse(category) if category else classify_fact(text)

        if resolved is MemoryCategory.SENSITIVE:
            # Nothing sensitive gets stored by this path; the scanner above is
            # the only judge of what is actually a credential, and it passed, so
            # a SENSITIVE guess here means "sounds risky" -- treat it as such.
            return {
                "stored": False,
                "reason": "sensitive",
                "category": resolved.value,
                "speech_reply": (
                    "Sir, ye sensitive lag raha hai, isliye main ise save nahi kar raha. "
                    "Passwords, PIN, ya keys main kabhi store nahi karta."
                ),
            }

        if requires_explicit_request(resolved) and not explicit:
            return {
                "stored": False,
                "reason": "needs_explicit_request",
                "category": resolved.value,
                "speech_reply": "Sir, ise yaad rakhne ke liye aap khud bolenge to hi main save karunga.",
            }

        if not is_persisted(resolved):
            logger.info(f"Memory kept in-conversation only (category={resolved.value}).")
            return {
                "stored": False,
                "reason": "ephemeral",
                "category": resolved.value,
                "speech_reply": "Theek hai Sir, abhi ke liye dhyan me rakh liya.",
            }

        key = self.db.store_free_fact(
            category=resolved.value,
            value_data=text,
            ttl_days=ttl_days(resolved),
            source=source,
            explicit=explicit,
            sensitive=False,
        )
        self.vector_store.add_text(
            text,
            {"type": "fact", "category": resolved.value, "key": key, "explicit": explicit},
        )
        logger.info(f"Remembered [{resolved.value}] under key '{key}'.")
        return {
            "stored": True,
            "key": key,
            "category": resolved.value,
            "speech_reply": f"Ji Sir, yaad rakh liya: {text}",
        }

    def store_user_fact(self, key_name: str, value_data: str, category: str = "user") -> Dict[str, Any]:
        """
        Stores a keyed fact (name, preference, wake word...).

        Kept for the existing callers in the planner and memory agent; the
        secret gate applies here too, so no route into storage is unguarded.
        """
        if scanner.contains_secret(f"{key_name} {value_data}"):
            logger.warning(f"Refused to store fact '{key_name}': looks like a credential.")
            return {
                "stored": False,
                "reason": "sensitive",
                "speech_reply": scanner.refusal_reply(str(value_data)),
            }

        resolved = MemoryCategory.parse(category, MemoryCategory.PERSONAL_FACT)
        self.db.set_fact(
            category=resolved.value,
            key_name=key_name,
            value_data=value_data,
            expires_at=None,
            source="user",
            explicit=True,
        )
        fact_str = f"User Preference - {key_name}: {value_data}"
        self.vector_store.add_text(
            fact_str, {"type": "fact", "category": resolved.value, "key": key_name}
        )
        logger.info(f"Learned user fact: {key_name} [{resolved.value}]")
        return {"stored": True, "key": key_name, "category": resolved.value}

    def store_correction(self, trigger_phrase: str, wrong_behavior: str, corrected_behavior: str):
        """Stores a self-learning correction rule."""
        self.db.add_correction(trigger_phrase, wrong_behavior, corrected_behavior)
        rule_str = (
            f"Correction Rule: When user says '{trigger_phrase}', do NOT "
            f"'{wrong_behavior}'. Instead: '{corrected_behavior}'."
        )
        self.vector_store.add_text(rule_str, {"type": "correction", "trigger": trigger_phrase})
        logger.info(f"Self-learning rule registered: {rule_str}")

    # ------------------------------------------------------------ deletion
    def forget_about(self, topic: str) -> Dict[str, Any]:
        """
        Removes every memory mentioning `topic`, from SQLite and vector memory.

        Both stores are pruned; deleting only one would leave JARVIS able to
        recall something it just promised to forget.
        """
        topic = (topic or "").strip()
        if not topic:
            return {
                "deleted": 0,
                "speech_reply": "Sir, kis baare me bhoolna hai ye bataiye.",
            }

        rows = self.db.delete_facts_matching(topic)
        vectors = self.vector_store.delete_matching_text(topic)
        total = len(rows) + len(vectors)

        if total == 0:
            return {
                "deleted": 0,
                "speech_reply": f"Sir, '{topic}' ke baare me mere paas kuch yaad nahi tha.",
            }
        return {
            "deleted": total,
            "facts_deleted": len(rows),
            "vectors_deleted": len(vectors),
            "speech_reply": f"Ji Sir, '{topic}' ke baare me sab kuch bhula diya.",
        }

    def forget_key(self, key_name: str) -> Dict[str, Any]:
        """Removes one keyed memory from both stores."""
        removed = self.db.delete_fact(key_name)
        vectors = self.vector_store.delete_by_metadata(key=key_name)
        return {
            "deleted": removed + len(vectors),
            "speech_reply": (
                "Ji Sir, wo memory delete kar di."
                if (removed or vectors) else "Sir, wo memory mile hi nahi."
            ),
        }

    def forget_last(self) -> Dict[str, Any]:
        """Removes the most recently stored memory ('ye bhool jao')."""
        facts = [f for f in self.db.get_facts(include_expired=True) if f["key_name"].startswith("fact_")]
        if not facts:
            return {
                "deleted": 0,
                "speech_reply": "Sir, haal filhaal koi memory save nahi hui thi.",
            }
        latest = sorted(facts, key=lambda f: (f.get("updated_at") or "", f.get("id") or 0))[-1]
        result = self.forget_key(latest["key_name"])
        self.vector_store.delete_matching_text(latest["value_data"])
        result["forgotten"] = latest["value_data"]
        if result["deleted"]:
            result["speech_reply"] = f"Ji Sir, '{latest['value_data']}' bhula diya."
        return result

    def forget_everything(self) -> Dict[str, Any]:
        """Wipes stored facts and the semantic index, keeping seeded defaults."""
        rows = self.db.delete_all_facts(keep_defaults=True)
        vectors = self.vector_store.clear()
        logger.info(f"Full memory wipe: {len(rows)} fact(s), {vectors} vector item(s).")
        return {
            "deleted": len(rows) + vectors,
            "speech_reply": "Ji Sir, aapke baare me saari saved memories delete kar di hain.",
        }

    def do_not_remember(self, session_id: str = "default") -> Dict[str, Any]:
        """
        Honours "do not remember this" / "ye yaad mat rakho".

        Drops the embedding of the turn just spoken and suppresses the next one,
        because the phrase is used both about what was just said and about what
        is coming next. The SQLite dialogue row stays -- the conversation has to
        stay coherent for the rest of the session -- but it is never indexed for
        semantic recall.
        """
        self._skip_next_embedding = True
        recent = self.db.get_recent_conversations(session_id=session_id, limit=4)
        user_turns = [t for t in recent if str(t.get("role", "")).lower() == "user"]
        removed = 0
        if user_turns:
            last_text = str(user_turns[-1].get("content", ""))
            if last_text.strip():
                removed = len(self.vector_store.delete_matching_text(last_text))
        logger.info(f"'Do not remember' honoured; {removed} embedding(s) dropped.")
        return {
            "deleted": removed,
            "speech_reply": "Theek hai Sir, ye main yaad nahi rakhunga.",
        }

    # -------------------------------------------------------------- reading
    def list_memories(self, mask_sensitive: bool = True) -> Dict[str, Any]:
        """
        Everything JARVIS remembers, grouped by category.

        SENSITIVE values are masked rather than printed, so answering "show me
        what you remember" can never itself leak a secret.
        """
        facts = self.db.get_facts()
        grouped: Dict[str, List[str]] = {}
        for fact in facts:
            category = MemoryCategory.parse(fact.get("category"))
            value = fact.get("value_data", "")
            if mask_sensitive and (fact.get("sensitive") or is_masked_when_shown(category)):
                value = "[hidden]"
            heading = DISPLAY_LABELS.get(category, category.value)
            grouped.setdefault(heading, []).append(value)

        if not grouped:
            return {
                "count": 0,
                "grouped": {},
                "speech_reply": "Sir, abhi mere paas aapke baare me kuch saved nahi hai.",
            }

        lines = [f"{heading}: " + "; ".join(values) for heading, values in grouped.items()]
        return {
            "count": len(facts),
            "grouped": grouped,
            "speech_reply": "Ji Sir, ye sab yaad hai mujhe. " + ". ".join(lines),
        }

    def recall(self, query: str, top_k: int = 5) -> Dict[str, Any]:
        """Answers "what do you remember about X"."""
        query = (query or "").strip()
        if not query:
            return self.list_memories()

        facts = [f["value_data"] for f in self.db.find_facts(query) if not f.get("sensitive")]
        semantic = [
            text for text in self.retrieve_relevant_memory(query, top_k=top_k)
            if text not in facts
        ]
        hits = facts + semantic
        if not hits:
            return {
                "count": 0,
                "memories": [],
                "speech_reply": f"Sir, '{query}' ke baare me mujhe kuch yaad nahi hai.",
            }
        return {
            "count": len(hits),
            "memories": hits,
            "speech_reply": f"Sir, '{query}' ke baare me itna yaad hai: " + "; ".join(hits[:5]),
        }

    def get_all_facts(self) -> List[Dict[str, Any]]:
        """Retrieves all non-expired user facts from SQLite."""
        return self.db.get_facts()

    def get_corrections(self) -> List[Dict[str, Any]]:
        """Retrieves self-learning corrections from SQLite."""
        return self.db.get_corrections()

    def purge_expired(self) -> int:
        """Drops expired SHORT_TERM/TASK memories from both stores."""
        expired = self.db.purge_expired_facts()
        for row in expired:
            self.vector_store.delete_by_metadata(key=row.get("key_name"))
        return len(expired)

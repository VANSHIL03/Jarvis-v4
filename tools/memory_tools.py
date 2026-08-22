"""
JARVIS v4 - Memory Tools

The user-facing half of the memory privacy layer (Section 6): remember, recall,
list, forget one thing, forget a whole topic, wipe everything, and "do not
remember this".

These tools are thin on purpose. Every decision about *whether* something may be
stored lives in MemoryManager and SecretScanner, not here -- a password typed
into "remember this" is refused inside store_user_fact, so no permission level or
prompt wording in this file could accidentally let a credential through. What
this module adds is the gate on destruction: forget_everything wipes the SQLite
rows and the FAISS vectors with no undo, so it is DANGEROUS and always asks.
"""

from __future__ import annotations

from typing import List

from security.permissions import PermissionLevel as P
from tools.base import ToolParam, ToolSpec

CATEGORY = "memory"


MEMORY_TOOLS: List[ToolSpec] = [
    ToolSpec(
        name="remember",
        description=(
            "Remember a fact the user has explicitly asked JARVIS to keep. "
            "Passwords, tokens, card numbers and keys are always refused."
        ),
        permission=P.SAFE,
        category=CATEGORY,
        agent="memory_agent",
        action="remember",
        parameters=(
            ToolParam("text", "string", required=True, description="The fact to remember, in the user's words."),
            ToolParam("category", "string", default=None, description="Optional category override."),
        ),
        aliases={"value": "text", "fact": "text", "content": "text", "message": "text", "info": "text"},
        legacy_actions=("remember_this", "save_memory", "store_memory"),
    ),
    ToolSpec(
        name="store_fact",
        description="Store a specific key/value fact about the user (name, city, preference).",
        permission=P.SAFE,
        category=CATEGORY,
        agent="memory_agent",
        action="store_fact",
        parameters=(
            ToolParam("key", "string", required=True, description="Fact name, e.g. 'user_name'."),
            ToolParam("value", "string", required=True, description="Fact value."),
            ToolParam("category", "string", default="user", description="Memory category."),
        ),
        aliases={
            "key_name": "key", "preference_name": "key", "name": "key", "field": "key",
            "value_data": "value", "preference_value": "value", "text": "value",
        },
        legacy_actions=("update_user_preference", "set_fact", "update_fact"),
    ),
    ToolSpec(
        name="recall",
        description="Search memory for what JARVIS knows about a topic.",
        permission=P.SAFE,
        category=CATEGORY,
        agent="memory_agent",
        action="recall",
        parameters=(
            ToolParam("query", "string", required=True, description="Topic or question to look up."),
            ToolParam("top_k", "integer", default=5, description="How many memories to return."),
        ),
        aliases={"topic": "query", "text": "query", "question": "query", "about": "query", "limit": "top_k"},
        legacy_actions=("what_do_you_remember", "remember_about", "search_memory", "retrieve_memory"),
    ),
    ToolSpec(
        name="list_memories",
        description=(
            "Show everything JARVIS remembers about the user. Anything flagged "
            "sensitive is masked unless the user asks to see it in full."
        ),
        permission=P.SAFE,
        category=CATEGORY,
        agent="memory_agent",
        action="list_memories",
        parameters=(
            ToolParam("mask_sensitive", "boolean", default=True, description="Mask sensitive values in the output."),
        ),
        aliases={"masked": "mask_sensitive", "mask": "mask_sensitive"},
        legacy_actions=("show_memories", "list_all_memories", "what_do_you_know"),
    ),
    ToolSpec(
        name="forget",
        description="Forget one memory - a named fact, or the most recent one when no name is given.",
        permission=P.LOW_RISK,
        category=CATEGORY,
        agent="memory_agent",
        action="forget",
        parameters=(
            ToolParam("key", "string", default="", description="Fact name to delete (blank = the last thing stored)."),
        ),
        aliases={"key_name": "key", "name": "key", "fact": "key", "target": "key"},
        confirm_template="Sir, '{key}' memory se hata doon? Haan ya na bataiye.",
        legacy_actions=("forget_this", "forget_last", "forget_key", "delete_memory"),
    ),
    ToolSpec(
        name="forget_about",
        description="Forget everything stored about one topic or person.",
        permission=P.LOW_RISK,
        category=CATEGORY,
        agent="memory_agent",
        action="forget_about",
        parameters=(
            ToolParam("topic", "string", required=True, description="Topic, person or subject to erase."),
        ),
        aliases={"query": "topic", "about": "topic", "subject": "topic", "text": "topic", "name": "topic"},
        confirm_template="Sir, '{topic}' ke baare me sab kuch bhool jaun? Haan ya na bataiye.",
        legacy_actions=("forget_topic", "forget_everything_about"),
    ),
    ToolSpec(
        name="forget_everything",
        description="Erase all stored memories and their vectors. Irreversible.",
        permission=P.DANGEROUS,
        category=CATEGORY,
        agent="memory_agent",
        action="forget_everything",
        confirm_template=(
            "Sir, main aapki poori memory delete kar doon? Ye wapas nahi aayegi. "
            "Haan ya na bataiye."
        ),
        legacy_actions=("wipe_memory", "delete_all_memories", "clear_memory"),
    ),
    ToolSpec(
        name="do_not_remember",
        description="Stop storing anything from this conversation onwards.",
        permission=P.SAFE,
        category=CATEGORY,
        agent="memory_agent",
        action="do_not_remember",
        parameters=(
            ToolParam("session_id", "string", default="default", description="Conversation to stop recording."),
        ),
        aliases={"session": "session_id", "conversation": "session_id"},
        legacy_actions=("dont_remember", "do_not_store", "stop_remembering"),
    ),
]

__all__ = ["MEMORY_TOOLS"]

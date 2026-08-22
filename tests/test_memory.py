"""
JARVIS v4 Unit Tests - Memory & Vector Store Subsystem
"""

import pytest
import os
import gc
import tempfile
from pathlib import Path
from memory.db import DatabaseManager
from memory.vector_store import VectorStore
from memory.memory_manager import MemoryManager

def test_database_manager():
    tmp_dir = tempfile.mkdtemp()
    try:
        db_path = os.path.join(tmp_dir, "test.db")
        db = DatabaseManager(db_path=db_path)
        db.set_fact("user", "user_alias", "Tony Stark")
        facts = db.get_facts(category="user")
        assert len(facts) >= 1
        found = any(f["key_name"] == "user_alias" and f["value_data"] == "Tony Stark" for f in facts)
        assert found is True
        del db
        gc.collect()
    finally:
        try:
            import shutil
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass

def test_vector_store():
    vs = VectorStore(index_name="test_index")
    vs.add_text("JARVIS is an AI assistant built for Windows 11.")
    results = vs.search("Windows 11 AI assistant", top_k=1)
    assert len(results) >= 1
    assert "JARVIS" in results[0]["text"]

def test_memory_manager():
    mm = MemoryManager()
    mm.store_user_fact("favorite_browser", "Chrome")
    mm.record_turn("test_session", "user", "What is my favorite browser?")
    dialogue = mm.get_dialogue_context("test_session", turns=1)
    assert len(dialogue) == 1
    assert dialogue[0]["content"] == "What is my favorite browser?"

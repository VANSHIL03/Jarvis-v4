"""
JARVIS v4 - SQLite Database Persistence Manager
"""

import sqlite3
from typing import List, Dict, Any, Optional
from config.settings import settings
from utils.logger import logger

class DatabaseManager:
    def __init__(self, db_path=None):
        self.db_path = str(db_path or settings.DB_PATH)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """Initializes tables using schema.sql or inline execution."""
        schema_file = settings.BASE_DIR / "schema.sql"
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if schema_file.exists():
                with open(schema_file, 'r', encoding='utf-8') as f:
                    cursor.executescript(f.read())
            else:
                cursor.executescript("""
                    CREATE TABLE IF NOT EXISTS conversations (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        session_id TEXT NOT NULL,
                        role TEXT NOT NULL,
                        content TEXT NOT NULL,
                        thought TEXT,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                    );
                    CREATE TABLE IF NOT EXISTS user_facts (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        category TEXT NOT NULL,
                        key_name TEXT NOT NULL UNIQUE,
                        value_data TEXT NOT NULL,
                        confidence REAL DEFAULT 1.0,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    );
                    CREATE TABLE IF NOT EXISTS self_learning_corrections (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        trigger_phrase TEXT NOT NULL,
                        wrong_behavior TEXT NOT NULL,
                        corrected_behavior TEXT NOT NULL,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    );
                    CREATE TABLE IF NOT EXISTS app_shortcuts (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        app_name TEXT NOT NULL UNIQUE,
                        executable_path TEXT NOT NULL,
                        launch_args TEXT DEFAULT ''
                    );
                    CREATE TABLE IF NOT EXISTS contacts (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        contact_name TEXT NOT NULL UNIQUE,
                        phone_number TEXT,
                        email_address TEXT,
                        notes TEXT
                    );
                """)
            conn.commit()
            logger.info("SQLite Database initialized cleanly.")

    def add_conversation(self, session_id: str, role: str, content: str, thought: Optional[str] = None):
        """Saves dialogue turn to conversation history."""
        if isinstance(content, (list, dict)):
            content = str(content)
        if isinstance(thought, (list, dict)):
            thought = str(thought)
        with self._get_connection() as conn:
            conn.execute(
                "INSERT INTO conversations (session_id, role, content, thought) VALUES (?, ?, ?, ?)",
                (session_id, role, content, thought)
            )
            conn.commit()

    def get_recent_conversations(self, session_id: str = "default", limit: int = 10) -> List[Dict[str, Any]]:
        """Retrieves recent conversation history."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT role, content, thought, timestamp FROM conversations WHERE session_id = ? ORDER BY id DESC LIMIT ?",
                (session_id, limit)
            )
            rows = cursor.fetchall()
            return [dict(row) for row in reversed(rows)]

    def set_fact(self, category: str, key_name: str, value_data: str, confidence: float = 1.0):
        """Stores or updates a user fact/preference."""
        with self._get_connection() as conn:
            conn.execute(
                """INSERT INTO user_facts (category, key_name, value_data, confidence) 
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(key_name) DO UPDATE SET 
                   category=excluded.category, value_data=excluded.value_data, confidence=excluded.confidence""",
                (category, key_name, value_data, confidence)
            )
            conn.commit()

    def get_facts(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """Gets all facts or facts filtered by category."""
        with self._get_connection() as conn:
            if category:
                cursor = conn.execute("SELECT * FROM user_facts WHERE category = ?", (category,))
            else:
                cursor = conn.execute("SELECT * FROM user_facts")
            return [{k: row[k] for k in row.keys()} for row in cursor.fetchall()]

    def add_correction(self, trigger_phrase: str, wrong_behavior: str, corrected_behavior: str):
        """Stores a self-learning correction rule."""
        with self._get_connection() as conn:
            conn.execute(
                "INSERT INTO self_learning_corrections (trigger_phrase, wrong_behavior, corrected_behavior) VALUES (?, ?, ?)",
                (trigger_phrase, wrong_behavior, corrected_behavior)
            )
            conn.commit()

    def get_corrections(self) -> List[Dict[str, Any]]:
        """Gets all stored self-learning corrections."""
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT * FROM self_learning_corrections ORDER BY id DESC")
            return [dict(row) for row in cursor.fetchall()]

    def get_app_path(self, app_name: str) -> Optional[str]:
        """Resolves an app shortcut name to its executable path."""
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT executable_path FROM app_shortcuts WHERE LOWER(app_name) = LOWER(?)", (app_name,))
            row = cursor.fetchone()
            return row["executable_path"] if row else None

    def get_contact(self, contact_name: str) -> Optional[Dict[str, Any]]:
        """Retrieves contact details by name."""
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT * FROM contacts WHERE LOWER(contact_name) LIKE LOWER(?)", (f"%{contact_name}%",))
            row = cursor.fetchone()
            return dict(row) if row else None

    def close(self):
        """Closes any active database resources."""
        pass

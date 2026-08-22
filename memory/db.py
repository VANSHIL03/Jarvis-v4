"""
JARVIS v4 - SQLite Database Persistence Manager
"""

import sqlite3
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from config.settings import settings
from memory.categories import slugify
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
            self._migrate(conn)
            conn.commit()
            logger.info("SQLite Database initialized cleanly.")

    def _migrate(self, conn: sqlite3.Connection):
        """
        Brings an existing data/jarvis.db up to the current schema.

        Purely additive and guarded by PRAGMA table_info, so a database created
        by an earlier build keeps every row it already holds. The new columns
        are what memory categories need: an expiry for SHORT_TERM/TASK facts,
        the provenance of the memory, whether the user asked for it literally,
        and whether its value must be masked when displayed.
        """
        additions = {
            "expires_at": "TEXT",
            "source": "TEXT DEFAULT 'inferred'",
            "explicit": "INTEGER DEFAULT 0",
            "sensitive": "INTEGER DEFAULT 0",
        }
        try:
            existing = {row["name"] for row in conn.execute("PRAGMA table_info(user_facts)")}
        except sqlite3.Error as e:
            logger.error(f"Could not inspect user_facts for migration: {e}")
            return

        if not existing:
            return  # table absent; the schema step above will have created it

        for column, declaration in additions.items():
            if column in existing:
                continue
            try:
                conn.execute(f"ALTER TABLE user_facts ADD COLUMN {column} {declaration}")
                logger.info(f"Migrated user_facts: added column '{column}'.")
            except sqlite3.Error as e:
                logger.error(f"Migration failed for user_facts.{column}: {e}")

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

    def set_fact(
        self,
        category: str,
        key_name: str,
        value_data: str,
        confidence: float = 1.0,
        expires_at: Optional[str] = None,
        source: str = "inferred",
        explicit: bool = False,
        sensitive: bool = False,
    ):
        """Stores or updates a user fact/preference under an exact key."""
        with self._get_connection() as conn:
            conn.execute(
                """INSERT INTO user_facts
                       (category, key_name, value_data, confidence, expires_at, source, explicit, sensitive)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(key_name) DO UPDATE SET
                   category=excluded.category, value_data=excluded.value_data,
                   confidence=excluded.confidence, expires_at=excluded.expires_at,
                   source=excluded.source, explicit=excluded.explicit,
                   sensitive=excluded.sensitive, updated_at=CURRENT_TIMESTAMP""",
                (category, key_name, value_data, confidence, expires_at,
                 source, int(bool(explicit)), int(bool(sensitive)))
            )
            conn.commit()

    def store_free_fact(
        self,
        category: str,
        value_data: str,
        ttl_days: Optional[int] = None,
        source: str = "user",
        explicit: bool = False,
        sensitive: bool = False,
        confidence: float = 1.0,
    ) -> str:
        """
        Stores a free-form "remember this" memory and returns its key.

        key_name is UNIQUE, so every free-form memory needs its own key. Writing
        them all under one fixed key made each new memory silently overwrite the
        previous one -- only a single free-form fact could ever exist. Deriving
        the key from the content fixes that, and makes re-remembering the same
        thing idempotent instead of duplicating it.
        """
        key_name = f"fact_{slugify(value_data)}"
        expires_at = None
        if ttl_days:
            expires_at = (datetime.now() + timedelta(days=int(ttl_days))).isoformat(timespec="seconds")
        self.set_fact(
            category=category,
            key_name=key_name,
            value_data=value_data,
            confidence=confidence,
            expires_at=expires_at,
            source=source,
            explicit=explicit,
            sensitive=sensitive,
        )
        return key_name

    def get_facts(
        self,
        category: Optional[str] = None,
        include_expired: bool = False,
    ) -> List[Dict[str, Any]]:
        """Gets all facts or facts filtered by category, skipping expired ones."""
        with self._get_connection() as conn:
            if category:
                cursor = conn.execute("SELECT * FROM user_facts WHERE category = ?", (category,))
            else:
                cursor = conn.execute("SELECT * FROM user_facts")
            rows = [{k: row[k] for k in row.keys()} for row in cursor.fetchall()]

        if include_expired:
            return rows
        now = datetime.now().isoformat(timespec="seconds")
        return [r for r in rows if not (r.get("expires_at") and r["expires_at"] < now)]

    def delete_fact(self, key_name: str) -> int:
        """Removes one fact by exact key. Returns the number of rows deleted."""
        with self._get_connection() as conn:
            cursor = conn.execute("DELETE FROM user_facts WHERE key_name = ?", (key_name,))
            conn.commit()
            return cursor.rowcount or 0

    def find_facts(self, query: str) -> List[Dict[str, Any]]:
        """Facts whose key or value mentions `query` (used by 'forget about X')."""
        needle = f"%{(query or '').strip()}%"
        with self._get_connection() as conn:
            cursor = conn.execute(
                """SELECT * FROM user_facts
                   WHERE LOWER(value_data) LIKE LOWER(?) OR LOWER(key_name) LIKE LOWER(?)""",
                (needle, needle)
            )
            return [{k: row[k] for k in row.keys()} for row in cursor.fetchall()]

    def delete_facts_matching(self, query: str) -> List[Dict[str, Any]]:
        """
        Deletes every fact mentioning `query` and returns the deleted rows.

        The rows come back so the caller can prune the same items from the
        vector store -- otherwise "forget everything about X" would remove the
        SQLite copy while leaving the embedding searchable, which would make the
        promise a lie.
        """
        doomed = self.find_facts(query)
        if not doomed:
            return []
        keys = [row["key_name"] for row in doomed]
        placeholders = ",".join("?" for _ in keys)
        with self._get_connection() as conn:
            conn.execute(f"DELETE FROM user_facts WHERE key_name IN ({placeholders})", keys)
            conn.commit()
        logger.info(f"Deleted {len(doomed)} fact(s) matching '{query}'.")
        return doomed

    def delete_all_facts(self, keep_defaults: bool = True) -> List[Dict[str, Any]]:
        """Wipes user facts. Keeps the seeded defaults unless told otherwise."""
        protected = ("user_name", "theme", "wake_word") if keep_defaults else ()
        rows = self.get_facts(include_expired=True)
        doomed = [r for r in rows if r["key_name"] not in protected]
        if not doomed:
            return []
        keys = [r["key_name"] for r in doomed]
        placeholders = ",".join("?" for _ in keys)
        with self._get_connection() as conn:
            conn.execute(f"DELETE FROM user_facts WHERE key_name IN ({placeholders})", keys)
            conn.commit()
        logger.info(f"Deleted all {len(doomed)} user fact(s) on request.")
        return doomed

    def purge_expired_facts(self) -> List[Dict[str, Any]]:
        """Drops SHORT_TERM/TASK memories whose expiry has passed."""
        now = datetime.now().isoformat(timespec="seconds")
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM user_facts WHERE expires_at IS NOT NULL AND expires_at < ?",
                (now,)
            )
            expired = [{k: row[k] for k in row.keys()} for row in cursor.fetchall()]
            if expired:
                conn.execute(
                    "DELETE FROM user_facts WHERE expires_at IS NOT NULL AND expires_at < ?",
                    (now,)
                )
                conn.commit()
                logger.info(f"Purged {len(expired)} expired memory item(s).")
        return expired

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

    def find_contacts(self, contact_name: str) -> List[Dict[str, Any]]:
        """
        Every contact whose name contains `contact_name`.

        Section 13 forbids messaging the wrong person on an uncertain match, so
        the send tools need to know whether a name is unambiguous -- one row means
        confident, zero or several means ask first.
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM contacts WHERE LOWER(contact_name) LIKE LOWER(?) ORDER BY contact_name",
                (f"%{(contact_name or '').strip()}%",)
            )
            return [dict(row) for row in cursor.fetchall()]

    def has_exact_contact(self, contact_name: str) -> bool:
        """True only for a single exact (case-insensitive) contact match."""
        name = (contact_name or "").strip()
        if not name:
            return False
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT COUNT(*) AS n FROM contacts WHERE LOWER(contact_name) = LOWER(?)",
                (name,)
            )
            row = cursor.fetchone()
            return bool(row and row["n"] == 1)

    def close(self):
        """
        No-op: this class holds no long-lived handle.

        Every operation opens its own connection through ``_get_connection()``
        inside a ``with`` block, so there is nothing to release here. The method
        exists because callers (and MemoryManager) reasonably expect a close()
        on anything database-shaped, and it stays a safe call if the connection
        strategy ever changes.
        """
        return None

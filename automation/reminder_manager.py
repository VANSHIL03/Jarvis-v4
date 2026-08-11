"""
JARVIS v4 - Reminder & Alarm Scheduler Engine
Handles background timers, SQLite persistence, Windows Alarms, and spoken audio reminders.
"""

import os
import re
import time
import sqlite3
import threading
import subprocess
from datetime import datetime, timedelta
from typing import List, Dict, Any, Callable, Optional
from config.settings import settings
from utils.logger import logger


class ReminderManager:
    def __init__(self, db_path=None, speech_callback: Optional[Callable[[str], None]] = None, ui_callback: Optional[Callable[[str], None]] = None):
        self.db_path = str(db_path or settings.DB_PATH)
        self.speech_callback = speech_callback
        self.ui_callback = ui_callback
        self._init_db()
        self._running = True
        self._worker_thread = threading.Thread(target=self._check_loop, daemon=True)
        self._worker_thread.start()

    def _get_conn(self):
        if self.db_path == ":memory:":
            if not hasattr(self, "_memory_conn") or self._memory_conn is None:
                self._memory_conn = sqlite3.connect(":memory:", check_same_thread=False)
            return self._memory_conn
        return sqlite3.connect(self.db_path)

    def set_callbacks(self, speech_cb: Callable[[str], None], ui_cb: Callable[[str], None]):
        self.speech_callback = speech_cb
        self.ui_callback = ui_cb

    def _init_db(self):
        try:
            conn = self._get_conn()
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS reminders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_text TEXT NOT NULL,
                    target_timestamp REAL NOT NULL,
                    target_time_str TEXT NOT NULL,
                    status TEXT DEFAULT 'PENDING'
                )
            """)
            conn.commit()
            if self.db_path != ":memory:":
                conn.close()
        except Exception as e:
            logger.error(f"Failed to initialize reminders table: {e}")

    def add_reminder(self, task_text: str, delay_seconds: float) -> Dict[str, Any]:
        """Schedules a new reminder to fire after delay_seconds."""
        target_ts = time.time() + delay_seconds
        target_dt = datetime.now() + timedelta(seconds=delay_seconds)
        time_str = target_dt.strftime("%I:%M %p")

        try:
            conn = self._get_conn()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO reminders (task_text, target_timestamp, target_time_str, status)
                VALUES (?, ?, ?, 'PENDING')
            """, (task_text, target_ts, time_str))
            conn.commit()
            rem_id = cursor.lastrowid
            if self.db_path != ":memory:":
                conn.close()
            logger.info(f"Scheduled reminder ID {rem_id}: '{task_text}' at {time_str}")
        except Exception as e:
            logger.error(f"Failed to save reminder: {e}")

        # Also trigger Windows Clock app launch
        try:
            subprocess.Popen("start ms-clock:", shell=True)
        except Exception:
            pass

        return {
            "task": task_text,
            "target_time": time_str,
            "delay_seconds": delay_seconds
        }

    def get_pending_reminders(self) -> List[Dict[str, Any]]:
        """Returns list of all active pending reminders."""
        results = []
        try:
            conn = self._get_conn()
            cursor = conn.cursor()
            cursor.execute("SELECT id, task_text, target_time_str FROM reminders WHERE status = 'PENDING'")
            rows = cursor.fetchall()
            for r in rows:
                results.append({"id": r[0], "task": r[1], "time": r[2]})
            if self.db_path != ":memory:":
                conn.close()
        except Exception as e:
            logger.error(f"Failed to fetch reminders: {e}")
        return results

    def _check_loop(self):
        """Background thread checking every 5 seconds for due reminders."""
        while self._running:
            try:
                now_ts = time.time()
                conn = self._get_conn()
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT id, task_text, target_time_str FROM reminders
                    WHERE status = 'PENDING' AND target_timestamp <= ?
                """, (now_ts,))
                due_items = cursor.fetchall()

                for item in due_items:
                    rem_id, task, t_str = item
                    cursor.execute("UPDATE reminders SET status = 'TRIGGERED' WHERE id = ?", (rem_id,))
                    conn.commit()
                    logger.info(f"REMINDER ALARM TRIGGERED: '{task}' scheduled for {t_str}")

                    # Play Windows Beep alarm sound
                    self._play_alarm_sound()

                    msg = f"Sir Vanshil! Aapka reminder time ho gaya hai: '{task}'."
                    if self.ui_callback:
                        self.ui_callback(msg)
                    if self.speech_callback:
                        self.speech_callback(msg)

                if self.db_path != ":memory:":
                    conn.close()
            except Exception as e:
                logger.error(f"Reminder loop error: {e}")
            time.sleep(5.0)

    def _play_alarm_sound(self):
        """Plays hardware audio beep alarm."""
        try:
            import winsound
            for _ in range(3):
                winsound.Beep(1000, 400)
                time.sleep(0.1)
        except Exception:
            pass

    def parse_time_and_task(self, text: str) -> Optional[tuple[str, float]]:
        """Parses natural language time duration and task from prompt."""
        clean = text.lower().strip()

        # Pattern 1: "remind me in 10 minutes to buy milk" or "remind me in 1 hour to sleep"
        p1 = re.search(r"remind\s+me\s+in\s+(\d+)\s*(minutes?|mins?|hours?|hrs?|seconds?|secs?)\s+(?:to\s+)?(.+)", clean)
        if p1:
            val = int(p1.group(1))
            unit = p1.group(2)
            task = p1.group(3).strip()
            mult = 60 if "min" in unit or "m" in unit else (3600 if "h" in unit or "hr" in unit else 1)
            return task, val * mult

        # Pattern 2: "remind me to buy milk in 10 minutes"
        p2 = re.search(r"remind\s+me\s+to\s+(.+)\s+in\s+(\d+)\s*(minutes?|mins?|hours?|hrs?|seconds?|secs?)", clean)
        if p2:
            task = p2.group(1).strip()
            val = int(p2.group(2))
            unit = p2.group(3)
            mult = 60 if "min" in unit or "m" in unit else (3600 if "h" in unit or "hr" in unit else 1)
            return task, val * mult

        # Pattern 3: "mujhe 10 minute mein chai peene ka yaad dilana"
        p3 = re.search(r"(?:mujhe|mujhko)?\s*(\d+)\s*(minutes?|mins?|ghante|ghanta)\s*(?:mein|par)?\s*(.+?)\s*(?:yaad dilana|reminder|alarm)", clean)
        if p3:
            val = int(p3.group(1))
            unit = p3.group(2)
            task = p3.group(3).strip()
            mult = 3600 if "ghant" in unit else 60
            return task, val * mult

        # Pattern 4: "set alarm in 15 minutes for meeting"
        p4 = re.search(r"(?:set\s+)?alarm\s+(?:in\s+)?(\d+)\s*(minutes?|mins?|hours?|hrs?|seconds?|secs?)\s*(?:for\s+)?(.+)?", clean)
        if p4:
            val = int(p4.group(1))
            unit = p4.group(2)
            task = p4.group(3).strip() if p4.group(3) else "Alarm Time"
            mult = 3600 if "h" in unit or "hr" in unit else 60
            return task, val * mult

        return None

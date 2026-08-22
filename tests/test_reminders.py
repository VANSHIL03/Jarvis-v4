import time
import pytest
from automation.reminder_manager import ReminderManager

def test_reminder_scheduling():
    rm = ReminderManager(db_path=":memory:")
    res = rm.add_reminder("water plants", 300)
    assert res["task"] == "water plants"
    assert res["delay_seconds"] == 300

    pending = rm.get_pending_reminders()
    assert len(pending) == 1
    assert pending[0]["task"] == "water plants"

def test_reminder_parsing():
    rm = ReminderManager(db_path=":memory:")
    parsed = rm.parse_time_and_task("remind me in 5 minutes to take medicine")
    assert parsed is not None
    assert parsed[0] == "take medicine"
    assert parsed[1] == 300

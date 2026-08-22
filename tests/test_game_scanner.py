import pytest
from automation.system import SystemControl

def test_detect_installed_games():
    sys_control = SystemControl()
    games = sys_control.detect_installed_games()
    assert isinstance(games, list)

import pytest
from utils.sound_pack import SoundPackManager

def test_sound_pack_manager():
    sp = SoundPackManager()
    assert sp.sound_dir.exists()
    sp.play_sound("welcome")
    sp.play_sound("confirm")

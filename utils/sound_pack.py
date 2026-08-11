"""
JARVIS v4 - Authentic Iron Man Voice & Sound Effects Pack Manager
Loads and plays authentic JARVIS movie sound effects for UI actions, alarms, and confirmations.
"""

import os
import random
import threading
from pathlib import Path
from typing import Optional
from config.settings import settings
from utils.logger import logger


class SoundPackManager:
    def __init__(self, sound_dir: Optional[Path] = None):
        self.sound_dir = Path(sound_dir or (settings.DATA_DIR / "sound_pack"))
        self._pygame_initialized = False
        self._sounds = {}
        self._preload_key_sounds()

    def _ensure_pygame(self):
        if not self._pygame_initialized:
            try:
                import pygame
                pygame.mixer.init(frequency=24000)
                self._pygame_initialized = True
            except Exception as e:
                logger.debug(f"Pygame mixer init failed: {e}")

    def _preload_key_sounds(self):
        """Preloads key sound files for instant zero-latency playback."""
        if not self.sound_dir.exists():
            return

        self._ensure_pygame()
        key_files = {
            "welcome": "caged_welcome.aif",
            "mic_on": "caged_button_sound_mic.aif",
            "process": "caged_button_sound_process.aif",
            "confirm": "caged_confirm_0_m.aif",
            "accessed": "caged_accessed.aif",
            "alarm": "caged_clock_alarm_wake_0.aif",
            "reminder": "caged_clock_reminder_alert_0.aif",
            "shutdown": "caged_power_down.aif"
        }

        try:
            import pygame
            for key, filename in key_files.items():
                file_path = self.sound_dir / filename
                if file_path.exists():
                    self._sounds[key] = pygame.mixer.Sound(str(file_path))
        except Exception as e:
            logger.debug(f"Failed to preload sound pack: {e}")

    def play_sound(self, sound_key: str):
        """Plays sound effect in background thread asynchronously."""
        def _play():
            try:
                if sound_key in self._sounds:
                    self._sounds[sound_key].play()
                else:
                    # Fallback to direct file play
                    file_path = self.sound_dir / f"{sound_key}.aif"
                    if file_path.exists():
                        import pygame
                        self._ensure_pygame()
                        s = pygame.mixer.Sound(str(file_path))
                        s.play()
            except Exception as e:
                logger.debug(f"Sound play error ({sound_key}): {e}")

        threading.Thread(target=_play, daemon=True).start()

    def play_welcome(self):
        self.play_sound("welcome")

    def play_mic_on(self):
        self.play_sound("mic_on")

    def play_process(self):
        self.play_sound("process")

    def play_confirm(self):
        self.play_sound("confirm")

    def play_alarm(self):
        self.play_sound("alarm")

    def play_shutdown(self):
        self.play_sound("shutdown")

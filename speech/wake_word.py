"""
JARVIS v4 - Wake Word Listener ("Jarvis")
"""

import time
import numpy as np
from typing import Callable, Optional
from config.settings import settings
from utils.logger import logger

class WakeWordDetector:
    def __init__(self, on_wake_callback: Optional[Callable[[], None]] = None):
        self.wake_word = settings.WAKE_WORD.lower()
        self.on_wake_callback = on_wake_callback
        self.is_listening = False

    def listen_loop(self):
        """Monitors audio stream buffer for wake word trigger."""
        self.is_listening = True
        logger.info(f"Wake word listener active for '{self.wake_word}'...")

        try:
            import speech_recognition as sr
            r = sr.Recognizer()
            mic = sr.Microphone()
            with mic as source:
                r.adjust_for_ambient_noise(source, duration=0.5)

            while self.is_listening:
                try:
                    with mic as source:
                        audio = r.listen(source, timeout=3.0, phrase_time_limit=3.0)
                    text = r.recognize_google(audio).lower()
                    if self.wake_word in text:
                        logger.info(f"Wake word '{self.wake_word}' detected in audio stream!")
                        if self.on_wake_callback:
                            self.on_wake_callback()
                except (sr.WaitTimeoutError, sr.UnknownValueError):
                    pass
                except Exception as e:
                    logger.error(f"Wake word listening error: {e}")
                    time.sleep(1.0)
        except Exception as e:
            logger.warning(f"Microphone input unavailable for wake word detector ({e}).")

    def stop(self):
        self.is_listening = False

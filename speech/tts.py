"""
JARVIS v4 - Text To Speech Engine
Edge-TTS Indian AI voice (hi-IN-MadhurNeural) with pygame audio playback.
Guarantees mic state recovery after speech completes.
"""

import os
import re
import time
import asyncio
import tempfile
import threading
import subprocess
import random
from typing import Callable, Optional
from config.settings import settings
from utils.logger import logger


class TextToSpeech:
    def __init__(self):
        self.voice = settings.TTS_VOICE
        self.rate = settings.SPEECH_RATE
        self.on_amplitude_callback: Optional[Callable[[float], None]] = None
        self._is_speaking = False
        self._pygame_initialized = False

    def set_amplitude_callback(self, callback: Callable[[float], None]):
        """Sets UI callback function to stream audio amplitude for waveform visualization."""
        self.on_amplitude_callback = callback

    @property
    def is_speaking(self) -> bool:
        return self._is_speaking

    def _ensure_pygame_init(self):
        if not self._pygame_initialized:
            try:
                import pygame
                pygame.mixer.init(frequency=24000)
                self._pygame_initialized = True
            except Exception as e:
                logger.debug(f"Pygame mixer init failed: {e}")

    def speak(self, text: str):
        """Speaks the exact chat text out loud with guaranteed state cleanup."""
        clean_text = text.strip()
        if not clean_text:
            return

        # Ensure TTS speaks "Jarvis" naturally as a word instead of spelling J - A - R - V - I - S
        clean_text = re.sub(r"J\.A\.R\.V\.I\.S\.", "Jarvis", clean_text, flags=re.I)
        clean_text = re.sub(r"\bJ\s+A\s+R\s+V\s+I\s+S\b", "Jarvis", clean_text, flags=re.I)

        self._is_speaking = True
        logger.info(f"JARVIS Speaking: '{clean_text}'")

        try:
            # 1. Primary Option: ElevenLabs (Target Voice ID: iWNf11sz1GrUE4ppxTOL)
            if self._speak_elevenlabs(clean_text):
                return

            # 2. Secondary: Edge-TTS
            try:
                import edge_tts
                communicate = edge_tts.Communicate(clean_text, self.voice)
                with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
                    tmp_file = tmp.name

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(communicate.save(tmp_file))
                loop.close()

                self._play_audio_file(tmp_file)

                if os.path.exists(tmp_file):
                    os.remove(tmp_file)
                return

            except Exception as e:
                logger.warning(f"Edge-TTS failed ({e}). Using pyttsx3 fallback.")

            # 3. Offline Fallback: Windows SAPI5 pyttsx3
            self._speak_pyttsx3(clean_text)

        finally:
            time.sleep(0.3)
            self._is_speaking = False
            if self.on_amplitude_callback:
                self.on_amplitude_callback(0.0)

    def _speak_elevenlabs(self, text: str) -> bool:
        """Synthesizes speech using ElevenLabs API with Voice ID (iWNf11sz1GrUE4ppxTOL)."""
        api_key = settings.ELEVENLABS_API_KEY or os.getenv("ELEVENLABS_API_KEY", "")
        voice_id = settings.ELEVENLABS_VOICE_ID or "iWNf11sz1GrUE4ppxTOL"

        if not api_key:
            return False

        try:
            import httpx
            url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
            headers = {
                "Accept": "audio/mpeg",
                "Content-Type": "application/json",
                "xi-api-key": api_key
            }
            body = {
                "text": text,
                "model_id": settings.ELEVENLABS_MODEL_ID,
                "voice_settings": {
                    "stability": 0.5,
                    "similarity_boost": 0.75
                }
            }

            with httpx.Client(timeout=15.0) as client:
                res = client.post(url, json=body, headers=headers)
                if res.status_code == 200:
                    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
                        tmp.write(res.content)
                        tmp_file = tmp.name

                    self._play_audio_file(tmp_file)
                    if os.path.exists(tmp_file):
                        os.remove(tmp_file)
                    return True
                else:
                    logger.warning(f"ElevenLabs API returned status {res.status_code}: {res.text[:100]}")
        except Exception as e:
            logger.warning(f"ElevenLabs speech synthesis failed: {e}")
        return False

    def _play_audio_file(self, file_path: str):
        """Plays synthesized mp3 audio file using pygame or PowerShell."""
        played = False

        # Try 1: Pygame
        try:
            import pygame
            self._ensure_pygame_init()
            pygame.mixer.music.load(file_path)
            pygame.mixer.music.play()

            while pygame.mixer.music.get_busy():
                if self.on_amplitude_callback:
                    self.on_amplitude_callback(random.uniform(0.3, 0.95))
                time.sleep(0.05)

            pygame.mixer.music.unload()
            played = True
        except Exception as e:
            logger.debug(f"Pygame audio playback failed: {e}")

        # Try 2: PowerShell MediaPlayer fallback
        if not played:
            try:
                if self.on_amplitude_callback:
                    self.on_amplitude_callback(random.uniform(0.5, 0.9))

                ps_cmd = f'''
                Add-Type -AssemblyName presentationCore
                $player = New-Object System.Windows.Media.MediaPlayer
                $player.Open([Uri]::new("{file_path}"))
                $player.Play()
                Start-Sleep -Seconds 1
                while ($player.Position -lt $player.NaturalDuration.TimeSpan) {{
                    Start-Sleep -Milliseconds 100
                }}
                $player.Close()
                '''
                subprocess.run(["powershell", "-Command", ps_cmd], capture_output=True, timeout=15)
                played = True
            except Exception as e:
                logger.debug(f"PowerShell playback failed: {e}")

    def _speak_pyttsx3(self, text: str):
        """Offline Windows SAPI5 speech synthesis using pyttsx3."""
        try:
            import pyttsx3
            engine = pyttsx3.init()
            engine.setProperty('rate', self.rate)
            voices = engine.getProperty('voices')
            for v in voices:
                if "david" in v.name.lower() or "male" in v.name.lower() or "mark" in v.name.lower():
                    engine.setProperty('voice', v.id)
                    break

            if self.on_amplitude_callback:
                self.on_amplitude_callback(random.uniform(0.5, 0.9))

            engine.say(text)
            engine.runAndWait()
        except Exception as e:
            logger.error(f"pyttsx3 speech error: {e}")

    async def speak_async(self, text: str):
        """Async wrapper calling speak in background thread."""
        threading.Thread(target=self.speak, args=(text,), daemon=True).start()

"""
JARVIS v4 - Speech To Text (Faster-Whisper CUDA Accelerated)
"""

import os
import sys
import tempfile
import numpy as np
from typing import Optional
from config.settings import settings
from utils.logger import logger

# Automatically register CUDA 12 DLL paths if installed via pip on Windows
for path in [
    os.path.expanduser(r"~\AppData\Roaming\Python\Python314\site-packages\nvidia\cublas\bin"),
    os.path.expanduser(r"~\AppData\Roaming\Python\Python314\site-packages\nvidia\cudnn\bin"),
    os.path.join(sys.prefix, "Lib", "site-packages", "nvidia", "cublas", "bin"),
    os.path.join(sys.prefix, "Lib", "site-packages", "nvidia", "cudnn", "bin")
]:
    if os.path.exists(path):
        if hasattr(os, "add_dll_directory"):
            try:
                os.add_dll_directory(path)
            except Exception:
                pass
        os.environ["PATH"] = path + os.pathsep + os.environ.get("PATH", "")


class SpeechToText:
    def __init__(self):
        self.model = None
        self._init_model()

    def _init_model(self):
        try:
            from faster_whisper import WhisperModel
            device = settings.WHISPER_DEVICE
            compute_type = settings.WHISPER_COMPUTE_TYPE
            self.model = WhisperModel(
                settings.WHISPER_MODEL,
                device=device,
                compute_type=compute_type
            )
            logger.info(f"Faster-Whisper STT model loaded on {device} ({compute_type}).")
        except Exception as e:
            logger.warning(f"Faster-Whisper CUDA initialization failed ({e}). Falling back to CPU.")
            try:
                from faster_whisper import WhisperModel
                self.model = WhisperModel(settings.WHISPER_MODEL, device="cpu", compute_type="int8")
                logger.info("Faster-Whisper STT model loaded on CPU (int8).")
            except Exception as ex:
                logger.error(f"Faster-Whisper CPU fallback failed: {ex}")

    def transcribe_audio_file(self, audio_path: str) -> str:
        """Transcribes an audio file to text with automatic CPU fallback on CUDA error."""
        if self.model:
            try:
                segments, info = self.model.transcribe(
                    audio_path,
                    beam_size=5,
                    vad_filter=True,
                    vad_parameters=dict(min_silence_duration_ms=500),
                    initial_prompt="Hinglish voice command for JARVIS: YouTube kholo, Google pe search karo, WhatsApp pe message bhejo, volume 50 percent, screenshot lo."
                )
                text = " ".join([segment.text for segment in segments]).strip()
                return text
            except Exception as e:
                logger.warning(f"Faster-Whisper CUDA runtime error ({e}). Re-initializing STT on CPU...")
                try:
                    from faster_whisper import WhisperModel
                    self.model = WhisperModel(settings.WHISPER_MODEL, device="cpu", compute_type="int8")
                    segments, info = self.model.transcribe(
                        audio_path,
                        beam_size=5,
                        vad_filter=True,
                        vad_parameters=dict(min_silence_duration_ms=500),
                        initial_prompt="Hinglish voice command for JARVIS"
                    )
                    return " ".join([segment.text for segment in segments]).strip()
                except Exception as ex:
                    logger.error(f"CPU transcription fallback failed: {ex}")

        # SpeechRecognition fallback (only if Faster-Whisper is completely unavailable)
        try:
            import speech_recognition as sr
            r = sr.Recognizer()
            with sr.AudioFile(audio_path) as source:
                audio = r.record(source)
                return r.recognize_google(audio)
        except Exception:
            return ""

    def transcribe_audio_array(self, audio_data: np.ndarray, sample_rate: int = 16000) -> str:
        """Transcribes raw numpy float32 audio samples."""
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            import soundfile as sf
            sf.write(tmp_path, audio_data, sample_rate)
            result = self.transcribe_audio_file(tmp_path)
            return result
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

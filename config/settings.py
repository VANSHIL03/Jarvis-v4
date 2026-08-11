"""
JARVIS v4 - System Settings & Configuration
Optimized for Windows 11, RTX 4050 GPU (6GB VRAM), Ryzen 7 CPU, 16GB RAM.
"""

import os
from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    BASE_DIR: Path = BASE_DIR
    # Assistant Metadata
    ASSISTANT_NAME: str = "JARVIS"
    VERSION: str = "4.0.0"
    WAKE_WORD: str = "jarvis"

    # Local LLM & Ollama Configuration
    OLLAMA_BASE_URL: str = "http://127.0.0.1:11434"
    DEFAULT_MODEL: str = "jarvis-model"
    FALLBACK_MODEL: str = "qwen2.5:7b"
    LLM_TEMPERATURE: float = 0.3
    LLM_MAX_TOKENS: int = 2048
    USE_CUDA: bool = True

    # Hardware & Performance Constraints (RTX 4050 6GB VRAM)
    MAX_VRAM_USAGE_GB: float = 5.5
    SYSTEM_POLL_INTERVAL: float = 1.0  # seconds

    # Database & Storage Paths
    DATA_DIR: Path = BASE_DIR / "data"
    DB_PATH: Path = DATA_DIR / "jarvis.db"
    VECTOR_DB_DIR: Path = DATA_DIR / "vector_store"
    LOGS_DIR: Path = BASE_DIR / "logs"

    # Speech Configuration
    WHISPER_MODEL: str = "base"
    WHISPER_DEVICE: str = "cuda"
    WHISPER_COMPUTE_TYPE: str = "float16"
    TTS_ENGINE: str = "edge-tts"
    TTS_VOICE: str = "en-US-ChristopherNeural"  # Deep, futuristic male AI voice
    SPEECH_RATE: int = 165  # Crisp, authoritative speech rate

    # Vision Settings
    WEBCAM_INDEX: int = 0
    FACIAL_RECOGNITION_ENABLED: bool = True

    # Safety & Security
    SAFETY_CONFIRMATION_REQUIRED: bool = True
    GITHUB_TOKEN: str = ""
    GITHUB_USERNAME: str = ""
    DANGEROUS_COMMAND_KEYWORDS: list[str] = Field(
        default_factory=lambda: [
            "delete file", "format drive", "shutdown", "restart",
            "send email", "rmdir /s", "del /f", "drop table", "uninstall"
        ]
    )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

# Create singleton instance
settings = Settings()

# Ensure directories exist
settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
settings.VECTOR_DB_DIR.mkdir(parents=True, exist_ok=True)
settings.LOGS_DIR.mkdir(parents=True, exist_ok=True)

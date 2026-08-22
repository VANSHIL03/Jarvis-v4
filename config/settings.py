"""
JARVIS v4 - System Settings & Configuration
Optimized for Windows 11, RTX 4050 GPU (6GB VRAM), Ryzen 7 CPU, 16GB RAM.
"""

import os
from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).resolve().parent.parent

# Module-level so other field defaults can be built from it. A pydantic field
# default cannot reference another field, so paths that live under data/ are
# derived from this instead of from Settings.DATA_DIR.
DATA_DIR_DEFAULT = BASE_DIR / "data"

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
    DATA_DIR: Path = DATA_DIR_DEFAULT
    DB_PATH: Path = DATA_DIR_DEFAULT / "jarvis.db"
    VECTOR_DB_DIR: Path = DATA_DIR_DEFAULT / "vector_store"
    LOGS_DIR: Path = BASE_DIR / "logs"

    # Speech Configuration
    WHISPER_MODEL: str = "base"
    WHISPER_DEVICE: str = "cuda"
    WHISPER_COMPUTE_TYPE: str = "float16"
    TTS_ENGINE: str = "edge-tts"
    TTS_VOICE: str = "hi-IN-MadhurNeural"  # Deep Indian male Neural AI voice — fluent Hinglish & English
    SPEECH_RATE: int = 150  # Natural conversational speech rate

    # Vision Settings
    WEBCAM_INDEX: int = 0
    FACIAL_RECOGNITION_ENABLED: bool = True

    # Safety & Security
    SAFETY_CONFIRMATION_REQUIRED: bool = True

    # Where the user's per-tool permission overrides live. PermissionPolicy reads
    # this file if it exists; a missing file simply means "use the built-in
    # four-tier defaults", so deleting it is a safe way to reset the policy.
    PERMISSIONS_FILE: Path = DATA_DIR_DEFAULT / "permissions.json"

    # How long a pending "haan ya na" confirmation stays answerable. After this
    # the held action is discarded WITHOUT executing, so a forgotten prompt can
    # never fire later when the user has moved on.
    CONFIRMATION_TTL_SECONDS: float = 120.0

    # Lifetime of SHORT_TERM memories ("kal doctor ke paas jana hai"). They are
    # purged from both SQLite and the vector store once this many days pass.
    MEMORY_SHORT_TERM_TTL_DAYS: int = 7

    GITHUB_TOKEN: str = ""
    GITHUB_USERNAME: str = ""
    EMAIL_ADDRESS: str = ""
    EMAIL_PASSWORD: str = ""

    # n8n Local Workflow Automation Integration
    N8N_BASE_URL: str = "http://localhost:5678"
    N8N_API_KEY: str = ""
    N8N_WEBHOOK_BASE_URL: str = "http://localhost:5678/webhook"
    N8N_TIMEOUT_SECONDS: float = 30.0
    N8N_MAX_RETRIES: int = 3

    # Grok AI (xAI API) Integration
    GROK_API_KEY: str = ""
    GROK_BASE_URL: str = "https://api.x.ai/v1"
    GROK_MODEL: str = "grok-2-mini"

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

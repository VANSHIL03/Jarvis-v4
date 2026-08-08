# J.A.R.V.I.S. v4 - Production Desktop AI Assistant for Windows 11

![JARVIS v4](https://img.shields.io/badge/JARVIS-v4.0.0-00d2ff?style=for-the-badge)
![Platform](https://img.shields.io/badge/Platform-Windows%2011-blue?style=for-the-badge)
![GPU](https://img.shields.io/badge/GPU-NVIDIA%20RTX%204050-76b900?style=for-the-badge)
![Python](https://img.shields.io/badge/Python-3.10%2B-yellow?style=for-the-badge)

**J.A.R.V.I.S. v4** is a complete, modular, local-first desktop AI assistant built for Windows 11 with Python, PySide6, Ollama/llama.cpp (CUDA accelerated), Faster-Whisper, FAISS vector memory, OpenCV vision, and multi-agent computer automation.

---

## Key Features

- **Iron Man Persona & Chain-of-Thought Reasoning**: Respectful, witty, highly capable assistant. Internal `<thought>` planning is executed silently without cluttering spoken responses.
- **Multi-Agent Scalable Architecture**:
  - `PlannerAgent`: Executive orchestrator delegating tasks to sub-agents.
  - `MemoryAgent`: RAG vector search (FAISS + SentenceTransformers) & SQLite memory.
  - `CodingAgent`: Writes, debugs, and executes Python, Java, C++, JS, React, Unity C#.
  - `BrowserAgent`: Playwright automated web browsing, YouTube music, Google search.
  - `WindowsAgent`: System controls (volume, brightness, power), app launcher, PyAutoGUI.
  - `WhatsAppAgent`: Native WhatsApp Desktop UI messaging & document sender.
  - `VisionAgent`: Webcam feed, facial detection/recognition, EasyOCR screen reader.
  - `EmailAgent`: IMAP/SMTP email reader, composer, sender.
  - `FileAgent`: Windows file explorer operations & Office docx/xlsx/pptx/pdf generation & summarization.
  - `GamingAgent`: Steam launcher & Unity development helper.
- **Futuristic PySide6 HUD UI**: Dark glassmorphism theme (`#060911` with `#00d2ff` neon accents), animated QPainter waveform visualizer, live CPU/GPU/RAM hardware gauges, and terminal log view.
- **Safety Interceptor**: Explicit user authorization prompts for high-risk operations (file deletion, formatting, system power commands, sending emails).
- **Self-Learning Feedback Loop**: Learns user preferences and correction rules on the fly, storing them in local SQLite + FAISS memory.

---

## Hardware Requirements

- **OS**: Windows 11
- **GPU**: NVIDIA RTX 4050 Laptop GPU (6 GB VRAM) or higher (CUDA acceleration)
- **CPU**: AMD Ryzen 7 / Intel Core i7
- **RAM**: 16 GB
- **Software Dependencies**: Python 3.10+, Ollama

---

## Installation Guide

### 1. Clone or Open Project Directory
```powershell
cd "c:\Users\vansh\Desktop\Jarvis v4"
```

### 2. Install Python Dependencies
```powershell
pip install -r requirements.txt
```

### 3. Install Playwright Chromium Browser Drivers
```powershell
playwright install chromium
```

### 4. Install & Run Local LLM (Ollama)
Download and install [Ollama for Windows](https://ollama.com). Run your choice of local open-source LLM:
```powershell
ollama run llama3.1:8b
# or
ollama run qwen2.5:7b
```

---

## Running JARVIS v4

To launch the PySide6 HUD desktop application:

```powershell
python main.py
```

---

## Testing

Run the full automated pytest test suite:

```powershell
pytest tests/
```

---

## Project Folder Structure

```
Jarvis v4/
│
├── config/             # Pydantic settings & system prompts
├── memory/             # SQLite DB manager & FAISS vector store
├── ai/                 # Async Ollama CUDA LLM client
├── speech/             # Faster-Whisper STT, Edge-TTS, Wake Word
├── vision/             # OpenCV camera feed, face detection, EasyOCR
├── automation/         # Windows OS, PyAutoGUI, Playwright, Office, Email
├── security/           # Safety & security confirmation interceptor
├── plugins/            # Extensible plugin system (WhatsApp, VSCode, Chrome, Spotify, etc.)
├── agents/             # Multi-agent system (Planner, Memory, Coding, Browser, Windows, WhatsApp, Vision, Email, File, Gaming)
├── ui/                 # PySide6 HUD window, waveform visualizer, system gauges
├── tests/              # Pytest unit tests suite
├── schema.sql          # SQLite schema
├── requirements.txt    # Python package dependencies
├── architecture.md     # Architectural specification
├── README.md           # User guide
└── main.py             # Main application entry point
```

---

## License

Production Ready - Built for Windows 11 Platform.

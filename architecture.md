# JARVIS v4 - Deep Dive Architecture Specification

JARVIS v4 is a modular, production-ready, local-first desktop AI assistant engineered specifically for **Windows 11** on hardware featuring an **NVIDIA RTX 4050 Laptop GPU (6GB VRAM)**, **Ryzen 7 CPU**, and **16GB RAM**.

---

## 1. System Overview & Component Diagram

```
+-----------------------------------------------------------------------------------+
|                            PySide6 Desktop HUD UI                                 |
|  [Waveform Visualizer] [System Metrics HUD] [Dark Glass Feed] [Interactive Console]|
+-----------------------------------------+-----------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
|                                   JARVIS Core                                     |
|                      (Async Loop, Safety Manager, Event Bus)                      |
+-----------------------------------------+-----------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
|                                  Planner Agent                                    |
|               (CoT Internal Reasoning <thought> & Intent Parsing)                 |
+-------+---------------+-----------------+---------------+-----------------+-------+
        |               |                 |               |                 |
        v               v                 v               v                 v
  +-----------+   +-----------+     +-----------+   +-----------+     +-----------+
  | Memory    |   | Coding    |     | Browser   |   | Windows   |     | WhatsApp  |
  | Agent     |   | Agent     |     | Agent     |   | Agent     |     | Agent     |
  +-----------+   +-----------+     +-----------+   +-----------+     +-----------+
        |               |                 |               |                 |
        v               v                 v               v                 v
  +-----------+   +-----------+     +-----------+   +-----------+     +-----------+
  | Vision    |   | Email     |     | File      |   | Gaming    |     | Speech    |
  | Agent     |   | Agent     |     | Agent     |   | Agent     |     | System    |
  +-----------+   +-----------+     +-----------+   +-----------+     +-----------+
```

---

## 2. Multi-Agent System Roles

1. **Executive Planner Agent (`agents/planner_agent.py`)**:
   - Analyzes incoming user prompts combined with short-term history and semantic vector memory.
   - Executes internal chain-of-thought (`<thought>...</thought>`).
   - Emits structured JSON delegation payloads to specialized sub-agents.
   - Synthesizes final natural voice responses.

2. **Memory Agent (`agents/memory_agent.py`)**:
   - Manages SQLite tables (`conversations`, `user_facts`, `self_learning_corrections`, `contacts`, `app_shortcuts`).
   - Conducts FAISS vector embeddings search (`sentence-transformers/all-MiniLM-L6-v2`) for semantic memory recall.
   - Handles real-time self-learning feedback correction loops.

3. **Coding Agent (`agents/coding_agent.py`)**:
   - Generates, explains, and debugs code across Python, Java, C++, HTML/CSS/JS, React, and Unity C#.
   - Executes Python snippets in an isolated subprocess execution sandbox.

4. **Browser Agent (`agents/browser_agent.py`)**:
   - Automated web control via async Playwright Chromium.
   - Google search snippet extraction, YouTube music playback, Wikipedia queries, form filling.

5. **Windows Agent (`agents/windows_agent.py`)**:
   - Controls OS functions: launches applications (VSCode, Chrome, Edge, Notepad, Calculator, Paint, CMD, Settings, Explorer).
   - Manages system volume via `pycaw`, brightness via `screen_brightness_control`, power commands (lock, sleep, restart, shutdown).
   - Performs mouse and keyboard typing/clicking via `PyAutoGUI` and `PyWinAuto`.

6. **WhatsApp Agent (`agents/whatsapp_agent.py`)**:
   - Native Windows UI automation for WhatsApp Desktop.
   - Searches contacts, sends chat messages, reads unread notifications, attaches files and documents, sends voice notes.

7. **Vision Agent (`agents/vision_agent.py`)**:
   - OpenCV webcam frame reader & facial recognition/detection.
   - EasyOCR screen capture reader for text extraction.

8. **Email Agent (`agents/email_agent.py`)**:
   - IMAP/SMTP client for reading, searching, composing, and sending emails.

9. **File Agent (`agents/file_agent.py`)**:
   - File system operations (create folder, rename, delete, copy, move, glob search).
   - Office automation: Word (`python-docx`), Excel (`openpyxl`), PowerPoint (`python-pptx`), PDF extraction & summarization (`pypdf`, `pdfplumber`).

10. **Gaming Agent (`agents/gaming_agent.py`)**:
    - Steam game launcher integration.
    - Unity Hub & C# script template creator.

---

## 3. Hardware Acceleration & Local LLM

- **GPU Acceleration**: NVIDIA RTX 4050 Laptop GPU (6GB VRAM) running CUDA float16/int8 workloads.
- **LLM Engine**: Local Ollama server (`http://localhost:11434`) running `llama3.1:8b` or `qwen2.5:7b`.
- **STT Engine**: `Faster-Whisper` running on CUDA float16.
- **TTS Engine**: `Edge-TTS` (online human-like voice synthesis) with `pyttsx3` offline fallback.

---

## 4. Security & Safety Architecture

- **`SafetyManager` (`security/safety.py`)**:
  - Intercepts all sub-agent execution payloads before execution.
  - Matches requested actions against high-risk action lists (deleting files, disk formatting, system power commands, sending emails).
  - Prompts user via UI/Console authorization dialog prior to execution.

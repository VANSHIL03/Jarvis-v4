"""
JARVIS v4 - Main PySide6 Arc Reactor HUD Desktop Dashboard Window
Iron Man inspired UI with animated arc reactor, compact chat, voice input, and mic toggle.
"""

import sys
import re
import asyncio
import threading
import time
import numpy as np
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QProgressBar, QStatusBar, QSpacerItem, QSizePolicy
)
from PySide6.QtCore import Qt, QTimer, Signal, Slot, QSize
from PySide6.QtGui import QFont, QColor, QIcon

from ui.components.arc_reactor_widget import ArcReactorWidget
from ui.components.stark_hud_widget import StarkHudWidget
from ui.components.chat_widget import ChatWidget
from ui.components.sys_monitor_widget import SystemMonitorWidget
from utils.system_monitor import SystemMonitor
from utils.sound_pack import SoundPackManager
from utils.logger import logger


class JarvisMainWindow(QMainWindow):
    # Qt Signals for cross-thread GUI updates
    request_finished_signal = Signal(dict)
    request_error_signal = Signal(str)
    voice_text_signal = Signal(str)
    mic_level_signal = Signal(float)

    def __init__(self, planner_agent=None, tts_engine=None, stt_engine=None):
        super().__init__()
        self.planner_agent = planner_agent
        self.tts_engine = tts_engine
        self.stt_engine = stt_engine
        self.sys_monitor = SystemMonitor()

        # Mic state
        self._mic_active = True
        self._listening = False
        self.sound_pack = SoundPackManager()

        self.setWindowTitle("J.A.R.V.I.S. v4 - Advanced Windows Desktop Assistant")
        self.resize(1200, 900)
        self._init_ui()

        # Connect signals
        self.request_finished_signal.connect(self._on_request_finished)
        self.request_error_signal.connect(self._on_request_error)
        self.voice_text_signal.connect(self._on_voice_text)
        self.mic_level_signal.connect(self._on_mic_level)

        # Connect TTS amplitude callback to Stark HUD for reactive pulsing
        if self.tts_engine and hasattr(self, 'stark_hud'):
            self.tts_engine.set_amplitude_callback(self.stark_hud.set_amplitude)

        # Play authentic JARVIS startup sound
        self.sound_pack.play_welcome()

        # Hardware telemetry timer (1 sec)
        self.telemetry_timer = QTimer(self)
        self.telemetry_timer.timeout.connect(self._update_hardware_metrics)
        self.telemetry_timer.start(1000)

        # Start voice listener thread
        if self.stt_engine:
            self._start_voice_listener()

    def _init_ui(self):
        # Dark Futuristic Window Styling
        self.setStyleSheet("""
            QMainWindow {
                background-color: #060911;
            }
        """)

        main_widget = QWidget()
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(15, 10, 15, 0)
        main_layout.setSpacing(8)

        # ═══ Top Header Bar ═══
        header_hbox = QHBoxLayout()
        header_hbox.setSpacing(10)

        title_lbl = QLabel("J.A.R.V.I.S.  v4.0  //  IRON MAN AI SYSTEM")
        title_lbl.setStyleSheet(
            "color: #00d2ff; font-size: 16px; font-weight: bold; "
            "font-family: 'Consolas', monospace; background: transparent; border: none;"
        )

        # Reactive Mic Level Bar
        mic_lbl = QLabel("MIC IN:")
        mic_lbl.setStyleSheet("color: #00ffaa; font-family: 'Consolas', monospace; font-size: 11px; font-weight: bold;")

        self.mic_level_bar = QProgressBar()
        self.mic_level_bar.setRange(0, 100)
        self.mic_level_bar.setValue(0)
        self.mic_level_bar.setFixedSize(120, 14)
        self.mic_level_bar.setTextVisible(False)
        self.mic_level_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid rgba(0, 255, 170, 80);
                border-radius: 4px;
                background-color: rgba(5, 12, 24, 220);
            }
            QProgressBar::chunk {
                background-color: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 #00ffaa, stop:1 #00d2ff
                );
                border-radius: 3px;
            }
        """)

        # Mic Toggle Button
        self.mic_btn = QPushButton("🎤 MIC ON")
        self.mic_btn.setFixedSize(110, 32)
        self.mic_btn.setCursor(Qt.PointingHandCursor)
        self._update_mic_btn_style()
        self.mic_btn.clicked.connect(self._toggle_mic)

        # Settings Button
        settings_btn = QPushButton("⚙ SETTINGS")
        settings_btn.setFixedSize(110, 32)
        settings_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(0, 180, 255, 25);
                border: 1px solid rgba(0, 180, 255, 80);
                color: #00d2ff;
                font-weight: bold;
                font-size: 11px;
                border-radius: 4px;
                font-family: 'Consolas', monospace;
            }
            QPushButton:hover {
                background-color: rgba(0, 180, 255, 60);
            }
        """)
        settings_btn.clicked.connect(self._open_settings)

        header_hbox.addWidget(title_lbl)
        header_hbox.addStretch()
        header_hbox.addWidget(mic_lbl)
        header_hbox.addWidget(self.mic_level_bar)
        header_hbox.addWidget(self.mic_btn)
        header_hbox.addWidget(settings_btn)
        main_layout.addLayout(header_hbox)

        # ═══ Center: Stark Industries Interactive Holographic HUD ═══
        hud_container = QHBoxLayout()
        hud_container.addStretch()
        self.stark_hud = StarkHudWidget()
        self.stark_hud.setMinimumSize(850, 480)
        self.stark_hud.node_clicked_signal.connect(self._on_hud_node_clicked)
        hud_container.addWidget(self.stark_hud)
        hud_container.addStretch()
        main_layout.addLayout(hud_container, stretch=6)

        # Connect TTS amplitude callback to Stark HUD for reactive pulsing
        if self.tts_engine:
            self.tts_engine.set_amplitude_callback(self.stark_hud.set_amplitude)

        # ═══ Bottom: Chat Feed ═══
        self.chat_widget = ChatWidget()
        self.chat_widget.user_submitted_message.connect(self._on_user_message)
        self.chat_widget.user_submitted_message_with_attachment.connect(self._on_user_message_with_attachment)
        main_layout.addWidget(self.chat_widget, stretch=3)

        self.setCentralWidget(main_widget)

        # ═══ Bottom Status Bar (System Metrics) ═══
        self.sys_widget = SystemMonitorWidget()
        self.setStatusBar(QStatusBar())
        self.statusBar().addPermanentWidget(self.sys_widget, 1)
        self.statusBar().setStyleSheet("QStatusBar { background: transparent; border: none; }")

        # Initial Interactive Welcome Message
        name = "Vanshil"
        try:
            if self.planner_agent:
                facts = self.planner_agent.memory.get_all_facts()
                name_fact = next((f["value_data"] for f in facts if f.get("key_name") == "user_name"), None)
                if name_fact:
                    name = name_fact.split()[0]
        except Exception:
            pass

        welcome_text = (
            f"Good day, Sir {name}. All systems operational, local GPU core online, "
            "and hardware telemetry running at nominal efficiency. "
            "Main aapki kya sewa kar sakta hoon, Sir? "
            "Kya aap koi game khelna chahenge, daily news sunna chahenge, ya kisi naye project pe kaam karna chahenge?"
        )
        self.chat_widget.append_jarvis_message(welcome_text)
        if self.tts_engine:
            threading.Thread(target=self.tts_engine.speak, args=(welcome_text,), daemon=True).start()

        # Register Reminder Trigger Callback
        try:
            if self.planner_agent and hasattr(self.planner_agent, 'reminder_mgr'):
                def _speak_reminder(msg: str):
                    if self.tts_engine:
                        threading.Thread(target=self.tts_engine.speak, args=(msg,), daemon=True).start()

                def _ui_reminder(msg: str):
                    self.chat_widget.append_jarvis_message(msg)

                self.planner_agent.reminder_mgr.set_callbacks(_speak_reminder, _ui_reminder)
        except Exception:
            pass

    @Slot(float)
    def _on_mic_level(self, rms: float):
        """Updates real-time microphone level bar and animates Arc Reactor glow as user speaks."""
        val = int(min(1.0, rms * 55.0) * 100)
        self.mic_level_bar.setValue(val)
        if hasattr(self, 'stark_hud'):
            if val > 4:
                self.stark_hud.set_amplitude(val / 100.0)
            elif not self.tts_engine or not self.tts_engine.is_speaking:
                self.stark_hud.set_amplitude(0.05)

    # ─── Mic Toggle ───
    def _toggle_mic(self):
        self._mic_active = not self._mic_active
        self._update_mic_btn_style()
        if not self._mic_active:
            self.mic_level_bar.setValue(0)
            self.chat_widget.append_system_log("Microphone Muted.")
        else:
            self.chat_widget.append_system_log("Microphone Active.")

    def _update_mic_btn_style(self):
        if self._mic_active:
            self.mic_btn.setText("🎤 MIC ON")
            self.mic_btn.setStyleSheet("""
                QPushButton {
                    background-color: rgba(0, 255, 170, 30);
                    border: 1px solid #00ffaa;
                    color: #00ffaa;
                    font-weight: bold;
                    font-size: 11px;
                    border-radius: 4px;
                    font-family: 'Consolas', monospace;
                }
                QPushButton:hover {
                    background-color: rgba(0, 255, 170, 70);
                }
            """)
        else:
            self.mic_btn.setText("🔇 MIC OFF")
            self.mic_btn.setStyleSheet("""
                QPushButton {
                    background-color: rgba(255, 50, 80, 30);
                    border: 1px solid #ff3250;
                    color: #ff3250;
                    font-weight: bold;
                    font-size: 11px;
                    border-radius: 4px;
                    font-family: 'Consolas', monospace;
                }
                QPushButton:hover {
                    background-color: rgba(255, 50, 80, 70);
                }
            """)

    # ─── Voice Listener Thread ───
    def _start_voice_listener(self):
        """Starts continuous voice listening using Realtek Microphone Array + Faster-Whisper."""
        def _voice_loop():
            try:
                import sounddevice as sd
                import soundfile as sf
                import tempfile
                import os
                import queue

                SAMPLE_RATE = 16000
                CHUNK_DURATION = 5.0  # 5 seconds chunk to capture complete long spoken commands
                SILENCE_THRESHOLD = 0.0004

                # Find Realtek Microphone Array device index
                realtek_dev = None
                try:
                    for i, d in enumerate(sd.query_devices()):
                        if d.get("max_input_channels", 0) > 0 and "realtek" in d.get("name", "").lower():
                            realtek_dev = i
                            logger.info(f"Selected audio input device: '{d['name']}' (Index {i})")
                            break
                except Exception as e:
                    logger.warning(f"Could not query audio devices: {e}")

                audio_q = queue.Queue()

                def callback(indata, frames, time_info, status):
                    # Echo Cancellation: Ignore mic input when JARVIS is speaking out loud
                    if not self._mic_active or (self.tts_engine and self.tts_engine.is_speaking):
                        self.mic_level_signal.emit(0.0)
                        return
                    rms = float(np.sqrt(np.mean(indata ** 2)))
                    self.mic_level_signal.emit(rms)
                    audio_q.put(indata.copy())

                stream_kwargs = {
                    "samplerate": SAMPLE_RATE,
                    "channels": 1,
                    "dtype": "float32",
                    "callback": callback,
                    "blocksize": int(SAMPLE_RATE * 0.08)  # 80ms blocks for smooth UI reaction
                }
                if realtek_dev is not None:
                    stream_kwargs["device"] = realtek_dev

                CHUNK_DURATION = 3.5  # 3.5s chunk for snappy voice responsiveness

                with sd.InputStream(**stream_kwargs):
                    chunk_samples = int(CHUNK_DURATION * SAMPLE_RATE)
                    while True:
                        collected = []
                        total_count = 0
                        
                        while total_count < chunk_samples:
                            if self.tts_engine and self.tts_engine.is_speaking:
                                collected.clear()
                                total_count = 0
                                audio_q.queue.clear()
                                time.sleep(0.1)
                                break
                            try:
                                block = audio_q.get(timeout=0.1)
                                collected.append(block)
                                total_count += len(block)
                            except queue.Empty:
                                pass

                        if not collected or not self._mic_active or (self.tts_engine and self.tts_engine.is_speaking):
                            continue

                        audio_data = np.concatenate(collected, axis=0).flatten()

                        # Calculate RMS volume level
                        rms = float(np.sqrt(np.mean(audio_data ** 2)))
                        if rms < 0.0001:
                            continue

                        # Smart dynamic auto-gain boost for quiet laptop microphones
                        peak = float(np.max(np.abs(audio_data)))
                        if peak > 0.0001:
                            gain = min(15.0, 0.75 / peak)
                            audio_data = np.clip(audio_data * gain, -1.0, 1.0)

                        # Save to temp wav file
                        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                            tmp_path = tmp.name
                        sf.write(tmp_path, audio_data, SAMPLE_RATE)

                        # Transcribe with Faster-Whisper (CUDA)
                        if self.stt_engine and self.stt_engine.model:
                            text = self.stt_engine.transcribe_audio_file(tmp_path)
                        else:
                            try:
                                import speech_recognition as sr
                                recognizer = sr.Recognizer()
                                with sr.AudioFile(tmp_path) as source:
                                    audio = recognizer.record(source)
                                text = recognizer.recognize_google(audio)
                            except Exception:
                                text = ""

                        if os.path.exists(tmp_path):
                            os.remove(tmp_path)

                        text = text.strip()
                        if text:
                            logger.info(f"Voice transcription: '{text}'")
                            # Clean leading wake-word if present, but process all spoken commands
                            command = re.sub(r"^(?:jarvis|jarvas|travis|service)\s*,?\s*", "", text, flags=re.IGNORECASE).strip()
                            command = command.lstrip(",").lstrip(".").strip()
                            if not command:
                                command = text

                            self.voice_text_signal.emit(command)

            except Exception as e:
                logger.warning(f"Voice listener failed to start: {e}")

        threading.Thread(target=_voice_loop, daemon=True).start()

    @Slot(str)
    def _on_voice_text(self, text: str):
        """Handles transcribed voice text on the Qt main thread."""
        if text:
            self._on_user_message(text)

    # ─── Settings ───
    def _open_settings(self):
        from ui.components.settings_widget import SettingsDialog
        dialog = SettingsDialog(self)
        dialog.exec()

    # ─── Telemetry ───
    def _update_hardware_metrics(self):
        data = self.sys_monitor.get_full_telemetry()
        self.sys_widget.update_metrics(data)
        if hasattr(self, 'stark_hud'):
            self.stark_hud.update_telemetry(data)

    def _on_hud_node_clicked(self, node_id: str):
        """Triggers direct automated commands when clicking interactive HUD orbital nodes."""
        node_commands = {
            "food": "swiggy se mera favourite food order kro",
            "shopping": "amazon pe lan cable search krke add to cart kroo",
            "news": "jarvis daily news batao",
            "games": "pc me installed games scan karo",
            "clean": "system memory clean karo",
            "mic": "toggle mic"
        }
        cmd = node_commands.get(node_id)
        if cmd == "toggle mic":
            self._toggle_mic()
        elif cmd:
            self._on_user_message(cmd)

    def _get_salutation(self) -> str:
        """Dynamically retrieves remembered user name or defaults to Sir."""
        try:
            if self.planner_agent:
                facts = self.planner_agent.memory.get_all_facts()
                name_fact = next((f["value_data"] for f in facts if f.get("key_name") == "user_name"), None)
                if name_fact:
                    first_name = name_fact.split()[0]
                    return f"Sir {first_name}"
        except Exception:
            pass
        return "Sir"

    def _on_user_message_with_attachment(self, text: str, image_path: str):
        """Triggered when user submits prompt with an attached photo/screenshot."""
        self._on_user_message(text, image_path=image_path)

    # ─── User Message Processing ───
    def _on_user_message(self, text: str, image_path: Optional[str] = None):
        """Triggered when user enters text, photo attachment, or voice command."""
        self.sys_widget.set_status(f"PROCESSING: '{text[:40]}'...")

        sir = self._get_salutation()
        clean = text.lower()

        if image_path:
            initial_ack = f"Ji {sir}, aapke screenshot ko analyze karke description write kar raha hoon."
            self.chat_widget.append_jarvis_message(initial_ack)
            if self.tts_engine:
                threading.Thread(target=self.tts_engine.speak, args=(initial_ack,), daemon=True).start()

        # Instant initial voice acknowledgment for code requests
        elif "code" in clean and any(k in clean for k in ["write", "likh", "banao", "create", "generate", "give", "do"]):
            initial_ack = f"Ji {sir}, thoda wait kijiye. Main aapka code generate karke Notepad me open kar raha hoon."
            self.chat_widget.append_jarvis_message(initial_ack)
            if self.tts_engine:
                threading.Thread(target=self.tts_engine.speak, args=(initial_ack,), daemon=True).start()

        if self.planner_agent:
            def _worker_thread():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    result = loop.run_until_complete(self.planner_agent.process_user_request(text, image_path=image_path))
                    self.request_finished_signal.emit(result)
                except Exception as e:
                    logger.error(f"Worker thread error: {e}")
                    self.request_error_signal.emit(str(e))
                finally:
                    loop.close()

            threading.Thread(target=_worker_thread, daemon=True).start()

    @Slot(dict)
    def _on_request_finished(self, result: dict):
        speech_reply = result.get("speech_reply", "")
        thought = result.get("thought", "")
        exec_results = result.get("execution_results", [])

        if speech_reply:
            self.chat_widget.append_jarvis_message(speech_reply, thought=thought)

        for item in exec_results:
            agent_name = item.get("agent", "")
            action_name = item.get("action", "")
            res_data = item.get("result", {})

            log_str = f"Agent '{agent_name}' executed '{action_name}'"
            self.chat_widget.append_system_log(log_str)

            # Display generated code or result payload directly in GUI feed
            if isinstance(res_data, dict):
                code_payload = (
                    res_data.get("code") or
                    res_data.get("description") or
                    res_data.get("post_content") or
                    res_data.get("explanation") or
                    res_data.get("debug_result") or
                    res_data.get("stdout")
                )
                lang = res_data.get("language", "Analysis & Description")
                if code_payload:
                    self.chat_widget.append_code_message(code_payload, language=lang)

        if speech_reply and self.tts_engine:
            threading.Thread(target=self.tts_engine.speak, args=(speech_reply,), daemon=True).start()

        self.sys_widget.set_status("SYSTEM READY")

    @Slot(str)
    def _on_request_error(self, err_msg: str):
        self.chat_widget.append_system_log(f"Error: {err_msg}")
        reply = f"Apologies Sir, I got stuck while attempting that process: {err_msg}. How would you like me to proceed?"
        self.chat_widget.append_jarvis_message(reply)
        if self.tts_engine:
            threading.Thread(target=self.tts_engine.speak, args=(reply,), daemon=True).start()
        self.sys_widget.set_status("ERROR")

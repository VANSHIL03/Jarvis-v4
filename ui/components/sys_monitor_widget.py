"""
JARVIS v4 - Futuristic System Telemetry Bar with Glowing Progress Gauges
Displays CPU, GPU VRAM, RAM usage as animated neon bars, plus GPU temperature.
"""

from PySide6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel, QProgressBar
from PySide6.QtCore import Qt


class SystemMonitorWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(60)
        self._init_ui()

    def _init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 6, 14, 6)
        layout.setSpacing(16)

        self.setStyleSheet("""
            QWidget {
                background-color: transparent;
                border-top: 1px solid rgba(0, 180, 255, 30);
                color: #88bbdd;
                font-family: 'Consolas', monospace;
                font-size: 10px;
            }
            QLabel {
                border: none;
                background: transparent;
            }
            QProgressBar {
                border: 1px solid rgba(0, 180, 255, 60);
                border-radius: 3px;
                background-color: rgba(0, 0, 0, 200);
                color: #ffffff;
                font-size: 9px;
                text-align: center;
                height: 14px;
                min-width: 100px;
            }
        """)

        # Status label
        self.status_lbl = QLabel("SYSTEM READY")
        self.status_lbl.setStyleSheet("color: #00d2ff; font-weight: bold; font-size: 11px;")
        layout.addWidget(self.status_lbl)
        layout.addStretch()

        # CPU gauge
        self.cpu_bar = self._create_gauge("CPU", "#00d2ff", "#005f99")
        layout.addLayout(self.cpu_bar["layout"])

        # GPU VRAM gauge
        self.vram_bar = self._create_gauge("VRAM", "#00ff88", "#006633")
        layout.addLayout(self.vram_bar["layout"])

        # RAM gauge
        self.ram_bar = self._create_gauge("RAM", "#ff8800", "#663300")
        layout.addLayout(self.ram_bar["layout"])

        # GPU Temp
        self.temp_lbl = QLabel("GPU: --°C")
        self.temp_lbl.setStyleSheet("color: #ffaa00; font-weight: bold; font-size: 10px;")
        layout.addWidget(self.temp_lbl)

    def _create_gauge(self, name: str, color_start: str, color_end: str) -> dict:
        """Creates a labeled progress bar gauge."""
        hbox = QHBoxLayout()
        hbox.setSpacing(5)

        label = QLabel(f"{name}:")
        label.setStyleSheet(f"color: {color_start}; font-weight: bold;")
        label.setFixedWidth(38)

        bar = QProgressBar()
        bar.setRange(0, 100)
        bar.setValue(0)
        bar.setFixedWidth(110)
        bar.setFixedHeight(14)
        bar.setStyleSheet(f"""
            QProgressBar {{
                border: 1px solid {color_start}40;
                border-radius: 3px;
                background-color: rgba(0, 0, 0, 200);
                color: #ffffff;
                font-size: 9px;
                text-align: center;
            }}
            QProgressBar::chunk {{
                background-color: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 {color_start}, stop:1 {color_end}
                );
                border-radius: 2px;
            }}
        """)

        hbox.addWidget(label)
        hbox.addWidget(bar)

        return {"layout": hbox, "bar": bar, "label": label}

    def update_metrics(self, data: dict):
        cpu = int(data.get('cpu_percent', 0))
        vram = int(data.get('gpu_vram_percent', 0))
        ram = int(data.get('ram_percent', 0))
        temp = data.get('gpu_temp_c', 0)

        self.cpu_bar["bar"].setValue(cpu)
        self.cpu_bar["bar"].setFormat(f"{cpu}%")
        self.vram_bar["bar"].setValue(vram)
        self.vram_bar["bar"].setFormat(f"{vram}%")
        self.ram_bar["bar"].setValue(ram)
        self.ram_bar["bar"].setFormat(f"{ram}%")
        self.temp_lbl.setText(f"GPU: {temp}°C")

    def set_status(self, text: str):
        self.status_lbl.setText(text)

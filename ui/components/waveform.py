"""
JARVIS v4 - Real-time Animated Audio Waveform Visualizer
Custom PySide6 Widget with smooth glowing cyan bars responding to voice activity.
"""

import math
import random
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPainter, QColor, QBrush, QPen, QLinearGradient

class AudioWaveformWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(80)
        self.amplitude = 0.1
        self.phase = 0.0
        self.is_active = False

        # Animation timer (60 FPS)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_animation)
        self.timer.start(16)

    def set_amplitude(self, amp: float):
        """Updates voice amplitude level (0.0 to 1.0)."""
        self.amplitude = max(0.05, min(1.0, amp))
        self.is_active = self.amplitude > 0.1

    def update_animation(self):
        self.phase += 0.08
        if not self.is_active and self.amplitude > 0.05:
            self.amplitude *= 0.95  # smooth decay
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        width = self.width()
        height = self.height()
        center_y = height / 2

        # Dark translucent background
        painter.fillRect(self.rect(), QColor(10, 14, 23, 200))

        bar_count = 32
        bar_spacing = width / bar_count
        bar_width = max(3, bar_spacing * 0.5)

        gradient = QLinearGradient(0, 0, 0, height)
        gradient.setColorAt(0.0, QColor(0, 210, 255, 255))   # Neon Cyan
        gradient.setColorAt(0.5, QColor(0, 150, 255, 220))   # Neon Blue
        gradient.setColorAt(1.0, QColor(0, 50, 150, 100))

        painter.setBrush(QBrush(gradient))
        painter.setPen(Qt.NoPen)

        for i in range(bar_count):
            x = i * bar_spacing + (bar_spacing - bar_width) / 2
            # Calculate height using sine waves & amplitude
            wave = math.sin(self.phase + i * 0.3) * math.cos(self.phase * 0.5 + i * 0.2)
            h = abs(wave) * height * 0.8 * self.amplitude + 4.0
            
            top_y = center_y - h / 2
            painter.drawRoundedRect(x, top_y, bar_width, h, 2, 2)

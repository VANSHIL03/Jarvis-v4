"""
JARVIS v4 - Iron Man Arc Reactor Animated HUD Widget
Custom QPainter widget with concentric rotating rings, pulsing core, and reactive glow.
"""

import math
import random
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, QTimer, QPointF, QRectF
from PySide6.QtGui import (
    QPainter, QColor, QBrush, QPen, QRadialGradient,
    QConicalGradient, QFont, QPainterPath
)


class ArcReactorWidget(QWidget):
    """Animated Iron Man Arc Reactor HUD center piece."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(350, 350)
        self.amplitude = 0.15  # TTS voice amplitude (0.0 - 1.0)
        self.phase = 0.0
        self.ring_rotation = [0.0, 0.0, 0.0, 0.0]  # 4 rotating ring angles
        self.pulse = 0.0

        # 60 FPS animation timer
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._animate)
        self.timer.start(16)

    def set_amplitude(self, amp: float):
        """Updates voice amplitude level (0.0 to 1.0) for reactive glow."""
        self.amplitude = max(0.05, min(1.0, amp))

    def _animate(self):
        self.phase += 0.03
        self.pulse = 0.5 + 0.5 * math.sin(self.phase * 2)
        # Rotate rings at different speeds
        self.ring_rotation[0] += 0.3
        self.ring_rotation[1] -= 0.5
        self.ring_rotation[2] += 0.7
        self.ring_rotation[3] -= 0.2
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w = self.width()
        h = self.height()
        cx = w / 2
        cy = h / 2
        size = min(w, h)

        # Black background
        painter.fillRect(self.rect(), QColor(6, 9, 17))

        # Glow intensity reacts to voice amplitude
        glow_intensity = 0.4 + 0.6 * self.amplitude
        base_alpha = int(120 * glow_intensity)
        bright_alpha = int(255 * glow_intensity)

        # === Outer Ambient Glow ===
        glow_radius = size * 0.48
        glow_grad = QRadialGradient(QPointF(cx, cy), glow_radius)
        glow_grad.setColorAt(0.0, QColor(0, 180, 255, int(40 * glow_intensity)))
        glow_grad.setColorAt(0.5, QColor(0, 100, 200, int(15 * glow_intensity)))
        glow_grad.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.setBrush(QBrush(glow_grad))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(QPointF(cx, cy), glow_radius, glow_radius)

        # === Ring 4 (Outermost) — Thin segmented ring ===
        self._draw_segmented_ring(painter, cx, cy, size * 0.44, size * 0.46,
                                  self.ring_rotation[3], 60, 4,
                                  QColor(0, 140, 220, base_alpha))

        # === Ring 3 — Dotted ring ===
        self._draw_dot_ring(painter, cx, cy, size * 0.40,
                            self.ring_rotation[2], 48,
                            QColor(0, 180, 255, bright_alpha), 3)

        # === Ring 2 — Thick arc segments ===
        self._draw_segmented_ring(painter, cx, cy, size * 0.33, size * 0.37,
                                  self.ring_rotation[1], 24, 10,
                                  QColor(0, 160, 255, base_alpha))

        # === Ring 1 — Inner thin ring with tick marks ===
        self._draw_tick_ring(painter, cx, cy, size * 0.28, size * 0.30,
                             self.ring_rotation[0], 36,
                             QColor(0, 200, 255, bright_alpha))

        # === Inner Glow Ring ===
        inner_r = size * 0.22
        inner_grad = QRadialGradient(QPointF(cx, cy), inner_r)
        inner_grad.setColorAt(0.0, QColor(0, 220, 255, int(80 * glow_intensity)))
        inner_grad.setColorAt(0.6, QColor(0, 150, 255, int(40 * glow_intensity)))
        inner_grad.setColorAt(1.0, QColor(0, 80, 180, 0))
        painter.setBrush(QBrush(inner_grad))
        painter.setPen(QPen(QColor(0, 200, 255, int(100 * glow_intensity)), 1.5))
        painter.drawEllipse(QPointF(cx, cy), inner_r, inner_r)

        # === Central Core ===
        core_r = size * 0.12
        core_pulse = core_r * (1.0 + 0.08 * self.pulse * self.amplitude)
        core_grad = QRadialGradient(QPointF(cx, cy), core_pulse)
        core_grad.setColorAt(0.0, QColor(180, 240, 255, int(200 * glow_intensity)))
        core_grad.setColorAt(0.3, QColor(0, 210, 255, int(160 * glow_intensity)))
        core_grad.setColorAt(0.7, QColor(0, 120, 200, int(80 * glow_intensity)))
        core_grad.setColorAt(1.0, QColor(0, 40, 100, 0))
        painter.setBrush(QBrush(core_grad))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(QPointF(cx, cy), core_pulse, core_pulse)

        # === Center Text ===
        painter.setPen(QColor(180, 230, 255, bright_alpha))
        font_title = QFont("Consolas", int(size * 0.032), QFont.Bold)
        painter.setFont(font_title)
        painter.drawText(QRectF(cx - 60, cy - 18, 120, 24), Qt.AlignCenter, "J.A.R.V.I.S.")

        font_sub = QFont("Consolas", int(size * 0.02))
        painter.setFont(font_sub)
        painter.setPen(QColor(0, 180, 255, int(180 * glow_intensity)))
        painter.drawText(QRectF(cx - 40, cy + 4, 80, 18), Qt.AlignCenter, "MARK IV")

        painter.end()

    def _draw_segmented_ring(self, painter, cx, cy, r_inner, r_outer,
                              rotation, segments, gap_deg, color):
        """Draws a ring made of arc segments with gaps."""
        span = (360 / segments) - gap_deg
        pen = QPen(color, r_outer - r_inner)
        pen.setCapStyle(Qt.FlatCap)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        r_mid = (r_inner + r_outer) / 2
        rect = QRectF(cx - r_mid, cy - r_mid, r_mid * 2, r_mid * 2)
        for i in range(segments):
            start_angle = int((rotation + i * (360 / segments)) * 16)
            span_angle = int(span * 16)
            painter.drawArc(rect, start_angle, span_angle)

    def _draw_dot_ring(self, painter, cx, cy, radius, rotation, count, color, dot_size):
        """Draws a ring of glowing dots."""
        painter.setBrush(QBrush(color))
        painter.setPen(Qt.NoPen)
        for i in range(count):
            angle = math.radians(rotation + i * (360 / count))
            x = cx + radius * math.cos(angle)
            y = cy + radius * math.sin(angle)
            # Vary dot size slightly with phase
            s = dot_size + 1.5 * math.sin(self.phase * 3 + i * 0.5)
            painter.drawEllipse(QPointF(x, y), s, s)

    def _draw_tick_ring(self, painter, cx, cy, r_inner, r_outer, rotation, count, color):
        """Draws radial tick marks around a ring."""
        pen = QPen(color, 1.5)
        painter.setPen(pen)
        for i in range(count):
            angle = math.radians(rotation + i * (360 / count))
            x1 = cx + r_inner * math.cos(angle)
            y1 = cy + r_inner * math.sin(angle)
            x2 = cx + r_outer * math.cos(angle)
            y2 = cy + r_outer * math.sin(angle)
            painter.drawLine(QPointF(x1, y1), QPointF(x2, y2))

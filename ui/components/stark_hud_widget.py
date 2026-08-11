"""
JARVIS v4 - Stark Industries Interactive Holographic HUD Dashboard Widget
Renders Iron Man Stark Expo / Stark Industries Sci-Fi HUD with interactive circular nodes,
top timeline ruler, rotating telemetry gauges, and audio visualizer spectrum.
"""

import math
import random
from datetime import datetime
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, QTimer, QPointF, QRectF, Signal
from PySide6.QtGui import (
    QPainter, QColor, QBrush, QPen, QRadialGradient,
    QConicalGradient, QFont, QPainterPath
)


class StarkHudWidget(QWidget):
    """Full Interactive Iron Man Stark Industries Holographic HUD Dashboard."""

    node_clicked_signal = Signal(str)  # Emits action string when user clicks an orbital HUD node

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(850, 520)
        self.amplitude = 0.15
        self.phase = 0.0
        self.ring_rotation = [0.0, 0.0, 0.0, 0.0]

        # System Metrics
        self.cpu_percent = 28.0
        self.ram_percent = 45.0
        self.vram_percent = 32.0
        self.gpu_temp = 42.0

        # Hover state for interactive orbital nodes
        self.hovered_node = None
        self.setMouseTracking(True)

        # Orbital Nodes (Angles relative to center)
        self.orbital_nodes = [
            {"id": "food", "label": "🍔 FOOD", "angle": -135, "radius_ratio": 0.38, "rect": QRectF()},
            {"id": "shopping", "label": "🛒 SHOPPING", "angle": -45, "radius_ratio": 0.38, "rect": QRectF()},
            {"id": "news", "label": "📰 NEWS", "angle": 45, "radius_ratio": 0.38, "rect": QRectF()},
            {"id": "games", "label": "🎮 GAMES", "angle": 135, "radius_ratio": 0.38, "rect": QRectF()},
            {"id": "clean", "label": "⚡ SYSTEM", "angle": 180, "radius_ratio": 0.44, "rect": QRectF()},
            {"id": "mic", "label": "🎙️ VOICE", "angle": 0, "radius_ratio": 0.44, "rect": QRectF()}
        ]

        # 60 FPS Animation Timer
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._animate)
        self.timer.start(16)

    def set_amplitude(self, amp: float):
        """Updates voice audio amplitude (0.0 to 1.0) for reactive pulsing."""
        self.amplitude = max(0.08, min(1.0, amp))

    def update_telemetry(self, data: dict):
        """Updates live CPU, RAM, VRAM, and Temp metrics."""
        self.cpu_percent = float(data.get("cpu_percent", 28.0))
        self.ram_percent = float(data.get("ram_percent", 45.0))
        self.vram_percent = float(data.get("gpu_vram_percent", 32.0))
        self.gpu_temp = float(data.get("gpu_temp_c", 42.0))

    def _animate(self):
        self.phase += 0.03
        self.ring_rotation[0] += 0.4
        self.ring_rotation[1] -= 0.6
        self.ring_rotation[2] += 0.8
        self.ring_rotation[3] -= 0.3
        self.update()

    def mouseMoveEvent(self, event):
        pos = event.position()
        self.hovered_node = None
        for node in self.orbital_nodes:
            if node["rect"].contains(pos):
                self.hovered_node = node["id"]
                self.setCursor(Qt.PointingHandCursor)
                self.update()
                return
        self.setCursor(Qt.ArrowCursor)
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.hovered_node:
            self.node_clicked_signal.emit(self.hovered_node)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w = self.width()
        h = self.height()
        cx = w / 2
        cy = h / 2 + 10
        size = min(w, h) * 0.95

        # Pitch Black Sci-Fi Background
        painter.fillRect(self.rect(), QColor(4, 7, 14))

        glow_intensity = 0.5 + 0.5 * self.amplitude
        cyan_bright = QColor(0, 240, 255, int(240 * glow_intensity))
        cyan_dim = QColor(0, 180, 255, int(130 * glow_intensity))
        cyan_faint = QColor(0, 140, 220, int(40 * glow_intensity))

        # === 1. Top Date Timeline Ruler Bar ===
        self._draw_top_timeline_ruler(painter, w)

        # === 2. Outer Ambient Radial Glow ===
        glow_r = size * 0.45
        glow_grad = QRadialGradient(QPointF(cx, cy), glow_r)
        glow_grad.setColorAt(0.0, QColor(0, 200, 255, int(50 * glow_intensity)))
        glow_grad.setColorAt(0.6, QColor(0, 100, 200, int(18 * glow_intensity)))
        glow_grad.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.setBrush(QBrush(glow_grad))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(QPointF(cx, cy), glow_r, glow_r)

        # === 3. Central Animated Stark Arc Reactor Core ===
        self._draw_central_arc_reactor(painter, cx, cy, size, glow_intensity)

        # === 4. Left Telemetry Gauges (CPU, RAM, Energy 100%) ===
        self._draw_left_hud_gauges(painter, 20, cy - 140, cyan_bright, cyan_dim)

        # === 5. Right Telemetry Gauges (VRAM, GPU Temp, Weather) ===
        self._draw_right_hud_gauges(painter, w - 180, cy - 140, cyan_bright, cyan_dim)

        # === 6. Interactive Orbital HUD Nodes ===
        self._draw_orbital_nodes(painter, cx, cy, size)

        # === 7. Bottom Frequency Waveform Visualizer & STARK Logo ===
        self._draw_bottom_waveform_and_branding(painter, w, h, cyan_bright)

        painter.end()

    def _draw_top_timeline_ruler(self, painter, w):
        """Draws top calendar timeline ruler (01 02 ... 21 ... 30)."""
        now = datetime.now()
        day_num = now.day

        painter.setPen(QPen(QColor(0, 180, 255, 60), 1))
        painter.drawLine(0, 28, w, 28)

        font_num = QFont("Consolas", 8, QFont.Bold)
        painter.setFont(font_num)

        spacing = w / 31
        for i in range(1, 32):
            x = (i - 0.5) * spacing
            num_str = f"{i:02d}"
            if i == day_num:
                # Active Day Box
                painter.fillRect(QRectF(x - 12, 6, 24, 18), QColor(0, 210, 255, 180))
                painter.setPen(QColor(4, 7, 14))
                painter.drawText(QRectF(x - 12, 6, 24, 18), Qt.AlignCenter, num_str)
            else:
                painter.setPen(QColor(0, 180, 255, 160) if abs(i - day_num) <= 2 else QColor(0, 140, 200, 70))
                painter.drawText(QRectF(x - 12, 6, 24, 18), Qt.AlignCenter, num_str)

        # Right Header City / Date
        date_str = now.strftime("%b %d, %Y  //  %I:%M %p")
        painter.setFont(QFont("Consolas", 9, QFont.Bold))
        painter.setPen(QColor(0, 240, 255, 200))
        painter.drawText(QRectF(w - 240, 32, 220, 20), Qt.AlignRight, date_str)

    def _draw_central_arc_reactor(self, painter, cx, cy, size, glow_intensity):
        """Draws multi-layered concentric rotating rings for Arc Reactor HUD."""
        # Ring 4 (Outermost)
        self._draw_segmented_arc(painter, cx, cy, size * 0.32, size * 0.33, self.ring_rotation[3], 48, 4, QColor(0, 160, 240, int(100 * glow_intensity)))
        # Ring 3 (Dotted)
        self._draw_dot_circle(painter, cx, cy, size * 0.28, self.ring_rotation[2], 36, QColor(0, 220, 255, int(200 * glow_intensity)))
        # Ring 2 (Arc Segments)
        self._draw_segmented_arc(painter, cx, cy, size * 0.22, size * 0.25, self.ring_rotation[1], 20, 10, QColor(0, 180, 255, int(150 * glow_intensity)))
        # Ring 1 (Inner Tick Ring)
        self._draw_tick_circle(painter, cx, cy, size * 0.17, size * 0.19, self.ring_rotation[0], 28, QColor(0, 240, 255, int(220 * glow_intensity)))

        # Central Core
        core_r = size * 0.08 * (1.0 + 0.1 * math.sin(self.phase * 2) * self.amplitude)
        core_grad = QRadialGradient(QPointF(cx, cy), core_r)
        core_grad.setColorAt(0.0, QColor(200, 245, 255, int(240 * glow_intensity)))
        core_grad.setColorAt(0.4, QColor(0, 210, 255, int(180 * glow_intensity)))
        core_grad.setColorAt(1.0, QColor(0, 60, 140, 0))
        painter.setBrush(QBrush(core_grad))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(QPointF(cx, cy), core_r, core_r)

        # Center Text
        painter.setFont(QFont("Consolas", int(size * 0.024), QFont.Bold))
        painter.setPen(QColor(220, 245, 255, int(230 * glow_intensity)))
        painter.drawText(QRectF(cx - 50, cy - 14, 100, 18), Qt.AlignCenter, "J.A.R.V.I.S.")

        painter.setFont(QFont("Consolas", int(size * 0.015)))
        painter.setPen(QColor(0, 190, 255, int(180 * glow_intensity)))
        painter.drawText(QRectF(cx - 40, cy + 4, 80, 14), Qt.AlignCenter, "MARK IV")

    def _draw_left_hud_gauges(self, painter, x, y, cyan_bright, cyan_dim):
        """Draws left circular HUD telemetry dials (CPU %, RAM %)."""
        # --- CPU Ring ---
        self._draw_gauge_dial(painter, x + 40, y + 40, 36, self.cpu_percent, f"CPU\n{int(self.cpu_percent)}%", cyan_bright)

        # --- RAM Ring ---
        self._draw_gauge_dial(painter, x + 125, y + 40, 36, self.ram_percent, f"RAM\n{int(self.ram_percent)}%", cyan_bright)

        # --- Energy Badge ---
        painter.setPen(QPen(QColor(0, 220, 255, 160), 1))
        painter.setBrush(QBrush(QColor(0, 180, 255, 20)))
        painter.drawRoundedRect(QRectF(x, y + 100, 160, 50), 6, 6)

        painter.setFont(QFont("Consolas", 8, QFont.Bold))
        painter.setPen(QColor(0, 240, 255, 220))
        painter.drawText(QRectF(x + 10, y + 106, 140, 16), Qt.AlignLeft, "⚡ ENERGY LEVEL")

        painter.setFont(QFont("Consolas", 12, QFont.Bold))
        painter.setPen(QColor(0, 255, 200, 240))
        painter.drawText(QRectF(x + 10, y + 124, 140, 20), Qt.AlignLeft, "100% HIGH VOLT")

    def _draw_right_hud_gauges(self, painter, x, y, cyan_bright, cyan_dim):
        """Draws right circular HUD telemetry dials (VRAM %, GPU Temp)."""
        # --- VRAM Ring ---
        self._draw_gauge_dial(painter, x + 40, y + 40, 36, self.vram_percent, f"VRAM\n{int(self.vram_percent)}%", cyan_bright)

        # --- GPU Temp Ring ---
        self._draw_gauge_dial(painter, x + 125, y + 40, 36, (self.gpu_temp / 100.0) * 100, f"GPU\n{int(self.gpu_temp)}°C", cyan_bright)

        # --- Status Badge ---
        painter.setPen(QPen(QColor(0, 220, 255, 160), 1))
        painter.setBrush(QBrush(QColor(0, 180, 255, 20)))
        painter.drawRoundedRect(QRectF(x, y + 100, 160, 50), 6, 6)

        painter.setFont(QFont("Consolas", 8, QFont.Bold))
        painter.setPen(QColor(0, 240, 255, 220))
        painter.drawText(QRectF(x + 10, y + 106, 140, 16), Qt.AlignLeft, "🖥️ RTX 4050 GPU")

        painter.setFont(QFont("Consolas", 11, QFont.Bold))
        painter.setPen(QColor(0, 240, 255, 240))
        painter.drawText(QRectF(x + 10, y + 124, 140, 20), Qt.AlignLeft, "CUDA OPERATIONAL")

    def _draw_gauge_dial(self, painter, cx, cy, radius, percent, text, color):
        """Draws a circular arc dial gauge."""
        rect = QRectF(cx - radius, cy - radius, radius * 2, radius * 2)

        # Track Ring
        painter.setPen(QPen(QColor(0, 140, 200, 50), 4))
        painter.setBrush(Qt.NoBrush)
        painter.drawArc(rect, 0, 360 * 16)

        # Fill Arc
        span = int((percent / 100.0) * 360 * 16)
        painter.setPen(QPen(color, 4))
        painter.drawArc(rect, 90 * 16, -span)

        # Center Text
        painter.setFont(QFont("Consolas", 7, QFont.Bold))
        painter.setPen(QColor(220, 245, 255, 220))
        painter.drawText(rect, Qt.AlignCenter, text)

    def _draw_orbital_nodes(self, painter, cx, cy, size):
        """Draws interactive clickable orbital HUD menu nodes."""
        r = size * 0.36
        for node in self.orbital_nodes:
            angle_rad = math.radians(node["angle"] + self.ring_rotation[0] * 0.2)
            nx = cx + r * math.cos(angle_rad)
            ny = cy + r * math.sin(angle_rad)

            node_r = 30
            rect = QRectF(nx - node_r, ny - node_r, node_r * 2, node_r * 2)
            node["rect"] = rect

            is_hovered = (self.hovered_node == node["id"])
            bg_alpha = 180 if is_hovered else 80
            border_color = QColor(0, 255, 220) if is_hovered else QColor(0, 180, 255, 160)

            # Draw Node Bubble
            painter.setBrush(QBrush(QColor(0, 40, 80, bg_alpha)))
            painter.setPen(QPen(border_color, 2 if is_hovered else 1.2))
            painter.drawEllipse(QPointF(nx, ny), node_r, node_r)

            # Connector line to core
            painter.setPen(QPen(QColor(0, 180, 255, 40), 1, Qt.DotLine))
            painter.drawLine(QPointF(cx, cy), QPointF(nx, ny))

            # Label
            painter.setFont(QFont("Consolas", 8, QFont.Bold))
            painter.setPen(QColor(240, 255, 255) if is_hovered else QColor(0, 220, 255, 220))
            painter.drawText(rect, Qt.AlignCenter, node["label"])

    def _draw_bottom_waveform_and_branding(self, painter, w, h, cyan_bright):
        """Draws STARK EXPO branding & bottom audio spectrum visualizer."""
        # STARK EXPO 2026 Logo Watermark
        painter.setFont(QFont("Consolas", 10, QFont.Bold))
        painter.setPen(QColor(0, 180, 255, 120))
        painter.drawText(QRectF(20, h - 35, 200, 20), Qt.AlignLeft, "STARK EXPO 2026")

        painter.setFont(QFont("Consolas", 8))
        painter.setPen(QColor(0, 140, 200, 90))
        painter.drawText(QRectF(20, h - 18, 240, 16), Qt.AlignLeft, "MARK IV // AUTONOMOUS ENGINE")

        # Frequency Audio Spectrum Waveform
        bar_count = 32
        bar_w = 4
        spacing = 3
        start_x = w - (bar_count * (bar_w + spacing)) - 20
        base_y = h - 12

        painter.setPen(Qt.NoPen)
        for i in range(bar_count):
            h_val = random.randint(4, 28) if self.amplitude > 0.15 else random.randint(3, 10)
            h_val = int(h_val * (0.5 + 0.5 * self.amplitude))
            bx = start_x + i * (bar_w + spacing)
            by = base_y - h_val

            painter.setBrush(QBrush(QColor(0, 240, 255, 220 if i % 2 == 0 else 160)))
            painter.drawRoundedRect(QRectF(bx, by, bar_w, h_val), 2, 2)

    def _draw_segmented_arc(self, painter, cx, cy, r_in, r_out, rot, count, gap, color):
        span = (360 / count) - gap
        pen = QPen(color, r_out - r_in)
        pen.setCapStyle(Qt.FlatCap)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        r_mid = (r_in + r_out) / 2
        rect = QRectF(cx - r_mid, cy - r_mid, r_mid * 2, r_mid * 2)
        for i in range(count):
            start = int((rot + i * (360 / count)) * 16)
            painter.drawArc(rect, start, int(span * 16))

    def _draw_dot_circle(self, painter, cx, cy, radius, rot, count, color):
        painter.setBrush(QBrush(color))
        painter.setPen(Qt.NoPen)
        for i in range(count):
            angle = math.radians(rot + i * (360 / count))
            x = cx + radius * math.cos(angle)
            y = cy + radius * math.sin(angle)
            s = 2.5 + 1.2 * math.sin(self.phase * 3 + i)
            painter.drawEllipse(QPointF(x, y), s, s)

    def _draw_tick_circle(self, painter, cx, cy, r_in, r_out, rot, count, color):
        painter.setPen(QPen(color, 1.2))
        for i in range(count):
            angle = math.radians(rot + i * (360 / count))
            x1 = cx + r_in * math.cos(angle)
            y1 = cy + r_in * math.sin(angle)
            x2 = cx + r_out * math.cos(angle)
            y2 = cy + r_out * math.sin(angle)
            painter.drawLine(QPointF(x1, y1), QPointF(x2, y2))

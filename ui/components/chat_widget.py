"""
JARVIS v4 - Compact Dark Neon Dialogue Feed Widget
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QLineEdit, QPushButton, QFileDialog, QLabel
)
from PySide6.QtCore import Qt, Signal


class ChatWidget(QWidget):
    user_submitted_message = Signal(str)
    user_submitted_message_with_attachment = Signal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.attached_image_path = None
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.setStyleSheet("""
            QWidget {
                background-color: transparent;
                color: #e0f7ff;
            }
            QTextEdit {
                background-color: rgba(0, 0, 0, 200);
                border: 1px solid rgba(0, 180, 255, 40);
                border-radius: 6px;
                color: #d8f3ff;
                font-family: 'Segoe UI', sans-serif;
                font-size: 12px;
                padding: 8px;
            }
            QLineEdit {
                background-color: rgba(0, 0, 0, 220);
                border: 1px solid rgba(0, 180, 255, 80);
                border-radius: 6px;
                color: #ffffff;
                font-size: 12px;
                padding: 7px 10px;
            }
            QLineEdit:focus {
                border: 1px solid #00d2ff;
            }
            QPushButton {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #00b8e6, stop:1 #0066cc);
                border: none;
                border-radius: 6px;
                color: #ffffff;
                font-weight: bold;
                font-size: 11px;
                padding: 7px 14px;
            }
            QPushButton:hover {
                background-color: #00e5ff;
            }
            QPushButton#attach_btn {
                background-color: rgba(0, 180, 255, 30);
                border: 1px solid rgba(0, 210, 255, 80);
                color: #00d2ff;
            }
            QPushButton#attach_btn:hover {
                background-color: rgba(0, 210, 255, 70);
                color: #ffffff;
            }
        """)

        # Dialogue Feed
        self.text_feed = QTextEdit()
        self.text_feed.setReadOnly(True)
        self.text_feed.setMaximumHeight(200)
        layout.addWidget(self.text_feed)

        # Attachment status bar
        self.attachment_lbl = QLabel("")
        self.attachment_lbl.setStyleSheet("color: #00ffaa; font-size: 10px; font-weight: bold; padding-left: 2px;")
        self.attachment_lbl.setVisible(False)
        layout.addWidget(self.attachment_lbl)

        # Input Row
        input_hbox = QHBoxLayout()
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Type command or attach screenshot...")
        self.input_field.returnPressed.connect(self._on_send)

        self.attach_btn = QPushButton("📷 ATTACH")
        self.attach_btn.setObjectName("attach_btn")
        self.attach_btn.clicked.connect(self._on_attach_file)

        self.send_btn = QPushButton("SEND")
        self.send_btn.clicked.connect(self._on_send)

        input_hbox.addWidget(self.input_field)
        input_hbox.addWidget(self.attach_btn)
        input_hbox.addWidget(self.send_btn)
        layout.addLayout(input_hbox)

    def _on_attach_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Screenshot or Photo",
            "",
            "Images & Documents (*.png *.jpg *.jpeg *.bmp *.webp *.pdf)"
        )
        if file_path:
            self.attached_image_path = file_path
            from pathlib import Path
            self.attachment_lbl.setText(f"📷 Attached: {Path(file_path).name}")
            self.attachment_lbl.setVisible(True)

    def _on_send(self):
        text = self.input_field.text().strip()
        img_path = self.attached_image_path

        if text or img_path:
            display_text = text if text else "Analyze attached screenshot"
            if img_path:
                from pathlib import Path
                display_text += f" <i style='color: #00ffaa;'>[📷 {Path(img_path).name}]</i>"

            self.append_user_message(display_text)

            if img_path:
                self.user_submitted_message_with_attachment.emit(text, img_path)
            else:
                self.user_submitted_message.emit(text)

            self.input_field.clear()
            self.attached_image_path = None
            self.attachment_lbl.setVisible(False)

    def append_user_message(self, message: str):
        html = f"<div style='margin-bottom: 4px;'><b style='color: #00d2ff;'>SIR:</b> {message}</div>"
        self.text_feed.append(html)

    def append_jarvis_message(self, message: str, thought: str = ""):
        html = f"<div style='margin-bottom: 4px;'><b style='color: #00ffaa;'>JARVIS:</b> {message}</div>"
        self.text_feed.append(html)

    def append_system_log(self, log_msg: str):
        html = f"<div style='margin-bottom: 2px; font-size: 10px; color: #6688aa;'><i>[SYSTEM]: {log_msg}</i></div>"
        self.text_feed.append(html)

    def append_code_message(self, code_text: str, language: str = "Code"):
        import html
        escaped_code = html.escape(code_text.strip())
        code_html = (
            f"<div style='margin-top: 4px; margin-bottom: 6px; background-color: rgba(0, 0, 0, 230); "
            f"border: 1px solid #00d2ff; border-radius: 6px; padding: 8px; font-family: Consolas, monospace; font-size: 11px;'>"
            f"<b style='color: #00e5ff;'>[{language.upper()}] OUTPUT:</b><br/>"
            f"<pre style='color: #a0f0ff; margin: 4px 0 0 0; white-space: pre-wrap;'>{escaped_code}</pre>"
            f"</div>"
        )
        self.text_feed.append(code_html)

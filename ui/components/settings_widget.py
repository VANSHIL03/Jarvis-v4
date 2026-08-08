"""
JARVIS v4 - Configuration Settings Dialog
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QCheckBox, QPushButton, QFormLayout
)
from config.settings import settings

class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("JARVIS System Configuration")
        self.resize(450, 300)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.setStyleSheet("""
            QDialog {
                background-color: #0d131f;
                color: #e0f7ff;
            }
            QLabel {
                color: #00d2ff;
                font-weight: bold;
            }
            QLineEdit {
                background-color: #162032;
                border: 1px solid #00d2ff;
                color: #ffffff;
                padding: 6px;
                border-radius: 4px;
            }
            QPushButton {
                background-color: #0077ff;
                color: white;
                font-weight: bold;
                padding: 8px 16px;
                border-radius: 4px;
            }
        """)

        self.ollama_url_input = QLineEdit(settings.OLLAMA_BASE_URL)
        self.model_input = QLineEdit(settings.DEFAULT_MODEL)
        self.wake_word_input = QLineEdit(settings.WAKE_WORD)
        self.github_token_input = QLineEdit(settings.GITHUB_TOKEN)
        self.github_token_input.setEchoMode(QLineEdit.Password)
        self.safety_chk = QCheckBox("Enable Safety Interceptor")
        self.safety_chk.setChecked(settings.SAFETY_CONFIRMATION_REQUIRED)

        form.addRow("Ollama API URL:", self.ollama_url_input)
        form.addRow("Default LLM Model:", self.model_input)
        form.addRow("Wake Word:", self.wake_word_input)
        form.addRow("GitHub Personal Token:", self.github_token_input)
        form.addRow("Security Confirmation:", self.safety_chk)

        layout.addLayout(form)

        save_btn = QPushButton("SAVE SETTINGS")
        save_btn.clicked.connect(self._save)
        layout.addWidget(save_btn)

    def _save(self):
        settings.OLLAMA_BASE_URL = self.ollama_url_input.text().strip()
        settings.DEFAULT_MODEL = self.model_input.text().strip()
        settings.WAKE_WORD = self.wake_word_input.text().strip()
        settings.GITHUB_TOKEN = self.github_token_input.text().strip()
        settings.SAFETY_CONFIRMATION_REQUIRED = self.safety_chk.isChecked()
        self.accept()

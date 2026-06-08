from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFormLayout, QMessageBox, QFrame
)
from PySide6.QtCore import Qt


class SettingsDialog(QDialog):
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.setWindowTitle("Settings")
        self.setMinimumWidth(460)
        self.setModal(True)
        self._build_ui()
        self._load()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        heading = QLabel("Settings")
        heading.setObjectName("heading")
        layout.addWidget(heading)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        layout.addWidget(sep)

        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        api_label = QLabel("Anthropic API Key:")
        self.api_key_edit = QLineEdit()
        self.api_key_edit.setEchoMode(QLineEdit.Password)
        self.api_key_edit.setPlaceholderText("sk-ant-...")
        form.addRow(api_label, self.api_key_edit)

        layout.addLayout(form)

        note = QLabel("The API key is used for AI-powered grammar correction and rewriting.\nGet yours at console.anthropic.com")
        note.setObjectName("subtext")
        note.setWordWrap(True)
        layout.addWidget(note)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        self.test_btn = QPushButton("Test Connection")
        self.test_btn.setObjectName("secondary")
        self.test_btn.clicked.connect(self._test_connection)
        btn_row.addWidget(self.test_btn)

        btn_row.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("secondary")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self._save)
        btn_row.addWidget(save_btn)

        layout.addLayout(btn_row)

    def _load(self):
        key = self.db.get_setting("anthropic_api_key", "")
        self.api_key_edit.setText(key)

    def _save(self):
        key = self.api_key_edit.text().strip()
        self.db.set_setting("anthropic_api_key", key)
        self.accept()

    def _test_connection(self):
        key = self.api_key_edit.text().strip()
        if not key:
            QMessageBox.warning(self, "No Key", "Please enter an API key first.")
            return
        self.test_btn.setText("Testing...")
        self.test_btn.setEnabled(False)
        from src.ai_processor import AIProcessor
        proc = AIProcessor(key)
        ok = proc.test_connection()
        self.test_btn.setEnabled(True)
        self.test_btn.setText("Test Connection")
        if ok:
            QMessageBox.information(self, "Success", "Connection successful! API key is valid.")
        else:
            QMessageBox.critical(self, "Failed", "Connection failed. Check your API key and internet connection.")

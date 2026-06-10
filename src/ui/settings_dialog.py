from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFormLayout, QMessageBox, QFrame, QComboBox
)
from PySide6.QtCore import Qt
from src.ai_processor import (
    AIProcessor,
    PROVIDER_ANTHROPIC, PROVIDER_GEMINI, PROVIDER_GROQ, PROVIDER_OLLAMA,
)

_PROVIDERS = [
    (PROVIDER_ANTHROPIC, "Anthropic — Claude Haiku"),
    (PROVIDER_GEMINI,    "Google Gemini Flash  (free tier)"),
    (PROVIDER_GROQ,      "Groq — Llama 3.3 70B  (free tier)"),
    (PROVIDER_OLLAMA,    "Ollama  (local, fully free)"),
]

_NOTES = {
    PROVIDER_ANTHROPIC: (
        "Get your key at console.anthropic.com\n"
        "$5 free credit on signup."
    ),
    PROVIDER_GEMINI: (
        "Get a free key at aistudio.google.com (click 'Get API key').\n"
        "Free tier: 1,500 requests/day · 15 requests/minute.\n"
        "If you see a quota error, wait a minute and try again."
    ),
    PROVIDER_GROQ: (
        "Get a free key at console.groq.com\n"
        "Free tier: 14,400 requests/day · 500 K tokens/min."
    ),
    PROVIDER_OLLAMA: (
        "Install Ollama from ollama.com, then pull a model:\n"
        "    ollama pull llama3.1\n"
        "No API key required — runs entirely on your machine."
    ),
}

_PLACEHOLDERS = {
    PROVIDER_ANTHROPIC: "sk-ant-...",
    PROVIDER_GEMINI:    "Paste your API key here",
    PROVIDER_GROQ:      "gsk_...",
}


class SettingsDialog(QDialog):
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.setWindowTitle("Settings")
        self.setMinimumWidth(500)
        self.setModal(True)
        self._keys: dict = {}
        self._active_provider: str = PROVIDER_ANTHROPIC
        self._build_ui()
        self._load()

    # ------------------------------------------------------------------ build

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

        # Provider selector
        provider_row = QHBoxLayout()
        provider_row.setSpacing(10)
        provider_row.addWidget(QLabel("AI Provider:"))
        self.provider_combo = QComboBox()
        for val, label in _PROVIDERS:
            self.provider_combo.addItem(label, userData=val)
        self.provider_combo.currentIndexChanged.connect(self._on_provider_changed)
        provider_row.addWidget(self.provider_combo, 1)
        layout.addLayout(provider_row)

        # Credentials form
        self.form = QFormLayout()
        self.form.setSpacing(10)
        self.form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.api_key_label = QLabel("API Key:")
        self.api_key_edit  = QLineEdit()
        self.api_key_edit.setEchoMode(QLineEdit.Password)
        self.form.addRow(self.api_key_label, self.api_key_edit)

        self.ollama_host_label = QLabel("Server URL:")
        self.ollama_host_edit  = QLineEdit()
        self.ollama_host_edit.setPlaceholderText("http://localhost:11434")
        self.form.addRow(self.ollama_host_label, self.ollama_host_edit)

        self.ollama_model_label = QLabel("Model:")
        self.ollama_model_edit  = QLineEdit()
        self.ollama_model_edit.setPlaceholderText("llama3.1")
        self.form.addRow(self.ollama_model_label, self.ollama_model_edit)

        layout.addLayout(self.form)

        self.note_lbl = QLabel()
        self.note_lbl.setObjectName("subtext")
        self.note_lbl.setWordWrap(True)
        layout.addWidget(self.note_lbl)

        # Buttons
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

    # ------------------------------------------------------------------ load / save

    def _load(self):
        self._keys = {
            PROVIDER_ANTHROPIC: self.db.get_setting("anthropic_api_key", ""),
            PROVIDER_GEMINI:    self.db.get_setting("gemini_api_key", ""),
            PROVIDER_GROQ:      self.db.get_setting("groq_api_key", ""),
        }
        self.ollama_host_edit.setText(
            self.db.get_setting("ollama_host", "http://localhost:11434")
        )
        self.ollama_model_edit.setText(
            self.db.get_setting("ollama_model", "llama3.1")
        )

        provider = self.db.get_setting("ai_provider", PROVIDER_ANTHROPIC)
        idx = next((i for i, (v, _) in enumerate(_PROVIDERS) if v == provider), 0)
        self._active_provider = provider

        # Block signals so _on_provider_changed doesn't flush the empty field
        self.provider_combo.blockSignals(True)
        self.provider_combo.setCurrentIndex(idx)
        self.provider_combo.blockSignals(False)

        self._apply_provider_ui(provider)

    def _save(self):
        provider = self.provider_combo.currentData()
        if provider in self._keys:
            self._keys[provider] = self.api_key_edit.text().strip()

        self.db.set_setting("ai_provider", provider)
        self.db.set_setting("anthropic_api_key", self._keys.get(PROVIDER_ANTHROPIC, ""))
        self.db.set_setting("gemini_api_key",    self._keys.get(PROVIDER_GEMINI, ""))
        self.db.set_setting("groq_api_key",      self._keys.get(PROVIDER_GROQ, ""))
        self.db.set_setting("ollama_host",
                            self.ollama_host_edit.text().strip() or "http://localhost:11434")
        self.db.set_setting("ollama_model",
                            self.ollama_model_edit.text().strip() or "llama3.1")
        self.accept()

    # ------------------------------------------------------------------ slots

    def _on_provider_changed(self, _index):
        if not self._keys:
            return
        # Flush current key to in-memory dict before switching
        if self._active_provider in self._keys:
            self._keys[self._active_provider] = self.api_key_edit.text()

        provider = self.provider_combo.currentData()
        self._active_provider = provider
        self._apply_provider_ui(provider)

    def _apply_provider_ui(self, provider: str):
        is_ollama = (provider == PROVIDER_OLLAMA)

        for w in (self.api_key_label, self.api_key_edit):
            w.setVisible(not is_ollama)
        for w in (self.ollama_host_label, self.ollama_host_edit,
                  self.ollama_model_label, self.ollama_model_edit):
            w.setVisible(is_ollama)

        self.api_key_edit.setPlaceholderText(_PLACEHOLDERS.get(provider, ""))
        if not is_ollama:
            self.api_key_edit.setText(self._keys.get(provider, ""))

        self.note_lbl.setText(_NOTES.get(provider, ""))
        self.adjustSize()

    def _test_connection(self):
        provider = self.provider_combo.currentData()

        if provider == PROVIDER_OLLAMA:
            host  = self.ollama_host_edit.text().strip() or "http://localhost:11434"
            model = self.ollama_model_edit.text().strip() or "llama3.1"
            proc  = AIProcessor(provider=provider, ollama_host=host, ollama_model=model)
        else:
            key = self.api_key_edit.text().strip()
            if not key:
                QMessageBox.warning(self, "No Key", "Please enter an API key first.")
                return
            proc = AIProcessor(provider=provider, api_key=key)

        self.test_btn.setText("Testing…")
        self.test_btn.setEnabled(False)
        ok, err = proc.test_connection()
        self.test_btn.setEnabled(True)
        self.test_btn.setText("Test Connection")

        if ok:
            QMessageBox.information(self, "Success", "Connection successful!")
        else:
            QMessageBox.critical(
                self, "Failed",
                f"Connection failed:\n\n{err}"
            )

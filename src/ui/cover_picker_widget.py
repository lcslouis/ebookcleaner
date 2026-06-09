from pathlib import Path
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QLineEdit,
    QPushButton, QFileDialog
)
from PySide6.QtCore import Signal, Qt, QThread, QObject
from PySide6.QtGui import QPixmap

THUMB_W, THUMB_H = 100, 140


class _DownloadSignals(QObject):
    done = Signal(bytes, str)
    error = Signal(str)


class _DownloadThread(QThread):
    def __init__(self, url):
        super().__init__()
        self.url = url
        self.signals = _DownloadSignals()

    def run(self):
        try:
            import requests
            resp = requests.get(
                self.url, timeout=20,
                headers={"User-Agent": "Mozilla/5.0"}
            )
            resp.raise_for_status()
            data = resp.content
            mime = resp.headers.get("Content-Type", "image/jpeg").split(";")[0].strip()
            self.signals.done.emit(data, mime)
        except Exception as e:
            self.signals.error.emit(str(e))


class CoverPickerWidget(QWidget):
    """Thumbnail + URL field + local file picker for cover images.

    Signals:
        cover_changed(bytes, str) — emitted whenever the cover changes.
                                     Empty bytes means cover was cleared.
    """
    cover_changed = Signal(bytes, str)  # data, mime_type

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cover_data: bytes = b""
        self._cover_mime: str = "image/jpeg"
        self._dl_thread = None
        self._build_ui()

    # ------------------------------------------------------------------ UI

    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        # Thumbnail
        self.thumb = QLabel("No Cover")
        self.thumb.setFixedSize(THUMB_W, THUMB_H)
        self.thumb.setAlignment(Qt.AlignCenter)
        self.thumb.setStyleSheet(
            "QLabel { background: #1a1a2e; border: 1px solid #555; "
            "color: #888; font-size: 10px; }"
        )
        layout.addWidget(self.thumb)

        right = QVBoxLayout()
        right.setSpacing(6)

        # URL row
        url_row = QHBoxLayout(); url_row.setSpacing(6)
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("Cover image URL")
        url_row.addWidget(self.url_edit, 1)
        self._dl_btn = QPushButton("Download")
        self._dl_btn.setObjectName("secondary")
        self._dl_btn.setFixedWidth(84)
        self._dl_btn.clicked.connect(self._on_download_clicked)
        url_row.addWidget(self._dl_btn)
        right.addLayout(url_row)

        # File / clear buttons
        btn_row = QHBoxLayout(); btn_row.setSpacing(6)
        browse_btn = QPushButton("Browse File…")
        browse_btn.setObjectName("secondary")
        browse_btn.clicked.connect(self._browse_file)
        btn_row.addWidget(browse_btn)
        clear_btn = QPushButton("Clear")
        clear_btn.setObjectName("secondary")
        clear_btn.clicked.connect(self.clear)
        btn_row.addWidget(clear_btn)
        btn_row.addStretch()
        right.addLayout(btn_row)

        self._status = QLabel("Auto-detected from page, or set manually above.")
        self._status.setObjectName("subtext")
        self._status.setWordWrap(True)
        right.addWidget(self._status)
        right.addStretch()

        layout.addLayout(right, 1)

    # ------------------------------------------------------------------ public API

    def set_url(self, url: str, auto_download: bool = False):
        """Set the URL field and optionally start a background download."""
        self.url_edit.setText(url)
        if auto_download and url:
            self._start_download(url)

    def set_cover_data(self, data: bytes, mime: str):
        """Set the cover from raw bytes (e.g. extracted from EPUB or downloaded)."""
        self._cover_data = data
        self._cover_mime = mime
        self._show_thumb(data)
        kb = len(data) // 1024 if data else 0
        self._status.setText(f"Cover loaded ({kb} KB)." if data else "No cover set.")
        self.cover_changed.emit(data, mime)

    def get_cover_data(self) -> bytes:
        return self._cover_data

    def get_cover_mime(self) -> str:
        return self._cover_mime

    def clear(self):
        self._cover_data = b""
        self._cover_mime = "image/jpeg"
        self.url_edit.clear()
        self.thumb.setPixmap(QPixmap())
        self.thumb.setText("No Cover")
        self._status.setText("Cover cleared.")
        self.cover_changed.emit(b"", "")

    # ------------------------------------------------------------------ internal

    def _on_download_clicked(self):
        url = self.url_edit.text().strip()
        if url:
            self._start_download(url)

    def _start_download(self, url: str):
        self._status.setText("Downloading cover…")
        self._dl_btn.setEnabled(False)
        self._dl_thread = _DownloadThread(url)
        self._dl_thread.signals.done.connect(self._on_download_done)
        self._dl_thread.signals.error.connect(self._on_download_error)
        self._dl_thread.start()

    def _on_download_done(self, data: bytes, mime: str):
        self._dl_btn.setEnabled(True)
        self.set_cover_data(data, mime)

    def _on_download_error(self, msg: str):
        self._dl_btn.setEnabled(True)
        self._status.setText(f"Download failed: {msg}")

    def _browse_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Cover Image", "",
            "Images (*.jpg *.jpeg *.png *.gif *.webp);;All Files (*)"
        )
        if not path:
            return
        data = Path(path).read_bytes()
        ext = Path(path).suffix.lower().lstrip(".")
        mime = f"image/{'jpeg' if ext == 'jpg' else ext}"
        self.url_edit.setText(path)
        self.set_cover_data(data, mime)

    def _show_thumb(self, data: bytes):
        if not data:
            self.thumb.setText("No Cover")
            return
        pix = QPixmap()
        if pix.loadFromData(data):
            self.thumb.setPixmap(
                pix.scaled(THUMB_W, THUMB_H, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            )
            self.thumb.setText("")
        else:
            self.thumb.setText("Preview\nnot available")

"""
Dialog for re-fetching selected chapters from their original source URLs.
Replaces original_content and clears cleaned/rewritten versions.
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QProgressBar, QPlainTextEdit, QFrame
)
from PySide6.QtCore import Qt, Signal

from src.ui.download_manager import _FetchWorker
from src.web_fetcher import WebFetcher


class ReFetchDialog(QDialog):
    chapters_updated = Signal(list)   # list of chapter_ids that were refreshed

    def __init__(self, chapters: list, db, parent=None):
        """
        chapters: list of dicts with keys id, title, source_url, chapter_number
        """
        super().__init__(parent)
        self.db = db
        self.setWindowTitle("Re-fetch Chapters")
        self.setMinimumWidth(500)
        self.setModal(True)

        self._fetchable = [c for c in chapters if c.get("source_url")]
        self._skipped   = len(chapters) - len(self._fetchable)
        self._worker    = None
        self._updated_ids: list = []

        self._build_ui()

    # ------------------------------------------------------------------ build

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        heading = QLabel("Re-fetch Chapters")
        heading.setObjectName("heading")
        layout.addWidget(heading)

        sep = QFrame(); sep.setFrameShape(QFrame.HLine)
        layout.addWidget(sep)

        n = len(self._fetchable)
        if n == 0:
            msg = (
                "None of the selected chapters have a stored source URL.\n"
                "Chapters imported from EPUB or TXT files cannot be re-fetched."
            )
        else:
            lines = [f"Re-fetching <b>{n}</b> chapter{'s' if n > 1 else ''} from the web."]
            if self._skipped:
                lines.append(
                    f"<b>{self._skipped}</b> chapter{'s' if self._skipped > 1 else ''} "
                    f"will be skipped (no source URL stored)."
                )
            lines.append(
                "Original content will be replaced and cleaned/rewritten "
                "versions will be cleared."
            )
            msg = "<br>".join(lines)

        info = QLabel(msg)
        info.setWordWrap(True)
        info.setTextFormat(Qt.RichText)
        layout.addWidget(info)

        self.bar = QProgressBar()
        self.bar.setMaximum(max(n, 1))
        self.bar.setValue(0)
        self.bar.setFixedHeight(8)
        self.bar.setTextVisible(False)
        self.bar.setVisible(n > 0)
        layout.addWidget(self.bar)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setFixedHeight(160)
        self.log.setVisible(n > 0)
        layout.addWidget(self.log)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        btn_row.addStretch()

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setObjectName("secondary")
        self.cancel_btn.clicked.connect(self._on_cancel)
        btn_row.addWidget(self.cancel_btn)

        self.start_btn = QPushButton("Re-fetch")
        self.start_btn.setEnabled(n > 0)
        self.start_btn.clicked.connect(self._start)
        btn_row.addWidget(self.start_btn)

        layout.addLayout(btn_row)

    # ------------------------------------------------------------------ slots

    def _start(self):
        self.start_btn.setEnabled(False)
        self.log.appendPlainText("Starting…")

        chapter_list = [
            {"url": c["source_url"], "title": c["title"] or f"Chapter {c['chapter_number']}"}
            for c in self._fetchable
        ]
        fetcher = WebFetcher(cookies=self.db.get_all_cookies_flat())
        self._worker = _FetchWorker(fetcher, chapter_list)
        self._worker.signals.chapter_done.connect(self._on_chapter_done)
        self._worker.signals.status_update.connect(self._on_status_update)
        self._worker.signals.finished.connect(self._on_finished)
        self._worker.start()

    def _on_chapter_done(self, idx, total, title):
        self.bar.setValue(idx)
        self.log.appendPlainText(f"  Fetched: {title}")

    def _on_status_update(self, msg):
        self.log.appendPlainText(f"  {msg}")

    def _on_finished(self, results):
        failed = 0
        for i, result in enumerate(results):
            ch = self._fetchable[i]
            if result.get("error"):
                self.log.appendPlainText(
                    f"  Failed: {ch['title'] or ch['chapter_number']} — {result['error']}"
                )
                failed += 1
            else:
                self.db.replace_chapter_content(ch["id"], result["content"])
                self._updated_ids.append(ch["id"])

        n_ok = len(self._updated_ids)
        self.log.appendPlainText(
            f"\nDone — {n_ok} chapter{'s' if n_ok != 1 else ''} updated"
            + (f", {failed} failed" if failed else "") + "."
        )
        self.bar.setValue(self.bar.maximum())
        self.cancel_btn.setText("Close")
        self.cancel_btn.setEnabled(True)
        self.chapters_updated.emit(self._updated_ids)

    def _on_cancel(self):
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
        self.reject()

    def closeEvent(self, event):
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
        super().closeEvent(event)

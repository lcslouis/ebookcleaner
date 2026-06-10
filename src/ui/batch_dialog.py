"""
Batch processing dialog: apply rules / fix grammar / rewrite across all chapters.
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QProgressBar, QFrame, QMessageBox
)
from PySide6.QtCore import Signal, QThread, QObject


class _BatchSignals(QObject):
    chapter_done = Signal(int, int, str)   # done, total, chapter_title
    log_line     = Signal(str)
    finished     = Signal(int, int)        # done_count, error_count


class _BatchWorker(QThread):
    def __init__(self, db, book_id: int, mode: str, ai_processor=None):
        super().__init__()
        self.db           = db
        self.book_id      = book_id
        self.mode         = mode           # "rules" | "grammar" | "rewrite"
        self.ai_processor = ai_processor
        self.signals      = _BatchSignals()
        self._cancelled   = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        chapters = self.db.get_chapters(self.book_id)
        total    = len(chapters)
        done = errors = 0
        custom_rules = self.db.get_custom_rules(self.book_id) if self.mode == "rules" else []

        for i, ch in enumerate(chapters):
            if self._cancelled:
                self.signals.log_line.emit("Cancelled.")
                break
            title = ch.get("title") or f"Chapter {ch['chapter_number']}"
            try:
                if self.mode == "rules":
                    self._apply_rules(ch, custom_rules)
                elif self.mode == "grammar":
                    self._fix_grammar(ch)
                elif self.mode == "rewrite":
                    self._rewrite(ch)
                done += 1
                self.signals.log_line.emit(f"✓ {title}")
            except Exception as e:
                errors += 1
                self.signals.log_line.emit(f"✗ {title}: {e}")
            self.signals.chapter_done.emit(i + 1, total, title)

        self.signals.finished.emit(done, errors)

    def _apply_rules(self, ch, custom_rules):
        from src.cleaner import TextCleaner
        source = ch.get("original_content") or ""
        if not source.strip():
            return
        result = TextCleaner(custom_rules=custom_rules).clean(source)
        self.db.update_chapter(ch["id"], cleaned_content=result, status="cleaned")

    def _fix_grammar(self, ch):
        source = ch.get("cleaned_content") or ch.get("original_content") or ""
        if not source.strip():
            return
        result = self.ai_processor.clean_chapter(source)
        self.db.update_chapter(ch["id"], cleaned_content=result, status="cleaned")

    def _rewrite(self, ch):
        source = ch.get("cleaned_content") or ch.get("original_content") or ""
        if not source.strip():
            return
        result = self.ai_processor.rewrite_chapter(source)
        self.db.update_chapter(ch["id"], rewritten_content=result, status="rewritten")


# ------------------------------------------------------------------ dialog

class BatchDialog(QDialog):
    def __init__(self, db, book_id: int, mode: str, ai_processor=None, parent=None):
        super().__init__(parent)
        self.db           = db
        self.book_id      = book_id
        self.mode         = mode
        self.ai_processor = ai_processor
        self._worker      = None

        titles = {
            "rules":   "Batch Apply Rules",
            "grammar": "Batch Fix Grammar",
            "rewrite": "Batch Rewrite",
        }
        self.setWindowTitle(titles.get(mode, "Batch Process"))
        self.setMinimumSize(520, 420)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        descriptions = {
            "rules":   (
                "Applies built-in cleaning passes plus your custom rules to every chapter's "
                "original content and saves the result as Cleaned."
            ),
            "grammar": (
                "Fixes grammar on every chapter using AI. "
                "Uses the Cleaned version if available, otherwise Original."
            ),
            "rewrite": (
                "Rewrites every chapter using AI. "
                "Uses the Cleaned version if available, otherwise Original. "
                "Results are saved to Rewritten."
            ),
        }
        desc = QLabel(descriptions.get(self.mode, ""))
        desc.setWordWrap(True)
        desc.setObjectName("subtext")
        layout.addWidget(desc)

        sep = QFrame(); sep.setFrameShape(QFrame.HLine)
        layout.addWidget(sep)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        self.status_label = QLabel("Ready — click Start to begin.")
        self.status_label.setObjectName("subtext")
        layout.addWidget(self.status_label)

        self.log_edit = QTextEdit()
        self.log_edit.setReadOnly(True)
        self.log_edit.setPlaceholderText("Processing log will appear here…")
        layout.addWidget(self.log_edit, 1)

        btn_row = QHBoxLayout()
        self.start_btn = QPushButton("Start")
        self.start_btn.clicked.connect(self._start)
        btn_row.addWidget(self.start_btn)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setObjectName("secondary")
        self.cancel_btn.clicked.connect(self._cancel)
        self.cancel_btn.setEnabled(False)
        btn_row.addWidget(self.cancel_btn)

        btn_row.addStretch()

        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.accept)
        btn_row.addWidget(self.close_btn)
        layout.addLayout(btn_row)

    # ------------------------------------------------------------------ slots

    def _start(self):
        chapters = self.db.get_chapters(self.book_id)
        if not chapters:
            QMessageBox.information(self, "No Chapters", "This book has no chapters to process.")
            return

        self.start_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.close_btn.setEnabled(False)
        self.log_edit.clear()
        self.progress_bar.setRange(0, len(chapters))
        self.progress_bar.setValue(0)

        self._worker = _BatchWorker(self.db, self.book_id, self.mode, self.ai_processor)
        self._worker.signals.chapter_done.connect(self._on_chapter_done)
        self._worker.signals.log_line.connect(self._on_log_line)
        self._worker.signals.finished.connect(self._on_finished)
        self._worker.start()

    def _cancel(self):
        if self._worker:
            self._worker.cancel()
        self.cancel_btn.setEnabled(False)
        self.status_label.setText("Cancelling…")

    def _on_chapter_done(self, done, total, title):
        self.progress_bar.setValue(done)
        self.status_label.setText(f"Processing {done}/{total}: {title[:60]}")

    def _on_log_line(self, line):
        self.log_edit.append(line)

    def _on_finished(self, done, errors):
        self.start_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.close_btn.setEnabled(True)
        if errors:
            self.status_label.setText(f"Finished: {done} succeeded, {errors} failed.")
        else:
            self.status_label.setText(f"Done — {done} chapter{'s' if done != 1 else ''} processed.")

    def closeEvent(self, event):
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            self._worker.wait(3000)
        super().closeEvent(event)

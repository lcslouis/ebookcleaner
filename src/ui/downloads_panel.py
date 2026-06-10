"""
Downloads panel — docked at the bottom of the main window.
Shows all active and recently completed DownloadTasks.
"""
import webbrowser

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QProgressBar, QFrame
)
from PySide6.QtCore import Qt
from src.ui.download_manager import DownloadTask


class _DownloadRowWidget(QFrame):
    def __init__(self, task: DownloadTask, manager, parent=None):
        super().__init__(parent)
        self.task         = task
        self._manager     = manager
        self._blocked_url = ""
        self.setFrameShape(QFrame.StyledPanel)
        self._build_ui()
        task.progress_changed.connect(self._on_progress)
        task.completed.connect(lambda _: self._on_done())
        task.failed.connect(lambda _, msg: self._on_error(msg))
        task.blocked_403.connect(lambda _tid, url, title: self._on_blocked_403(url, title))

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 6, 8, 6)
        root.setSpacing(4)

        # ---- main row: title / bar / status / cancel ----
        main_row = QHBoxLayout(); main_row.setSpacing(10)

        info = QVBoxLayout(); info.setSpacing(2)

        title = self.task.book_title
        if len(title) > 55:
            title = title[:52] + "…"
        self.title_lbl = QLabel(title)
        self.title_lbl.setObjectName("subtext")
        info.addWidget(self.title_lbl)

        self.bar = QProgressBar()
        self.bar.setMaximum(max(self.task.total_count, 1))
        self.bar.setValue(0)
        self.bar.setFixedHeight(8)
        self.bar.setTextVisible(False)
        info.addWidget(self.bar)

        self.status_lbl = QLabel(f"0 / {self.task.total_count} chapters")
        self.status_lbl.setObjectName("subtext")
        info.addWidget(self.status_lbl)

        main_row.addLayout(info, 1)

        self.cancel_btn = QPushButton("✕")
        self.cancel_btn.setFixedSize(22, 22)
        self.cancel_btn.setObjectName("secondary")
        self.cancel_btn.setToolTip("Cancel")
        self.cancel_btn.clicked.connect(
            lambda: self._manager.cancel_task(self.task.task_id)
        )
        main_row.addWidget(self.cancel_btn, alignment=Qt.AlignVCenter)
        root.addLayout(main_row)

        # ---- blocked row (hidden until 403 fires) ----
        self._blocked_widget = QWidget()
        blocked_row = QHBoxLayout(self._blocked_widget)
        blocked_row.setContentsMargins(0, 2, 0, 2)
        blocked_row.setSpacing(6)

        blocked_lbl = QLabel("Chapter blocked (403) — solve CAPTCHA then retry:")
        blocked_lbl.setObjectName("subtext")
        blocked_row.addWidget(blocked_lbl)

        open_btn = QPushButton("Open in Browser")
        open_btn.setObjectName("secondary")
        open_btn.clicked.connect(self._open_in_browser)
        blocked_row.addWidget(open_btn)

        retry_btn = QPushButton("Retry")
        retry_btn.clicked.connect(lambda: self._resume(skip=False))
        blocked_row.addWidget(retry_btn)

        skip_btn = QPushButton("Skip Chapter")
        skip_btn.setObjectName("secondary")
        skip_btn.clicked.connect(lambda: self._resume(skip=True))
        blocked_row.addWidget(skip_btn)

        blocked_row.addStretch()
        self._blocked_widget.setVisible(False)
        root.addWidget(self._blocked_widget)

    # ------------------------------------------------------------------ slots

    def _on_progress(self, done, total, chapter_title):
        self.bar.setMaximum(max(total, 1))
        self.bar.setValue(done)
        short = chapter_title[:40] + "…" if len(chapter_title) > 40 else chapter_title
        self.status_lbl.setText(f"{done} / {total}  —  {short}")

    def _on_done(self):
        self._blocked_widget.setVisible(False)
        self.bar.setValue(self.bar.maximum())
        fc = self.task.failed_count
        if fc:
            self.status_lbl.setText(f"Done — {fc} chapter(s) failed (saved as placeholders)")
            self.status_lbl.setStyleSheet("color: #ff9800;")
        else:
            self.status_lbl.setText("Complete")
            self.status_lbl.setStyleSheet("color: #4caf50;")
        self.cancel_btn.setEnabled(False)

    def _on_error(self, msg):
        short = msg[:60] + "…" if len(msg) > 60 else msg
        self.status_lbl.setText(f"Error: {short}")
        self.status_lbl.setStyleSheet("color: #ef5350;")
        self.cancel_btn.setEnabled(False)

    def _on_blocked_403(self, url: str, title: str):
        self._blocked_url = url
        short = title[:40] + "…" if len(title) > 40 else title
        self.status_lbl.setText(f"Blocked (403): {short}")
        self.status_lbl.setStyleSheet("color: #ef5350;")
        self._blocked_widget.setVisible(True)

    def _open_in_browser(self):
        if self._blocked_url:
            webbrowser.open(self._blocked_url)

    def _resume(self, skip: bool):
        self._blocked_widget.setVisible(False)
        self.status_lbl.setStyleSheet("")
        self.task.resume_after_403(skip=skip)


class DownloadsPanel(QWidget):
    """Bottom-docked panel showing all download tasks."""

    def __init__(self, manager, parent=None):
        super().__init__(parent)
        self.manager = manager
        self._rows: dict[str, _DownloadRowWidget] = {}
        self._build_ui()
        manager.task_added.connect(self._on_task_added)
        manager.tasks_changed.connect(self._refresh_empty)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(4)

        # Header bar
        hdr = QHBoxLayout()
        lbl = QLabel("Downloads")
        lbl.setObjectName("heading")
        hdr.addWidget(lbl)
        hdr.addStretch()
        clear_btn = QPushButton("Clear Finished")
        clear_btn.setObjectName("secondary")
        clear_btn.clicked.connect(self._clear_finished)
        hdr.addWidget(clear_btn)
        layout.addLayout(hdr)

        sep = QFrame(); sep.setFrameShape(QFrame.HLine)
        layout.addWidget(sep)

        # Scrollable row area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        self._container = QWidget()
        self._container_layout = QVBoxLayout(self._container)
        self._container_layout.setContentsMargins(0, 0, 0, 0)
        self._container_layout.setSpacing(4)
        self._container_layout.addStretch()
        scroll.setWidget(self._container)
        layout.addWidget(scroll, 1)

        self._empty_lbl = QLabel("No downloads yet.")
        self._empty_lbl.setObjectName("subtext")
        self._empty_lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._empty_lbl)

    # ------------------------------------------------------------------ slots

    def _on_task_added(self, task: DownloadTask):
        row = _DownloadRowWidget(task, self.manager)
        # Newest at top — insert before the stretch (last item)
        self._container_layout.insertWidget(0, row)
        self._rows[task.task_id] = row
        self._refresh_empty()

    def _clear_finished(self):
        done_statuses = {DownloadTask.STATUS_DONE, DownloadTask.STATUS_ERROR,
                         DownloadTask.STATUS_CANCELLED}
        for tid in list(self._rows):
            if self._rows[tid].task.status in done_statuses:
                self._rows[tid].deleteLater()
                del self._rows[tid]
        self.manager.clear_finished()
        self._refresh_empty()

    def _refresh_empty(self):
        self._empty_lbl.setVisible(len(self._rows) == 0)

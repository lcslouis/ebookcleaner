"""
Check for new chapters across all books that have a source_url.

UpdateCheckerWorker   — background QThread; fetches each book's TOC and
                        compares remote chapter count vs stored count.
CheckForUpdatesDialog — shows results; user can tick books and kick off
                        update downloads in one click.
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QProgressBar, QFrame, QMessageBox
)
from PySide6.QtCore import Qt, QThread, QObject, Signal, Slot


# ------------------------------------------------------------------ worker

class _CheckSignals(QObject):
    book_checked  = Signal(int, int, str, int, int)  # idx, total, title, stored, remote
    finished      = Signal(list)                     # [{book, stored, remote, new_count}]
    error         = Signal(str)


class UpdateCheckerWorker(QThread):
    def __init__(self, db):
        super().__init__()
        self.db      = db
        self.signals = _CheckSignals()
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        try:
            books = [b for b in self.db.get_all_books() if b.get("source_url")]
            total = len(books)
            results = []

            cookies = self.db.get_all_cookies_flat()
            from src.web_fetcher import WebFetcher

            for i, book in enumerate(books):
                if self._cancelled:
                    break
                stored = self.db.get_max_chapter_number(book["id"])
                remote = stored   # default: assume no change
                try:
                    fetcher = WebFetcher(delay=0.5, cookies=cookies)
                    info = fetcher.fetch_toc(book["source_url"])
                    remote = len(info.get("chapters") or [])
                except Exception:
                    pass   # network error — skip this book silently

                self.signals.book_checked.emit(i + 1, total, book["title"], stored, remote)

                if remote > stored:
                    results.append({
                        "book":      book,
                        "stored":    stored,
                        "remote":    remote,
                        "new_count": remote - stored,
                    })

            self.signals.finished.emit(results)
        except Exception as e:
            self.signals.error.emit(str(e))


# ------------------------------------------------------------------ dialog

class CheckForUpdatesDialog(QDialog):
    def __init__(self, db, download_manager, parent=None):
        super().__init__(parent)
        self.db               = db
        self._download_manager = download_manager
        self._worker          = None
        self._results         = []
        self.setWindowTitle("Check for New Chapters")
        self.setMinimumSize(600, 480)
        self._build_ui()
        self._start_check()

    # ------------------------------------------------------------------ UI

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        heading = QLabel("Check for New Chapters")
        heading.setObjectName("heading")
        layout.addWidget(heading)

        self.status_lbl = QLabel("Checking books for updates…")
        self.status_lbl.setObjectName("subtext")
        layout.addWidget(self.status_lbl)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)   # indeterminate until count known
        layout.addWidget(self.progress_bar)

        sep = QFrame(); sep.setFrameShape(QFrame.HLine)
        layout.addWidget(sep)

        self.result_lbl = QLabel("Books with new chapters:")
        self.result_lbl.setVisible(False)
        layout.addWidget(self.result_lbl)

        self.book_list = QListWidget()
        self.book_list.setAlternatingRowColors(True)
        self.book_list.setVisible(False)
        layout.addWidget(self.book_list, 1)

        btn_row = QHBoxLayout(); btn_row.setSpacing(8)

        sel_all_btn = QPushButton("Select All")
        sel_all_btn.setObjectName("secondary")
        sel_all_btn.clicked.connect(self._select_all)
        btn_row.addWidget(sel_all_btn)
        self._sel_all_btn = sel_all_btn
        sel_all_btn.setVisible(False)

        btn_row.addStretch()

        self.update_btn = QPushButton("Download Selected Updates")
        self.update_btn.setEnabled(False)
        self.update_btn.setVisible(False)
        self.update_btn.clicked.connect(self._download_selected)
        btn_row.addWidget(self.update_btn)

        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.accept)
        btn_row.addWidget(self.close_btn)

        layout.addLayout(btn_row)

    # ------------------------------------------------------------------ check

    def _start_check(self):
        books_with_url = [b for b in self.db.get_all_books() if b.get("source_url")]
        if not books_with_url:
            self.status_lbl.setText(
                "No books have a source URL. Fetch a book from the web first."
            )
            self.progress_bar.setVisible(False)
            return

        self.progress_bar.setRange(0, len(books_with_url))
        self.progress_bar.setValue(0)

        self._worker = UpdateCheckerWorker(self.db)
        self._worker.signals.book_checked.connect(self._on_book_checked)
        self._worker.signals.finished.connect(self._on_finished)
        self._worker.signals.error.connect(self._on_error)
        self._worker.start()

    @Slot(int, int, str, int, int)
    def _on_book_checked(self, idx, total, title, stored, remote):
        self.progress_bar.setRange(0, total)
        self.progress_bar.setValue(idx)
        short = title[:50] + "…" if len(title) > 50 else title
        self.status_lbl.setText(
            f"Checking {idx}/{total}: {short}"
            + (f"  (+{remote - stored} new)" if remote > stored else "")
        )

    @Slot(list)
    def _on_finished(self, results):
        self._results = results
        self.progress_bar.setVisible(False)

        if not results:
            self.status_lbl.setText("All books are up to date.")
            return

        self.status_lbl.setText(
            f"Found {len(results)} book{'s' if len(results) != 1 else ''} with new chapters:"
        )
        self.result_lbl.setVisible(True)
        self.book_list.setVisible(True)
        self._sel_all_btn.setVisible(True)
        self.update_btn.setVisible(True)
        self.update_btn.setEnabled(True)

        for r in results:
            label = (
                f"{r['book']['title']}  —  "
                f"{r['stored']} stored → {r['remote']} available  "
                f"(+{r['new_count']} new)"
            )
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, r)
            item.setCheckState(Qt.Checked)
            self.book_list.addItem(item)

        self.book_list.itemChanged.connect(self._on_item_changed)

    @Slot(str)
    def _on_error(self, msg):
        self.progress_bar.setVisible(False)
        self.status_lbl.setText(f"Error: {msg}")

    # ------------------------------------------------------------------ actions

    def _select_all(self):
        for i in range(self.book_list.count()):
            self.book_list.item(i).setCheckState(Qt.Checked)

    def _on_item_changed(self):
        any_checked = any(
            self.book_list.item(i).checkState() == Qt.Checked
            for i in range(self.book_list.count())
        )
        self.update_btn.setEnabled(any_checked)

    def _download_selected(self):
        selected = [
            self.book_list.item(i).data(Qt.UserRole)
            for i in range(self.book_list.count())
            if self.book_list.item(i).checkState() == Qt.Checked
        ]
        if not selected:
            return

        from src.web_fetcher import WebFetcher
        from src.ui.download_manager import DownloadTask

        cookies = self.db.get_all_cookies_flat()
        queued  = 0

        for r in selected:
            book   = r["book"]
            stored = r["stored"]
            try:
                fetcher = WebFetcher(delay=1.5, cookies=cookies)
                info    = fetcher.fetch_toc(book["source_url"])
            except Exception as e:
                QMessageBox.warning(
                    self, "Fetch Error",
                    f"Could not load chapter list for \"{book['title']}\":\n{e}"
                )
                continue

            all_chapters = info.get("chapters") or []
            # Only queue chapters beyond what we already have
            existing_urls = self.db.get_chapter_source_urls(book["id"])
            if existing_urls:
                new_chs = [c for c in all_chapters
                           if c.get("url") and c["url"] not in existing_urls]
            else:
                new_chs = all_chapters[stored:]

            if not new_chs:
                continue

            task = DownloadTask(
                db=self.db,
                fetcher=WebFetcher(delay=1.5, cookies=cookies),
                selected_chapters=new_chs,
                toc_info=info,
                update_book_id=book["id"],
                source_url=book["source_url"],
            )
            self._download_manager.add_task(task)
            queued += 1

        if queued:
            self.accept()
        else:
            QMessageBox.information(self, "Nothing to Queue",
                                    "No new chapters found to download.")

    def closeEvent(self, event):
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            self._worker.wait(2000)
        super().closeEvent(event)

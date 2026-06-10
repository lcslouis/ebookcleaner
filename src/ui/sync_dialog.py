"""
Cloud sync dialog — backs up and restores the library to/from any local folder
(OneDrive, Google Drive, Dropbox, etc.) via the desktop sync client.

Backup writes:
  <sync_folder>/library.db           — full database copy (for restore)
  <sync_folder>/covers/              — cover image files
  <sync_folder>/books/<title>/       — human-readable structured export
      metadata.json
      chapters/0001_Title.txt        — best available content per chapter

Restore copies library.db + covers back, then asks the user to restart.
"""
import json
import shutil
from datetime import datetime
from pathlib import Path

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QTextEdit, QProgressBar, QFrame, QFileDialog,
    QMessageBox
)
from PySide6.QtCore import Qt, Signal, QThread, QObject

_DB_DIR    = Path.home() / ".ebookcleaner"
_DB_PATH   = _DB_DIR / "library.db"
_COVER_DIR = _DB_DIR / "covers"


# ------------------------------------------------------------------ workers

class _SyncSignals(QObject):
    log_line = Signal(str)
    progress = Signal(int, int)    # done, total
    finished = Signal(bool, str)   # success, message


class _BackupWorker(QThread):
    def __init__(self, db, sync_folder: Path):
        super().__init__()
        self.db          = db
        self.sync_folder = sync_folder
        self.signals     = _SyncSignals()

    def run(self):
        try:
            sf = self.sync_folder
            sf.mkdir(parents=True, exist_ok=True)

            # 1. Database file
            self.signals.log_line.emit("Copying database…")
            shutil.copy2(_DB_PATH, sf / "library.db")
            self.signals.log_line.emit("  ✓ library.db")

            # 2. Cover images
            self.signals.log_line.emit("Copying cover images…")
            if _COVER_DIR.exists():
                dest = sf / "covers"
                dest.mkdir(exist_ok=True)
                count = 0
                for f in _COVER_DIR.iterdir():
                    shutil.copy2(f, dest / f.name)
                    count += 1
                self.signals.log_line.emit(f"  ✓ {count} cover file(s)")
            else:
                self.signals.log_line.emit("  (no covers to copy)")

            # 3. Structured text export
            self.signals.log_line.emit("Exporting books as readable text files…")
            books    = self.db.get_all_books()
            books_dir = sf / "books"
            books_dir.mkdir(exist_ok=True)
            self.signals.progress.emit(0, len(books))

            for i, book in enumerate(books):
                self._export_book(book, books_dir)
                self.signals.progress.emit(i + 1, len(books))

            # 4. Timestamp
            (sf / "last_backup.txt").write_text(
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"), encoding="utf-8"
            )

            self.signals.finished.emit(
                True, f"Backup complete — {len(books)} book(s) exported."
            )
        except Exception as e:
            self.signals.finished.emit(False, str(e))

    def _export_book(self, book, books_dir: Path):
        safe = _safe_name(book["title"], 60)
        book_dir = books_dir / safe
        book_dir.mkdir(exist_ok=True)

        chapters = self.db.get_chapters(book["id"])

        meta = {
            "title":         book["title"],
            "author":        book.get("author", ""),
            "description":   book.get("description", ""),
            "source_url":    book.get("source_url", ""),
            "chapter_count": len(chapters),
            "exported_at":   datetime.now().isoformat(),
        }
        (book_dir / "metadata.json").write_text(
            json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        ch_dir = book_dir / "chapters"
        ch_dir.mkdir(exist_ok=True)
        for ch in chapters:
            content = (
                ch.get("rewritten_content")
                or ch.get("cleaned_content")
                or ch.get("original_content")
                or ""
            )
            safe_ch = _safe_name(ch.get("title") or "Untitled", 50)
            fname   = f"{ch['chapter_number']:04d}_{safe_ch}.txt"
            (ch_dir / fname).write_text(content, encoding="utf-8")

        self.signals.log_line.emit(f"  ✓ {book['title']} ({len(chapters)} chapters)")


class _RestoreWorker(QThread):
    def __init__(self, sync_folder: Path):
        super().__init__()
        self.sync_folder = sync_folder
        self.signals     = _SyncSignals()

    def run(self):
        try:
            src_db = self.sync_folder / "library.db"
            if not src_db.exists():
                self.signals.finished.emit(
                    False, "No library.db found in the sync folder.\n"
                           "Make sure you ran a backup first."
                )
                return

            self.signals.log_line.emit("Restoring database…")
            _DB_DIR.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_db, _DB_PATH)
            self.signals.log_line.emit("  ✓ library.db restored")

            src_covers = self.sync_folder / "covers"
            if src_covers.exists():
                self.signals.log_line.emit("Restoring cover images…")
                _COVER_DIR.mkdir(parents=True, exist_ok=True)
                count = 0
                for f in src_covers.iterdir():
                    shutil.copy2(f, _COVER_DIR / f.name)
                    count += 1
                self.signals.log_line.emit(f"  ✓ {count} cover file(s) restored")

            self.signals.finished.emit(
                True,
                "Restore complete.\n\nPlease restart EbookCleaner to load the restored library."
            )
        except Exception as e:
            self.signals.finished.emit(False, str(e))


# ------------------------------------------------------------------ helpers

def _safe_name(text: str, max_len: int) -> str:
    return "".join(c if c.isalnum() or c in " -_" else "_" for c in text)[:max_len].strip() or "Untitled"


def _read_last_backup(sync_folder: Path) -> str:
    try:
        ts = (sync_folder / "last_backup.txt").read_text(encoding="utf-8").strip()
        return f"Last backup: {ts}"
    except Exception:
        return "Last backup: never"


# ------------------------------------------------------------------ dialog

class SyncDialog(QDialog):
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db      = db
        self._worker = None
        self.setWindowTitle("Cloud Sync")
        self.setMinimumSize(560, 480)
        self._build_ui()
        self._load_settings()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        heading = QLabel("Cloud Sync")
        heading.setObjectName("heading")
        layout.addWidget(heading)

        note = QLabel(
            "Choose a folder inside your OneDrive, Google Drive, or Dropbox folder. "
            "Backup copies the database + covers and exports each book as readable text files. "
            "Restore brings back the database and covers from a previous backup."
        )
        note.setWordWrap(True)
        note.setObjectName("subtext")
        layout.addWidget(note)

        sep = QFrame(); sep.setFrameShape(QFrame.HLine)
        layout.addWidget(sep)

        # Sync folder row
        folder_row = QHBoxLayout()
        folder_row.setSpacing(6)
        folder_row.addWidget(QLabel("Sync folder:"))
        self.folder_edit = QLineEdit()
        self.folder_edit.setPlaceholderText(
            "e.g. C:\\Users\\you\\OneDrive\\EbookCleaner"
        )
        folder_row.addWidget(self.folder_edit, 1)
        browse_btn = QPushButton("Browse…")
        browse_btn.setObjectName("secondary")
        browse_btn.clicked.connect(self._browse_folder)
        folder_row.addWidget(browse_btn)
        layout.addLayout(folder_row)

        self.last_backup_lbl = QLabel("Last backup: never")
        self.last_backup_lbl.setObjectName("subtext")
        layout.addWidget(self.last_backup_lbl)

        sep2 = QFrame(); sep2.setFrameShape(QFrame.HLine)
        layout.addWidget(sep2)

        # Action buttons
        action_row = QHBoxLayout()
        action_row.setSpacing(8)

        self.backup_btn = QPushButton("Backup to Cloud")
        self.backup_btn.clicked.connect(self._start_backup)
        action_row.addWidget(self.backup_btn)

        self.restore_btn = QPushButton("Restore from Cloud")
        self.restore_btn.setObjectName("secondary")
        self.restore_btn.clicked.connect(self._start_restore)
        action_row.addWidget(self.restore_btn)

        action_row.addStretch()
        layout.addLayout(action_row)

        # Progress
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.status_lbl = QLabel("")
        self.status_lbl.setObjectName("subtext")
        layout.addWidget(self.status_lbl)

        self.log_edit = QTextEdit()
        self.log_edit.setReadOnly(True)
        self.log_edit.setPlaceholderText("Activity log will appear here…")
        layout.addWidget(self.log_edit, 1)

        close_row = QHBoxLayout()
        close_row.addStretch()
        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.accept)
        close_row.addWidget(self.close_btn)
        layout.addLayout(close_row)

    # ------------------------------------------------------------------ settings

    def _load_settings(self):
        folder = self.db.get_setting("sync_folder", "")
        self.folder_edit.setText(folder)
        if folder:
            self.last_backup_lbl.setText(_read_last_backup(Path(folder)))

    def _save_folder(self):
        folder = self.folder_edit.text().strip()
        if folder:
            self.db.set_setting("sync_folder", folder)
        return Path(folder) if folder else None

    # ------------------------------------------------------------------ UI helpers

    def _browse_folder(self):
        current = self.folder_edit.text().strip()
        chosen = QFileDialog.getExistingDirectory(
            self, "Choose Sync Folder", current or ""
        )
        if chosen:
            self.folder_edit.setText(chosen)

    def _set_busy(self, busy: bool):
        self.backup_btn.setEnabled(not busy)
        self.restore_btn.setEnabled(not busy)
        self.close_btn.setEnabled(not busy)
        self.progress_bar.setVisible(busy)
        if busy:
            self.log_edit.clear()
            self.progress_bar.setValue(0)

    def _get_valid_folder(self) -> Path | None:
        folder = self.folder_edit.text().strip()
        if not folder:
            QMessageBox.warning(
                self, "No Folder",
                "Please choose a sync folder first."
            )
            return None
        return Path(folder)

    # ------------------------------------------------------------------ backup

    def _start_backup(self):
        folder = self._get_valid_folder()
        if not folder:
            return
        self._save_folder()
        self.status_lbl.setText("Backing up…")
        self._set_busy(True)
        self.progress_bar.setRange(0, 0)   # indeterminate until books count known

        self._worker = _BackupWorker(self.db, folder)
        self._worker.signals.log_line.connect(self.log_edit.append)
        self._worker.signals.progress.connect(self._on_progress)
        self._worker.signals.finished.connect(self._on_finished)
        self._worker.start()

    # ------------------------------------------------------------------ restore

    def _start_restore(self):
        folder = self._get_valid_folder()
        if not folder:
            return
        if not (folder / "library.db").exists():
            QMessageBox.warning(
                self, "No Backup Found",
                "No library.db found in that folder.\n"
                "Run a backup first, or choose the correct folder."
            )
            return
        reply = QMessageBox.warning(
            self, "Restore Library",
            "This will replace your current library with the backup.\n\n"
            "Your current data will be overwritten. Continue?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        self._save_folder()
        self.status_lbl.setText("Restoring…")
        self._set_busy(True)
        self.progress_bar.setRange(0, 0)

        self._worker = _RestoreWorker(folder)
        self._worker.signals.log_line.connect(self.log_edit.append)
        self._worker.signals.finished.connect(self._on_finished)
        self._worker.start()

    # ------------------------------------------------------------------ shared finish

    def _on_progress(self, done, total):
        if total > 0:
            self.progress_bar.setRange(0, total)
            self.progress_bar.setValue(done)

    def _on_finished(self, success: bool, message: str):
        self._set_busy(False)
        self.status_lbl.setText(message.split("\n")[0])
        folder = self.folder_edit.text().strip()
        if folder:
            self.last_backup_lbl.setText(_read_last_backup(Path(folder)))
        if success:
            QMessageBox.information(self, "Done", message)
        else:
            QMessageBox.critical(self, "Error", message)

    def closeEvent(self, event):
        if self._worker and self._worker.isRunning():
            self._worker.wait(3000)
        super().closeEvent(event)

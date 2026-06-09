from pathlib import Path
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QPushButton,
    QFileDialog, QLineEdit, QCheckBox, QMessageBox, QFrame, QFormLayout,
    QProgressDialog
)
from PySide6.QtCore import Qt


class ExportDialog(QDialog):
    def __init__(self, db, book_id: int, parent=None):
        super().__init__(parent)
        self.db = db
        self.book_id = book_id
        self.setWindowTitle("Export to EPUB")
        self.setMinimumWidth(480)
        self.setModal(True)
        self._build_ui()
        self._load_book_info()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)

        heading = QLabel("Export to EPUB")
        heading.setObjectName("heading")
        layout.addWidget(heading)

        sep = QFrame(); sep.setFrameShape(QFrame.HLine)
        layout.addWidget(sep)

        form = QFormLayout(); form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.title_label = QLabel("")
        form.addRow("Book:", self.title_label)

        self.version_combo = QComboBox()
        self.version_combo.addItems(["Rewritten", "Cleaned", "Original"])
        self.version_combo.setCurrentIndex(0)
        form.addRow("Content version:", self.version_combo)

        layout.addLayout(form)

        # Cover
        self.cover_cb = QCheckBox("Include cover image (if available)")
        self.cover_cb.setChecked(True)
        layout.addWidget(self.cover_cb)

        cover_info = QLabel("")
        cover_info.setObjectName("subtext")
        cover_info.setWordWrap(True)
        self._cover_info_label = cover_info
        layout.addWidget(cover_info)

        sep2 = QFrame(); sep2.setFrameShape(QFrame.HLine)
        layout.addWidget(sep2)

        # Output path
        path_row = QHBoxLayout(); path_row.setSpacing(8)
        self.path_edit = QLineEdit()
        self.path_edit.setReadOnly(True)
        self.path_edit.setPlaceholderText("Choose output location...")
        path_row.addWidget(self.path_edit, 1)
        browse_btn = QPushButton("Browse")
        browse_btn.setObjectName("secondary")
        browse_btn.clicked.connect(self._browse)
        path_row.addWidget(browse_btn)
        layout.addLayout(path_row)

        # Buttons
        btn_row = QHBoxLayout(); btn_row.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("secondary")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)
        self.export_btn = QPushButton("Export")
        self.export_btn.setEnabled(False)
        self.export_btn.clicked.connect(self._export)
        btn_row.addWidget(self.export_btn)
        layout.addLayout(btn_row)

    def _load_book_info(self):
        book = self.db.get_book(self.book_id)
        if book:
            self.title_label.setText(f"{book['title']} — {book['author'] or 'Unknown Author'}")

            # Check for cover
            from pathlib import Path
            covers_dir = Path.home() / ".ebookcleaner" / "covers"
            cover_files = list(covers_dir.glob(f"{self.book_id}.*")) if covers_dir.exists() else []
            if cover_files:
                self._cover_info_label.setText(f"Cover found: {cover_files[0].name}")
                self.cover_cb.setEnabled(True)
            else:
                self._cover_info_label.setText("No cover image downloaded for this book.")
                self.cover_cb.setEnabled(False)
                self.cover_cb.setChecked(False)

            # Suggest output path
            safe_title = "".join(c for c in book["title"] if c.isalnum() or c in " -_").strip()
            default_path = str(Path.home() / "Documents" / f"{safe_title}.epub")
            self.path_edit.setText(default_path)
            self.export_btn.setEnabled(True)

    def _browse(self):
        book = self.db.get_book(self.book_id)
        safe_title = ""
        if book:
            safe_title = "".join(c for c in book["title"] if c.isalnum() or c in " -_").strip()
        default = str(Path.home() / "Documents" / f"{safe_title or 'book'}.epub")
        path, _ = QFileDialog.getSaveFileName(
            self, "Save EPUB", default, "EPUB Files (*.epub);;All Files (*)"
        )
        if path:
            if not path.endswith(".epub"):
                path += ".epub"
            self.path_edit.setText(path)
            self.export_btn.setEnabled(True)

    def _export(self):
        output_path = self.path_edit.text().strip()
        if not output_path:
            QMessageBox.warning(self, "No Path", "Please choose an output file path.")
            return

        version_map = {"Rewritten": "rewritten", "Cleaned": "cleaned", "Original": "original"}
        content_version = version_map[self.version_combo.currentText()]

        # Load cover if requested
        cover_data = None
        cover_mime = "image/jpeg"
        if self.cover_cb.isChecked():
            from pathlib import Path
            covers_dir = Path.home() / ".ebookcleaner" / "covers"
            cover_files = list(covers_dir.glob(f"{self.book_id}.*")) if covers_dir.exists() else []
            if cover_files:
                cover_data = cover_files[0].read_bytes()
                ext = cover_files[0].suffix.lower().lstrip(".")
                cover_mime = f"image/{'jpeg' if ext == 'jpg' else ext}"

        from src.epub_exporter import EpubExporter
        try:
            n = EpubExporter().export(
                self.book_id, self.db, output_path,
                content_version=content_version,
                cover_data=cover_data,
                cover_mime=cover_mime,
            )
            QMessageBox.information(
                self, "Export Complete",
                f"Exported {n} chapter(s) to:\n{output_path}"
            )
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Export Failed", str(e))

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QFileDialog, QCheckBox, QComboBox, QProgressDialog, QMessageBox,
    QFormLayout, QFrame
)
from PySide6.QtCore import Qt, QThread, QObject, Signal


class _ParseSignals(QObject):
    finished = Signal(dict)
    error = Signal(str)


class _ParseThread(QThread):
    def __init__(self, file_path):
        super().__init__()
        self.file_path = file_path
        self.signals = _ParseSignals()

    def run(self):
        try:
            from src.ebook_parser import EbookParser
            data = EbookParser().parse(self.file_path)
            self.signals.finished.emit(data)
        except Exception as e:
            self.signals.error.emit(str(e))


class ImportDialog(QDialog):
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self._parsed_data = None
        self._parse_thread = None
        self._file_path = None
        self.imported_book_id = None

        self.setWindowTitle("Import Ebook")
        self.setMinimumWidth(500)
        self.setModal(True)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)

        heading = QLabel("Import Ebook")
        heading.setObjectName("heading")
        layout.addWidget(heading)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        layout.addWidget(sep)

        # File picker
        file_row = QHBoxLayout()
        self.file_edit = QLineEdit()
        self.file_edit.setReadOnly(True)
        self.file_edit.setPlaceholderText("No file selected")
        file_row.addWidget(self.file_edit)
        browse_btn = QPushButton("Browse")
        browse_btn.setObjectName("secondary")
        browse_btn.clicked.connect(self._browse)
        file_row.addWidget(browse_btn)
        layout.addLayout(file_row)

        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("Book title")
        form.addRow("Title:", self.title_edit)

        self.author_edit = QLineEdit()
        self.author_edit.setPlaceholderText("Author name")
        form.addRow("Author:", self.author_edit)

        layout.addLayout(form)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.HLine)
        layout.addWidget(sep2)

        self.update_cb = QCheckBox("This is an updated version of an existing book")
        self.update_cb.toggled.connect(self._toggle_existing)
        layout.addWidget(self.update_cb)

        self.existing_label = QLabel("Existing book:")
        self.existing_combo = QComboBox()
        self._populate_books()
        existing_row = QHBoxLayout()
        existing_row.addWidget(self.existing_label)
        existing_row.addWidget(self.existing_combo, 1)
        layout.addLayout(existing_row)

        self.existing_label.setVisible(False)
        self.existing_combo.setVisible(False)

        btn_row = QHBoxLayout()
        btn_row.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("secondary")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        self.import_btn = QPushButton("Import")
        self.import_btn.setEnabled(False)
        self.import_btn.clicked.connect(self._import)
        btn_row.addWidget(self.import_btn)

        layout.addLayout(btn_row)

    def _populate_books(self):
        self.existing_combo.clear()
        for book in self.db.get_all_books():
            self.existing_combo.addItem(
                f"{book['title']} ({book['author'] or 'Unknown'})",
                book["id"]
            )

    def _toggle_existing(self, checked):
        self.existing_label.setVisible(checked)
        self.existing_combo.setVisible(checked)

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Ebook", "", "Ebooks (*.epub *.txt);;All Files (*)"
        )
        if not path:
            return
        self._file_path = path
        self.file_edit.setText(path)

        # Auto-parse to fill title/author
        self._parse_thread = _ParseThread(path)
        self._parse_thread.signals.finished.connect(self._on_parsed)
        self._parse_thread.signals.error.connect(self._on_parse_error)
        self._parse_thread.start()

    def _on_parsed(self, data):
        self._parsed_data = data
        if not self.title_edit.text():
            self.title_edit.setText(data.get("title", ""))
        if not self.author_edit.text():
            self.author_edit.setText(data.get("author", ""))
        self.import_btn.setEnabled(True)

    def _on_parse_error(self, msg):
        QMessageBox.warning(self, "Parse Error", f"Could not parse file:\n{msg}")
        self.import_btn.setEnabled(False)

    def _import(self):
        if not self._parsed_data:
            QMessageBox.warning(self, "No Data", "Please select a valid ebook file first.")
            return

        title = self.title_edit.text().strip() or self._parsed_data.get("title", "Untitled")
        author = self.author_edit.text().strip() or self._parsed_data.get("author", "")
        chapters = self._parsed_data.get("chapters", [])

        if not chapters:
            QMessageBox.warning(self, "Empty Book", "No chapters were found in this file.")
            return

        is_update = self.update_cb.isChecked()

        if is_update and self.existing_combo.count() > 0:
            existing_book_id = self.existing_combo.currentData()
            self._do_merge(existing_book_id, chapters)
        else:
            self._do_new_import(title, author, chapters)

    def _do_new_import(self, title, author, chapters):
        progress = QProgressDialog("Importing chapters...", None, 0, len(chapters), self)
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(0)

        book_id = self.db.add_book(title, author)
        for i, ch in enumerate(chapters):
            progress.setValue(i)
            self.db.add_chapter(book_id, ch["number"], ch["title"], ch["content"])
        progress.setValue(len(chapters))

        version_num = self.db.get_next_version_number(book_id)
        self.db.add_version(book_id, version_num, self._file_path or "", len(chapters))

        self.imported_book_id = book_id
        self.accept()

    def _do_merge(self, existing_book_id, new_chapters):
        existing_chapters = self.db.get_chapters(existing_book_id)
        from src.merger import ChapterMerger
        analysis = ChapterMerger().analyze(existing_chapters, new_chapters)

        if not analysis["new"] and not analysis["updated"]:
            QMessageBox.information(
                self,
                "No Changes",
                "All chapters in this version already exist in the library. Nothing to merge.",
            )
            return

        from src.ui.merge_dialog import MergeDialog
        dlg = MergeDialog(existing_book_id, analysis, self.db, self)
        if dlg.exec():
            version_num = self.db.get_next_version_number(existing_book_id)
            self.db.add_version(
                existing_book_id, version_num, self._file_path or "", len(new_chapters),
                notes=f"Merged: {len(analysis['new'])} new, {len(analysis['updated'])} updated"
            )
            self.imported_book_id = existing_book_id
            self.accept()

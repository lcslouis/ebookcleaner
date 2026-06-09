from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QSplitter, QToolBar,
    QStatusBar, QLabel, QMessageBox
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QAction

from src.ui.book_list_widget import BookListWidget
from src.ui.book_editor_widget import BookEditorWidget
from src.ui.import_dialog import ImportDialog
from src.ui.settings_dialog import SettingsDialog


class MainWindow(QMainWindow):
    def __init__(self, db):
        super().__init__()
        self.db = db
        self.setWindowTitle("EbookCleaner")
        self.setMinimumSize(1100, 700)
        self.resize(1280, 800)
        self._build_ui()
        self._build_toolbar()
        self._build_statusbar()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(1)

        self.book_list = BookListWidget(self.db)
        self.book_list.setMinimumWidth(200)
        self.book_list.setMaximumWidth(320)
        self.book_list.book_selected.connect(self._on_book_selected)
        self.book_list.import_requested.connect(self._import_book)
        self.book_list.book_deleted.connect(self._on_book_deleted)
        splitter.addWidget(self.book_list)

        self.editor = BookEditorWidget(self.db)
        self.editor.chapter_saved.connect(self._on_chapter_saved)
        splitter.addWidget(self.editor)

        splitter.setSizes([250, 1030])
        layout.addWidget(splitter)

    def _build_toolbar(self):
        tb = QToolBar("Main Toolbar")
        tb.setMovable(False)
        tb.setIconSize(QSize(16, 16))
        self.addToolBar(tb)

        import_action = QAction("Import File", self)
        import_action.setToolTip("Import EPUB or TXT file from disk")
        import_action.triggered.connect(self._import_book)
        tb.addAction(import_action)

        fetch_action = QAction("Fetch from Web", self)
        fetch_action.setToolTip(
            "Download an ebook directly from a URL (RoyalRoad, FanFiction.net, AO3, ScribbleHub, and more)"
        )
        fetch_action.triggered.connect(self._fetch_from_web)
        tb.addAction(fetch_action)

        tb.addSeparator()

        self._export_action = QAction("Export EPUB", self)
        self._export_action.setToolTip("Export the current book to an EPUB file")
        self._export_action.setEnabled(False)
        self._export_action.triggered.connect(self._export_epub)
        tb.addAction(self._export_action)

        tb.addSeparator()

        settings_action = QAction("Settings", self)
        settings_action.triggered.connect(self._open_settings)
        tb.addAction(settings_action)

        tb.addSeparator()

        about_action = QAction("About", self)
        about_action.triggered.connect(self._show_about)
        tb.addAction(about_action)

    def _build_statusbar(self):
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self._status_label = QLabel("Ready")
        self.status_bar.addWidget(self._status_label)

    # ------------------------------------------------------------------ slots

    def _on_book_selected(self, book_id):
        self._current_book_id = book_id
        self.editor.load_book(book_id)
        self._export_action.setEnabled(True)
        book = self.db.get_book(book_id)
        if book:
            self._status_label.setText(f"Loaded: {book['title']}")

    def _on_book_deleted(self, book_id):
        self.editor._show_empty()
        self._export_action.setEnabled(False)
        self._current_book_id = None
        self._status_label.setText("Book deleted")

    def _on_chapter_saved(self):
        self._status_label.setText("Chapter saved")

    # ------------------------------------------------------------------ actions

    def _import_book(self):
        dlg = ImportDialog(self.db, self)
        if dlg.exec():
            self._after_import(dlg.imported_book_id, "Import complete")

    def _fetch_from_web(self):
        from src.ui.fetch_dialog import FetchDialog
        dlg = FetchDialog(self.db, self)
        if dlg.exec():
            self._after_import(dlg.imported_book_id, "Web fetch complete")

    def _after_import(self, book_id, msg):
        self.book_list.refresh()
        if book_id:
            self.book_list.select_book(book_id)
            self.editor.load_book(book_id)
            self._current_book_id = book_id
            self._export_action.setEnabled(True)
        self._status_label.setText(msg)

    def _export_epub(self):
        book_id = getattr(self, "_current_book_id", None)
        if not book_id:
            QMessageBox.warning(self, "No Book", "Select a book first.")
            return
        from src.ui.export_dialog import ExportDialog
        dlg = ExportDialog(self.db, book_id, self)
        dlg.exec()

    def _open_settings(self):
        dlg = SettingsDialog(self.db, self)
        dlg.exec()

    def _show_about(self):
        QMessageBox.about(
            self,
            "About EbookCleaner",
            "<b>EbookCleaner</b><br><br>"
            "An ebook management and processing tool.<br><br>"
            "<b>Import:</b><br>"
            "• Import EPUB / TXT files from disk<br>"
            "• Fetch directly from Royal Road, FanFiction.net, AO3, ScribbleHub, or any URL<br><br>"
            "<b>Process:</b><br>"
            "• Rule-based text cleaning (page numbers, OCR artifacts, broken hyphenation)<br>"
            "• AI grammar correction and full rewriting (Anthropic API)<br><br>"
            "<b>Manage:</b><br>"
            "• Book library with version tracking<br>"
            "• Import updated versions and merge new chapters<br>"
            "• Export processed books to EPUB with cover image<br><br>"
            "Configure your Anthropic API key in <b>Settings</b>.",
        )

    def closeEvent(self, event):
        self.db.close()
        event.accept()

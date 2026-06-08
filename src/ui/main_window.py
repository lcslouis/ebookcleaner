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

        import_action = QAction("Import Book", self)
        import_action.triggered.connect(self._import_book)
        tb.addAction(import_action)

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

    def _on_book_selected(self, book_id):
        self.editor.load_book(book_id)
        book = self.db.get_book(book_id)
        if book:
            self._status_label.setText(f"Loaded: {book['title']}")

    def _on_book_deleted(self, book_id):
        self.editor._show_empty()
        self._status_label.setText("Book deleted")

    def _on_chapter_saved(self):
        self._status_label.setText("Chapter saved")

    def _import_book(self):
        dlg = ImportDialog(self.db, self)
        if dlg.exec():
            self.book_list.refresh()
            if dlg.imported_book_id:
                self.book_list.select_book(dlg.imported_book_id)
                self.editor.load_book(dlg.imported_book_id)
            self._status_label.setText("Import complete")

    def _open_settings(self):
        dlg = SettingsDialog(self.db, self)
        dlg.exec()

    def _show_about(self):
        QMessageBox.about(
            self,
            "About EbookCleaner",
            "<b>EbookCleaner</b><br><br>"
            "An ebook management tool for cleaning, proofreading, and rewriting ebooks.<br><br>"
            "Features:<br>"
            "• Import EPUB and TXT ebooks<br>"
            "• Rule-based text cleaning<br>"
            "• AI-powered grammar correction and rewriting<br>"
            "• Version management and chapter merging<br><br>"
            "Requires an Anthropic API key for AI features.<br>"
            "Configure in Settings.",
        )

    def closeEvent(self, event):
        self.db.close()
        event.accept()

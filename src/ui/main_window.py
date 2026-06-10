from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QSplitter, QToolBar,
    QStatusBar, QLabel, QMessageBox, QFrame
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QAction

from src.ui.book_list_widget import BookListWidget
from src.ui.book_editor_widget import BookEditorWidget
from src.ui.import_dialog import ImportDialog
from src.ui.settings_dialog import SettingsDialog
from src.ui.download_manager import DownloadManager
from src.ui.downloads_panel import DownloadsPanel


class MainWindow(QMainWindow):
    def __init__(self, db):
        super().__init__()
        self.db = db
        self.setWindowTitle("EbookCleaner")
        self.setMinimumSize(1100, 700)
        self.resize(1280, 800)

        from src.version import get_version
        self.setWindowTitle(f"EbookCleaner  v{get_version()}")

        self.download_manager = DownloadManager(self)
        self.download_manager.book_saved.connect(self._on_background_book_saved)
        self.download_manager.active_count_changed.connect(self._on_active_downloads_changed)

        self._build_ui()
        self._build_toolbar()
        self._build_statusbar()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Main content splitter (left library | right editor)
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(1)

        self.book_list = BookListWidget(self.db)
        self.book_list.setMinimumWidth(200)
        self.book_list.setMaximumWidth(320)
        self.book_list.book_selected.connect(self._on_book_selected)
        self.book_list.import_requested.connect(self._import_book)
        self.book_list.book_deleted.connect(self._on_book_deleted)
        self.book_list.update_requested.connect(self._update_from_web)
        splitter.addWidget(self.book_list)

        self.editor = BookEditorWidget(self.db)
        self.editor.chapter_saved.connect(self._on_chapter_saved)
        splitter.addWidget(self.editor)

        splitter.setSizes([250, 1030])
        outer.addWidget(splitter, 1)

        # Downloads panel (hidden until first download starts)
        sep = QFrame(); sep.setFrameShape(QFrame.HLine)
        outer.addWidget(sep)

        self.downloads_panel = DownloadsPanel(self.download_manager)
        self.downloads_panel.setFixedHeight(170)
        self.downloads_panel.setVisible(False)
        outer.addWidget(self.downloads_panel)

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
            "Download an ebook from a URL (RoyalRoad, FanFiction.net, AO3, ScribbleHub, and more)"
        )
        fetch_action.triggered.connect(self._fetch_from_web)
        tb.addAction(fetch_action)

        self._update_action = QAction("Update from Web", self)
        self._update_action.setToolTip("Re-fetch the selected book and add any new chapters")
        self._update_action.setEnabled(False)
        self._update_action.triggered.connect(self._update_selected_from_web)
        tb.addAction(self._update_action)

        tb.addSeparator()

        self._export_action = QAction("Export EPUB", self)
        self._export_action.setToolTip("Export the current book to an EPUB file")
        self._export_action.setEnabled(False)
        self._export_action.triggered.connect(self._export_epub)
        tb.addAction(self._export_action)

        tb.addSeparator()

        sync_action = QAction("Sync", self)
        sync_action.setToolTip(
            "Back up or restore your library to/from a cloud folder "
            "(OneDrive, Google Drive, Dropbox, etc.)"
        )
        sync_action.triggered.connect(self._open_sync)
        tb.addAction(sync_action)

        tb.addSeparator()

        self._downloads_action = QAction("Downloads", self)
        self._downloads_action.setToolTip("Show / hide the downloads panel")
        self._downloads_action.triggered.connect(self._toggle_downloads_panel)
        tb.addAction(self._downloads_action)

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
        self._dl_status_label = QLabel("")
        self._dl_status_label.setObjectName("subtext")
        self.status_bar.addPermanentWidget(self._dl_status_label)

    # ------------------------------------------------------------------ slots

    def _on_book_selected(self, book_id):
        self._current_book_id = book_id
        self.editor.load_book(book_id)
        self._export_action.setEnabled(True)
        book = self.db.get_book(book_id)
        if book:
            self._status_label.setText(f"Loaded: {book['title']}")
            self._update_action.setEnabled(True)

    def _on_book_deleted(self, book_id):
        self.editor._show_empty()
        self._export_action.setEnabled(False)
        self._update_action.setEnabled(False)
        self._current_book_id = None
        self._status_label.setText("Book deleted")

    def _on_chapter_saved(self):
        self._status_label.setText("Chapter saved")

    def _on_background_book_saved(self, book_id):
        """Called when a background download completes and saves a book."""
        self.book_list.refresh()
        # If this was an update for the currently open book, reload it
        if getattr(self, "_current_book_id", None) == book_id:
            self.editor.load_book(book_id)

    def _on_active_downloads_changed(self, count: int):
        if count > 0:
            self._downloads_action.setText(f"Downloads ({count})")
            self._dl_status_label.setText(f"  {count} download(s) running")
            # Auto-show the panel when downloads start
            if not self.downloads_panel.isVisible():
                self.downloads_panel.setVisible(True)
        else:
            self._downloads_action.setText("Downloads")
            self._dl_status_label.setText("")

    # ------------------------------------------------------------------ actions

    def _toggle_downloads_panel(self):
        self.downloads_panel.setVisible(not self.downloads_panel.isVisible())

    def _import_book(self):
        dlg = ImportDialog(self.db, self)
        if dlg.exec():
            self._after_import(dlg.imported_book_id, "Import complete")

    def _fetch_from_web(self):
        from src.ui.fetch_dialog import FetchDialog
        dlg = FetchDialog(self.db, self, download_manager=self.download_manager)
        if dlg.exec():
            self._after_import(dlg.imported_book_id, "Web fetch complete")

    def _update_selected_from_web(self):
        book_id = getattr(self, "_current_book_id", None)
        if book_id:
            self._update_from_web(book_id)

    def _update_from_web(self, book_id):
        from src.ui.fetch_dialog import FetchDialog
        dlg = FetchDialog(self.db, self,
                          update_book_id=book_id,
                          download_manager=self.download_manager)
        if dlg.exec():
            self._after_import(dlg.imported_book_id, "Book updated")

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

    def _open_sync(self):
        from src.ui.sync_dialog import SyncDialog
        SyncDialog(self.db, self).exec()

    def _open_settings(self):
        dlg = SettingsDialog(self.db, self)
        dlg.exec()

    def _show_about(self):
        from src.version import get_version
        ver = get_version()
        QMessageBox.about(
            self,
            "About EbookCleaner",
            f"<b>EbookCleaner</b> &nbsp; <small>v{ver}</small><br><br>"
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

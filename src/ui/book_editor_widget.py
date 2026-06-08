from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QListWidget, QListWidgetItem,
    QTabWidget, QTextEdit, QPushButton, QLabel, QLineEdit, QMessageBox,
    QProgressDialog, QFrame
)
from PySide6.QtCore import Qt, Signal, QThread, QObject, QRunnable, QThreadPool
import threading


class _WorkerSignals(QObject):
    finished = Signal(str)
    error = Signal(str)
    progress = Signal(int, int)


class _AIWorker(QRunnable):
    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = _WorkerSignals()

    def run(self):
        try:
            result = self.fn(*self.args, **self.kwargs)
            self.signals.finished.emit(result)
        except Exception as e:
            self.signals.error.emit(str(e))


class BookEditorWidget(QWidget):
    chapter_saved = Signal()

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self._current_book_id = None
        self._current_chapter_id = None
        self._saving = False
        self._thread_pool = QThreadPool.globalInstance()
        self._build_ui()
        self._show_empty()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # Book header
        header_row = QHBoxLayout()
        header_row.setSpacing(12)

        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        QLabel_title = QLabel("Title:")
        QLabel_title.setObjectName("subtext")
        title_col.addWidget(QLabel_title)
        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("Book title")
        self.title_edit.editingFinished.connect(self._save_book_meta)
        title_col.addWidget(self.title_edit)
        header_row.addLayout(title_col, 3)

        author_col = QVBoxLayout()
        author_col.setSpacing(2)
        QLabel_author = QLabel("Author:")
        QLabel_author.setObjectName("subtext")
        author_col.addWidget(QLabel_author)
        self.author_edit = QLineEdit()
        self.author_edit.setPlaceholderText("Author name")
        self.author_edit.editingFinished.connect(self._save_book_meta)
        author_col.addWidget(self.author_edit)
        header_row.addLayout(author_col, 2)

        layout.addLayout(header_row)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        layout.addWidget(sep)

        # Main splitter
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(1)

        # Chapter list
        ch_panel = QWidget()
        ch_layout = QVBoxLayout(ch_panel)
        ch_layout.setContentsMargins(0, 0, 0, 0)
        ch_layout.setSpacing(6)

        ch_label = QLabel("Chapters")
        ch_label.setObjectName("subtext")
        ch_layout.addWidget(ch_label)

        self.chapter_list = QListWidget()
        self.chapter_list.itemSelectionChanged.connect(self._on_chapter_selected)
        ch_layout.addWidget(self.chapter_list)

        splitter.addWidget(ch_panel)

        # Editor tabs
        editor_panel = QWidget()
        editor_layout = QVBoxLayout(editor_panel)
        editor_layout.setContentsMargins(0, 0, 0, 0)
        editor_layout.setSpacing(6)

        self.tabs = QTabWidget()

        # Original tab
        orig_widget = QWidget()
        orig_layout = QVBoxLayout(orig_widget)
        orig_layout.setContentsMargins(0, 0, 0, 0)
        self.original_edit = QTextEdit()
        self.original_edit.setReadOnly(True)
        self.original_edit.setPlaceholderText("Original imported content")
        orig_layout.addWidget(self.original_edit)
        self.tabs.addTab(orig_widget, "Original")

        # Cleaned tab
        cleaned_widget = QWidget()
        cleaned_layout = QVBoxLayout(cleaned_widget)
        cleaned_layout.setContentsMargins(4, 4, 4, 4)
        cleaned_layout.setSpacing(6)

        clean_btn_row = QHBoxLayout()
        self.clean_btn = QPushButton("Clean with Rules")
        self.clean_btn.clicked.connect(self._clean_chapter)
        clean_btn_row.addWidget(self.clean_btn)
        self.ai_clean_btn = QPushButton("Fix Grammar with AI")
        self.ai_clean_btn.clicked.connect(self._ai_clean)
        clean_btn_row.addWidget(self.ai_clean_btn)
        clean_btn_row.addStretch()
        cleaned_layout.addLayout(clean_btn_row)

        self.cleaned_edit = QTextEdit()
        self.cleaned_edit.setPlaceholderText("Cleaned content will appear here")
        self.cleaned_edit.textChanged.connect(self._on_text_changed)
        cleaned_layout.addWidget(self.cleaned_edit)
        self.tabs.addTab(cleaned_widget, "Cleaned")

        # Rewritten tab
        rewritten_widget = QWidget()
        rewritten_layout = QVBoxLayout(rewritten_widget)
        rewritten_layout.setContentsMargins(4, 4, 4, 4)
        rewritten_layout.setSpacing(6)

        rewrite_btn_row = QHBoxLayout()
        self.rewrite_btn = QPushButton("Rewrite with AI")
        self.rewrite_btn.clicked.connect(self._ai_rewrite)
        rewrite_btn_row.addWidget(self.rewrite_btn)
        rewrite_btn_row.addStretch()
        rewritten_layout.addLayout(rewrite_btn_row)

        self.rewritten_edit = QTextEdit()
        self.rewritten_edit.setPlaceholderText("Rewritten content will appear here")
        self.rewritten_edit.textChanged.connect(self._on_text_changed)
        rewritten_layout.addWidget(self.rewritten_edit)
        self.tabs.addTab(rewritten_widget, "Rewritten")

        editor_layout.addWidget(self.tabs)

        # Bottom bar
        bottom_row = QHBoxLayout()
        self.word_count_label = QLabel("Words: 0")
        self.word_count_label.setObjectName("subtext")
        bottom_row.addWidget(self.word_count_label)

        self.status_label = QLabel("")
        self.status_label.setObjectName("subtext")
        bottom_row.addWidget(self.status_label)

        bottom_row.addStretch()

        self.save_btn = QPushButton("Save")
        self.save_btn.clicked.connect(self._save_chapter)
        self.save_btn.setEnabled(False)
        bottom_row.addWidget(self.save_btn)

        editor_layout.addLayout(bottom_row)
        splitter.addWidget(editor_panel)

        splitter.setSizes([200, 700])
        layout.addWidget(splitter)

    def _show_empty(self):
        self.title_edit.setText("")
        self.author_edit.setText("")
        self.title_edit.setEnabled(False)
        self.author_edit.setEnabled(False)
        self.chapter_list.clear()
        self.original_edit.clear()
        self.cleaned_edit.clear()
        self.rewritten_edit.clear()
        self.save_btn.setEnabled(False)
        self._current_book_id = None
        self._current_chapter_id = None

    def load_book(self, book_id):
        # Auto-save current chapter before switching
        if self._current_chapter_id and not self._saving:
            self._save_chapter(silent=True)

        self._current_book_id = book_id
        book = self.db.get_book(book_id)
        if not book:
            self._show_empty()
            return

        self.title_edit.setEnabled(True)
        self.author_edit.setEnabled(True)
        self.title_edit.setText(book["title"])
        self.author_edit.setText(book["author"])

        self._load_chapter_list()

    def _load_chapter_list(self):
        current_id = self._current_chapter_id
        chapters = self.db.get_chapters(self._current_book_id)
        self.chapter_list.blockSignals(True)
        self.chapter_list.clear()
        for ch in chapters:
            label = f"Ch. {ch['chapter_number']}: {ch['title'] or 'Untitled'}"
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, ch["id"])
            self.chapter_list.addItem(item)
        self.chapter_list.blockSignals(False)

        if chapters:
            # Re-select previously selected, else first
            restored = False
            if current_id:
                for i in range(self.chapter_list.count()):
                    if self.chapter_list.item(i).data(Qt.UserRole) == current_id:
                        self.chapter_list.setCurrentRow(i)
                        restored = True
                        break
            if not restored:
                self.chapter_list.setCurrentRow(0)

    def _on_chapter_selected(self):
        if self._current_chapter_id and not self._saving:
            self._save_chapter(silent=True)

        items = self.chapter_list.selectedItems()
        if not items:
            return
        chapter_id = items[0].data(Qt.UserRole)
        self._load_chapter(chapter_id)

    def _load_chapter(self, chapter_id):
        self._current_chapter_id = chapter_id
        ch = self.db.get_chapter(chapter_id)
        if not ch:
            return

        self._saving = True
        self.original_edit.setPlainText(ch["original_content"] or "")
        self.cleaned_edit.setPlainText(ch["cleaned_content"] or "")
        self.rewritten_edit.setPlainText(ch["rewritten_content"] or "")
        self._saving = False

        self.save_btn.setEnabled(True)
        self.status_label.setText(f"Status: {ch['status']}")
        self._update_word_count()

    def _on_text_changed(self):
        if not self._saving:
            self.save_btn.setEnabled(True)
            self._update_word_count()

    def _update_word_count(self):
        tab = self.tabs.currentIndex()
        if tab == 0:
            text = self.original_edit.toPlainText()
        elif tab == 1:
            text = self.cleaned_edit.toPlainText()
        else:
            text = self.rewritten_edit.toPlainText()
        count = len(text.split()) if text.strip() else 0
        self.word_count_label.setText(f"Words: {count:,}")

    def _save_book_meta(self):
        if not self._current_book_id:
            return
        self.db.update_book(
            self._current_book_id,
            title=self.title_edit.text().strip(),
            author=self.author_edit.text().strip(),
        )

    def _save_chapter(self, silent=False):
        if not self._current_chapter_id:
            return
        self._saving = True
        cleaned = self.cleaned_edit.toPlainText()
        rewritten = self.rewritten_edit.toPlainText()

        status = "original"
        if rewritten.strip():
            status = "rewritten"
        elif cleaned.strip():
            status = "cleaned"

        self.db.update_chapter(
            self._current_chapter_id,
            cleaned_content=cleaned,
            rewritten_content=rewritten,
            word_count=len(cleaned.split()) if cleaned.strip() else 0,
            status=status,
        )
        self._saving = False
        self.save_btn.setEnabled(False)
        self.status_label.setText(f"Status: {status}")
        if not silent:
            self.chapter_saved.emit()

    def _get_ai_processor(self):
        api_key = self.db.get_setting("anthropic_api_key", "")
        if not api_key:
            QMessageBox.information(
                self,
                "API Key Required",
                "Please configure your Anthropic API key in Settings to use AI features.",
            )
            return None
        from src.ai_processor import AIProcessor
        return AIProcessor(api_key)

    def _clean_chapter(self):
        if not self._current_chapter_id:
            return
        ch = self.db.get_chapter(self._current_chapter_id)
        source = ch["original_content"] or ""
        if not source.strip():
            QMessageBox.warning(self, "No Content", "No original content to clean.")
            return
        from src.cleaner import TextCleaner
        result = TextCleaner().clean(source)
        self.cleaned_edit.setPlainText(result)
        self.tabs.setCurrentIndex(1)

    def _ai_clean(self):
        proc = self._get_ai_processor()
        if not proc:
            return
        if not self._current_chapter_id:
            return
        ch = self.db.get_chapter(self._current_chapter_id)
        source = ch["cleaned_content"] or ch["original_content"] or ""
        if not source.strip():
            QMessageBox.warning(self, "No Content", "No content to process.")
            return
        self._run_ai_task(proc.clean_chapter, source, self.cleaned_edit, "Fixing grammar...", 1)

    def _ai_rewrite(self):
        proc = self._get_ai_processor()
        if not proc:
            return
        if not self._current_chapter_id:
            return
        ch = self.db.get_chapter(self._current_chapter_id)
        source = ch["cleaned_content"] or ch["original_content"] or ""
        if not source.strip():
            QMessageBox.warning(self, "No Content", "Clean the chapter first before rewriting.")
            return
        self._run_ai_task(proc.rewrite_chapter, source, self.rewritten_edit, "Rewriting...", 2)

    def _run_ai_task(self, fn, text, target_edit, label, tab_index):
        self.clean_btn.setEnabled(False)
        self.ai_clean_btn.setEnabled(False)
        self.rewrite_btn.setEnabled(False)
        self.status_label.setText(label)

        worker = _AIWorker(fn, text)
        worker.signals.finished.connect(lambda result: self._ai_done(result, target_edit, tab_index))
        worker.signals.error.connect(self._ai_error)
        self._thread_pool.start(worker)

    def _ai_done(self, result, target_edit, tab_index):
        target_edit.setPlainText(result)
        self.tabs.setCurrentIndex(tab_index)
        self.clean_btn.setEnabled(True)
        self.ai_clean_btn.setEnabled(True)
        self.rewrite_btn.setEnabled(True)
        self.status_label.setText("Done")
        self._save_chapter(silent=True)

    def _ai_error(self, error_msg):
        self.clean_btn.setEnabled(True)
        self.ai_clean_btn.setEnabled(True)
        self.rewrite_btn.setEnabled(True)
        self.status_label.setText("Error")
        QMessageBox.critical(self, "AI Error", f"Processing failed:\n{error_msg}")

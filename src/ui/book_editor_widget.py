from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QListWidget, QListWidgetItem,
    QTabWidget, QTextEdit, QPushButton, QLabel, QLineEdit, QMessageBox,
    QProgressDialog, QFrame, QDialog, QMenu
)
from PySide6.QtCore import Qt, Signal, QThread, QObject, QRunnable, QThreadPool
from PySide6.QtGui import QPixmap
import threading
import traceback


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
            # Guard against None — PySide6 Signal(str).emit(None) hard-crashes
            self.signals.finished.emit(result or "")
        except BaseException as e:
            self.signals.error.emit(traceback.format_exc() or str(e))


class BookEditorWidget(QWidget):
    chapter_saved = Signal()

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self._current_book_id = None
        self._current_chapter_id = None
        self._saving = False
        self._pending: dict = {}   # chapter_id → (cleaned_content, rewritten_content)
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

        # Cover thumbnail
        cover_col = QVBoxLayout(); cover_col.setSpacing(3)
        self.cover_thumb = QLabel("No\nCover")
        self.cover_thumb.setFixedSize(56, 76)
        self.cover_thumb.setAlignment(Qt.AlignCenter)
        self.cover_thumb.setStyleSheet(
            "QLabel { background: #1a1a2e; border: 1px solid #555; "
            "color: #777; font-size: 9px; }"
        )
        cover_col.addWidget(self.cover_thumb)
        change_cover_btn = QPushButton("Cover…")
        change_cover_btn.setObjectName("secondary")
        change_cover_btn.setFixedWidth(56)
        change_cover_btn.clicked.connect(self._edit_cover)
        cover_col.addWidget(change_cover_btn)
        header_row.addLayout(cover_col)

        meta_col = QVBoxLayout(); meta_col.setSpacing(6)
        title_row = QVBoxLayout(); title_row.setSpacing(2)
        QLabel_title = QLabel("Title:")
        QLabel_title.setObjectName("subtext")
        title_row.addWidget(QLabel_title)
        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("Book title")
        self.title_edit.editingFinished.connect(self._save_book_meta)
        title_row.addWidget(self.title_edit)
        meta_col.addLayout(title_row)

        author_row = QVBoxLayout(); author_row.setSpacing(2)
        QLabel_author = QLabel("Author:")
        QLabel_author.setObjectName("subtext")
        author_row.addWidget(QLabel_author)
        self.author_edit = QLineEdit()
        self.author_edit.setPlaceholderText("Author name")
        self.author_edit.editingFinished.connect(self._save_book_meta)
        author_row.addWidget(self.author_edit)
        meta_col.addLayout(author_row)
        header_row.addLayout(meta_col, 1)

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

        ch_header_row = QHBoxLayout()
        ch_label = QLabel("Chapters")
        ch_label.setObjectName("subtext")
        ch_header_row.addWidget(ch_label)
        ch_header_row.addStretch()
        self.edit_toc_btn = QPushButton("Edit TOC…")
        self.edit_toc_btn.setObjectName("secondary")
        self.edit_toc_btn.setEnabled(False)
        self.edit_toc_btn.clicked.connect(self._open_toc_editor)
        ch_header_row.addWidget(self.edit_toc_btn)
        ch_layout.addLayout(ch_header_row)

        self.chapter_list = QListWidget()
        self.chapter_list.setSelectionMode(QListWidget.ExtendedSelection)
        self.chapter_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.chapter_list.customContextMenuRequested.connect(self._chapter_context_menu)
        self.chapter_list.itemSelectionChanged.connect(self._on_chapter_selected)
        ch_layout.addWidget(self.chapter_list)

        splitter.addWidget(ch_panel)

        # Editor tabs
        editor_panel = QWidget()
        editor_layout = QVBoxLayout(editor_panel)
        editor_layout.setContentsMargins(0, 0, 0, 0)
        editor_layout.setSpacing(6)

        # Toolbar row: rule editor + batch operations
        toolbar_row = QHBoxLayout()
        toolbar_row.setSpacing(6)

        self.edit_rules_btn = QPushButton("Edit Rules…")
        self.edit_rules_btn.setObjectName("secondary")
        self.edit_rules_btn.setEnabled(False)
        self.edit_rules_btn.clicked.connect(self._open_rule_editor)
        toolbar_row.addWidget(self.edit_rules_btn)

        vline = QFrame(); vline.setFrameShape(QFrame.VLine)
        toolbar_row.addWidget(vline)

        self.batch_rules_btn = QPushButton("Batch Rules")
        self.batch_rules_btn.setObjectName("secondary")
        self.batch_rules_btn.setEnabled(False)
        self.batch_rules_btn.clicked.connect(self._open_batch_rules)
        toolbar_row.addWidget(self.batch_rules_btn)

        self.batch_grammar_btn = QPushButton("Batch Grammar")
        self.batch_grammar_btn.setObjectName("secondary")
        self.batch_grammar_btn.setEnabled(False)
        self.batch_grammar_btn.clicked.connect(self._open_batch_grammar)
        toolbar_row.addWidget(self.batch_grammar_btn)

        self.batch_rewrite_btn = QPushButton("Batch Rewrite")
        self.batch_rewrite_btn.setObjectName("secondary")
        self.batch_rewrite_btn.setEnabled(False)
        self.batch_rewrite_btn.clicked.connect(self._open_batch_rewrite)
        toolbar_row.addWidget(self.batch_rewrite_btn)

        vline2 = QFrame(); vline2.setFrameShape(QFrame.VLine)
        toolbar_row.addWidget(vline2)

        self.rename_chapters_btn = QPushButton("Rename Chapters…")
        self.rename_chapters_btn.setObjectName("secondary")
        self.rename_chapters_btn.setEnabled(False)
        self.rename_chapters_btn.clicked.connect(self._open_rename_chapters)
        toolbar_row.addWidget(self.rename_chapters_btn)

        toolbar_row.addStretch()
        editor_layout.addLayout(toolbar_row)

        self.tabs = QTabWidget()

        # Original tab
        orig_widget = QWidget()
        orig_layout = QVBoxLayout(orig_widget)
        orig_layout.setContentsMargins(4, 4, 4, 4)
        orig_layout.setSpacing(6)

        orig_btn_row = QHBoxLayout()
        self.create_rule_btn = QPushButton("Create Rule from Selection")
        self.create_rule_btn.setObjectName("secondary")
        self.create_rule_btn.setEnabled(False)
        self.create_rule_btn.clicked.connect(self._create_rule_from_selection)
        orig_btn_row.addWidget(self.create_rule_btn)
        orig_btn_row.addStretch()
        orig_layout.addLayout(orig_btn_row)

        self.original_edit = QTextEdit()
        self.original_edit.setReadOnly(True)
        self.original_edit.setPlaceholderText("Original imported content")
        self.original_edit.selectionChanged.connect(self._on_original_selection_changed)
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
        self.cover_thumb.setPixmap(QPixmap())
        self.cover_thumb.setText("No\nCover")
        self.edit_rules_btn.setEnabled(False)
        self.batch_rules_btn.setEnabled(False)
        self.batch_grammar_btn.setEnabled(False)
        self.batch_rewrite_btn.setEnabled(False)
        self.rename_chapters_btn.setEnabled(False)
        self.create_rule_btn.setEnabled(False)
        self.edit_toc_btn.setEnabled(False)
        self._pending.clear()
        self._current_book_id = None
        self._current_chapter_id = None

    def load_book(self, book_id):
        if self._current_chapter_id and not self._saving:
            self._save_chapter(silent=True)
        self._pending.clear()
        self._current_book_id = book_id
        book = self.db.get_book(book_id)
        if not book:
            self._show_empty()
            return

        self.title_edit.setEnabled(True)
        self.author_edit.setEnabled(True)
        self.title_edit.setText(book["title"])
        self.author_edit.setText(book["author"])

        self.edit_rules_btn.setEnabled(True)
        self.batch_rules_btn.setEnabled(True)
        self.batch_grammar_btn.setEnabled(True)
        self.batch_rewrite_btn.setEnabled(True)
        self.rename_chapters_btn.setEnabled(True)
        self.edit_toc_btn.setEnabled(True)

        self._refresh_cover_thumb(book_id)
        self._load_chapter_list()

    def _load_chapter_list(self):
        current_id = self._current_chapter_id
        chapters = self.db.get_chapters(self._current_book_id)
        self.chapter_list.blockSignals(True)
        self.chapter_list.clear()
        for ch in chapters:
            label = f"Ch. {ch['chapter_number']}: {ch['title'] or 'Untitled'}"
            if ch["id"] in self._pending:
                label = "* " + label
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

        item = self.chapter_list.currentItem()
        if item is None:
            return
        self._load_chapter(item.data(Qt.UserRole))

    def _load_chapter(self, chapter_id):
        self._current_chapter_id = chapter_id
        ch = self.db.get_chapter(chapter_id)
        if not ch:
            return

        self._saving = True
        self.original_edit.setPlainText(ch["original_content"] or "")
        if chapter_id in self._pending:
            cleaned, rewritten = self._pending[chapter_id]
        else:
            cleaned  = ch["cleaned_content"]  or ""
            rewritten = ch["rewritten_content"] or ""
        self.cleaned_edit.setPlainText(cleaned)
        self.rewritten_edit.setPlainText(rewritten)
        self._saving = False

        self.save_btn.setEnabled(True)
        status_txt = f"Status: {ch['status']}"
        if chapter_id in self._pending:
            status_txt += "  (unsaved)"
        self.status_label.setText(status_txt)
        self._update_word_count()

    def _on_text_changed(self):
        if not self._saving:
            self.save_btn.setEnabled(True)
            self._update_word_count()
            if self._current_chapter_id:
                self._pending[self._current_chapter_id] = (
                    self.cleaned_edit.toPlainText(),
                    self.rewritten_edit.toPlainText(),
                )
                self._mark_chapter_dirty(self._current_chapter_id, True)

    def _mark_chapter_dirty(self, chapter_id: int, dirty: bool):
        for i in range(self.chapter_list.count()):
            item = self.chapter_list.item(i)
            if item and item.data(Qt.UserRole) == chapter_id:
                text = item.text()
                if dirty and not text.startswith("* "):
                    item.setText("* " + text)
                elif not dirty and text.startswith("* "):
                    item.setText(text[2:])
                break

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

    def _refresh_cover_thumb(self, book_id):
        from pathlib import Path
        covers_dir = Path.home() / ".ebookcleaner" / "covers"
        files = list(covers_dir.glob(f"{book_id}.*")) if covers_dir.exists() else []
        if files:
            self._set_cover_thumb(files[0].read_bytes())
        else:
            self.cover_thumb.setPixmap(QPixmap())
            self.cover_thumb.setText("No\nCover")

    def _set_cover_thumb(self, data: bytes):
        pix = QPixmap()
        if data and pix.loadFromData(data):
            self.cover_thumb.setPixmap(
                pix.scaled(56, 76, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            )
            self.cover_thumb.setText("")
        else:
            self.cover_thumb.setText("No\nCover")

    def _edit_cover(self):
        if not self._current_book_id:
            return
        from pathlib import Path
        from src.ui.cover_picker_widget import CoverPickerWidget

        dlg = QDialog(self)
        dlg.setWindowTitle("Change Cover Image")
        dlg.setMinimumWidth(520)
        dlg_layout = QVBoxLayout(dlg)
        dlg_layout.setContentsMargins(16, 16, 16, 16)
        dlg_layout.setSpacing(12)

        picker = CoverPickerWidget()

        # Pre-load existing cover file
        covers_dir = Path.home() / ".ebookcleaner" / "covers"
        files = list(covers_dir.glob(f"{self._current_book_id}.*")) if covers_dir.exists() else []
        if files:
            data = files[0].read_bytes()
            ext = files[0].suffix.lower().lstrip(".")
            picker.set_cover_data(data, f"image/{'jpeg' if ext == 'jpg' else ext}")

        # Pre-fill URL from book record
        book = self.db.get_book(self._current_book_id)
        if book and book.get("cover_url") and not files:
            picker.set_url(book["cover_url"])

        dlg_layout.addWidget(picker)

        btn_row = QHBoxLayout(); btn_row.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("secondary")
        cancel_btn.clicked.connect(dlg.reject)
        btn_row.addWidget(cancel_btn)
        save_btn = QPushButton("Save Cover")
        save_btn.clicked.connect(dlg.accept)
        btn_row.addWidget(save_btn)
        dlg_layout.addLayout(btn_row)

        if dlg.exec():
            data = picker.get_cover_data()
            mime = picker.get_cover_mime()
            self._write_cover_file(self._current_book_id, data, mime)
            # Update cover_url in DB if the field looks like a URL
            url = picker.url_edit.text().strip()
            if url.startswith("http"):
                self.db.update_book(self._current_book_id, cover_url=url)
            self._refresh_cover_thumb(self._current_book_id)

    def _write_cover_file(self, book_id, data: bytes, mime: str):
        from pathlib import Path
        covers_dir = Path.home() / ".ebookcleaner" / "covers"
        covers_dir.mkdir(parents=True, exist_ok=True)
        # Remove old cover files for this book (different extension)
        for old in covers_dir.glob(f"{book_id}.*"):
            old.unlink(missing_ok=True)
        if data:
            ext = "jpg" if "jpeg" in mime else (mime.split("/")[-1] if "/" in mime else "jpg")
            (covers_dir / f"{book_id}.{ext}").write_bytes(data)

    def _save_book_meta(self):
        if not self._current_book_id:
            return
        self.db.update_book(
            self._current_book_id,
            title=self.title_edit.text().strip(),
            author=self.author_edit.text().strip(),
        )

    def _save_chapter(self, silent=False):
        # Capture current editor state into pending first
        if self._current_chapter_id:
            self._pending[self._current_chapter_id] = (
                self.cleaned_edit.toPlainText(),
                self.rewritten_edit.toPlainText(),
            )

        if not self._pending:
            return

        self._saving = True
        current_status = "original"

        for chapter_id, (cleaned, rewritten) in list(self._pending.items()):
            status = "original"
            if rewritten.strip():
                status = "rewritten"
            elif cleaned.strip():
                status = "cleaned"

            self.db.update_chapter(
                chapter_id,
                cleaned_content=cleaned,
                rewritten_content=rewritten,
                word_count=len(cleaned.split()) if cleaned.strip() else 0,
                status=status,
            )
            self._mark_chapter_dirty(chapter_id, False)
            if chapter_id == self._current_chapter_id:
                current_status = status

        self._pending.clear()
        self._saving = False
        self.save_btn.setEnabled(False)
        self.status_label.setText(f"Status: {current_status}")
        if not silent:
            self.chapter_saved.emit()

    def _get_ai_processor(self):
        from src.build_variant import has_ai
        if not has_ai():
            QMessageBox.information(
                self, "Not Available",
                "AI features are not included in EbookCleaner Lite.\n\n"
                "Download EbookCleaner (Full) from the releases page to use AI cleaning and rewriting."
            )
            return None
        from src.ai_processor import (
            AIProcessor,
            PROVIDER_ANTHROPIC, PROVIDER_GEMINI, PROVIDER_GROQ, PROVIDER_OLLAMA,
        )
        provider = self.db.get_setting("ai_provider", PROVIDER_ANTHROPIC)

        _key_settings = {
            PROVIDER_ANTHROPIC: ("anthropic_api_key", "Anthropic", "console.anthropic.com"),
            PROVIDER_GEMINI:    ("gemini_api_key",    "Google Gemini", "aistudio.google.com"),
            PROVIDER_GROQ:      ("groq_api_key",      "Groq", "console.groq.com"),
        }

        if provider in _key_settings:
            setting_key, name, url = _key_settings[provider]
            api_key = self.db.get_setting(setting_key, "")
            if not api_key:
                QMessageBox.information(
                    self,
                    "API Key Required",
                    f"Please configure your {name} API key in Settings.\nGet it at {url}",
                )
                return None
            kwargs = {"provider": provider, "api_key": api_key}
            if provider == PROVIDER_GEMINI:
                kwargs["gemini_model"] = self.db.get_setting("gemini_model", "gemini-2.5-flash")
            return AIProcessor(**kwargs)

        if provider == PROVIDER_OLLAMA:
            host  = self.db.get_setting("ollama_host",  "http://localhost:11434")
            model = self.db.get_setting("ollama_model", "llama3.1")
            return AIProcessor(provider=provider, ollama_host=host, ollama_model=model)

        return None

    # ------------------------------------------------------------------ TOC editor

    def _open_toc_editor(self):
        if not self._current_book_id:
            return
        from src.ui.toc_editor_dialog import TOCEditorDialog
        dlg = TOCEditorDialog(self.db, self._current_book_id, parent=self)
        dlg.toc_changed.connect(self._on_toc_changed)
        dlg.exec()

    def _on_toc_changed(self):
        """Refresh the chapter list and re-select the current chapter after a TOC edit."""
        self._load_chapter_list()

    # ------------------------------------------------------------------ chapter context menu

    def _chapter_context_menu(self, pos):
        selected = self.chapter_list.selectedItems()
        if not selected:
            return

        chapter_ids = [item.data(Qt.UserRole) for item in selected]
        chapters    = [self.db.get_chapter(cid) for cid in chapter_ids]
        n           = len(chapters)
        n_fetchable = sum(1 for c in chapters if c and c.get("source_url"))

        menu = QMenu(self)

        lbl_del = f"Delete {n} Chapter{'s' if n > 1 else ''}"
        delete_action = menu.addAction(lbl_del)
        delete_action.triggered.connect(lambda: self._delete_chapters(chapter_ids))

        lbl_ref = f"Re-fetch {n} Chapter{'s' if n > 1 else ''}"
        if n_fetchable < n:
            lbl_ref += f"  ({n_fetchable} have URLs)"
        refetch_action = menu.addAction(lbl_ref)
        refetch_action.setEnabled(n_fetchable > 0)
        refetch_action.triggered.connect(lambda: self._refetch_chapters(chapters))

        menu.exec(self.chapter_list.mapToGlobal(pos))

    def _delete_chapters(self, chapter_ids: list):
        n = len(chapter_ids)
        if n == 1:
            ch = self.db.get_chapter(chapter_ids[0])
            if ch:
                ch_label = f"Ch. {ch['chapter_number']}: {ch['title'] or 'Untitled'}"
            else:
                ch_label = "this chapter"
            msg   = f"Delete \"{ch_label}\"?\nThis cannot be undone."
            title = "Delete Chapter"
        else:
            msg   = f"Permanently delete {n} chapters?\nThis cannot be undone."
            title = "Delete Chapters"

        reply = QMessageBox.question(
            self, title, msg,
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        if self._current_chapter_id in chapter_ids:
            self._current_chapter_id = None

        self.db.delete_chapters(chapter_ids)
        self._load_chapter_list()
        if not self._current_chapter_id:
            self.original_edit.clear()
            self.cleaned_edit.clear()
            self.rewritten_edit.clear()
            self.save_btn.setEnabled(False)
            self.status_label.setText("")

    def _refetch_chapters(self, chapters: list):
        from src.ui.refetch_dialog import ReFetchDialog
        dlg = ReFetchDialog(chapters, self.db, parent=self)
        dlg.chapters_updated.connect(self._on_refetch_done)
        dlg.exec()

    def _on_refetch_done(self, updated_ids: list):
        self._load_chapter_list()
        if self._current_chapter_id in updated_ids:
            self._load_chapter(self._current_chapter_id)

    def _clean_chapter(self):
        if not self._current_chapter_id:
            return
        ch = self.db.get_chapter(self._current_chapter_id)
        source = ch["original_content"] or ""
        if not source.strip():
            QMessageBox.warning(self, "No Content", "No original content to clean.")
            return
        from src.cleaner import TextCleaner
        custom_rules = self.db.get_custom_rules(self._current_book_id) if self._current_book_id else []
        result = TextCleaner(custom_rules=custom_rules).clean(source)
        self.cleaned_edit.setPlainText(result)
        self.tabs.setCurrentIndex(1)

    # ------------------------------------------------------------------ rule editor / batch

    def _on_original_selection_changed(self):
        has_sel = bool(self.original_edit.textCursor().selectedText())
        self.create_rule_btn.setEnabled(has_sel and bool(self._current_book_id))

    def _open_rule_editor(self):
        if not self._current_book_id:
            return
        ch = self.db.get_chapter(self._current_chapter_id) if self._current_chapter_id else None
        chapter_text = ch.get("original_content", "") if ch else ""
        from src.ui.rule_editor_dialog import RuleEditorDialog
        RuleEditorDialog(self.db, self._current_book_id, chapter_text, parent=self).exec()

    def _create_rule_from_selection(self):
        if not self._current_book_id:
            return
        selected = self.original_edit.textCursor().selectedText()
        if not selected:
            return
        from src.ui.rule_editor_dialog import RuleEditorDialog
        dlg = RuleEditorDialog(self.db, self._current_book_id, parent=self)
        dlg.add_rule_from_selection(selected)

    def _open_batch_rules(self):
        if not self._current_book_id:
            return
        self._save_chapter(silent=True)   # flush unsaved edits before batch overwrites DB
        from src.ui.batch_dialog import BatchDialog
        dlg = BatchDialog(self.db, self._current_book_id, "rules", parent=self)
        dlg.exec()
        if self._current_chapter_id:
            self._load_chapter(self._current_chapter_id)

    def _open_batch_grammar(self):
        if not self._current_book_id:
            return
        self._save_chapter(silent=True)
        proc = self._get_ai_processor()
        if not proc:
            return
        from src.ui.batch_dialog import BatchDialog
        dlg = BatchDialog(self.db, self._current_book_id, "grammar", ai_processor=proc, parent=self)
        dlg.exec()
        if self._current_chapter_id:
            self._load_chapter(self._current_chapter_id)

    def _open_batch_rewrite(self):
        if not self._current_book_id:
            return
        self._save_chapter(silent=True)
        proc = self._get_ai_processor()
        if not proc:
            return
        from src.ui.batch_dialog import BatchDialog
        dlg = BatchDialog(self.db, self._current_book_id, "rewrite", ai_processor=proc, parent=self)
        dlg.exec()
        if self._current_chapter_id:
            self._load_chapter(self._current_chapter_id)

    def _open_rename_chapters(self):
        if not self._current_book_id:
            return
        chapters = self.db.get_chapters(self._current_book_id)
        if not chapters:
            return
        from src.ui.rename_chapters_dialog import RenameChaptersDialog
        dlg = RenameChaptersDialog(chapters, parent=self)
        if dlg.exec() != RenameChaptersDialog.Accepted:
            return
        for ch_id, new_title in dlg.result_titles():
            self.db.update_chapter(ch_id, title=new_title)
        self._load_chapter_list()
        if self._current_chapter_id:
            self._load_chapter(self._current_chapter_id)

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

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QListWidget, QListWidgetItem, QProgressBar, QSpinBox, QDoubleSpinBox,
    QCheckBox, QMessageBox, QSplitter, QWidget, QTextEdit, QFrame,
    QGroupBox, QFormLayout
)
from PySide6.QtCore import Qt, QThread, QObject, Signal, Slot
from PySide6.QtGui import QColor, QBrush


# ------------------------------------------------------------------ workers

class _TocSignals(QObject):
    finished = Signal(dict)
    error = Signal(str)


class _TocWorker(QThread):
    def __init__(self, fetcher, url):
        super().__init__()
        self.fetcher = fetcher
        self.url = url
        self.signals = _TocSignals()

    def run(self):
        try:
            info = self.fetcher.fetch_toc(self.url)
            self.signals.finished.emit(info)
        except Exception as e:
            self.signals.error.emit(str(e))


class _FetchSignals(QObject):
    chapter_done = Signal(int, int, str)   # index, total, title
    finished = Signal(list)               # list of {title, content}
    error = Signal(str)


class _FetchWorker(QThread):
    def __init__(self, fetcher, chapter_list):
        super().__init__()
        self.fetcher = fetcher
        self.chapter_list = chapter_list
        self.signals = _FetchSignals()
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        results = []
        total = len(self.chapter_list)
        for i, ch in enumerate(self.chapter_list):
            if self._cancelled:
                break
            try:
                content = self.fetcher.fetch_chapter(ch["url"])
            except Exception as e:
                content = f"[Error fetching chapter: {e}]"
            results.append({"title": ch["title"], "content": content, "url": ch["url"]})
            self.signals.chapter_done.emit(i + 1, total, ch["title"])
        self.signals.finished.emit(results)


# ------------------------------------------------------------------ dialog

class FetchDialog(QDialog):
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self._toc_worker = None
        self._fetch_worker = None
        self._toc_info = None
        self._cover_data = None
        self._cover_mime = None
        self.imported_book_id = None

        self.setWindowTitle("Fetch from Web")
        self.setMinimumSize(820, 640)
        self.setModal(True)
        self._build_ui()

    # ------------------------------------------------------------------ UI

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        heading = QLabel("Fetch Ebook from URL")
        heading.setObjectName("heading")
        root.addWidget(heading)

        supported = QLabel(
            "Supported: Royal Road · FanFiction.net · Archive of Our Own · ScribbleHub · Any site (generic)"
        )
        supported.setObjectName("subtext")
        root.addWidget(supported)

        sep = QFrame(); sep.setFrameShape(QFrame.HLine)
        root.addWidget(sep)

        # URL row
        url_row = QHBoxLayout(); url_row.setSpacing(8)
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("https://www.royalroad.com/fiction/...")
        self.url_edit.textChanged.connect(self._on_url_changed)
        url_row.addWidget(self.url_edit, 1)
        self.load_btn = QPushButton("Load Chapter List")
        self.load_btn.setEnabled(False)
        self.load_btn.clicked.connect(self._load_toc)
        url_row.addWidget(self.load_btn)
        root.addLayout(url_row)

        # Site detection label
        site_row = QHBoxLayout()
        site_row.addWidget(QLabel("Detected site:"))
        self.site_label = QLabel("—")
        self.site_label.setObjectName("subtext")
        site_row.addWidget(self.site_label)
        site_row.addStretch()
        root.addLayout(site_row)

        # Advanced options (generic parser CSS selector)
        adv_group = QGroupBox("Advanced (Generic Parser)")
        adv_group.setCheckable(True)
        adv_group.setChecked(False)
        adv_layout = QFormLayout(adv_group)
        adv_layout.setSpacing(6)
        self.selector_edit = QLineEdit()
        self.selector_edit.setPlaceholderText("e.g. div.chapter-text  (leave blank for auto-detect)")
        adv_layout.addRow("Content CSS selector:", self.selector_edit)
        root.addWidget(adv_group)
        self._adv_group = adv_group

        sep2 = QFrame(); sep2.setFrameShape(QFrame.HLine)
        root.addWidget(sep2)

        # Splitter: chapter list | preview
        splitter = QSplitter(Qt.Horizontal)

        left = QWidget()
        ll = QVBoxLayout(left); ll.setContentsMargins(0, 0, 0, 0); ll.setSpacing(6)

        meta_form = QFormLayout(); meta_form.setSpacing(6)
        self.title_edit = QLineEdit(); self.title_edit.setPlaceholderText("Title")
        self.author_edit = QLineEdit(); self.author_edit.setPlaceholderText("Author")
        meta_form.addRow("Title:", self.title_edit)
        meta_form.addRow("Author:", self.author_edit)
        ll.addLayout(meta_form)

        ch_header_row = QHBoxLayout()
        ch_header_row.addWidget(QLabel("Chapters:"))
        self.ch_count_label = QLabel("0 found")
        self.ch_count_label.setObjectName("subtext")
        ch_header_row.addWidget(self.ch_count_label)
        ch_header_row.addStretch()
        sel_all_btn = QPushButton("All")
        sel_all_btn.setObjectName("secondary")
        sel_all_btn.setFixedWidth(40)
        sel_all_btn.clicked.connect(self._select_all)
        ch_header_row.addWidget(sel_all_btn)
        sel_none_btn = QPushButton("None")
        sel_none_btn.setObjectName("secondary")
        sel_none_btn.setFixedWidth(48)
        sel_none_btn.clicked.connect(self._select_none)
        ch_header_row.addWidget(sel_none_btn)
        ll.addLayout(ch_header_row)

        self.chapter_list = QListWidget()
        self.chapter_list.setSelectionMode(QListWidget.SingleSelection)
        self.chapter_list.itemChanged.connect(self._update_selected_count)
        ll.addWidget(self.chapter_list)

        splitter.addWidget(left)

        right = QWidget()
        rl = QVBoxLayout(right); rl.setContentsMargins(0, 0, 0, 0); rl.setSpacing(6)
        rl.addWidget(QLabel("Description:"))
        self.desc_edit = QTextEdit()
        self.desc_edit.setReadOnly(True)
        self.desc_edit.setMaximumHeight(120)
        rl.addWidget(self.desc_edit)
        rl.addWidget(QLabel("Cover image:"))
        self.cover_label = QLabel("None")
        self.cover_label.setObjectName("subtext")
        self.cover_label.setWordWrap(True)
        rl.addWidget(self.cover_label)
        rl.addStretch()
        splitter.addWidget(right)

        splitter.setSizes([520, 280])
        root.addWidget(splitter, 1)

        # Progress
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        root.addWidget(self.progress_bar)
        self.progress_label = QLabel("")
        self.progress_label.setObjectName("subtext")
        self.progress_label.setVisible(False)
        root.addWidget(self.progress_label)

        # Delay + buttons
        bottom_row = QHBoxLayout(); bottom_row.setSpacing(10)
        bottom_row.addWidget(QLabel("Delay (s):"))
        self.delay_spin = QDoubleSpinBox()
        self.delay_spin.setRange(0.5, 10.0)
        self.delay_spin.setSingleStep(0.5)
        self.delay_spin.setValue(1.5)
        self.delay_spin.setFixedWidth(70)
        bottom_row.addWidget(self.delay_spin)
        bottom_row.addStretch()
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setObjectName("secondary")
        self.cancel_btn.clicked.connect(self._cancel)
        bottom_row.addWidget(self.cancel_btn)
        self.fetch_btn = QPushButton("Fetch & Import")
        self.fetch_btn.setEnabled(False)
        self.fetch_btn.clicked.connect(self._start_fetch)
        bottom_row.addWidget(self.fetch_btn)
        root.addLayout(bottom_row)

    # ------------------------------------------------------------------ slots

    def _on_url_changed(self, text):
        text = text.strip()
        self.load_btn.setEnabled(bool(text))
        if text:
            from src.parsers.registry import detect_site_name
            try:
                site = detect_site_name(text)
                self.site_label.setText(site)
            except Exception:
                self.site_label.setText("—")

    def _load_toc(self):
        url = self.url_edit.text().strip()
        if not url:
            return
        self._set_loading(True, "Loading chapter list...")

        selector = self.selector_edit.text().strip() if self._adv_group.isChecked() else ""
        from src.web_fetcher import WebFetcher
        fetcher = WebFetcher(delay=self.delay_spin.value(), content_selector=selector)

        self._toc_worker = _TocWorker(fetcher, url)
        self._toc_worker.signals.finished.connect(self._on_toc_loaded)
        self._toc_worker.signals.error.connect(self._on_error)
        self._toc_worker.start()

    @Slot(dict)
    def _on_toc_loaded(self, info):
        self._toc_info = info
        self._set_loading(False)

        self.title_edit.setText(info.get("title") or "")
        self.author_edit.setText(info.get("author") or "")
        self.desc_edit.setPlainText(info.get("description") or "")

        cover_url = info.get("cover_url") or ""
        self.cover_label.setText(cover_url if cover_url else "None")

        self.chapter_list.blockSignals(True)
        self.chapter_list.clear()
        for ch in info.get("chapters") or []:
            item = QListWidgetItem(ch["title"])
            item.setData(Qt.UserRole, ch)
            item.setCheckState(Qt.Checked)
            self.chapter_list.addItem(item)
        self.chapter_list.blockSignals(False)

        count = self.chapter_list.count()
        self.ch_count_label.setText(f"{count} found")
        self.fetch_btn.setEnabled(count > 0)
        self._update_selected_count()

    def _update_selected_count(self):
        checked = sum(
            1 for i in range(self.chapter_list.count())
            if self.chapter_list.item(i).checkState() == Qt.Checked
        )
        total = self.chapter_list.count()
        self.ch_count_label.setText(f"{checked}/{total} selected")
        self.fetch_btn.setEnabled(checked > 0)

    def _select_all(self):
        self.chapter_list.blockSignals(True)
        for i in range(self.chapter_list.count()):
            self.chapter_list.item(i).setCheckState(Qt.Checked)
        self.chapter_list.blockSignals(False)
        self._update_selected_count()

    def _select_none(self):
        self.chapter_list.blockSignals(True)
        for i in range(self.chapter_list.count()):
            self.chapter_list.item(i).setCheckState(Qt.Unchecked)
        self.chapter_list.blockSignals(False)
        self._update_selected_count()

    def _start_fetch(self):
        selected = []
        for i in range(self.chapter_list.count()):
            item = self.chapter_list.item(i)
            if item.checkState() == Qt.Checked:
                selected.append(item.data(Qt.UserRole))

        if not selected:
            QMessageBox.warning(self, "No Chapters", "Select at least one chapter.")
            return

        self.fetch_btn.setEnabled(False)
        self.load_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setMaximum(len(selected))
        self.progress_bar.setValue(0)
        self.progress_label.setVisible(True)
        self.progress_label.setText(f"Fetching 0 / {len(selected)}...")

        url = self.url_edit.text().strip()
        selector = self.selector_edit.text().strip() if self._adv_group.isChecked() else ""
        from src.web_fetcher import WebFetcher
        fetcher = WebFetcher(delay=self.delay_spin.value(), content_selector=selector)

        # Download cover in the background if available
        cover_url = (self._toc_info or {}).get("cover_url", "")
        if cover_url:
            data, mime = fetcher.download_image(cover_url)
            self._cover_data = data
            self._cover_mime = mime or "image/jpeg"

        self._fetch_worker = _FetchWorker(fetcher, selected)
        self._fetch_worker.signals.chapter_done.connect(self._on_chapter_done)
        self._fetch_worker.signals.finished.connect(self._on_fetch_complete)
        self._fetch_worker.signals.error.connect(self._on_error)
        self._fetch_worker.start()

    @Slot(int, int, str)
    def _on_chapter_done(self, idx, total, title):
        self.progress_bar.setValue(idx)
        self.progress_label.setText(f"Fetching {idx} / {total}: {title[:60]}")

    @Slot(list)
    def _on_fetch_complete(self, results):
        self.progress_label.setText("Saving to library...")
        self._save_to_db(results)

    def _save_to_db(self, chapter_results):
        info = self._toc_info or {}
        title = self.title_edit.text().strip() or info.get("title") or "Untitled"
        author = self.author_edit.text().strip() or info.get("author") or ""
        description = info.get("description") or ""
        source_url = self.url_edit.text().strip()
        cover_url = info.get("cover_url") or ""

        book_id = self.db.add_book(title, author, description,
                                    source_url=source_url, cover_url=cover_url)
        # Save cover image file
        if self._cover_data:
            self._save_cover_file(book_id, self._cover_data, self._cover_mime)

        for i, ch in enumerate(chapter_results, start=1):
            self.db.add_chapter(book_id, i, ch["title"], ch["content"])

        version_num = self.db.get_next_version_number(book_id)
        self.db.add_version(book_id, version_num, source_url, len(chapter_results),
                             notes="Fetched from web")

        self.imported_book_id = book_id
        self._set_loading(False)
        self.accept()

    def _save_cover_file(self, book_id, data, mime):
        from pathlib import Path
        ext = "jpg" if "jpeg" in mime else mime.split("/")[-1]
        covers_dir = Path.home() / ".ebookcleaner" / "covers"
        covers_dir.mkdir(parents=True, exist_ok=True)
        path = covers_dir / f"{book_id}.{ext}"
        path.write_bytes(data)

    @Slot(str)
    def _on_error(self, msg):
        self._set_loading(False)
        QMessageBox.critical(self, "Error", msg)

    def _cancel(self):
        if self._toc_worker and self._toc_worker.isRunning():
            self._toc_worker.terminate()
        if self._fetch_worker and self._fetch_worker.isRunning():
            self._fetch_worker.cancel()
        self.reject()

    def _set_loading(self, loading: bool, msg: str = ""):
        self.load_btn.setEnabled(not loading)
        self.url_edit.setEnabled(not loading)
        if loading:
            self.progress_bar.setVisible(True)
            self.progress_bar.setRange(0, 0)  # indeterminate
            self.progress_label.setVisible(True)
            self.progress_label.setText(msg)
        else:
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setVisible(False)
            self.progress_label.setVisible(False)

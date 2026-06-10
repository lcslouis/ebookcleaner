from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QListWidget, QListWidgetItem, QProgressBar, QSpinBox, QDoubleSpinBox,
    QCheckBox, QMessageBox, QSplitter, QWidget, QTextEdit, QFrame,
    QGroupBox, QFormLayout, QComboBox
)
from PySide6.QtCore import Qt, QThread, QObject, Signal, Slot
from PySide6.QtGui import QColor, QBrush

# Worker classes live in download_manager to be shared with background tasks
from src.ui.download_manager import _FetchWorker, _FetchSignals


# ------------------------------------------------------------------ TOC worker (dialog-only)

class _TocSignals(QObject):
    finished = Signal(dict)
    error = Signal(str)
    progress = Signal(str)   # status message updates during crawl


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


class _TocCrawlWorker(QThread):
    """Builds chapter list by following next-chapter links from a seed URL."""

    def __init__(self, fetcher, toc_url, first_chapter_url):
        super().__init__()
        self.fetcher = fetcher
        self.toc_url = toc_url
        self.first_chapter_url = first_chapter_url
        self.signals = _TocSignals()

    def run(self):
        try:
            def on_progress(n):
                self.signals.progress.emit(f"Found {n} chapter{'s' if n != 1 else ''}…")

            info = self.fetcher.fetch_toc_by_crawl(
                self.toc_url, self.first_chapter_url, progress_cb=on_progress
            )
            self.signals.finished.emit(info)
        except Exception as e:
            self.signals.error.emit(str(e))


# ------------------------------------------------------------------ dialog

class FetchDialog(QDialog):
    def __init__(self, db, parent=None, update_book_id=None, download_manager=None):
        super().__init__(parent)
        self.db = db
        self._update_book_id   = update_book_id
        self._download_manager = download_manager
        self._toc_worker    = None
        self._fetch_worker  = None
        self._toc_info      = None
        self.imported_book_id = None
        self._url_locked    = False   # True only when book already has a stored source_url

        title = "Update Book from Web" if update_book_id else "Fetch from Web"
        self.setWindowTitle(title)
        self.setMinimumSize(820, 640)
        self.setModal(True)
        self._build_ui()

        if update_book_id:
            self._prefill_for_update(update_book_id)

    # ------------------------------------------------------------------ UI

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        heading = QLabel("Fetch Ebook from URL")
        heading.setObjectName("heading")
        root.addWidget(heading)

        from src.parsers.registry import list_supported_sites
        sites = list_supported_sites()
        site_names = " · ".join(s["name"] for s in sites[:12])
        if len(sites) > 12:
            site_names += f" · (+{len(sites) - 12} more)"
        supported = QLabel(f"Supported ({len(sites)} sites): {site_names}")
        supported.setObjectName("subtext")
        supported.setWordWrap(True)
        root.addWidget(supported)

        view_sites_btn = QPushButton("View All Supported Sites")
        view_sites_btn.setObjectName("secondary")
        view_sites_btn.clicked.connect(self._show_supported_sites)
        root.addWidget(view_sites_btn)

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

        # Parser detection banner — prominent, color-coded
        parser_frame = QFrame()
        parser_frame.setObjectName("parserBanner")
        parser_layout = QHBoxLayout(parser_frame)
        parser_layout.setContentsMargins(10, 6, 10, 6)
        parser_layout.setSpacing(8)
        self._parser_icon = QLabel("?")
        self._parser_icon.setFixedWidth(18)
        self._parser_icon.setAlignment(Qt.AlignCenter)
        parser_layout.addWidget(self._parser_icon)
        self._parser_label = QLabel("Enter a URL above to detect the parser")
        self._parser_label.setWordWrap(True)
        parser_layout.addWidget(self._parser_label, 1)
        root.addWidget(parser_frame)
        self._parser_frame = parser_frame

        # Parser override row
        override_row = QHBoxLayout(); override_row.setSpacing(8)
        override_lbl = QLabel("Parser override:")
        override_lbl.setObjectName("subtext")
        override_row.addWidget(override_lbl)
        self._parser_combo = QComboBox()
        self._parser_combo.setToolTip(
            "Auto-detect picks the best parser automatically.\n"
            "Override to force a specific parser if auto-detect is wrong."
        )
        self._parser_combo.addItem("Auto-detect (recommended)", "")
        from src.parsers.registry import list_parser_names
        for name, ptype in list_parser_names():
            self._parser_combo.addItem(f"{name}  [{ptype}]", name)
        self._parser_combo.currentIndexChanged.connect(self._on_parser_override_changed)
        override_row.addWidget(self._parser_combo, 1)
        root.addLayout(override_row)

        # Advanced options (generic parser CSS selector + first chapter crawl)
        adv_group = QGroupBox("Advanced Options")
        adv_group.setCheckable(True)
        adv_group.setChecked(False)
        adv_layout = QFormLayout(adv_group)
        adv_layout.setSpacing(6)
        self.selector_edit = QLineEdit()
        self.selector_edit.setPlaceholderText("e.g. div.chapter-text  (leave blank for auto-detect)")
        adv_layout.addRow("Content CSS selector:", self.selector_edit)

        self.first_chapter_edit = QLineEdit()
        self.first_chapter_edit.setPlaceholderText(
            "https://example.com/novel/chapter-1/  (leave blank to use TOC page)"
        )
        adv_layout.addRow("First chapter URL:", self.first_chapter_edit)

        first_ch_hint = QLabel(
            "Use this when the TOC page doesn't list chapters. "
            "The app will follow next-chapter links to discover all chapters automatically."
        )
        first_ch_hint.setObjectName("subtext")
        first_ch_hint.setWordWrap(True)
        adv_layout.addRow("", first_ch_hint)

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
        self.desc_edit.setMaximumHeight(100)
        rl.addWidget(self.desc_edit)
        rl.addWidget(QLabel("Cover image:"))
        from src.ui.cover_picker_widget import CoverPickerWidget
        self.cover_picker = CoverPickerWidget()
        rl.addWidget(self.cover_picker)
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

        site_logins_btn = QPushButton("Site Logins…")
        site_logins_btn.setObjectName("secondary")
        site_logins_btn.setToolTip("Manage saved login sessions for sites that require authentication")
        site_logins_btn.clicked.connect(self._open_site_logins)
        bottom_row.addWidget(site_logins_btn)

        bottom_row.addStretch()
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setObjectName("secondary")
        self.cancel_btn.clicked.connect(self._cancel)
        bottom_row.addWidget(self.cancel_btn)

        if self._download_manager:
            bg_label = "Update in Background" if self._update_book_id else "Fetch in Background"
            self.bg_btn = QPushButton(bg_label)
            self.bg_btn.setObjectName("secondary")
            self.bg_btn.setEnabled(False)
            self.bg_btn.setToolTip(
                "Start downloading and close this window — "
                "track progress in the Downloads panel"
            )
            self.bg_btn.clicked.connect(self._start_background)
            bottom_row.addWidget(self.bg_btn)
        else:
            self.bg_btn = None

        fg_label = "Fetch New Chapters" if self._update_book_id else "Fetch & Import"
        self.fetch_btn = QPushButton(fg_label)
        self.fetch_btn.setEnabled(False)
        self.fetch_btn.clicked.connect(self._start_fetch)
        bottom_row.addWidget(self.fetch_btn)
        root.addLayout(bottom_row)

    def _prefill_for_update(self, book_id):
        book = self.db.get_book(book_id)
        if not book:
            return
        url = book.get("source_url", "")
        if url:
            self.url_edit.setText(url)
            # Lock the URL — update always uses the stored source
            self.url_edit.setReadOnly(True)
            self.url_edit.setToolTip("URL locked — editing is disabled in update mode")
            self._url_locked = True
        else:
            # Book was imported from a file — let the user supply the web URL
            self.url_edit.setPlaceholderText(
                "Enter the web URL to fetch new chapters from…"
            )
            self.url_edit.setToolTip(
                "This book was imported locally. Enter the web URL to link it to a source."
            )

        existing_count = len(self.db.get_chapters(book_id))
        existing_lbl = QLabel(
            f"Updating: <b>{book.get('title','')}</b>  "
            f"({existing_count} chapter(s) already in library — only new chapters will be added)"
        )
        existing_lbl.setObjectName("subtext")
        existing_lbl.setWordWrap(True)
        # Insert just below heading (index 1)
        layout = self.layout()
        layout.insertWidget(1, existing_lbl)

    # ------------------------------------------------------------------ helpers

    def _get_cookies(self) -> list:
        """Return all stored site cookies for injection into WebFetcher."""
        return self.db.get_all_cookies_flat()

    def _open_site_logins(self):
        from src.ui.site_logins_dialog import SiteLoginsDialog
        SiteLoginsDialog(self.db, self).exec()

    # ------------------------------------------------------------------ slots

    def _on_parser_override_changed(self, _index):
        override = self._parser_combo.currentData()
        if override:
            self._update_parser_banner(override, "Override")
        elif self.url_edit.text().strip():
            self._on_url_changed(self.url_edit.text())

    def _get_parser_override(self) -> str:
        return self._parser_combo.currentData() or ""

    def _on_url_changed(self, text):
        text = text.strip()
        self.load_btn.setEnabled(bool(text))
        if text:
            from src.parsers.registry import get_parser_info
            try:
                info = get_parser_info(text)
                self._update_parser_banner(info["site_name"], info["parser_type"])
            except Exception:
                self._update_parser_banner("Unknown", "Default")
        else:
            self._parser_icon.setText("?")
            self._parser_label.setText("Enter a URL above to detect the parser")
            self._parser_frame.setStyleSheet("")

    def _update_parser_banner(self, site_name: str, parser_type: str):
        if parser_type == "Dedicated":
            icon = "✓"
            color = "#2e7d32"      # dark green
            bg = "#e8f5e9"
            border = "#a5d6a7"
            desc = "Dedicated parser — full support for this site"
        elif parser_type == "Config":
            icon = "~"
            color = "#e65100"      # dark orange
            bg = "#fff3e0"
            border = "#ffcc80"
            desc = "Config-based parser — CSS-selector driven, good support"
        elif parser_type == "Override":
            icon = "⚙"
            color = "#1565c0"      # blue
            bg = "#e3f2fd"
            border = "#90caf9"
            desc = "Manually overridden — using this parser regardless of URL"
        else:
            icon = "!"
            color = "#b71c1c"      # dark red
            bg = "#ffebee"
            border = "#ef9a9a"
            desc = "Default heuristic parser — results may vary for this site"

        self._parser_icon.setText(icon)
        self._parser_label.setText(
            f"<b>Parser:</b> {site_name} &nbsp;·&nbsp; {desc}"
        )
        self._parser_frame.setStyleSheet(
            f"QFrame#parserBanner {{ "
            f"background: {bg}; border: 1px solid {border}; border-radius: 4px; }}"
        )
        self._parser_label.setStyleSheet(f"color: {color};")
        self._parser_icon.setStyleSheet(
            f"color: {color}; font-weight: bold; font-size: 14px;"
        )

    def _load_toc(self):
        url = self.url_edit.text().strip()
        if not url:
            return

        selector = self.selector_edit.text().strip() if self._adv_group.isChecked() else ""
        first_chapter = (
            self.first_chapter_edit.text().strip()
            if self._adv_group.isChecked() else ""
        )
        from src.web_fetcher import WebFetcher
        fetcher = WebFetcher(delay=self.delay_spin.value(), content_selector=selector,
                             cookies=self._get_cookies(),
                             parser_override=self._get_parser_override())

        if first_chapter:
            self._set_loading(True, "Crawling chapters via next-chapter links…")
            self._toc_worker = _TocCrawlWorker(fetcher, url, first_chapter)
        else:
            self._set_loading(True, "Loading chapter list...")
            self._toc_worker = _TocWorker(fetcher, url)

        self._toc_worker.signals.finished.connect(self._on_toc_loaded)
        self._toc_worker.signals.error.connect(self._on_error)
        self._toc_worker.signals.progress.connect(self.progress_label.setText)
        self._toc_worker.start()

    @Slot(dict)
    def _on_toc_loaded(self, info):
        self._toc_info = info
        self._set_loading(False)

        self.title_edit.setText(info.get("title") or "")
        self.author_edit.setText(info.get("author") or "")
        self.desc_edit.setPlainText(info.get("description") or "")

        cover_url = info.get("cover_url") or ""
        self.cover_picker.set_url(cover_url, auto_download=bool(cover_url))

        # In update mode, mark already-fetched chapters so user can see what's new
        existing_urls: set = set()
        existing_count: int = 0
        if self._update_book_id:
            existing_urls = self.db.get_chapter_source_urls(self._update_book_id)
            existing_count = self.db.get_max_chapter_number(self._update_book_id)

        self.chapter_list.blockSignals(True)
        self.chapter_list.clear()
        new_count = 0
        for i, ch in enumerate(info.get("chapters") or []):
            url = ch.get("url", "")
            if existing_urls:
                # URL-based matching (precise): used for books fetched with the new code
                already_have = bool(url) and url in existing_urls
            else:
                # Position-based fallback: first existing_count chapters are already imported
                already_have = (i + 1) <= existing_count
            label = ch["title"]
            if already_have:
                label = f"[already imported] {label}"
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, ch)
            item.setCheckState(Qt.Unchecked if already_have else Qt.Checked)
            if already_have:
                item.setForeground(QColor("#888888"))
            else:
                new_count += 1
            self.chapter_list.addItem(item)
        self.chapter_list.blockSignals(False)

        count = self.chapter_list.count()
        if self._update_book_id:
            self.ch_count_label.setText(
                f"{count} found · {new_count} new"
            )
        else:
            self.ch_count_label.setText(f"{count} found")

        enabled = (new_count > 0 if self._update_book_id else count > 0)
        self.fetch_btn.setEnabled(enabled)
        if self.bg_btn:
            self.bg_btn.setEnabled(enabled)
        self._update_selected_count()

    def _update_selected_count(self):
        checked = sum(
            1 for i in range(self.chapter_list.count())
            if self.chapter_list.item(i).checkState() == Qt.Checked
        )
        total = self.chapter_list.count()
        if self._update_book_id:
            self.ch_count_label.setText(f"{checked} selected to add")
        else:
            self.ch_count_label.setText(f"{checked}/{total} selected")
        enabled = checked > 0
        self.fetch_btn.setEnabled(enabled)
        if self.bg_btn:
            self.bg_btn.setEnabled(enabled)

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
        selected = self._get_selected_chapters()
        if not selected:
            QMessageBox.warning(self, "No Chapters", "Select at least one chapter.")
            return

        self.fetch_btn.setEnabled(False)
        if self.bg_btn:
            self.bg_btn.setEnabled(False)
        self.load_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setMaximum(len(selected))
        self.progress_bar.setValue(0)
        self.progress_label.setVisible(True)
        self.progress_label.setText(f"Fetching 0 / {len(selected)}...")

        url = self.url_edit.text().strip()
        selector = self.selector_edit.text().strip() if self._adv_group.isChecked() else ""
        from src.web_fetcher import WebFetcher
        fetcher = WebFetcher(delay=self.delay_spin.value(), content_selector=selector,
                             cookies=self._get_cookies(),
                             parser_override=self._get_parser_override())

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
        if self._update_book_id:
            self._update_existing_book(results)
        else:
            self._create_new_book(results)

    # ------------------------------------------------------------------ save

    def _create_new_book(self, chapter_results):
        info = self._toc_info or {}
        title = self.title_edit.text().strip() or info.get("title") or "Untitled"
        author = self.author_edit.text().strip() or info.get("author") or ""
        description = info.get("description") or ""
        source_url = self.url_edit.text().strip()
        cover_url = info.get("cover_url") or ""

        book_id = self.db.add_book(title, author, description,
                                    source_url=source_url, cover_url=cover_url)
        cover_data = self.cover_picker.get_cover_data()
        cover_mime = self.cover_picker.get_cover_mime()
        if cover_data:
            self._save_cover_file(book_id, cover_data, cover_mime)

        for i, ch in enumerate(chapter_results, start=1):
            self.db.add_chapter(book_id, i, ch["title"], ch["content"],
                                source_url=ch.get("url", ""))

        version_num = self.db.get_next_version_number(book_id)
        self.db.add_version(book_id, version_num, source_url, len(chapter_results),
                             notes="Fetched from web")

        self.imported_book_id = book_id
        self._set_loading(False)
        self.accept()

    def _update_existing_book(self, chapter_results):
        book_id = self._update_book_id
        existing_urls = self.db.get_chapter_source_urls(book_id)

        if existing_urls:
            # URL-based dedup: precise for books with stored source URLs
            new_chapters = [
                ch for ch in chapter_results
                if not (ch.get("url", "") and ch.get("url", "") in existing_urls)
            ]
        else:
            # No stored URLs — the dialog already pre-filtered to only new chapters,
            # so everything in chapter_results is new
            new_chapters = chapter_results

        if not new_chapters:
            self._set_loading(False)
            QMessageBox.information(
                self, "No New Chapters",
                "All fetched chapters are already in the library. Nothing was added."
            )
            self.reject()
            return

        start_num = self.db.get_max_chapter_number(book_id) + 1
        for i, ch in enumerate(new_chapters):
            self.db.add_chapter(book_id, start_num + i, ch["title"], ch["content"],
                                source_url=ch.get("url", ""))

        # Persist source_url if this book didn't have one (imported from file)
        source_url = self.url_edit.text().strip()
        book = self.db.get_book(book_id)
        update_fields = {"title": book["title"]}
        if source_url and not book.get("source_url"):
            update_fields["source_url"] = source_url
        self.db.update_book(book_id, **update_fields)
        version_num = self.db.get_next_version_number(book_id)
        self.db.add_version(book_id, version_num, source_url, len(new_chapters),
                             notes=f"Update: {len(new_chapters)} new chapter(s) added")

        self.imported_book_id = book_id
        self._set_loading(False)
        QMessageBox.information(
            self, "Update Complete",
            f"{len(new_chapters)} new chapter(s) added to the library."
        )
        self.accept()

    def _start_background(self):
        """Hand off to DownloadManager and close the dialog immediately."""
        selected = self._get_selected_chapters()
        if not selected:
            QMessageBox.warning(self, "No Chapters", "Select at least one chapter.")
            return

        from src.web_fetcher import WebFetcher
        from src.ui.download_manager import DownloadTask
        selector = self.selector_edit.text().strip() if self._adv_group.isChecked() else ""
        fetcher = WebFetcher(delay=self.delay_spin.value(), content_selector=selector,
                             cookies=self._get_cookies(),
                             parser_override=self._get_parser_override())

        task = DownloadTask(
            db=self.db,
            fetcher=fetcher,
            selected_chapters=selected,
            toc_info=self._toc_info,
            update_book_id=self._update_book_id,
            cover_data=self.cover_picker.get_cover_data(),
            cover_mime=self.cover_picker.get_cover_mime(),
            custom_title=self.title_edit.text().strip(),
            custom_author=self.author_edit.text().strip(),
            source_url=self.url_edit.text().strip(),
        )
        self._download_manager.add_task(task)
        self.reject()   # close dialog; task keeps running independently

    def _get_selected_chapters(self) -> list:
        return [
            self.chapter_list.item(i).data(Qt.UserRole)
            for i in range(self.chapter_list.count())
            if self.chapter_list.item(i).checkState() == Qt.Checked
        ]

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

    def _show_supported_sites(self):
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QTableWidget, QTableWidgetItem, QHeaderView, QPushButton, QHBoxLayout
        from src.parsers.registry import list_supported_sites
        sites = list_supported_sites()

        dlg = QDialog(self)
        dlg.setWindowTitle(f"Supported Sites ({len(sites)})")
        dlg.setMinimumSize(600, 500)
        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(12, 12, 12, 12)

        table = QTableWidget(len(sites), 2)
        table.setHorizontalHeaderLabels(["Site Name", "Domains"])
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setSelectionMode(QTableWidget.SingleSelection)

        for row, site in enumerate(sites):
            table.setItem(row, 0, QTableWidgetItem(site["name"]))
            table.setItem(row, 1, QTableWidgetItem(site["domains"]))

        layout.addWidget(table)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dlg.accept)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

        dlg.exec()

    def _set_loading(self, loading: bool, msg: str = ""):
        self.load_btn.setEnabled(not loading)
        self.url_edit.setEnabled(not loading and not self._url_locked)
        if loading:
            self.progress_bar.setVisible(True)
            self.progress_bar.setRange(0, 0)  # indeterminate
            self.progress_label.setVisible(True)
            self.progress_label.setText(msg)
        else:
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setVisible(False)
            self.progress_label.setVisible(False)

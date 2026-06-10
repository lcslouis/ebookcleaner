"""
Provider Studio main window.

Workflow:
  1. Enter a TOC URL + optional chapter URL
  2. Fetch → app downloads the page and auto-suggests selectors
  3. Fill / tweak each selector field; click Test to see what it matches
  4. Fill in plugin metadata (name, domains, description, version)
  5. Save locally — installs directly to ~/.ebookcleaner/plugins/
  6. Export JSON — save the file to share / submit to the registry
  7. Submit PR — push to the ebookcleaner-plugins repo via GitHub API
     (requires a GitHub Personal Access Token)
"""
import json
import re

import requests
from bs4 import BeautifulSoup

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QLabel, QLineEdit, QPushButton, QTextEdit, QFormLayout,
    QGroupBox, QScrollArea, QStatusBar, QFileDialog, QMessageBox,
    QFrame, QTabWidget, QPlainTextEdit, QInputDialog
)
from PySide6.QtCore import Qt, QThread, QObject, Signal

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# GitHub API constants for PR submission
PLUGINS_REPO_OWNER = "lcslouis"
PLUGINS_REPO_NAME  = "ebookcleaner-plugins"


class _FetchWorker(QThread):
    finished = Signal(str, str)   # html, final_url
    error    = Signal(str)

    def __init__(self, url):
        super().__init__()
        self._url = url

    def run(self):
        try:
            resp = requests.get(self._url, headers=HEADERS, timeout=30)
            resp.raise_for_status()
            try:
                html = resp.content.decode("utf-8")
            except UnicodeDecodeError:
                html = resp.text
            self.finished.emit(html, resp.url)
        except Exception as e:
            self.error.emit(str(e))


class _SelectorField(QWidget):
    """One row: label + line-edit + Test button + result count."""

    def __init__(self, label: str, placeholder: str = "", parent=None):
        super().__init__(parent)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)
        self.edit = QLineEdit()
        self.edit.setPlaceholderText(placeholder)
        row.addWidget(self.edit, 1)
        self._test_btn = QPushButton("Test")
        self._test_btn.setObjectName("secondary")
        self._test_btn.setFixedWidth(48)
        row.addWidget(self._test_btn)
        self._result = QLabel("")
        self._result.setObjectName("subtext")
        self._result.setFixedWidth(80)
        row.addWidget(self._result)
        self._soup = None
        self._test_btn.clicked.connect(self._test)

    def set_soup(self, soup):
        self._soup = soup

    def value(self) -> str:
        return self.edit.text().strip()

    def set_value(self, v: str):
        self.edit.setText(v)

    def _test(self):
        if not self._soup:
            self._result.setText("No page")
            return
        sel = self.value()
        if not sel:
            self._result.setText("")
            return
        try:
            matches = self._soup.select(sel)
            n = len(matches)
            self._result.setText(f"{n} match{'es' if n != 1 else ''}")
            self._result.setStyleSheet(
                "color: #2e7d32;" if n > 0 else "color: #b71c1c;"
            )
        except Exception as e:
            self._result.setText("Error")
            self._result.setStyleSheet("color: #b71c1c;")


class _MultiSelectorField(QWidget):
    """Multiple selectors, one per line, all tested together."""

    def __init__(self, placeholder: str = "", parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        row = QHBoxLayout()
        self.edit = QPlainTextEdit()
        self.edit.setPlaceholderText(placeholder)
        self.edit.setFixedHeight(72)
        row.addWidget(self.edit, 1)
        btn_col = QVBoxLayout()
        self._test_btn = QPushButton("Test")
        self._test_btn.setObjectName("secondary")
        btn_col.addWidget(self._test_btn)
        btn_col.addStretch()
        row.addLayout(btn_col)
        layout.addLayout(row)
        self._result = QLabel("")
        self._result.setObjectName("subtext")
        layout.addWidget(self._result)
        self._soup = None
        self._test_btn.clicked.connect(self._test)

    def set_soup(self, soup):
        self._soup = soup

    def value(self) -> list:
        lines = [l.strip() for l in self.edit.toPlainText().splitlines()]
        return [l for l in lines if l]

    def set_value(self, items: list):
        self.edit.setPlainText("\n".join(items))

    def _test(self):
        if not self._soup:
            self._result.setText("No page fetched")
            return
        results = []
        for sel in self.value():
            try:
                matches = self._soup.select(sel)
                results.append(f"{sel}  →  {len(matches)} match(es)")
            except Exception as e:
                results.append(f"{sel}  →  ERROR: {e}")
        self._result.setText("\n".join(results) if results else "")


class StudioWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("EbookCleaner — Provider Studio")
        self.setMinimumSize(1100, 750)
        self._toc_soup    = None
        self._chapter_soup = None
        self._toc_url     = ""
        self._chapter_url = ""
        self._build_ui()
        self._build_statusbar()

    # ------------------------------------------------------------------ UI

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        # Header
        heading = QLabel("Provider Studio")
        heading.setObjectName("heading")
        root.addWidget(heading)

        sub = QLabel(
            "Create a plugin for any site. Fetch the TOC and chapter pages, "
            "define CSS selectors, then Save or Export."
        )
        sub.setObjectName("subtext")
        sub.setWordWrap(True)
        root.addWidget(sub)

        sep = QFrame(); sep.setFrameShape(QFrame.HLine)
        root.addWidget(sep)

        # URL inputs
        url_group = QGroupBox("1. Fetch pages")
        url_layout = QFormLayout(url_group)
        url_layout.setSpacing(8)

        self._toc_url_edit = QLineEdit()
        self._toc_url_edit.setPlaceholderText("https://example.com/novel/my-book/")
        url_layout.addRow("TOC / book page URL:", self._toc_url_edit)

        self._chapter_url_edit = QLineEdit()
        self._chapter_url_edit.setPlaceholderText("https://example.com/novel/my-book/chapter-1/")
        url_layout.addRow("Chapter page URL:", self._chapter_url_edit)

        fetch_row = QHBoxLayout()
        self._fetch_toc_btn = QPushButton("Fetch TOC Page")
        self._fetch_toc_btn.clicked.connect(self._fetch_toc)
        fetch_row.addWidget(self._fetch_toc_btn)
        self._fetch_ch_btn = QPushButton("Fetch Chapter Page")
        self._fetch_ch_btn.clicked.connect(self._fetch_chapter)
        fetch_row.addWidget(self._fetch_ch_btn)
        self._auto_detect_btn = QPushButton("Auto-suggest Selectors")
        self._auto_detect_btn.setObjectName("secondary")
        self._auto_detect_btn.clicked.connect(self._auto_suggest)
        fetch_row.addWidget(self._auto_detect_btn)
        fetch_row.addStretch()
        url_layout.addRow("", fetch_row)
        root.addWidget(url_group)

        # Main splitter — selectors left, preview right
        splitter = QSplitter(Qt.Horizontal)

        # ---- Left: selector fields ----
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        sel_widget = QWidget()
        sel_layout = QVBoxLayout(sel_widget)
        sel_layout.setSpacing(10)

        # Metadata
        meta_group = QGroupBox("2. Plugin metadata")
        meta_form = QFormLayout(meta_group)
        meta_form.setSpacing(6)
        self._name_edit    = QLineEdit(); self._name_edit.setPlaceholderText("My Site")
        self._id_edit      = QLineEdit(); self._id_edit.setPlaceholderText("my_site (unique id, no spaces)")
        self._domains_edit = QLineEdit(); self._domains_edit.setPlaceholderText("example.com, www.example.com")
        self._version_edit = QLineEdit(); self._version_edit.setText("1.0.0")
        self._author_edit  = QLineEdit()
        self._desc_edit    = QLineEdit(); self._desc_edit.setPlaceholderText("One-line description")
        meta_form.addRow("Name:", self._name_edit)
        meta_form.addRow("ID:", self._id_edit)
        meta_form.addRow("Domains:", self._domains_edit)
        meta_form.addRow("Version:", self._version_edit)
        meta_form.addRow("Author:", self._author_edit)
        meta_form.addRow("Description:", self._desc_edit)
        sel_layout.addWidget(meta_group)

        # TOC selectors
        toc_group = QGroupBox("3. TOC selectors (tested against TOC page)")
        toc_form  = QFormLayout(toc_group)
        toc_form.setSpacing(6)
        self._toc_sel  = _MultiSelectorField("div.chapter-list a\nul.chapters li a")
        self._title_sel = _SelectorField("", "h1.entry-title")
        self._author_sel = _SelectorField("", "a[rel='author']")
        self._desc_sel   = _SelectorField("", "div.summary__content")
        self._cover_sel  = _SelectorField("", "div.summary_image img")
        toc_form.addRow("Chapter links (one per line):", self._toc_sel)
        toc_form.addRow("Book title:", self._title_sel)
        toc_form.addRow("Author:", self._author_sel)
        toc_form.addRow("Description:", self._desc_sel)
        toc_form.addRow("Cover image:", self._cover_sel)
        sel_layout.addWidget(toc_group)

        # Content selectors
        content_group = QGroupBox("4. Content selectors (tested against chapter page)")
        content_form  = QFormLayout(content_group)
        content_form.setSpacing(6)
        self._content_sel = _MultiSelectorField("div.entry-content\ndiv.chapter-content")
        content_form.addRow("Content (one per line):", self._content_sel)
        sel_layout.addWidget(content_group)

        sel_layout.addStretch()
        scroll.setWidget(sel_widget)
        splitter.addWidget(scroll)

        # ---- Right: page preview / JSON ----
        right = QWidget()
        rl = QVBoxLayout(right); rl.setContentsMargins(0, 0, 0, 0)
        preview_tabs = QTabWidget()
        self._toc_preview   = QPlainTextEdit(); self._toc_preview.setReadOnly(True)
        self._ch_preview    = QPlainTextEdit(); self._ch_preview.setReadOnly(True)
        self._json_preview  = QPlainTextEdit(); self._json_preview.setReadOnly(True)
        preview_tabs.addTab(self._toc_preview, "TOC HTML")
        preview_tabs.addTab(self._ch_preview,  "Chapter HTML")
        preview_tabs.addTab(self._json_preview, "Plugin JSON")
        rl.addWidget(preview_tabs)
        self._preview_tabs = preview_tabs
        splitter.addWidget(right)

        splitter.setSizes([560, 520])
        root.addWidget(splitter, 1)

        # Action buttons
        action_row = QHBoxLayout()
        action_row.setSpacing(8)

        preview_btn = QPushButton("Preview JSON")
        preview_btn.setObjectName("secondary")
        preview_btn.clicked.connect(self._preview_json)
        action_row.addWidget(preview_btn)

        action_row.addStretch()

        save_local_btn = QPushButton("Save to App (Install)")
        save_local_btn.setToolTip(
            "Install this plugin to ~/.ebookcleaner/plugins/ — "
            "available immediately in the main app"
        )
        save_local_btn.clicked.connect(self._save_local)
        action_row.addWidget(save_local_btn)

        export_btn = QPushButton("Export JSON…")
        export_btn.setToolTip("Save the plugin JSON file to disk for sharing")
        export_btn.clicked.connect(self._export_json)
        action_row.addWidget(export_btn)

        submit_btn = QPushButton("Submit to Registry…")
        submit_btn.setToolTip(
            "Create a pull request on the ebookcleaner-plugins repo "
            "(requires a GitHub Personal Access Token)"
        )
        submit_btn.clicked.connect(self._submit_pr)
        action_row.addWidget(submit_btn)

        root.addLayout(action_row)

    def _build_statusbar(self):
        sb = QStatusBar()
        self.setStatusBar(sb)
        self._status = QLabel("Ready")
        sb.addWidget(self._status)

    # ------------------------------------------------------------------ fetch

    def _fetch_toc(self):
        url = self._toc_url_edit.text().strip()
        if not url:
            return
        self._status.setText("Fetching TOC page…")
        self._fetch_toc_btn.setEnabled(False)
        self._worker = _FetchWorker(url)
        self._worker.finished.connect(self._on_toc_fetched)
        self._worker.error.connect(self._on_fetch_error)
        self._worker.start()

    def _on_toc_fetched(self, html: str, final_url: str):
        self._fetch_toc_btn.setEnabled(True)
        self._toc_url = final_url
        self._toc_soup = BeautifulSoup(html, "lxml")
        self._toc_preview.setPlainText(html[:50_000])
        self._preview_tabs.setCurrentIndex(0)
        # Pass soup to all TOC selectors
        for field in (self._toc_sel, self._title_sel, self._author_sel,
                      self._desc_sel, self._cover_sel):
            field.set_soup(self._toc_soup)
        self._status.setText(f"TOC fetched — {len(html):,} chars")
        # Auto-fill domain if empty
        if not self._domains_edit.text().strip():
            from urllib.parse import urlparse
            self._domains_edit.setText(urlparse(final_url).netloc)

    def _fetch_chapter(self):
        url = self._chapter_url_edit.text().strip()
        if not url:
            return
        self._status.setText("Fetching chapter page…")
        self._fetch_ch_btn.setEnabled(False)
        self._worker2 = _FetchWorker(url)
        self._worker2.finished.connect(self._on_chapter_fetched)
        self._worker2.error.connect(self._on_fetch_error)
        self._worker2.start()

    def _on_chapter_fetched(self, html: str, final_url: str):
        self._fetch_ch_btn.setEnabled(True)
        self._chapter_url = final_url
        self._chapter_soup = BeautifulSoup(html, "lxml")
        self._ch_preview.setPlainText(html[:50_000])
        self._preview_tabs.setCurrentIndex(1)
        self._content_sel.set_soup(self._chapter_soup)
        self._status.setText(f"Chapter fetched — {len(html):,} chars")

    def _on_fetch_error(self, msg: str):
        self._fetch_toc_btn.setEnabled(True)
        self._fetch_ch_btn.setEnabled(True)
        self._status.setText(f"Fetch error: {msg}")
        QMessageBox.critical(self, "Fetch Error", msg)

    # ------------------------------------------------------------------ auto-suggest

    def _auto_suggest(self):
        """Run the WordPress/generic parser auto-detection and pre-fill fields."""
        soup = self._toc_soup or self._chapter_soup
        if not soup:
            QMessageBox.information(self, "No Page", "Fetch a page first.")
            return
        url = self._toc_url or self._chapter_url

        try:
            from src.parsers.registry import get_parser
            parser = get_parser(url, "", soup)
            self._status.setText(f"Auto-detected parser: {parser.site_name}")
        except Exception:
            pass

        # Try WordPress TOC selectors
        from src.parsers.lightnovel_wp_parser import _TOC_SELECTORS, _CONTENT_SELECTORS
        found_toc = []
        for sel in _TOC_SELECTORS:
            try:
                if soup.select(sel):
                    found_toc.append(sel)
            except Exception:
                pass
        if found_toc and not self._toc_sel.value():
            self._toc_sel.set_value(found_toc[:4])

        if self._chapter_soup:
            found_content = []
            for sel in _CONTENT_SELECTORS:
                try:
                    if self._chapter_soup.select(sel):
                        found_content.append(sel)
                except Exception:
                    pass
            if found_content and not self._content_sel.value():
                self._content_sel.set_value(found_content[:3])

        # Try to fill title/author/cover from og: meta
        if self._toc_soup:
            og_title = self._toc_soup.find("meta", property="og:title")
            if og_title and not self._name_edit.text():
                self._name_edit.setText(og_title.get("content", ""))

        self._status.setText("Auto-suggest complete — review and adjust selectors")

    # ------------------------------------------------------------------ build plugin dict

    def _build_plugin(self) -> dict:
        name    = self._name_edit.text().strip()
        pid     = self._id_edit.text().strip() or re.sub(r"\W+", "_", name.lower())
        domains = [d.strip() for d in self._domains_edit.text().split(",") if d.strip()]
        return {
            "id":                   pid,
            "name":                 name,
            "version":              self._version_edit.text().strip() or "1.0.0",
            "author":               self._author_edit.text().strip(),
            "description":          self._desc_edit.text().strip(),
            "domains":              domains,
            "toc_selectors":        self._toc_sel.value(),
            "content_selectors":    self._content_sel.value(),
            "title_selectors":      [self._title_sel.value()] if self._title_sel.value() else [],
            "author_selectors":     [self._author_sel.value()] if self._author_sel.value() else [],
            "description_selectors":[self._desc_sel.value()] if self._desc_sel.value() else [],
            "cover_selectors":      [self._cover_sel.value()] if self._cover_sel.value() else [],
        }

    def _validate(self) -> bool:
        p = self._build_plugin()
        if not p["name"]:
            QMessageBox.warning(self, "Validation", "Plugin name is required.")
            return False
        if not p["domains"]:
            QMessageBox.warning(self, "Validation", "At least one domain is required.")
            return False
        if not p["content_selectors"]:
            QMessageBox.warning(self, "Validation", "At least one content selector is required.")
            return False
        return True

    # ------------------------------------------------------------------ actions

    def _preview_json(self):
        p = self._build_plugin()
        self._json_preview.setPlainText(json.dumps(p, indent=2, ensure_ascii=False))
        self._preview_tabs.setCurrentIndex(2)

    def _save_local(self):
        if not self._validate():
            return
        from src.plugin_manager import PluginManager
        PluginManager().save_plugin(self._build_plugin())
        try:
            from src.parsers.registry import reload_plugins
            reload_plugins()
        except Exception:
            pass
        p = self._build_plugin()
        self._status.setText(f"Installed: {p['name']} — available in main app immediately")
        QMessageBox.information(
            self, "Installed",
            f"Plugin \"{p['name']}\" installed.\n"
            "It will be active in the main app immediately (no restart needed)."
        )

    def _export_json(self):
        if not self._validate():
            return
        p = self._build_plugin()
        default_name = f"{p['id']}.json"
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Plugin", default_name, "Plugin JSON (*.json)"
        )
        if not path:
            return
        with open(path, "w", encoding="utf-8") as f:
            json.dump(p, f, indent=2, ensure_ascii=False)
        self._status.setText(f"Exported: {path}")

    def _submit_pr(self):
        if not self._validate():
            return
        token, ok = QInputDialog.getText(
            self, "GitHub Token",
            "Enter your GitHub Personal Access Token\n"
            "(needs repo scope on lcslouis/ebookcleaner-plugins):",
            QLineEdit.Password if hasattr(QLineEdit, "Password") else QLineEdit.Normal,
        )
        if not ok or not token.strip():
            return
        token = token.strip()
        p = self._build_plugin()
        self._status.setText("Submitting PR…")
        self._pr_worker = _PRWorker(token, p)
        self._pr_worker.finished.connect(self._on_pr_done)
        self._pr_worker.error.connect(self._on_pr_error)
        self._pr_worker.start()

    def _on_pr_done(self, pr_url: str):
        self._status.setText(f"PR created: {pr_url}")
        QMessageBox.information(
            self, "PR Created",
            f"Pull request created successfully!\n\n{pr_url}"
        )

    def _on_pr_error(self, msg: str):
        self._status.setText(f"PR failed: {msg}")
        QMessageBox.critical(self, "PR Failed", msg)


# ------------------------------------------------------------------ PR worker

class _PRWorker(QThread):
    finished = Signal(str)
    error    = Signal(str)

    def __init__(self, token: str, plugin: dict):
        super().__init__()
        self._token  = token
        self._plugin = plugin

    def run(self):
        try:
            pr_url = self._create_pr()
            self.finished.emit(pr_url)
        except Exception as e:
            self.error.emit(str(e))

    def _create_pr(self) -> str:
        import base64
        from datetime import datetime

        headers = {
            "Authorization": f"token {self._token}",
            "Accept": "application/vnd.github.v3+json",
        }
        base = f"https://api.github.com/repos/{PLUGINS_REPO_OWNER}/{PLUGINS_REPO_NAME}"
        p = self._plugin
        pid = p["id"]

        # Get default branch SHA
        r = requests.get(f"{base}/git/ref/heads/main", headers=headers, timeout=15)
        r.raise_for_status()
        main_sha = r.json()["object"]["sha"]

        # Create branch
        branch = f"plugin/{pid}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        requests.post(f"{base}/git/refs", headers=headers, timeout=15, json={
            "ref": f"refs/heads/{branch}",
            "sha": main_sha,
        }).raise_for_status()

        # Create plugin file
        content = base64.b64encode(
            json.dumps(p, indent=2, ensure_ascii=False).encode()
        ).decode()
        requests.put(
            f"{base}/contents/plugins/{pid}.json",
            headers=headers, timeout=15,
            json={
                "message": f"Add plugin: {p['name']}",
                "content": content,
                "branch": branch,
            }
        ).raise_for_status()

        # Update registry.json
        reg_resp = requests.get(f"{base}/contents/registry.json",
                                headers=headers, timeout=15)
        if reg_resp.status_code == 200:
            reg_data = reg_resp.json()
            registry = json.loads(base64.b64decode(reg_data["content"]).decode())
            registry.setdefault("plugins", [])
            # Remove existing entry with same id, then append
            registry["plugins"] = [x for x in registry["plugins"] if x.get("id") != pid]
            registry["plugins"].append({
                "id":          pid,
                "name":        p["name"],
                "version":     p.get("version", "1.0.0"),
                "author":      p.get("author", ""),
                "description": p.get("description", ""),
                "domains":     p.get("domains", []),
                "file":        f"plugins/{pid}.json",
            })
            new_content = base64.b64encode(
                json.dumps(registry, indent=2, ensure_ascii=False).encode()
            ).decode()
            requests.put(
                f"{base}/contents/registry.json",
                headers=headers, timeout=15,
                json={
                    "message": f"Add {p['name']} to registry",
                    "content": new_content,
                    "sha": reg_data["sha"],
                    "branch": branch,
                }
            ).raise_for_status()

        # Create PR
        pr_resp = requests.post(f"{base}/pulls", headers=headers, timeout=15, json={
            "title": f"Add plugin: {p['name']}",
            "body": (
                f"### New site plugin: {p['name']}\n\n"
                f"**Domains:** {', '.join(p.get('domains', []))}\n"
                f"**Author:** {p.get('author', '')}\n"
                f"**Description:** {p.get('description', '')}\n\n"
                f"Added via Provider Studio."
            ),
            "head": branch,
            "base": "main",
        })
        pr_resp.raise_for_status()
        return pr_resp.json()["html_url"]

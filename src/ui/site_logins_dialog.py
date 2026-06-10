"""
Site Logins dialog — manage per-site cookies for authenticated scraping.

Uses a pywebview subprocess so the user can log in via a real browser
(WebView2/Edge on Windows). Cookies are saved to the DB and loaded
automatically when fetching from those sites.
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlparse

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QMessageBox, QFrame, QInputDialog
)
from PySide6.QtCore import Qt, QThread, Signal


class _LoginWatcher(QThread):
    """Waits for the login subprocess to exit, then reads the output JSON."""
    finished = Signal(list, str)   # cookies, final_url
    error    = Signal(str)

    def __init__(self, process, output_file: str):
        super().__init__()
        self._process    = process
        self._output_file = output_file

    def run(self):
        self._process.wait()
        try:
            with open(self._output_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.finished.emit(data.get("cookies", []), data.get("final_url", ""))
        except Exception as e:
            self.error.emit(str(e))
        finally:
            try:
                os.unlink(self._output_file)
            except Exception:
                pass


class SiteLoginsDialog(QDialog):
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db       = db
        self._watcher = None
        self.setWindowTitle("Site Logins")
        self.setMinimumSize(560, 420)
        self._build_ui()
        self._load()

    # ------------------------------------------------------------------ UI

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        heading = QLabel("Site Logins")
        heading.setObjectName("heading")
        layout.addWidget(heading)

        note = QLabel(
            "Save login sessions for sites that require authentication "
            "(Patreon, Scribble Hub premium, etc.).\n"
            "Click \"Login to Site…\" to open a browser, log in, then click "
            "\"✓ Done — Save Login\" to capture your session cookies."
        )
        note.setWordWrap(True)
        note.setObjectName("subtext")
        layout.addWidget(note)

        sep = QFrame(); sep.setFrameShape(QFrame.HLine)
        layout.addWidget(sep)

        self.site_list = QListWidget()
        self.site_list.setAlternatingRowColors(True)
        layout.addWidget(self.site_list, 1)

        btn_row = QHBoxLayout(); btn_row.setSpacing(8)

        self.login_btn = QPushButton("Login to Site…")
        self.login_btn.clicked.connect(self._login_to_site)
        btn_row.addWidget(self.login_btn)

        self.remove_btn = QPushButton("Remove Selected")
        self.remove_btn.setObjectName("danger")
        self.remove_btn.setEnabled(False)
        self.remove_btn.clicked.connect(self._remove_selected)
        btn_row.addWidget(self.remove_btn)

        btn_row.addStretch()

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)

        layout.addLayout(btn_row)

        self.status_lbl = QLabel("")
        self.status_lbl.setObjectName("subtext")
        layout.addWidget(self.status_lbl)

        self.site_list.itemSelectionChanged.connect(
            lambda: self.remove_btn.setEnabled(
                bool(self.site_list.selectedItems())
                and self.site_list.currentItem() is not None
                and self.site_list.currentItem().data(Qt.UserRole) is not None
            )
        )

    # ------------------------------------------------------------------ data

    def _load(self):
        self.site_list.blockSignals(True)
        self.site_list.clear()
        rows = self.db.get_all_site_cookies()
        for row in rows:
            try:
                n = len(json.loads(row["cookies_json"]) or [])
            except Exception:
                n = 0
            ts = (row.get("updated_at") or "")[:16]
            item = QListWidgetItem(
                f"{row['domain']}   ({n} cookie{'s' if n != 1 else ''})   —   {ts}"
            )
            item.setData(Qt.UserRole, row["domain"])
            self.site_list.addItem(item)
        self.site_list.blockSignals(False)

        if self.site_list.count() == 0:
            placeholder = QListWidgetItem("No site logins saved yet.")
            placeholder.setFlags(Qt.NoItemFlags)
            self.site_list.addItem(placeholder)
        self.remove_btn.setEnabled(False)

    # ------------------------------------------------------------------ actions

    def _login_to_site(self):
        url, ok = QInputDialog.getText(
            self, "Login to Site",
            "Enter the site URL (home page or login page):",
            text="https://"
        )
        if not ok or not url.strip():
            return
        url = url.strip()
        self._launch_browser(url)

    def _launch_browser(self, url: str):
        self.login_btn.setEnabled(False)
        self.status_lbl.setText(
            "Browser opening… log in, then click \"✓ Done — Save Login\"."
        )

        tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
        tmp.close()
        output_file = tmp.name

        # main.py is two directories up from this file (src/ui/ → src/ → root)
        main_py = str(Path(__file__).parent.parent.parent / "main.py")
        process = subprocess.Popen(
            [sys.executable, main_py, "--webview-login", url, output_file]
        )

        self._watcher = _LoginWatcher(process, output_file)
        self._watcher.finished.connect(self._on_login_done)
        self._watcher.error.connect(self._on_login_error)
        self._watcher.start()

    def _on_login_done(self, cookies: list, final_url: str):
        self.login_btn.setEnabled(True)

        if not cookies:
            self.status_lbl.setText(
                "No cookies were captured. Try logging in again."
            )
            return

        # Group cookies by domain, stripping leading dot
        domain_cookies: dict = {}
        for c in cookies:
            d = c.get("domain", "").lstrip(".")
            if not d and final_url:
                d = urlparse(final_url).netloc
            if d:
                domain_cookies.setdefault(d, []).append(c)

        if not domain_cookies and final_url:
            d = urlparse(final_url).netloc
            domain_cookies[d] = cookies

        for domain, clist in domain_cookies.items():
            if domain:
                self.db.set_site_cookies(domain, clist)

        total = sum(len(v) for v in domain_cookies.values())
        sites = ", ".join(domain_cookies.keys())
        self.status_lbl.setText(f"Saved {total} cookies for: {sites}")
        self._load()

    def _on_login_error(self, msg: str):
        self.login_btn.setEnabled(True)
        self.status_lbl.setText(f"Error: {msg}")

    def _remove_selected(self):
        item = self.site_list.currentItem()
        if not item:
            return
        domain = item.data(Qt.UserRole)
        if not domain:
            return
        reply = QMessageBox.question(
            self, "Remove Login",
            f"Remove saved cookies for \"{domain}\"?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self.db.delete_site_cookies(domain)
            self._load()

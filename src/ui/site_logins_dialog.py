"""
Site Logins dialog — manage per-site cookies for authenticated scraping.

Uses an embedded QtWebEngine browser (LoginBrowserDialog) so the user can
log in via a real browser inside the app.  No subprocess, no .NET runtime,
no pywebview required.  Cookies are saved to the DB and loaded automatically
when fetching from those sites.
"""
import json
from urllib.parse import urlparse

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QMessageBox, QFrame, QInputDialog
)
from PySide6.QtCore import Qt

from src.build_variant import has_webengine


class SiteLoginsDialog(QDialog):
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
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
        self._launch_browser(url.strip())

    def _launch_browser(self, url: str):
        if not has_webengine():
            QMessageBox.information(
                self, "Not Available",
                "The in-app login browser requires the Full version of EbookCleaner.\n\n"
                "Download EbookCleaner (Full) from the releases page to use Site Logins."
            )
            return
        from src.site_login import LoginBrowserDialog
        dlg = LoginBrowserDialog(url, parent=self)
        if dlg.exec() != QDialog.Accepted:
            self.status_lbl.setText("Login cancelled.")
            return

        cookies = dlg.cookies()
        final_url = dlg.final_url()

        if not cookies:
            self.status_lbl.setText("No cookies were captured. Try logging in again.")
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

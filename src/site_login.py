"""
Site login browser — uses PySide6.QtWebEngineWidgets so no pywebview,
pythonnet, or .NET runtime is required.

Opens a full browser dialog inside the app.  Cookies are captured
automatically via QWebEngineCookieStore.cookieAdded.  When the user
clicks "Done — Save Login" the dialog closes and returns the cookies.
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QProgressBar
)
from PySide6.QtCore import Qt, QUrl
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEngineProfile, QWebEnginePage


class LoginBrowserDialog(QDialog):
    """Modal browser window for logging into a site and capturing session cookies."""

    def __init__(self, url: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Site Login — EbookCleaner")
        self.resize(1100, 820)
        self.setWindowFlags(self.windowFlags() | Qt.WindowMaximizeButtonHint)

        self._captured: list = []   # list of cookie dicts as they arrive
        self._final_url: str = ""

        # Isolated profile so login cookies don't bleed into the app
        self._profile = QWebEngineProfile("ec_login_profile", self)
        self._profile.setPersistentCookiesPolicy(
            QWebEngineProfile.NoPersistentCookies
        )
        cookie_store = self._profile.cookieStore()
        cookie_store.cookieAdded.connect(self._on_cookie_added)
        cookie_store.loadAllCookies()

        page = QWebEnginePage(self._profile, self)
        self._view = QWebEngineView(self)
        self._view.setPage(page)
        self._view.loadStarted.connect(self._on_load_started)
        self._view.loadFinished.connect(self._on_load_finished)
        self._view.load(QUrl(url))

        # ---- UI layout ----
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Top hint bar
        hint_bar = QHBoxLayout()
        hint_bar.setContentsMargins(10, 6, 10, 6)
        hint = QLabel(
            "Log in to the site normally. "
            "When you're done, click <b>Done — Save Login</b>."
        )
        hint.setObjectName("subtext")
        hint_bar.addWidget(hint, 1)
        layout.addLayout(hint_bar)

        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setFixedHeight(3)
        self._progress.setTextVisible(False)
        self._progress.setStyleSheet(
            "QProgressBar { border: none; background: transparent; }"
            "QProgressBar::chunk { background: #1d4ed8; }"
        )
        self._view.loadProgress.connect(self._progress.setValue)
        layout.addWidget(self._progress)

        layout.addWidget(self._view, 1)

        # Bottom bar
        bottom = QHBoxLayout()
        bottom.setContentsMargins(10, 8, 10, 8)
        self._url_label = QLabel("")
        self._url_label.setObjectName("subtext")
        self._url_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        bottom.addWidget(self._url_label, 1)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("secondary")
        cancel_btn.clicked.connect(self.reject)
        bottom.addWidget(cancel_btn)

        done_btn = QPushButton("✓  Done — Save Login")
        done_btn.clicked.connect(self._done)
        bottom.addWidget(done_btn)
        layout.addLayout(bottom)

    # ------------------------------------------------------------------ slots

    def _on_cookie_added(self, cookie):
        self._captured.append({
            "name":   bytes(cookie.name()).decode("utf-8", errors="replace"),
            "value":  bytes(cookie.value()).decode("utf-8", errors="replace"),
            "domain": cookie.domain().lstrip("."),
            "path":   cookie.path() or "/",
            "secure": cookie.isSecure(),
        })

    def _on_load_started(self):
        self._progress.setVisible(True)

    def _on_load_finished(self, _ok):
        self._progress.setVisible(False)
        url = self._view.url().toString()
        self._url_label.setText(url)
        self._final_url = url

    def _done(self):
        self._final_url = self._view.url().toString()
        self.accept()

    # ------------------------------------------------------------------ result

    def cookies(self) -> list:
        """Return all cookies captured during the session."""
        return self._captured

    def final_url(self) -> str:
        return self._final_url

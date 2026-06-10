import sys
import os

# Allow running from repo root
sys.path.insert(0, os.path.dirname(__file__))

# Subprocess mode: main.py --webview-login <url> <output_json>
if len(sys.argv) >= 4 and sys.argv[1] == "--webview-login":
    from src.site_login import run_login_browser
    run_login_browser(sys.argv[2], sys.argv[3])
    sys.exit(0)

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from src.ui.style import STYLESHEET
from src.ui.main_window import MainWindow
from src.database import Database


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("EbookCleaner")
    app.setApplicationDisplayName("EbookCleaner")
    app.setApplicationVersion("1.0.0")
    app.setStyleSheet(STYLESHEET)

    db = Database()
    db.initialize()

    window = MainWindow(db)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()

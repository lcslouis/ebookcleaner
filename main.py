import sys
import os

# Allow running from repo root
sys.path.insert(0, os.path.dirname(__file__))

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

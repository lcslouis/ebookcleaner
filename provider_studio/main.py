"""
EbookCleaner Provider Studio — standalone tool for creating site plugins.

Run with:  python provider_studio/main.py
"""
import sys
import os

# Allow imports from the repo root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from provider_studio.studio_window import StudioWindow

# Reuse the main app stylesheet
from src.ui.style import STYLESHEET


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("EbookCleaner Provider Studio")
    app.setStyleSheet(STYLESHEET)
    window = StudioWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

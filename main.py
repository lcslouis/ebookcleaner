import sys
import os
from pathlib import Path

# Allow running from repo root
sys.path.insert(0, os.path.dirname(__file__))

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon
from PySide6.QtCore import Qt

from src.ui.style import STYLESHEET
from src.ui.main_window import MainWindow
from src.database import Database


def _resource_path(relative: str) -> Path:
    """Return the absolute path to a bundled asset.

    Works in both development (relative to repo root) and when frozen by
    PyInstaller (files land in sys._MEIPASS).
    """
    if getattr(sys, "frozen", False):
        base = Path(sys._MEIPASS)
    else:
        base = Path(__file__).parent
    return base / relative


def main():
    # Windows: set AppUserModelID so the taskbar groups the window with the
    # correct icon instead of the generic Python/Qt icon.
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                "EbookCleaner.EbookCleaner.1"
            )
        except Exception:
            pass

    app = QApplication(sys.argv)
    app.setApplicationName("EbookCleaner")
    app.setApplicationDisplayName("EbookCleaner")
    app.setApplicationVersion("1.0.0")
    app.setStyleSheet(STYLESHEET)

    icon_path = _resource_path("assets/icon.ico")
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    db = Database()
    db.initialize()

    window = MainWindow(db)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()

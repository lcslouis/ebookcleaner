STYLESHEET = """
QMainWindow, QDialog {
    background-color: #1e1e2e;
    color: #cdd6f4;
}
QWidget {
    background-color: #1e1e2e;
    color: #cdd6f4;
    font-family: "Segoe UI", Arial, sans-serif;
    font-size: 13px;
}
QListWidget {
    background-color: #181825;
    border: 1px solid #313244;
    border-radius: 4px;
    color: #cdd6f4;
    outline: none;
}
QListWidget::item {
    padding: 6px 8px;
    border-radius: 3px;
}
QListWidget::item:selected {
    background-color: #89b4fa;
    color: #1e1e2e;
}
QListWidget::item:hover:!selected {
    background-color: #313244;
}
QTextEdit, QPlainTextEdit {
    background-color: #181825;
    border: 1px solid #313244;
    border-radius: 4px;
    color: #cdd6f4;
    font-family: "Segoe UI", Arial, sans-serif;
    font-size: 13px;
    padding: 8px;
    selection-background-color: #89b4fa;
    selection-color: #1e1e2e;
}
QPushButton {
    background-color: #89b4fa;
    color: #1e1e2e;
    border: none;
    border-radius: 4px;
    padding: 6px 16px;
    font-weight: bold;
    min-height: 28px;
}
QPushButton:hover {
    background-color: #b4befe;
}
QPushButton:pressed {
    background-color: #7287fd;
}
QPushButton:disabled {
    background-color: #313244;
    color: #585b70;
}
QPushButton#danger {
    background-color: #f38ba8;
    color: #1e1e2e;
}
QPushButton#danger:hover {
    background-color: #eba0ac;
}
QPushButton#secondary {
    background-color: #313244;
    color: #cdd6f4;
}
QPushButton#secondary:hover {
    background-color: #45475a;
}
QLineEdit {
    background-color: #181825;
    border: 1px solid #313244;
    border-radius: 4px;
    color: #cdd6f4;
    padding: 5px 8px;
    min-height: 26px;
}
QLineEdit:focus {
    border-color: #89b4fa;
}
QTabWidget::pane {
    border: 1px solid #313244;
    background-color: #181825;
    border-radius: 0 4px 4px 4px;
}
QTabBar::tab {
    background-color: #181825;
    color: #6c7086;
    padding: 7px 18px;
    border: 1px solid #313244;
    border-bottom: none;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    margin-right: 2px;
}
QTabBar::tab:selected {
    background-color: #313244;
    color: #cdd6f4;
    border-color: #313244;
}
QTabBar::tab:hover:!selected {
    background-color: #2a2a3e;
    color: #cdd6f4;
}
QLabel {
    color: #cdd6f4;
    background: transparent;
}
QLabel#heading {
    font-size: 15px;
    font-weight: bold;
    color: #cdd6f4;
}
QLabel#subtext {
    color: #6c7086;
    font-size: 12px;
}
QComboBox {
    background-color: #181825;
    border: 1px solid #313244;
    border-radius: 4px;
    color: #cdd6f4;
    padding: 5px 8px;
    min-height: 26px;
}
QComboBox::drop-down {
    border: none;
    padding-right: 8px;
}
QComboBox::down-arrow {
    width: 12px;
    height: 12px;
}
QComboBox QAbstractItemView {
    background-color: #181825;
    border: 1px solid #313244;
    color: #cdd6f4;
    selection-background-color: #89b4fa;
    selection-color: #1e1e2e;
}
QCheckBox {
    color: #cdd6f4;
    spacing: 6px;
}
QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border: 2px solid #585b70;
    border-radius: 3px;
    background-color: #181825;
}
QCheckBox::indicator:checked {
    background-color: #89b4fa;
    border-color: #89b4fa;
}
QScrollBar:vertical {
    background-color: #181825;
    width: 10px;
    border: none;
    border-radius: 5px;
}
QScrollBar::handle:vertical {
    background-color: #45475a;
    border-radius: 5px;
    min-height: 20px;
}
QScrollBar::handle:vertical:hover {
    background-color: #585b70;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}
QScrollBar:horizontal {
    background-color: #181825;
    height: 10px;
    border: none;
}
QScrollBar::handle:horizontal {
    background-color: #45475a;
    border-radius: 5px;
    min-width: 20px;
}
QScrollBar::handle:horizontal:hover {
    background-color: #585b70;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0;
}
QStatusBar {
    background-color: #181825;
    color: #6c7086;
    border-top: 1px solid #313244;
}
QStatusBar QLabel {
    color: #6c7086;
}
QToolBar {
    background-color: #181825;
    border-bottom: 1px solid #313244;
    spacing: 4px;
    padding: 4px 8px;
}
QToolBar QToolButton {
    background-color: transparent;
    color: #cdd6f4;
    border: none;
    border-radius: 4px;
    padding: 4px 10px;
    font-size: 13px;
}
QToolBar QToolButton:hover {
    background-color: #313244;
}
QToolBar QToolButton:pressed {
    background-color: #45475a;
}
QSplitter::handle {
    background-color: #313244;
}
QSplitter::handle:horizontal {
    width: 1px;
}
QProgressBar {
    background-color: #181825;
    border: 1px solid #313244;
    border-radius: 4px;
    color: #cdd6f4;
    text-align: center;
}
QProgressBar::chunk {
    background-color: #89b4fa;
    border-radius: 3px;
}
QMessageBox {
    background-color: #1e1e2e;
    color: #cdd6f4;
}
QMessageBox QLabel {
    color: #cdd6f4;
}
QDialog {
    background-color: #1e1e2e;
}
QFrame[frameShape="4"],
QFrame[frameShape="5"] {
    color: #313244;
}
"""

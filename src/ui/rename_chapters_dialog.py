"""
Batch chapter title rename dialog.

Lets the user pick a format template and starting number, previews
the result, then applies it to all chapters in the book.
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QSpinBox, QListWidget, QListWidgetItem,
    QFrame, QButtonGroup, QRadioButton, QWidget, QMessageBox
)
from PySide6.QtCore import Qt


# Built-in format presets  {label: template}
PRESETS = {
    "Chapter N":        "Chapter {n}",
    "Ch. N":            "Ch. {n}",
    "Chapter N: Title": "Chapter {n}: {title}",
    "Part N":           "Part {n}",
    "Episode N":        "Episode {n}",
    "Custom…":          None,
}


class RenameChaptersDialog(QDialog):
    def __init__(self, chapters: list, parent=None):
        """
        chapters: list of dicts with keys id, chapter_number, title
        """
        super().__init__(parent)
        self.chapters = chapters
        self.setWindowTitle("Rename Chapters")
        self.setMinimumSize(520, 480)
        self._build_ui()
        self._refresh_preview()

    # ------------------------------------------------------------------ UI

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        heading = QLabel("Rename Chapters")
        heading.setObjectName("heading")
        layout.addWidget(heading)

        # --- Format section
        fmt_label = QLabel("Format:")
        fmt_label.setObjectName("subtext")
        layout.addWidget(fmt_label)

        self._radio_group = QButtonGroup(self)
        self._preset_radios = {}
        grid = QHBoxLayout()
        grid.setSpacing(12)
        for i, (label, tpl) in enumerate(PRESETS.items()):
            rb = QRadioButton(label)
            self._radio_group.addButton(rb, i)
            self._preset_radios[label] = rb
            grid.addWidget(rb)
        grid.addStretch()
        layout.addLayout(grid)

        # Custom template input (shown only when Custom… selected)
        self._custom_widget = QWidget()
        cw_layout = QHBoxLayout(self._custom_widget)
        cw_layout.setContentsMargins(0, 0, 0, 0)
        cw_layout.addWidget(QLabel("Template:"))
        self._custom_edit = QLineEdit()
        self._custom_edit.setPlaceholderText("e.g.  Arc 1 — Chapter {n}: {title}")
        self._custom_edit.textChanged.connect(self._refresh_preview)
        cw_layout.addWidget(self._custom_edit, 1)
        hint = QLabel("  {n} = number   {title} = original title")
        hint.setObjectName("subtext")
        cw_layout.addWidget(hint)
        self._custom_widget.setVisible(False)
        layout.addWidget(self._custom_widget)

        self._radio_group.idToggled.connect(self._on_preset_toggled)
        # Select first preset by default
        list(self._preset_radios.values())[0].setChecked(True)

        sep = QFrame(); sep.setFrameShape(QFrame.HLine)
        layout.addWidget(sep)

        # --- Start number
        num_row = QHBoxLayout()
        num_row.addWidget(QLabel("Start numbering at:"))
        self._start_spin = QSpinBox()
        self._start_spin.setRange(0, 9999)
        self._start_spin.setValue(1)
        self._start_spin.setFixedWidth(70)
        self._start_spin.valueChanged.connect(self._refresh_preview)
        num_row.addWidget(self._start_spin)
        num_row.addStretch()
        layout.addLayout(num_row)

        sep2 = QFrame(); sep2.setFrameShape(QFrame.HLine)
        layout.addWidget(sep2)

        # --- Preview
        preview_label = QLabel("Preview (first 10 chapters):")
        preview_label.setObjectName("subtext")
        layout.addWidget(preview_label)

        self._preview_list = QListWidget()
        self._preview_list.setAlternatingRowColors(True)
        self._preview_list.setMaximumHeight(180)
        layout.addWidget(self._preview_list)

        # --- Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)
        self._apply_btn = QPushButton(f"Rename {len(self.chapters)} Chapters")
        self._apply_btn.setDefault(True)
        self._apply_btn.clicked.connect(self._apply)
        btn_row.addWidget(self._apply_btn)
        layout.addLayout(btn_row)

    # ------------------------------------------------------------------ logic

    def _current_template(self) -> str:
        for label, rb in self._preset_radios.items():
            if rb.isChecked():
                if label == "Custom…":
                    return self._custom_edit.text().strip() or "Chapter {n}"
                return PRESETS[label]
        return "Chapter {n}"

    def _on_preset_toggled(self, btn_id, checked):
        if not checked:
            return
        labels = list(PRESETS.keys())
        is_custom = labels[btn_id] == "Custom…"
        self._custom_widget.setVisible(is_custom)
        self._refresh_preview()

    def _format_title(self, n: int, original_title: str) -> str:
        tpl = self._current_template()
        return tpl.replace("{n}", str(n)).replace("{title}", original_title or "")

    def _refresh_preview(self):
        self._preview_list.clear()
        start = self._start_spin.value()
        for i, ch in enumerate(self.chapters[:10]):
            new_title = self._format_title(start + i, ch.get("title") or "")
            item = QListWidgetItem(new_title)
            self._preview_list.addItem(item)
        if len(self.chapters) > 10:
            self._preview_list.addItem(
                QListWidgetItem(f"  … and {len(self.chapters) - 10} more")
            )

    def result_titles(self) -> list[tuple[int, str]]:
        """Returns list of (chapter_id, new_title) pairs."""
        start = self._start_spin.value()
        return [
            (ch["id"], self._format_title(start + i, ch.get("title") or ""))
            for i, ch in enumerate(self.chapters)
        ]

    def _apply(self):
        self.accept()

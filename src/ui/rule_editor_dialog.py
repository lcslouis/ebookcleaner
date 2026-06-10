"""
Per-book custom cleaning rule editor.
Rules are stored in the book_custom_rules table and applied by TextCleaner
after the built-in passes.
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QListWidget, QListWidgetItem, QCheckBox, QTextEdit, QSplitter,
    QFrame, QMessageBox, QDialogButtonBox, QFormLayout, QWidget
)
from PySide6.QtCore import Qt


# ------------------------------------------------------------------ rule edit sub-dialog

class _RuleEditDialog(QDialog):
    def __init__(self, rule: dict = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Rule" if rule else "Add Rule")
        self.setMinimumWidth(440)
        self.setModal(True)
        self._build_ui(rule or {})

    def _build_ui(self, rule: dict):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        form = QFormLayout()
        form.setSpacing(8)
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.name_edit = QLineEdit(rule.get("rule_name", ""))
        self.name_edit.setPlaceholderText("e.g. Remove site watermark")
        form.addRow("Name:", self.name_edit)

        self.pattern_edit = QLineEdit(rule.get("pattern", ""))
        self.pattern_edit.setPlaceholderText("Text or regex pattern to find")
        form.addRow("Find:", self.pattern_edit)

        self.replacement_edit = QLineEdit(rule.get("replacement", ""))
        self.replacement_edit.setPlaceholderText("Leave empty to delete matches")
        form.addRow("Replace with:", self.replacement_edit)

        self.regex_chk = QCheckBox("Treat as regular expression (regex)")
        self.regex_chk.setChecked(bool(rule.get("is_regex", False)))
        form.addRow("", self.regex_chk)

        layout.addLayout(form)

        note = QLabel(
            "Tip: Plain text match is case-sensitive. "
            "In regex mode you can use \\n for newline, ^ for line start, etc."
        )
        note.setWordWrap(True)
        note.setObjectName("subtext")
        layout.addWidget(note)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self._accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _accept(self):
        if not self.pattern_edit.text().strip():
            QMessageBox.warning(self, "Missing Pattern", "Please enter a find pattern.")
            return
        self.accept()

    def get_rule(self) -> dict:
        return {
            "rule_name":   self.name_edit.text().strip(),
            "pattern":     self.pattern_edit.text(),
            "replacement": self.replacement_edit.text(),
            "is_regex":    int(self.regex_chk.isChecked()),
        }


# ------------------------------------------------------------------ main dialog

class RuleEditorDialog(QDialog):
    def __init__(self, db, book_id: int, current_chapter_text: str = "", parent=None):
        super().__init__(parent)
        self.db                   = db
        self.book_id              = book_id
        self._chapter_text        = current_chapter_text
        book = db.get_book(book_id)
        self.setWindowTitle(f"Cleaning Rules — {book['title'] if book else 'Book'}")
        self.setMinimumSize(640, 500)
        self._build_ui()
        self._load_rules()

    # ------------------------------------------------------------------ build

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(10)

        heading = QLabel("Custom Cleaning Rules")
        heading.setObjectName("heading")
        root.addWidget(heading)

        note = QLabel(
            "These rules run after the built-in cleaning passes. "
            "They are applied in order from top to bottom."
        )
        note.setObjectName("subtext")
        note.setWordWrap(True)
        root.addWidget(note)

        sep = QFrame(); sep.setFrameShape(QFrame.HLine)
        root.addWidget(sep)

        splitter = QSplitter(Qt.Vertical)

        # --- Rule list ---
        list_widget = QWidget()
        list_layout = QVBoxLayout(list_widget)
        list_layout.setContentsMargins(0, 0, 0, 0)
        list_layout.setSpacing(6)

        self.rule_list = QListWidget()
        self.rule_list.setAlternatingRowColors(True)
        self.rule_list.itemSelectionChanged.connect(self._on_selection_changed)
        list_layout.addWidget(self.rule_list)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)

        self.add_btn = QPushButton("Add Rule")
        self.add_btn.clicked.connect(self._add_rule)
        btn_row.addWidget(self.add_btn)

        self.edit_btn = QPushButton("Edit")
        self.edit_btn.setObjectName("secondary")
        self.edit_btn.setEnabled(False)
        self.edit_btn.clicked.connect(self._edit_rule)
        btn_row.addWidget(self.edit_btn)

        self.del_btn = QPushButton("Delete")
        self.del_btn.setObjectName("danger")
        self.del_btn.setEnabled(False)
        self.del_btn.clicked.connect(self._delete_rule)
        btn_row.addWidget(self.del_btn)

        btn_row.addStretch()

        self.up_btn = QPushButton("↑")
        self.up_btn.setFixedWidth(32)
        self.up_btn.setObjectName("secondary")
        self.up_btn.setEnabled(False)
        self.up_btn.clicked.connect(lambda: self._move_rule(-1))
        btn_row.addWidget(self.up_btn)

        self.down_btn = QPushButton("↓")
        self.down_btn.setFixedWidth(32)
        self.down_btn.setObjectName("secondary")
        self.down_btn.setEnabled(False)
        self.down_btn.clicked.connect(lambda: self._move_rule(1))
        btn_row.addWidget(self.down_btn)

        list_layout.addLayout(btn_row)
        splitter.addWidget(list_widget)

        # --- Preview pane ---
        preview_widget = QWidget()
        preview_layout = QVBoxLayout(preview_widget)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        preview_layout.setSpacing(4)

        preview_header = QHBoxLayout()
        preview_header.addWidget(QLabel("Preview on current chapter:"))
        preview_header.addStretch()
        self.test_btn = QPushButton("Run Preview")
        self.test_btn.setObjectName("secondary")
        self.test_btn.clicked.connect(self._run_preview)
        self.test_btn.setEnabled(bool(self._chapter_text))
        preview_header.addWidget(self.test_btn)
        preview_layout.addLayout(preview_header)

        self.preview_edit = QTextEdit()
        self.preview_edit.setReadOnly(True)
        self.preview_edit.setPlaceholderText(
            "Click 'Run Preview' to see the effect of all enabled rules on the current chapter."
        )
        preview_layout.addWidget(self.preview_edit)
        splitter.addWidget(preview_widget)

        splitter.setSizes([280, 200])
        root.addWidget(splitter, 1)

        # --- Close button ---
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        close_row = QHBoxLayout()
        close_row.addStretch()
        close_row.addWidget(close_btn)
        root.addLayout(close_row)

    # ------------------------------------------------------------------ load

    def _load_rules(self):
        self._rules = self.db.get_custom_rules(self.book_id)
        self._refresh_list()

    def _refresh_list(self, select_index: int = -1):
        self.rule_list.blockSignals(True)
        self.rule_list.clear()
        for rule in self._rules:
            label = rule.get("rule_name") or rule["pattern"][:50]
            type_tag = "[regex]" if rule.get("is_regex") else "[text]"
            item = QListWidgetItem(f"{type_tag}  {label}")
            item.setData(Qt.UserRole, rule["id"])
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if rule.get("enabled", 1) else Qt.Unchecked)
            self.rule_list.addItem(item)
        self.rule_list.blockSignals(False)
        if 0 <= select_index < self.rule_list.count():
            self.rule_list.setCurrentRow(select_index)
        self.rule_list.itemChanged.connect(self._on_item_check_changed)
        self._on_selection_changed()

    # ------------------------------------------------------------------ slots

    def _on_selection_changed(self):
        has = self.rule_list.currentRow() >= 0
        row = self.rule_list.currentRow()
        self.edit_btn.setEnabled(has)
        self.del_btn.setEnabled(has)
        self.up_btn.setEnabled(has and row > 0)
        self.down_btn.setEnabled(has and row < self.rule_list.count() - 1)

    def _on_item_check_changed(self, item: QListWidgetItem):
        rule_id = item.data(Qt.UserRole)
        enabled = int(item.checkState() == Qt.Checked)
        self.db.update_custom_rule(rule_id, enabled=enabled)
        for rule in self._rules:
            if rule["id"] == rule_id:
                rule["enabled"] = enabled
                break

    def _add_rule(self):
        dlg = _RuleEditDialog(parent=self)
        if dlg.exec() != QDialog.Accepted:
            return
        data = dlg.get_rule()
        self.db.add_custom_rule(
            self.book_id, data["rule_name"], data["pattern"],
            data["replacement"], bool(data["is_regex"])
        )
        self._load_rules()

    def _edit_rule(self):
        row = self.rule_list.currentRow()
        if row < 0:
            return
        rule = self._rules[row]
        dlg = _RuleEditDialog(rule=rule, parent=self)
        if dlg.exec() != QDialog.Accepted:
            return
        data = dlg.get_rule()
        self.db.update_custom_rule(
            rule["id"],
            rule_name=data["rule_name"],
            pattern=data["pattern"],
            replacement=data["replacement"],
            is_regex=data["is_regex"],
        )
        self._load_rules()

    def _delete_rule(self):
        row = self.rule_list.currentRow()
        if row < 0:
            return
        rule = self._rules[row]
        name = rule.get("rule_name") or rule["pattern"][:40]
        reply = QMessageBox.question(
            self, "Delete Rule",
            f"Delete rule \"{name}\"?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return
        self.db.delete_custom_rule(rule["id"])
        self._load_rules()

    def _move_rule(self, direction: int):
        row = self.rule_list.currentRow()
        new_row = row + direction
        if new_row < 0 or new_row >= len(self._rules):
            return
        self._rules[row], self._rules[new_row] = self._rules[new_row], self._rules[row]
        for i, r in enumerate(self._rules):
            self.db.update_custom_rule(r["id"], sort_order=i)
        self._load_rules()
        self.rule_list.setCurrentRow(new_row)

    def _run_preview(self):
        from src.cleaner import TextCleaner
        rules = self.db.get_custom_rules(self.book_id)
        result = TextCleaner(custom_rules=rules).clean(self._chapter_text)
        self.preview_edit.setPlainText(result)

    # ------------------------------------------------------------------ public helper

    def add_rule_from_selection(self, selected_text: str):
        """Pre-populate the Add Rule dialog with a text selection."""
        rule = {
            "rule_name":   f"Remove: {selected_text[:30]}",
            "pattern":     selected_text,
            "replacement": "",
            "is_regex":    0,
        }
        dlg = _RuleEditDialog(rule=rule, parent=self)
        if dlg.exec() != QDialog.Accepted:
            return
        data = dlg.get_rule()
        self.db.add_custom_rule(
            self.book_id, data["rule_name"], data["pattern"],
            data["replacement"], bool(data["is_regex"])
        )
        self._load_rules()

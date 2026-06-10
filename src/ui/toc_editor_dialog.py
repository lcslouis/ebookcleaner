"""
TOC (Table of Contents) Editor.

Lets the user reorder chapters (Move Up / Move Down), rename chapter
titles inline, and delete chapters.  Changes are written to the database
only when the user clicks Save.
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QLabel, QLineEdit, QMessageBox, QFrame
)
from PySide6.QtCore import Qt, Signal


class TOCEditorDialog(QDialog):
    toc_changed = Signal()  # emitted after a successful save

    def __init__(self, db, book_id: int, parent=None):
        super().__init__(parent)
        self.db = db
        self.book_id = book_id
        self.setWindowTitle("Edit Table of Contents")
        self.setMinimumSize(540, 500)
        self._build_ui()
        self._load()

    # ------------------------------------------------------------------ UI

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        hint = QLabel(
            "Drag, or use Move Up / Move Down to reorder. "
            "Double-click a title to rename it."
        )
        hint.setObjectName("subtext")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        # List + side buttons
        list_row = QHBoxLayout()
        list_row.setSpacing(8)

        self.list_widget = QListWidget()
        self.list_widget.setDragDropMode(QListWidget.InternalMove)
        self.list_widget.setDefaultDropAction(Qt.MoveAction)
        self.list_widget.setSelectionMode(QListWidget.SingleSelection)
        self.list_widget.itemDoubleClicked.connect(self._inline_rename)
        self.list_widget.currentRowChanged.connect(self._update_buttons)
        list_row.addWidget(self.list_widget, 1)

        btn_col = QVBoxLayout()
        btn_col.setSpacing(6)
        btn_col.setAlignment(Qt.AlignTop)

        self.up_btn = QPushButton("▲  Move Up")
        self.up_btn.setObjectName("secondary")
        self.up_btn.setEnabled(False)
        self.up_btn.clicked.connect(self._move_up)
        btn_col.addWidget(self.up_btn)

        self.down_btn = QPushButton("▼  Move Down")
        self.down_btn.setObjectName("secondary")
        self.down_btn.setEnabled(False)
        self.down_btn.clicked.connect(self._move_down)
        btn_col.addWidget(self.down_btn)

        sep = QFrame(); sep.setFrameShape(QFrame.HLine)
        btn_col.addWidget(sep)

        self.rename_btn = QPushButton("Rename…")
        self.rename_btn.setObjectName("secondary")
        self.rename_btn.setEnabled(False)
        self.rename_btn.clicked.connect(lambda: self._inline_rename(self.list_widget.currentItem()))
        btn_col.addWidget(self.rename_btn)

        self.delete_btn = QPushButton("Delete")
        self.delete_btn.setObjectName("secondary")
        self.delete_btn.setEnabled(False)
        self.delete_btn.clicked.connect(self._delete_selected)
        btn_col.addWidget(self.delete_btn)

        list_row.addLayout(btn_col)
        layout.addLayout(list_row)

        # Chapter count label
        self.count_label = QLabel("")
        self.count_label.setObjectName("subtext")
        layout.addWidget(self.count_label)

        sep2 = QFrame(); sep2.setFrameShape(QFrame.HLine)
        layout.addWidget(sep2)

        # Bottom buttons
        bottom_row = QHBoxLayout()
        bottom_row.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("secondary")
        cancel_btn.clicked.connect(self.reject)
        bottom_row.addWidget(cancel_btn)

        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self._save)
        bottom_row.addWidget(save_btn)

        layout.addLayout(bottom_row)

    # ------------------------------------------------------------------ data

    def _load(self):
        self.list_widget.clear()
        chapters = self.db.get_chapters(self.book_id)
        for ch in chapters:
            item = QListWidgetItem(ch["title"] or f"Chapter {ch['chapter_number']}")
            item.setData(Qt.UserRole, ch["id"])
            item.setFlags(item.flags() | Qt.ItemIsEditable)
            self.list_widget.addItem(item)
        self._refresh_count()

    def _refresh_count(self):
        n = self.list_widget.count()
        self.count_label.setText(f"{n} chapter{'s' if n != 1 else ''}")

    # ------------------------------------------------------------------ actions

    def _update_buttons(self, row: int = -1):
        row = self.list_widget.currentRow()
        n = self.list_widget.count()
        has = row >= 0
        self.up_btn.setEnabled(has and row > 0)
        self.down_btn.setEnabled(has and row < n - 1)
        self.rename_btn.setEnabled(has)
        self.delete_btn.setEnabled(has)

    def _move_up(self):
        row = self.list_widget.currentRow()
        if row <= 0:
            return
        item = self.list_widget.takeItem(row)
        self.list_widget.insertItem(row - 1, item)
        self.list_widget.setCurrentRow(row - 1)

    def _move_down(self):
        row = self.list_widget.currentRow()
        if row < 0 or row >= self.list_widget.count() - 1:
            return
        item = self.list_widget.takeItem(row)
        self.list_widget.insertItem(row + 1, item)
        self.list_widget.setCurrentRow(row + 1)

    def _inline_rename(self, item):
        if item is None:
            return
        self.list_widget.editItem(item)

    def _delete_selected(self):
        row = self.list_widget.currentRow()
        item = self.list_widget.item(row)
        if item is None:
            return
        title = item.text()
        reply = QMessageBox.question(
            self,
            "Delete Chapter",
            f"Delete \"{title}\"?\nThis cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        chapter_id = item.data(Qt.UserRole)
        self.db.delete_chapters([chapter_id])
        self.list_widget.takeItem(row)
        self._refresh_count()
        self._update_buttons()

    def _save(self):
        # Collect current order and titles from the list widget
        n = self.list_widget.count()
        chapter_ids = []
        titles = {}
        for i in range(n):
            item = self.list_widget.item(i)
            cid = item.data(Qt.UserRole)
            chapter_ids.append(cid)
            titles[cid] = item.text().strip()

        # Write new order to DB
        self.db.reorder_chapters(self.book_id, chapter_ids)

        # Write any renamed titles
        for cid, title in titles.items():
            if title:
                self.db.update_chapter(cid, title=title)

        self.toc_changed.emit()
        self.accept()

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QSplitter, QWidget, QCheckBox,
    QFrame, QMessageBox
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QBrush


NEW_COLOR = QColor("#a6e3a1")       # green
UPDATED_COLOR = QColor("#f9e2af")   # yellow
UNCHANGED_COLOR = QColor("#585b70") # gray


class MergeDialog(QDialog):
    def __init__(self, book_id, analysis, db, parent=None):
        super().__init__(parent)
        self.book_id = book_id
        self.analysis = analysis
        self.db = db
        self.setWindowTitle("Merge Chapters")
        self.setMinimumSize(700, 500)
        self.setModal(True)
        self._build_ui()
        self._populate()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        heading = QLabel("Merge New Version")
        heading.setObjectName("heading")
        layout.addWidget(heading)

        legend_row = QHBoxLayout()
        for color, label in [
            (NEW_COLOR, "New chapters"),
            (UPDATED_COLOR, "Modified chapters"),
            (UNCHANGED_COLOR, "Unchanged"),
        ]:
            dot = QLabel("  ")
            dot.setStyleSheet(f"background-color: {color.name()}; border-radius: 3px;")
            dot.setFixedSize(14, 14)
            legend_row.addWidget(dot)
            legend_row.addWidget(QLabel(label))
            legend_row.addSpacing(12)
        legend_row.addStretch()
        layout.addLayout(legend_row)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        layout.addWidget(sep)

        splitter = QSplitter(Qt.Horizontal)

        # New/updated chapters (selectable)
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.setSpacing(4)
        ll.addWidget(QLabel("Incoming Chapters"))
        self.incoming_list = QListWidget()
        ll.addWidget(self.incoming_list)
        splitter.addWidget(left)

        # Existing chapters
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(4)
        rl.addWidget(QLabel("Existing Chapters"))
        self.existing_list = QListWidget()
        self.existing_list.setEnabled(False)
        rl.addWidget(self.existing_list)
        splitter.addWidget(right)

        layout.addWidget(splitter, 1)

        self.include_updated_cb = QCheckBox("Also import modified chapters (replace existing content)")
        self.include_updated_cb.setChecked(True)
        layout.addWidget(self.include_updated_cb)

        stats = (
            f"{len(self.analysis['new'])} new  •  "
            f"{len(self.analysis['updated'])} modified  •  "
            f"{len(self.analysis['unchanged'])} unchanged"
        )
        self.stats_label = QLabel(stats)
        self.stats_label.setObjectName("subtext")
        layout.addWidget(self.stats_label)

        btn_row = QHBoxLayout()
        btn_row.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("secondary")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        self.merge_btn = QPushButton("Merge")
        self.merge_btn.clicked.connect(self._do_merge)
        btn_row.addWidget(self.merge_btn)

        layout.addLayout(btn_row)

    def _populate(self):
        for ch in self.analysis["new"]:
            item = QListWidgetItem(f"[NEW] Ch.{ch['number']}: {ch['title']}")
            item.setForeground(QBrush(NEW_COLOR))
            item.setData(Qt.UserRole, ("new", ch))
            self.incoming_list.addItem(item)

        for ch in self.analysis["updated"]:
            item = QListWidgetItem(f"[MODIFIED] Ch.{ch['number']}: {ch['title']}")
            item.setForeground(QBrush(UPDATED_COLOR))
            item.setData(Qt.UserRole, ("updated", ch))
            self.incoming_list.addItem(item)

        for ch in self.analysis["unchanged"]:
            item = QListWidgetItem(f"[UNCHANGED] Ch.{ch['number']}: {ch['title']}")
            item.setForeground(QBrush(UNCHANGED_COLOR))
            item.setData(Qt.UserRole, ("unchanged", ch))
            self.incoming_list.addItem(item)

        # Existing chapters
        existing = self.db.get_chapters(self.book_id)
        for ch in existing:
            item = QListWidgetItem(f"Ch.{ch['chapter_number']}: {ch['title']}")
            self.existing_list.addItem(item)

        if not self.analysis["new"] and not self.analysis["updated"]:
            self.merge_btn.setEnabled(False)
            self.merge_btn.setText("Nothing to Merge")

    def _do_merge(self):
        from src.merger import ChapterMerger
        include_updated = self.include_updated_cb.isChecked()
        merger = ChapterMerger()
        try:
            merger.merge(self.book_id, self.analysis, self.db, include_updated)
        except Exception as e:
            QMessageBox.critical(self, "Merge Error", str(e))
            return

        n_new = len(self.analysis["new"])
        n_updated = len(self.analysis["updated"]) if include_updated else 0
        QMessageBox.information(
            self,
            "Merge Complete",
            f"Added {n_new} new chapter(s) and updated {n_updated} existing chapter(s).",
        )
        self.accept()

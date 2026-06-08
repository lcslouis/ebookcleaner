from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QLineEdit, QLabel, QMessageBox
)
from PySide6.QtCore import Signal, Qt


class BookListWidget(QWidget):
    book_selected = Signal(int)
    import_requested = Signal()
    book_deleted = Signal(int)

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self._book_ids = []
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        header = QLabel("Library")
        header.setObjectName("heading")
        layout.addWidget(header)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search books...")
        self.search_edit.textChanged.connect(self._filter)
        layout.addWidget(self.search_edit)

        self.list_widget = QListWidget()
        self.list_widget.setAlternatingRowColors(False)
        self.list_widget.itemSelectionChanged.connect(self._on_selection_changed)
        layout.addWidget(self.list_widget)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)

        import_btn = QPushButton("+ Import")
        import_btn.clicked.connect(self.import_requested.emit)
        btn_row.addWidget(import_btn)

        self.delete_btn = QPushButton("Delete")
        self.delete_btn.setObjectName("danger")
        self.delete_btn.setEnabled(False)
        self.delete_btn.clicked.connect(self._delete_selected)
        btn_row.addWidget(self.delete_btn)

        layout.addLayout(btn_row)

    def refresh(self):
        current_id = self._current_book_id()
        books = self.db.get_all_books()
        self._all_books = books
        self._populate(books, current_id)

    def _populate(self, books, select_id=None):
        self.list_widget.blockSignals(True)
        self.list_widget.clear()
        self._book_ids = []
        for book in books:
            title = book["title"] or "Untitled"
            author = book["author"] or "Unknown Author"
            item = QListWidgetItem(f"{title}\n{author}")
            item.setData(Qt.UserRole, book["id"])
            self.list_widget.addItem(item)
            self._book_ids.append(book["id"])
        self.list_widget.blockSignals(False)

        if select_id is not None:
            for i in range(self.list_widget.count()):
                if self.list_widget.item(i).data(Qt.UserRole) == select_id:
                    self.list_widget.setCurrentRow(i)
                    break

    def _filter(self, text):
        q = text.strip().lower()
        if not q:
            filtered = self._all_books
        else:
            filtered = [
                b for b in self._all_books
                if q in (b["title"] or "").lower() or q in (b["author"] or "").lower()
            ]
        self._populate(filtered)

    def _on_selection_changed(self):
        items = self.list_widget.selectedItems()
        if items:
            book_id = items[0].data(Qt.UserRole)
            self.delete_btn.setEnabled(True)
            self.book_selected.emit(book_id)
        else:
            self.delete_btn.setEnabled(False)

    def _current_book_id(self):
        items = self.list_widget.selectedItems()
        if items:
            return items[0].data(Qt.UserRole)
        return None

    def _delete_selected(self):
        book_id = self._current_book_id()
        if book_id is None:
            return
        book = self.db.get_book(book_id)
        title = book["title"] if book else "this book"
        reply = QMessageBox.question(
            self,
            "Delete Book",
            f"Delete \"{title}\" and all its chapters? This cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self.db.delete_book(book_id)
            self.book_deleted.emit(book_id)
            self.refresh()

    def select_book(self, book_id):
        for i in range(self.list_widget.count()):
            if self.list_widget.item(i).data(Qt.UserRole) == book_id:
                self.list_widget.setCurrentRow(i)
                break

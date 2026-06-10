"""
Plugin Manager dialog — browse, install, and remove community site plugins.
"""
import json

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QFrame,
    QMessageBox, QTabWidget, QWidget, QFileDialog, QAbstractItemView
)
from PySide6.QtCore import Qt, QThread, QObject, Signal
from PySide6.QtGui import QColor


class _RegistryWorker(QThread):
    finished = Signal(list)
    error    = Signal(str)

    def __init__(self, pm):
        super().__init__()
        self._pm = pm

    def run(self):
        try:
            self.finished.emit(self._pm.fetch_registry())
        except Exception as e:
            self.error.emit(str(e))


class _InstallWorker(QThread):
    finished = Signal()
    error    = Signal(str)

    def __init__(self, pm, meta):
        super().__init__()
        self._pm   = pm
        self._meta = meta

    def run(self):
        try:
            self._pm.install(self._meta)
            self.finished.emit()
        except Exception as e:
            self.error.emit(str(e))


class _BatchInstallWorker(QThread):
    progress = Signal(str)   # name of each plugin as it finishes
    finished = Signal(int)   # total installed count
    error    = Signal(str)

    def __init__(self, pm, metas):
        super().__init__()
        self._pm    = pm
        self._metas = metas

    def run(self):
        count = 0
        for meta in self._metas:
            try:
                self._pm.install(meta)
                count += 1
                self.progress.emit(meta.get("name", meta.get("id", "")))
            except Exception as e:
                self.error.emit(f"{meta.get('name', '')}: {e}")
        self.finished.emit(count)


class PluginManagerDialog(QDialog):
    plugins_changed = Signal()   # emitted when install/uninstall happens

    def __init__(self, parent=None, db=None):
        super().__init__(parent)
        from src.plugin_manager import PluginManager
        self._pm = PluginManager()
        self._db = db
        self._registry = []
        self.setWindowTitle("Plugin Manager")
        self.setMinimumSize(780, 540)
        self._build_ui()
        self._load_installed()

    # ------------------------------------------------------------------ UI

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        heading = QLabel("Plugin Manager")
        heading.setObjectName("heading")
        layout.addWidget(heading)

        note = QLabel(
            "Plugins add support for new sites without updating the app. "
            "They are stored in <i>~/.ebookcleaner/plugins/</i> and loaded on startup."
        )
        note.setWordWrap(True)
        note.setObjectName("subtext")
        layout.addWidget(note)

        sep = QFrame(); sep.setFrameShape(QFrame.HLine)
        layout.addWidget(sep)

        tabs = QTabWidget()
        layout.addWidget(tabs, 1)

        # ---- Installed tab ----
        installed_widget = QWidget()
        il = QVBoxLayout(installed_widget)
        il.setContentsMargins(0, 8, 0, 0)
        il.setSpacing(8)

        self._installed_table = self._make_table(["Name", "Domains", "Version", "Author"])
        self._installed_table.itemSelectionChanged.connect(self._on_installed_selection)
        il.addWidget(self._installed_table)

        inst_btn_row = QHBoxLayout()
        self._import_btn = QPushButton("Install from File…")
        self._import_btn.setObjectName("secondary")
        self._import_btn.clicked.connect(self._import_from_file)
        inst_btn_row.addWidget(self._import_btn)
        inst_btn_row.addStretch()
        self._uninstall_btn = QPushButton("Remove Selected")
        self._uninstall_btn.setObjectName("danger")
        self._uninstall_btn.setEnabled(False)
        self._uninstall_btn.clicked.connect(self._uninstall_selected)
        inst_btn_row.addWidget(self._uninstall_btn)
        il.addLayout(inst_btn_row)

        tabs.addTab(installed_widget, "Installed")

        # ---- Available tab ----
        avail_widget = QWidget()
        al = QVBoxLayout(avail_widget)
        al.setContentsMargins(0, 8, 0, 0)
        al.setSpacing(8)

        self._avail_table = self._make_table(["Name", "Domains", "Version", "Author", "Status"])
        al.addWidget(self._avail_table)

        avail_btn_row = QHBoxLayout()
        self._refresh_btn = QPushButton("Refresh Registry")
        self._refresh_btn.clicked.connect(self._refresh_registry)
        avail_btn_row.addWidget(self._refresh_btn)

        self._recommend_btn = QPushButton("Get Plugins for My Library")
        self._recommend_btn.setObjectName("secondary")
        self._recommend_btn.setEnabled(self._db is not None)
        self._recommend_btn.setToolTip(
            "Find plugins for sites you have books from and install them in one click."
        )
        self._recommend_btn.clicked.connect(self._get_recommended)
        avail_btn_row.addWidget(self._recommend_btn)

        avail_btn_row.addStretch()
        self._install_btn = QPushButton("Install Selected")
        self._install_btn.setEnabled(False)
        self._install_btn.clicked.connect(self._install_selected)
        avail_btn_row.addWidget(self._install_btn)
        al.addLayout(avail_btn_row)

        tabs.addTab(avail_widget, "Available")

        self._tabs = tabs
        self._tabs.currentChanged.connect(self._on_tab_changed)

        # Status bar
        self._status_lbl = QLabel("")
        self._status_lbl.setObjectName("subtext")
        layout.addWidget(self._status_lbl)

        # Close button
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

    def _make_table(self, headers: list) -> QTableWidget:
        t = QTableWidget(0, len(headers))
        t.setHorizontalHeaderLabels(headers)
        t.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        t.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        t.verticalHeader().setVisible(False)
        t.setEditTriggers(QTableWidget.NoEditTriggers)
        t.setSelectionBehavior(QAbstractItemView.SelectRows)
        t.setSelectionMode(QAbstractItemView.SingleSelection)
        t.setAlternatingRowColors(True)
        return t

    # ------------------------------------------------------------------ data

    def _load_installed(self):
        meta = self._pm.get_installed_meta()
        t = self._installed_table
        t.setRowCount(0)
        for m in meta:
            row = t.rowCount(); t.insertRow(row)
            t.setItem(row, 0, QTableWidgetItem(m.get("name", m.get("id", ""))))
            t.setItem(row, 1, QTableWidgetItem(", ".join(m.get("domains", []))))
            t.setItem(row, 2, QTableWidgetItem(str(m.get("version", ""))))
            t.setItem(row, 3, QTableWidgetItem(m.get("author", "")))
            t.item(row, 0).setData(Qt.UserRole, m.get("id", ""))
        self._status_lbl.setText(f"{len(meta)} plugin(s) installed")

    def _on_installed_selection(self):
        self._uninstall_btn.setEnabled(
            bool(self._installed_table.selectedItems())
        )

    def _on_tab_changed(self, idx):
        if idx == 1 and not self._registry:
            self._refresh_registry()

    # ------------------------------------------------------------------ registry

    def _refresh_registry(self):
        self._refresh_btn.setEnabled(False)
        self._status_lbl.setText("Fetching registry…")
        self._worker = _RegistryWorker(self._pm)
        self._worker.finished.connect(self._on_registry_loaded)
        self._worker.error.connect(self._on_registry_error)
        self._worker.start()

    def _on_registry_loaded(self, plugins: list):
        self._refresh_btn.setEnabled(True)
        self._registry = plugins
        installed = self._pm.get_installed_ids()

        t = self._avail_table
        t.setRowCount(0)
        for p in plugins:
            row = t.rowCount(); t.insertRow(row)
            t.setItem(row, 0, QTableWidgetItem(p.get("name", "")))
            t.setItem(row, 1, QTableWidgetItem(", ".join(p.get("domains", []))))
            t.setItem(row, 2, QTableWidgetItem(str(p.get("version", ""))))
            t.setItem(row, 3, QTableWidgetItem(p.get("author", "")))
            pid = p.get("id", "")
            status = "Installed" if pid in installed else "Available"
            status_item = QTableWidgetItem(status)
            if status == "Installed":
                status_item.setForeground(QColor("#2e7d32"))
            t.setItem(row, 4, status_item)
            t.item(row, 0).setData(Qt.UserRole, p)

        t.itemSelectionChanged.connect(self._on_avail_selection)
        self._status_lbl.setText(f"{len(plugins)} plugin(s) in registry")

    def _on_registry_error(self, msg: str):
        self._refresh_btn.setEnabled(True)
        self._status_lbl.setText(f"Registry error: {msg}")

    def _on_avail_selection(self):
        rows = self._avail_table.selectedItems()
        if not rows:
            self._install_btn.setEnabled(False)
            return
        row = self._avail_table.currentRow()
        meta = self._avail_table.item(row, 0).data(Qt.UserRole)
        pid = meta.get("id", "") if meta else ""
        already = pid in self._pm.get_installed_ids()
        self._install_btn.setEnabled(not already)
        self._install_btn.setText("Reinstall" if already else "Install Selected")

    # ------------------------------------------------------------------ actions

    def _install_selected(self):
        row = self._avail_table.currentRow()
        if row < 0:
            return
        meta = self._avail_table.item(row, 0).data(Qt.UserRole)
        if not meta:
            return
        self._install_btn.setEnabled(False)
        self._status_lbl.setText(f"Installing {meta.get('name', '')}…")
        self._inst_worker = _InstallWorker(self._pm, meta)
        self._inst_worker.finished.connect(lambda: self._on_installed(meta.get("name", "")))
        self._inst_worker.error.connect(self._on_install_error)
        self._inst_worker.start()

    def _on_installed(self, name: str):
        self._status_lbl.setText(f"Installed: {name}")
        self._load_installed()
        self._on_registry_loaded(self._registry)  # refresh status column
        self._reload_parsers()
        self.plugins_changed.emit()

    def _reload_parsers(self):
        try:
            from src.parsers.registry import reload_plugins
            reload_plugins()
        except Exception:
            pass

    def _on_install_error(self, msg: str):
        self._install_btn.setEnabled(True)
        self._status_lbl.setText(f"Install failed: {msg}")
        QMessageBox.critical(self, "Install Failed", msg)

    def _import_from_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Plugin File", "", "Plugin JSON (*.json)"
        )
        if not path:
            return
        try:
            plugin_id = self._pm.install_from_file(path)
            self._status_lbl.setText(f"Installed: {plugin_id}")
            self._load_installed()
            self._reload_parsers()
            self.plugins_changed.emit()
        except Exception as e:
            QMessageBox.critical(self, "Import Failed", str(e))

    def _uninstall_selected(self):
        row = self._installed_table.currentRow()
        if row < 0:
            return
        pid = self._installed_table.item(row, 0).data(Qt.UserRole)
        name = self._installed_table.item(row, 0).text()
        reply = QMessageBox.question(
            self, "Remove Plugin",
            f"Remove \"{name}\"?\nYou can reinstall it from the registry later.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self._pm.uninstall(pid)
            self._load_installed()
            self._reload_parsers()
            self._status_lbl.setText(f"Removed: {name}")
            self.plugins_changed.emit()

    # ------------------------------------------------------------------ recommendations

    def _get_recommended(self):
        if not self._registry:
            QMessageBox.information(
                self, "Registry Not Loaded",
                "Please refresh the registry first, then try again."
            )
            return
        matches = self._pm.get_recommended_plugins(self._db, self._registry)
        if not matches:
            QMessageBox.information(
                self, "All Set",
                "No new plugins found for sites in your library.\n"
                "All supported sites are already covered."
            )
            return
        names = "\n".join(
            f"• {m.get('name', m.get('id', ''))}  "
            f"({', '.join(m.get('domains', [])[:2])})"
            for m in matches
        )
        reply = QMessageBox.question(
            self, "Recommended Plugins",
            f"Found {len(matches)} plugin(s) for sites in your library:\n\n{names}\n\nInstall all?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes,
        )
        if reply == QMessageBox.Yes:
            self._batch_install(matches)

    def _batch_install(self, metas: list):
        self._recommend_btn.setEnabled(False)
        self._refresh_btn.setEnabled(False)
        self._status_lbl.setText(f"Installing {len(metas)} plugin(s)…")
        self._batch_worker = _BatchInstallWorker(self._pm, metas)
        self._batch_worker.progress.connect(
            lambda name: self._status_lbl.setText(f"Installed: {name}…")
        )
        self._batch_worker.finished.connect(self._on_batch_finished)
        self._batch_worker.error.connect(
            lambda msg: self._status_lbl.setText(f"Warning: {msg}")
        )
        self._batch_worker.start()

    def _on_batch_finished(self, count: int):
        self._recommend_btn.setEnabled(self._db is not None)
        self._refresh_btn.setEnabled(True)
        self._status_lbl.setText(f"Installed {count} plugin(s)")
        self._load_installed()
        self._on_registry_loaded(self._registry)
        self._reload_parsers()
        self.plugins_changed.emit()

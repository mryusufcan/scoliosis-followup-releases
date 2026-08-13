from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QComboBox, QDialog, QHBoxLayout, QInputDialog, QLabel, QMessageBox, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout

from modular_app.database.exam_repository import ExamRepository


class UserManagerDialog(QDialog):
    active_user_selected = Signal(dict)

    def __init__(self, repository: ExamRepository, current_name: str = "", parent=None):
        super().__init__(parent)
        self.repo, self.current_name, self.rows = repository, current_name, []
        self.setWindowTitle("Yerel Kullanıcı ve Roller")
        self.resize(620, 360)
        self.setStyleSheet("background:#242424;color:#ecf0f1;")
        root = QVBoxLayout(self)
        root.addWidget(QLabel("<b>Yerel Kullanıcı ve Roller</b>"))
        root.addWidget(QLabel("Bu ekran yerel sorumluluk ve işlem kaydı içindir; kurumsal oturum açma sistemi değildir."))
        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["Kullanıcı", "Rol"])
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.cellDoubleClicked.connect(self.use_selected)
        root.addWidget(self.table)
        buttons = QHBoxLayout()
        add = QPushButton("Kullanıcı Ekle")
        add.clicked.connect(self.add_user)
        use = QPushButton("Seçili Kullanıcıyla Devam Et")
        use.clicked.connect(self.use_selected)
        buttons.addWidget(add); buttons.addStretch(); buttons.addWidget(use)
        root.addLayout(buttons)
        self.load()

    def load(self):
        self.rows = self.repo.list_users()
        self.table.setRowCount(0)
        for index, row in enumerate(self.rows):
            self.table.insertRow(index)
            self.table.setItem(index, 0, QTableWidgetItem(str(row["display_name"])))
            self.table.setItem(index, 1, QTableWidgetItem(str(row["role"])))

    def add_user(self):
        name, accepted = QInputDialog.getText(self, "Kullanıcı ekle", "Görünen ad:")
        if not accepted or not name.strip():
            return
        role, accepted = QInputDialog.getItem(self, "Rol", "Rol:", ["Yönetici", "Hekim", "Teknisyen"], 2, False)
        if not accepted:
            return
        try:
            self.repo.add_user(name, role)
        except Exception as exc:
            QMessageBox.warning(self, "Kullanıcı", f"Kullanıcı eklenemedi:\n{exc}")
            return
        self.load()

    def use_selected(self, *_args):
        index = self.table.currentRow()
        if 0 <= index < len(self.rows):
            self.active_user_selected.emit(self.rows[index])
            self.accept()

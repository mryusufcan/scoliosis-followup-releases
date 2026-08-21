from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QDialog, QHBoxLayout, QInputDialog, QLabel, QLineEdit, QMessageBox, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout

from modular_app.database.exam_repository import ExamRepository


class UserManagerDialog(QDialog):
    active_user_selected = Signal(dict)

    def __init__(self, repository: ExamRepository, current_name: str = "", current_role: str = "Yönetici", parent=None):
        super().__init__(parent)
        self.repo, self.current_name, self.current_role, self.rows = repository, current_name, current_role, []
        self.can_manage = self.current_role == "Yönetici"
        self.setWindowTitle("Yerel Kullanıcı ve Roller")
        self.resize(620, 360)
        self.setStyleSheet("background:#242424;color:#ecf0f1;")
        root = QVBoxLayout(self)
        root.addWidget(QLabel("<b>Yerel Kullanıcı ve Roller</b>"))
        root.addWidget(QLabel("Yerel parola, kullanıcı/rol seçimini korur; kurumsal oturum açma sisteminin yerine geçmez."))
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Kullanıcı", "Rol", "Parola koruması"])
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.cellDoubleClicked.connect(self.use_selected)
        root.addWidget(self.table)
        buttons = QHBoxLayout()
        add = QPushButton("Kullanıcı Ekle")
        add.clicked.connect(self.add_user)
        password = QPushButton("Seçili Kullanıcıya Parola Ata")
        password.clicked.connect(self.set_password)
        clear_password = QPushButton("Parolayı Kaldır")
        clear_password.clicked.connect(self.clear_password)
        use = QPushButton("Seçili Kullanıcıyla Devam Et")
        use.clicked.connect(self.use_selected)
        add.setEnabled(self.can_manage)
        password.setEnabled(self.can_manage)
        clear_password.setEnabled(self.can_manage)
        buttons.addWidget(add); buttons.addWidget(password); buttons.addWidget(clear_password)
        buttons.addStretch(); buttons.addWidget(use)
        root.addLayout(buttons)
        self.load()

    def load(self):
        self.rows = self.repo.list_users()
        self.table.setRowCount(0)
        for index, row in enumerate(self.rows):
            self.table.insertRow(index)
            self.table.setItem(index, 0, QTableWidgetItem(str(row["display_name"])))
            self.table.setItem(index, 1, QTableWidgetItem(str(row["role"])))
            self.table.setItem(index, 2, QTableWidgetItem("Etkin" if bool(row.get("password_protected")) else "Yok"))

    def add_user(self):
        if not self.can_manage:
            return
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

    def _selected(self) -> dict | None:
        index = self.table.currentRow()
        return self.rows[index] if 0 <= index < len(self.rows) else None

    def set_password(self):
        user = self._selected()
        if not user or not self.can_manage:
            return
        password, accepted = QInputDialog.getText(
            self, "Yerel parola", f"{user['display_name']} için en az 8 karakterlik parola:", QLineEdit.EchoMode.Password
        )
        if not accepted:
            return
        confirm, accepted = QInputDialog.getText(
            self, "Yerel parola", "Parolayı tekrar girin:", QLineEdit.EchoMode.Password
        )
        if not accepted or password != confirm:
            QMessageBox.warning(self, "Yerel parola", "Parolalar eşleşmiyor.")
            return
        try:
            self.repo.set_user_password(int(user["id"]), password)
        except ValueError as exc:
            QMessageBox.warning(self, "Yerel parola", str(exc))
            return
        QMessageBox.information(self, "Yerel parola", "Parola koruması etkinleştirildi.")
        self.load()

    def clear_password(self):
        user = self._selected()
        if not user or not self.can_manage:
            return
        answer = QMessageBox.question(
            self, "Parolayı kaldır", f"{user['display_name']} için yerel parola koruması kaldırılacak. Devam edilsin mi?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.repo.clear_user_password(int(user["id"]))
        self.load()

    def use_selected(self, *_args):
        user = self._selected()
        if not user:
            return
        authenticated = user
        if bool(user.get("password_protected")):
            password, accepted = QInputDialog.getText(
                self, "Kullanıcı doğrulama", f"{user['display_name']} parolası:", QLineEdit.EchoMode.Password
            )
            if not accepted:
                return
            authenticated = self.repo.authenticate_user(int(user["id"]), password)
            if authenticated is None:
                QMessageBox.warning(self, "Kullanıcı doğrulama", "Parola hatalı veya kullanıcı artık etkin değil.")
                return
        self.active_user_selected.emit(authenticated)
        self.accept()

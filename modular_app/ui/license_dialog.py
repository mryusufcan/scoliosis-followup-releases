from __future__ import annotations

from PySide6.QtWidgets import QDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QVBoxLayout


class LicenseDialog(QDialog):
    """Qt activation dialog sharing the existing HWID/Supabase license API."""

    def __init__(self, repository, parent=None, startup_message=None):
        super().__init__(parent)
        self.repo = repository
        self.startup_message = startup_message
        self.setWindowTitle("Lisans Yönetimi")
        self.resize(460, 300)
        self.setStyleSheet("background:#242424;color:#ecf0f1;")
        root = QVBoxLayout(self)
        self.status = QLabel(startup_message or "Lisans durumu kontrol ediliyor…")
        self.status.setWordWrap(True)
        root.addWidget(self.status)
        form = QFormLayout()
        self.name = QLineEdit(); self.email = QLineEdit(); self.key = QLineEdit()
        self.key.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Ad soyad", self.name); form.addRow("E-posta", self.email); form.addRow("Lisans anahtarı", self.key)
        root.addLayout(form)
        policy_note = QLabel("Açılış lisans denetimi aktiftir. Etkin lisans çevrimdışı en fazla 6 saat kullanılabilir; ilk lisanssız deneme süresi 14 gündür.")
        policy_note.setWordWrap(True)
        policy_note.setStyleSheet("color:#f1c40f; padding:4px 0;")
        root.addWidget(policy_note)
        buttons = QHBoxLayout()
        check = QPushButton("Durumu Kontrol Et"); check.clicked.connect(self.check)
        activate = QPushButton("Etkinleştir"); activate.clicked.connect(self.activate)
        close = QPushButton("Kapat"); close.clicked.connect(self.reject)
        buttons.addWidget(check); buttons.addWidget(activate); buttons.addStretch()
        if startup_message:
            proceed = QPushButton("Doğrula ve Başlat")
            proceed.setStyleSheet("background:#27ae60; color:white; font-weight:bold;")
            proceed.clicked.connect(self.accept_if_active)
            buttons.addWidget(proceed)
        buttons.addWidget(close)
        root.addLayout(buttons)
        self.check()

    def check(self) -> bool:
        try:
            from license_app import check_license_status
            result = check_license_status()
            active = bool(result.active)
            detail = result.message
        except Exception as exc:
            active, detail = False, f"Lisans denetlenemedi: {exc}"
            result = None
        expiry = getattr(result, "expires_at", None) or self.repo.get_setting("license/expires_at", "")
        expiry_line = f"\nLisans son kullanım tarihi: {expiry}" if expiry else "\nLisans son kullanım tarihi: Tanımlı değil"
        self.status.setText(
            ("Lisans bu bilgisayar için etkin." if active else f"Etkin lisans doğrulanamadı. {detail}") + expiry_line
        )
        return active

    def accept_if_active(self):
        if self.check():
            self.accept()
        else:
            QMessageBox.warning(self, "Lisans", "Uygulamayı başlatmak için etkin lisans çevrimiçi olarak doğrulanmalıdır.")

    def activate(self):
        if not all((self.name.text().strip(), self.email.text().strip(), self.key.text().strip())):
            QMessageBox.warning(self, "Lisans", "Ad, e-posta ve lisans anahtarı zorunludur.")
            return
        try:
            from license_app import activate_license
            active, message = activate_license(self.name.text().strip(), self.email.text().strip(), self.key.text().strip())
        except Exception as exc:
            active, message = False, str(exc)
        QMessageBox.information(self, "Lisans" if active else "Lisans etkinleştirme", message)
        if active:
            self.status.setText("Lisans başarıyla etkinleştirildi.")
            self.accept()

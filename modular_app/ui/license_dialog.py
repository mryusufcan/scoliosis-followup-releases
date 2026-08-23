from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)


class LicenseDialog(QDialog):
    """Qt activation dialog sharing Supabase and signed offline licensing."""

    def __init__(self, repository, parent=None, startup_message=None):
        super().__init__(parent)
        self.repo = repository
        self.startup_message = startup_message
        self.setWindowTitle("Lisans Yönetimi")
        self.resize(520, 360)
        self.setStyleSheet("background:#242424;color:#ecf0f1;")
        root = QVBoxLayout(self)
        self.status = QLabel(startup_message or "Lisans durumu kontrol ediliyor…")
        self.status.setWordWrap(True)
        root.addWidget(self.status)

        form = QFormLayout()
        self.name = QLineEdit()
        self.email = QLineEdit()
        self.key = QLineEdit()
        self.key.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Ad soyad", self.name)
        form.addRow("E-posta", self.email)
        form.addRow("Lisans anahtarı", self.key)
        root.addLayout(form)

        offline_note = QLabel(
            "İmzalı offline lisans dosyanız varsa internet olmadan yükleyebilirsiniz. "
            "Dosya bu bilgisayarda doğrulanmadan kurulmaz; PatientID/DICOM verisi gönderilmez."
        )
        offline_note.setWordWrap(True)
        offline_note.setStyleSheet("color:#9ad0f5; padding:4px 0;")
        root.addWidget(offline_note)
        offline_button = QPushButton("İmzalı offline lisans yükle")
        offline_button.clicked.connect(self.install_offline_license)
        root.addWidget(offline_button)
        device_button = QPushButton("Bu bilgisayarın cihaz kodunu kopyala")
        device_button.setToolTip("Lisans issuer’a göndermek için anonim cihaz digest’ini panoya kopyalar")
        device_button.clicked.connect(self.copy_device_fingerprint)
        root.addWidget(device_button)
        entitlement_button = QPushButton("Çevrimiçi offline lisans al / yenile")
        entitlement_button.setToolTip("Aktif Supabase lisansınız için imzalı offline entitlement varsa bu bilgisayara kurar")
        entitlement_button.clicked.connect(self.fetch_offline_entitlement)
        root.addWidget(entitlement_button)

        policy_note = QLabel(
            "Açılış lisans denetimi aktiftir. Etkin lisans çevrimdışı en fazla 6 saat "
            "kullanılabilir; imzalı offline lisans kendi son kullanım tarihine kadar geçerlidir."
        )
        policy_note.setWordWrap(True)
        policy_note.setStyleSheet("color:#f1c40f; padding:4px 0;")
        root.addWidget(policy_note)

        buttons = QHBoxLayout()
        check = QPushButton("Durumu Kontrol Et")
        check.clicked.connect(self.check)
        activate = QPushButton("Etkinleştir")
        activate.clicked.connect(self.activate)
        close = QPushButton("Kapat")
        close.clicked.connect(self.reject)
        buttons.addWidget(check)
        buttons.addWidget(activate)
        buttons.addStretch()
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
            from modular_app.services.license_policy import evaluate_license_gate

            result = evaluate_license_gate(self.repo)
            allowed = bool(result.allowed)
            detail = str(result.message)
        except Exception as exc:
            allowed, detail = False, f"Lisans denetlenemedi: {exc}"
            result = None
        expiry = getattr(result, "expires_at", None)
        expiry_line = f"\nLisans son kullanım tarihi: {expiry}" if expiry else ""
        self.status.setText(detail + expiry_line)
        return allowed

    def accept_if_active(self):
        if self.check():
            self.accept()
        else:
            QMessageBox.warning(
                self,
                "Lisans",
                "Uygulamayı başlatmak için geçerli lisans veya izinli offline lisans gerekir.",
            )

    def copy_device_fingerprint(self):
        try:
            from modular_app.security.device_fingerprint import calculate_device_fingerprint

            fingerprint = calculate_device_fingerprint()
            QApplication.clipboard().setText(fingerprint)
        except Exception as exc:
            QMessageBox.warning(self, "Cihaz kodu", f"Cihaz kodu üretilemedi.\n\nAyrıntı: {exc}")
            return
        QMessageBox.information(
            self,
            "Cihaz kodu",
            "Anonim cihaz kodu panoya kopyalandı. Bu kodu yalnızca lisans issuer’ına gönderin; "
            "hasta veya DICOM verisi göndermeyin.",
        )

    def fetch_offline_entitlement(self):
        key = self.key.text().strip()
        if not key:
            QMessageBox.warning(self, "Offline lisans", "Önce lisans anahtarını girin.")
            return
        try:
            from license_app import fetch_signed_offline_entitlement
            from modular_app.services.license_policy import install_offline_license_text

            document, message = fetch_signed_offline_entitlement(key)
            if not document:
                self.status.setText("İmzalı offline entitlement alınamadı; çevrimiçi lisans akışı değişmedi.")
                QMessageBox.information(
                    self,
                    "Offline lisans",
                    "Bu anahtar için çevrimiçi imzalı offline entitlement bulunamadı. "
                    "Supabase migration henüz etkin değilse manuel imzalı JSON dosyası yükleyebilirsiniz.",
                )
                return
            verified = install_offline_license_text(document)
        except Exception:
            self.status.setText("Offline entitlement doğrulanamadı; mevcut çevrimiçi lisans akışı korunuyor.")
            QMessageBox.warning(
                self,
                "Offline lisans",
                "İmzalı offline entitlement alınamadı veya bu bilgisayarda doğrulanamadı.",
            )
            return
        self.status.setText(
            "İmzalı offline lisans doğrulandı. "
            f"Geçerlilik: {verified.expires_at.date().isoformat()}"
        )
        QMessageBox.information(
            self,
            "Offline lisans",
            "İmzalı offline lisans bu bilgisayarda doğrulandı ve güvenli kullanıcı klasörüne kuruldu.",
        )

    def install_offline_license(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "İmzalı offline lisans dosyasını seç",
            str(Path.home()),
            "Lisans JSON (*.json);;Tüm dosyalar (*.*)",
        )
        if not path:
            return
        try:
            from modular_app.services.license_policy import install_offline_license

            verified = install_offline_license(path)
        except Exception as exc:
            QMessageBox.warning(
                self,
                "Offline lisans doğrulanamadı",
                "Dosya bu bilgisayar için geçerli değil veya imzası doğrulanamadı.\n\n"
                f"Ayrıntı: {exc}",
            )
            return
        self.status.setText(
            "İmzalı offline lisans doğrulandı. "
            f"Geçerlilik: {verified.expires_at.date().isoformat()}"
        )
        QMessageBox.information(
            self,
            "Offline lisans",
            "Lisans bu bilgisayarda doğrulandı ve güvenli kullanıcı klasörüne kuruldu.",
        )
        self.check()

    def activate(self):
        if not all((self.name.text().strip(), self.email.text().strip(), self.key.text().strip())):
            QMessageBox.warning(self, "Lisans", "Ad, e-posta ve lisans anahtarı zorunludur.")
            return
        try:
            from license_app import activate_license

            active, message = activate_license(
                self.name.text().strip(),
                self.email.text().strip(),
                self.key.text().strip(),
            )
        except Exception as exc:
            active, message = False, str(exc)
        QMessageBox.information(self, "Lisans" if active else "Lisans etkinleştirme", message)
        if active:
            offline_note = ""
            try:
                from license_app import fetch_signed_offline_entitlement
                from modular_app.services.license_policy import install_offline_license_text

                document, _ = fetch_signed_offline_entitlement(self.key.text().strip())
                if document:
                    verified = install_offline_license_text(document)
                    offline_note = (
                        f" İmzalı offline kullanım {verified.expires_at.date().isoformat()} tarihine kadar hazır."
                    )
            except Exception:
                # Online license activation remains valid even when the optional
                # entitlement migration is not installed or the fetch fails.
                pass
            self.status.setText("Lisans başarıyla etkinleştirildi." + offline_note)
            self.accept()

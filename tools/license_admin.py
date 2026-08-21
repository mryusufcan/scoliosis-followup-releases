from __future__ import annotations

import csv
import os
import secrets
import string
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

DEFAULT_SUPABASE_URL = "https://mvszpbrjedpvxtkcebzr.supabase.co"
TIMEOUT = 6


def _admin_key() -> str:
    return (
        os.environ.get("SUPABASE_SECRET_KEY", "").strip()
        or os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    )


def _headers() -> dict[str, str]:
    key = _admin_key()
    if not key:
        raise RuntimeError("SUPABASE_SECRET_KEY tanımlı değil.")
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def _base_url() -> str:
    return os.environ.get("SUPABASE_URL", DEFAULT_SUPABASE_URL).rstrip("/")


def generate_license_key() -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "SCOL-" + "-".join(
        "".join(secrets.choice(alphabet) for _ in range(5))
        for _ in range(4)
    )


def parse_expiry(value):
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except Exception:
        try:
            return datetime.strptime(text, "%Y-%m-%d").replace(
                tzinfo=timezone.utc
            )
        except Exception:
            return None


def expiry_for_period(period: str, base: datetime | None = None) -> str:
    if period == "Süresiz":
        return ""
    days = {
        "30 gün": 30,
        "3 ay": 90,
        "6 ay": 180,
        "1 yıl": 365,
        "2 yıl": 730,
    }[period]
    base = base or datetime.now(timezone.utc)
    return (base + timedelta(days=days)).isoformat()


def remaining_days(value) -> int | None:
    expiry = parse_expiry(value)
    if expiry is None:
        return None
    return int((expiry - datetime.now(timezone.utc)).total_seconds() // 86400)


def remaining_text(value) -> str:
    if not str(value or "").strip():
        return "Süresiz"
    days = remaining_days(value)
    if days is None:
        return "Tarih hatalı"
    if days < 0:
        return "Süresi doldu"
    if days == 0:
        return "Bugün bitiyor"
    return f"{days} gün"


def short_hwid(value) -> str:
    value = str(value or "").strip()
    if not value or value.upper() == "EMPTY":
        return "—"
    if len(value) <= 20:
        return value
    return f"{value[:10]}…{value[-8:]}"


class CreateLicenseDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Yeni Lisans")
        self.resize(440, 270)

        root = QVBoxLayout(self)
        form = QFormLayout()

        self.key = QLineEdit(generate_license_key())
        self.name = QLineEdit()
        self.email = QLineEdit()
        self.period = QComboBox()
        self.period.addItems(
            ["1 yıl", "30 gün", "3 ay", "6 ay", "2 yıl", "Süresiz"]
        )

        form.addRow("Lisans anahtarı", self.key)
        form.addRow("Müşteri", self.name)
        form.addRow("E-posta", self.email)
        form.addRow("Süre", self.period)
        root.addLayout(form)

        note = QLabel(
            "Lisans ilk aktivasyonda cihaz HWID'sine bağlanır."
        )
        note.setWordWrap(True)
        root.addWidget(note)

        buttons = QHBoxLayout()
        regenerate = QPushButton("Yeni Anahtar Üret")
        regenerate.clicked.connect(
            lambda: self.key.setText(generate_license_key())
        )
        cancel = QPushButton("İptal")
        cancel.clicked.connect(self.reject)
        create = QPushButton("Oluştur")
        create.clicked.connect(self.accept)

        buttons.addWidget(regenerate)
        buttons.addStretch()
        buttons.addWidget(cancel)
        buttons.addWidget(create)
        root.addLayout(buttons)

    def payload(self) -> dict:
        return {
            "license_key": self.key.text().strip(),
            "hwid": "EMPTY",
            "status": "active",
            "expires_at": expiry_for_period(self.period.currentText()),
            "name": self.name.text().strip() or None,
            "email": self.email.text().strip() or None,
        }


class EditCustomerDialog(QDialog):
    def __init__(self, row, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Müşteri Bilgilerini Düzenle")
        self.resize(420, 190)

        root = QVBoxLayout(self)
        form = QFormLayout()

        key = QLineEdit(str(row.get("license_key") or ""))
        key.setReadOnly(True)
        self.name = QLineEdit(str(row.get("name") or ""))
        self.email = QLineEdit(str(row.get("email") or ""))

        form.addRow("Lisans", key)
        form.addRow("Müşteri", self.name)
        form.addRow("E-posta", self.email)
        root.addLayout(form)

        buttons = QHBoxLayout()
        buttons.addStretch()
        cancel = QPushButton("İptal")
        cancel.clicked.connect(self.reject)
        save = QPushButton("Kaydet")
        save.clicked.connect(self.accept)
        buttons.addWidget(cancel)
        buttons.addWidget(save)
        root.addLayout(buttons)

    def payload(self) -> dict:
        return {
            "name": self.name.text().strip() or None,
            "email": self.email.text().strip() or None,
        }


class ExtendLicenseDialog(QDialog):
    def __init__(self, row, parent=None):
        super().__init__(parent)
        self.row = row
        self.setWindowTitle("Lisans Süresini Uzat")
        self.resize(430, 190)

        root = QVBoxLayout(self)
        form = QFormLayout()

        self.period = QComboBox()
        self.period.addItems(
            ["30 gün", "3 ay", "6 ay", "1 yıl", "2 yıl", "Süresiz"]
        )

        current = str(row.get("expires_at") or "").strip() or "Süresiz"
        form.addRow("Mevcut bitiş", QLabel(current))
        form.addRow("Eklenecek süre", self.period)
        root.addLayout(form)

        note = QLabel(
            "Süresi devam eden lisanslarda uzatma mevcut bitiş tarihine eklenir. "
            "Süresi dolmuşsa bugünden başlar."
        )
        note.setWordWrap(True)
        root.addWidget(note)

        buttons = QHBoxLayout()
        buttons.addStretch()
        cancel = QPushButton("İptal")
        cancel.clicked.connect(self.reject)
        extend = QPushButton("Uzat")
        extend.clicked.connect(self.accept)
        buttons.addWidget(cancel)
        buttons.addWidget(extend)
        root.addLayout(buttons)

    def new_expiry(self) -> str:
        period = self.period.currentText()
        if period == "Süresiz":
            return ""
        current = parse_expiry(self.row.get("expires_at"))
        now = datetime.now(timezone.utc)
        base = current if current is not None and current > now else now
        return expiry_for_period(period, base)


class LicenseAdminWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Scoliosis Follow-Up - Lisans Yönetimi V3")
        self.resize(1380, 760)
        self.rows = []
        self.filtered_rows = []

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)

        filter_bar = QHBoxLayout()
        filter_bar.addWidget(QLabel("Ara"))
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText(
            "Lisans anahtarı, müşteri, e-posta veya HWID..."
        )
        self.search_box.textChanged.connect(self.apply_filter)
        filter_bar.addWidget(self.search_box, 1)

        filter_bar.addWidget(QLabel("Filtre"))
        self.filter_box = QComboBox()
        self.filter_box.addItems(
            [
                "Tümü",
                "Aktif",
                "Pasif",
                "Cihaza bağlı",
                "Cihaz boş",
                "Süresi dolmuş",
                "30 gün içinde bitecek",
            ]
        )
        self.filter_box.currentTextChanged.connect(self.apply_filter)
        filter_bar.addWidget(self.filter_box)

        root.addLayout(filter_bar)

        action_bar = QHBoxLayout()
        actions = [
            ("Yenile", self.load_licenses),
            ("Yeni Lisans", self.create_license),
            ("Anahtarı Kopyala", self.copy_key),
            ("Müşteri Düzenle", self.edit_customer),
            ("Süreyi Uzat", self.extend_license),
            ("Aktif / Pasif", self.toggle_status),
            ("Cihaz Bağını Sıfırla", self.reset_hwid),
            ("CSV Dışa Aktar", self.export_csv),
            ("Seçili Lisansı Sil", self.delete_license),
        ]
        for text, handler in actions:
            button = QPushButton(text)
            button.clicked.connect(handler)
            action_bar.addWidget(button)
        action_bar.addStretch()
        root.addLayout(action_bar)

        self.status = QLabel()
        root.addWidget(self.status)

        self.table = QTableWidget(0, 9)
        self.table.setHorizontalHeaderLabels(
            [
                "ID",
                "Lisans Anahtarı",
                "Durum",
                "Bitiş",
                "Kalan",
                "HWID",
                "Müşteri",
                "E-posta",
                "Cihaz",
            ]
        )
        self.table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.table.setSelectionMode(
            QTableWidget.SelectionMode.SingleSelection
        )
        self.table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )
        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.doubleClicked.connect(self.copy_key)
        root.addWidget(self.table)

        self.load_licenses()

    def request(self, method: str, path: str, **kwargs):
        response = requests.request(
            method,
            f"{_base_url()}/rest/v1/{path.lstrip('/')}",
            headers=_headers(),
            timeout=TIMEOUT,
            **kwargs,
        )
        if response.status_code not in (200, 201, 204):
            raise RuntimeError(
                f"Supabase HTTP {response.status_code}: "
                f"{response.text[:500]}"
            )
        if response.status_code == 204 or not response.text.strip():
            return None
        return response.json()

    def load_licenses(self):
        try:
            self.rows = self.request(
                "GET",
                "licenses?select=id,license_key,hwid,status,expires_at,name,email"
                "&order=id.desc",
            ) or []
            self.apply_filter()
        except Exception as exc:
            QMessageBox.critical(self, "Lisans Yönetimi", str(exc))
            self.status.setText("Supabase bağlantısı başarısız.")

    def apply_filter(self):
        query = self.search_box.text().strip().lower()
        mode = self.filter_box.currentText()
        result = []

        for row in self.rows:
            haystack = " ".join(
                str(row.get(key) or "")
                for key in (
                    "license_key",
                    "hwid",
                    "status",
                    "expires_at",
                    "name",
                    "email",
                )
            ).lower()

            hwid = str(row.get("hwid") or "")
            is_bound = bool(hwid and hwid.upper() != "EMPTY")
            status = str(row.get("status") or "").lower()
            days = remaining_days(row.get("expires_at"))
            has_expiry = bool(str(row.get("expires_at") or "").strip())

            filter_ok = (
                mode == "Tümü"
                or (mode == "Aktif" and status == "active")
                or (mode == "Pasif" and status != "active")
                or (mode == "Cihaza bağlı" and is_bound)
                or (mode == "Cihaz boş" and not is_bound)
                or (
                    mode == "Süresi dolmuş"
                    and has_expiry
                    and days is not None
                    and days < 0
                )
                or (
                    mode == "30 gün içinde bitecek"
                    and has_expiry
                    and days is not None
                    and 0 <= days <= 30
                )
            )

            if (not query or query in haystack) and filter_ok:
                result.append(row)

        self.filtered_rows = result
        self.render_rows()

    def render_rows(self):
        self.table.setRowCount(len(self.filtered_rows))

        for row_index, row in enumerate(self.filtered_rows):
            hwid = str(row.get("hwid") or "")
            values = [
                row.get("id", ""),
                row.get("license_key", ""),
                row.get("status", ""),
                row.get("expires_at", "") or "Süresiz",
                remaining_text(row.get("expires_at")),
                short_hwid(hwid),
                row.get("name", "") or "",
                row.get("email", "") or "",
                "Bağlı" if hwid and hwid.upper() != "EMPTY" else "Boş",
            ]

            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setData(Qt.ItemDataRole.UserRole, row)
                if column == 0:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(row_index, column, item)

        self.status.setText(
            f"{len(self.filtered_rows)} / {len(self.rows)} lisans gösteriliyor"
        )

    def selected_row(self):
        row_index = self.table.currentRow()
        if row_index < 0:
            QMessageBox.information(
                self,
                "Lisans Yönetimi",
                "Önce bir lisans seçin.",
            )
            return None
        item = self.table.item(row_index, 0)
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def patch_row(self, row, payload):
        self.request(
            "PATCH",
            f"licenses?id=eq.{int(row['id'])}",
            json=payload,
        )
        self.load_licenses()

    def create_license(self):
        dialog = CreateLicenseDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        payload = dialog.payload()
        if len(payload["license_key"]) < 8:
            QMessageBox.warning(
                self, "Yeni Lisans", "Lisans anahtarı geçersiz."
            )
            return

        try:
            self.request("POST", "licenses", json=payload)
            QApplication.clipboard().setText(payload["license_key"])
            QMessageBox.information(
                self,
                "Yeni Lisans",
                "Lisans oluşturuldu ve anahtar panoya kopyalandı:\n\n"
                + payload["license_key"],
            )
            self.load_licenses()
        except Exception as exc:
            QMessageBox.critical(self, "Yeni Lisans", str(exc))

    def copy_key(self, *_):
        row = self.selected_row()
        if not row:
            return
        QApplication.clipboard().setText(
            str(row.get("license_key") or "")
        )
        self.status.setText("Lisans anahtarı panoya kopyalandı.")

    def edit_customer(self):
        row = self.selected_row()
        if not row:
            return
        dialog = EditCustomerDialog(row, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            self.patch_row(row, dialog.payload())
        except Exception as exc:
            QMessageBox.critical(self, "Müşteri Düzenle", str(exc))

    def extend_license(self):
        row = self.selected_row()
        if not row:
            return
        dialog = ExtendLicenseDialog(row, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            self.patch_row(
                row,
                {"expires_at": dialog.new_expiry()},
            )
        except Exception as exc:
            QMessageBox.critical(self, "Süreyi Uzat", str(exc))

    def toggle_status(self):
        row = self.selected_row()
        if not row:
            return
        current = str(row.get("status") or "").lower()
        new_status = "inactive" if current == "active" else "active"

        if QMessageBox.question(
            self,
            "Lisans Durumu",
            f"Lisans durumu '{new_status}' yapılsın mı?",
        ) != QMessageBox.StandardButton.Yes:
            return

        try:
            self.patch_row(row, {"status": new_status})
        except Exception as exc:
            QMessageBox.critical(self, "Lisans Durumu", str(exc))

    def reset_hwid(self):
        row = self.selected_row()
        if not row:
            return

        key = str(row.get("license_key") or "")
        answer = QMessageBox.warning(
            self,
            "Cihaz Bağını Sıfırla",
            f"{key}\n\n"
            "Mevcut cihaz bağlantısı kaldırılacak. "
            "Lisans sonraki aktivasyonda başka bir bilgisayara bağlanabilir.",
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        try:
            self.patch_row(row, {"hwid": "EMPTY"})
        except Exception as exc:
            QMessageBox.critical(
                self, "Cihaz Bağını Sıfırla", str(exc)
            )

    def export_csv(self):
        if not self.filtered_rows:
            QMessageBox.information(
                self, "CSV", "Dışa aktarılacak kayıt yok."
            )
            return

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Lisans Listesini Dışa Aktar",
            "lisanslar.csv",
            "CSV (*.csv)",
        )
        if not path:
            return

        fields = [
            "id",
            "license_key",
            "status",
            "expires_at",
            "hwid",
            "name",
            "email",
        ]

        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as handle:
                writer = csv.DictWriter(handle, fieldnames=fields)
                writer.writeheader()
                for row in self.filtered_rows:
                    writer.writerow(
                        {field: row.get(field, "") for field in fields}
                    )
            QMessageBox.information(
                self, "CSV", f"Liste kaydedildi:\n{path}"
            )
        except Exception as exc:
            QMessageBox.critical(self, "CSV", str(exc))

    def delete_license(self):
        row = self.selected_row()
        if not row:
            return

        key = str(row.get("license_key") or "")
        typed, accepted = QInputDialog.getText(
            self,
            "Kalıcı Lisans Silme",
            "Bu işlem geri alınamaz.\n\n"
            "Silmek için lisans anahtarını aynen yazın:",
        )
        if not accepted:
            return

        if typed.strip() != key:
            QMessageBox.warning(
                self,
                "Kalıcı Lisans Silme",
                "Lisans anahtarı eşleşmedi. Silme iptal edildi.",
            )
            return

        try:
            self.request(
                "DELETE",
                f"licenses?id=eq.{int(row['id'])}",
            )
            self.load_licenses()
        except Exception as exc:
            QMessageBox.critical(
                self, "Kalıcı Lisans Silme", str(exc)
            )


def main():
    if not _admin_key():
        print()
        print("HATA: SUPABASE_SECRET_KEY bulunamadı.")
        print(
            "Önce scripts\\admin\\Lisans_Yonetimi_Anahtar_Kaydet.ps1 "
            "çalıştırın."
        )
        print()
        return 2

    app = QApplication(sys.argv)
    window = LicenseAdminWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

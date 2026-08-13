from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QDialog, QHBoxLayout, QInputDialog, QLabel, QMessageBox, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout

from modular_app.database.exam_repository import ExamRepository


class CobbHistoryDialog(QDialog):
    """Cobb history with local clinician verification and immutable approved records."""

    def __init__(self, repository: ExamRepository, patient_id: str, actor: str = "", actor_role: str = "", parent=None):
        super().__init__(parent)
        self.repository = repository
        self.patient_id = str(patient_id)
        self.actor, self.actor_role = str(actor), str(actor_role)
        self.setWindowTitle("Cobb Ölçüm Geçmişi")
        self.resize(880, 380)
        self.setStyleSheet("background:#242424;color:#ecf0f1;")
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"<b>Cobb Ölçüm Geçmişi</b>  |  Hasta ID: {patient_id}"))
        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels(["Tarih", "Görüntü", "Taraf", "Cobb açısı", "Durum", "Doğrulayan", "Doğrulama zamanı", "Not"])
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.rows = repository.list_cobb_measurements(patient_id)
        for row in self.rows:
            index = self.table.rowCount()
            self.table.insertRow(index)
            values = [
                row.get("exam_date", "") or row.get("created_at", ""),
                Path(row.get("dicom_path", "")).name,
                str(row.get("side", "")).upper(),
                f"{float(row.get('angle_degrees', 0.0)):.2f}°",
                "Kilitli" if bool(row.get("is_locked")) else "Taslak",
                str(row.get("verified_by", "")) or "—",
                str(row.get("verified_at", "")) or "—",
                str(row.get("verification_note", "")) or "—",
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setData(256, row.get("id"))
                self.table.setItem(index, column, item)
        layout.addWidget(self.table)
        self.summary = QLabel(self._summary_text(self.rows))
        self.summary.setWordWrap(True)
        self.summary.setStyleSheet("color:#95a5a6;")
        layout.addWidget(self.summary)
        buttons = QHBoxLayout()
        edit_button = QPushButton("Seçili Ölçümü Düzenle")
        edit_button.clicked.connect(self._edit_selected)
        remove_button = QPushButton("Seçili Ölçümü Kaldır")
        remove_button.clicked.connect(self._delete_selected)
        verify_button = QPushButton("Doğrula ve Kilitle")
        verify_button.clicked.connect(self._verify_selected)
        buttons.addStretch()
        buttons.addWidget(edit_button)
        buttons.addWidget(remove_button)
        buttons.addWidget(verify_button)
        layout.addLayout(buttons)

    @staticmethod
    def _summary_text(rows: list[dict]) -> str:
        if not rows:
            return "Henüz kayıtlı Cobb ölçümü yok."
        if len(rows) == 1:
            return f"1 ölçüm kayıtlı. Başlangıç değeri: {float(rows[0]['angle_degrees']):.2f}°"

        latest = float(rows[0]["angle_degrees"])
        baseline = float(rows[-1]["angle_degrees"])
        change = latest - baseline
        direction = "artış" if change > 0 else "azalış" if change < 0 else "değişim yok"
        return (
            f"{len(rows)} ölçüm kayıtlı. İlk: {baseline:.2f}°  |  Son: {latest:.2f}°  |  "
            f"Değişim: {change:+.2f}° ({direction})."
        )

    def _delete_selected(self) -> None:
        index = self.table.currentRow()
        if not 0 <= index < len(self.rows):
            return
        answer = QMessageBox.question(
            self,
            "Cobb ölçümünü kaldır",
            "Seçili ölçüm kaydı silinecek. DICOM dosyası değişmeyecek.\n\nDevam edilsin mi?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        measurement = self.rows[index]
        if bool(measurement.get("is_locked")):
            QMessageBox.information(self, "Cobb ölçümü", "Doğrulanıp kilitlenen ölçüm kaldırılamaz.")
            return
        try:
            self.repository.delete_cobb_measurement(int(measurement["id"]))
        except PermissionError as exc:
            QMessageBox.warning(self, "Cobb ölçümü", str(exc))
            return
        self.repository.record_audit_event(self.patient_id, "cobb_measurement_deleted", f"Kayıt #{measurement['id']}", actor=self.actor, actor_role=self.actor_role)
        self.accept()

    def _edit_selected(self) -> None:
        index = self.table.currentRow()
        if not 0 <= index < len(self.rows):
            return
        measurement = self.rows[index]
        if bool(measurement.get("is_locked")):
            QMessageBox.information(self, "Cobb ölçümü", "Doğrulanıp kilitlenen ölçüm değiştirilemez.")
            return
        angle, accepted = QInputDialog.getDouble(
            self, "Cobb ölçümünü düzenle", "Cobb açısı (derece):",
            float(measurement["angle_degrees"]), 0.0, 180.0, 2,
        )
        if not accepted:
            return
        try:
            self.repository.update_cobb_measurement(int(measurement["id"]), angle)
        except (PermissionError, ValueError) as exc:
            QMessageBox.warning(self, "Cobb ölçümü", str(exc))
            return
        self.repository.record_audit_event(self.patient_id, "cobb_measurement_updated", f"Kayıt #{measurement['id']}; {angle:.2f} derece", actor=self.actor, actor_role=self.actor_role)
        self.accept()

    def _verify_selected(self) -> None:
        index = self.table.currentRow()
        if not 0 <= index < len(self.rows):
            return
        if self.actor_role not in {"Yönetici", "Hekim"}:
            QMessageBox.warning(self, "Ölçüm doğrulama", "Cobb ölçümünü yalnızca Hekim veya Yönetici rolü doğrulayıp kilitleyebilir.")
            return
        measurement = self.rows[index]
        if bool(measurement.get("is_locked")):
            QMessageBox.information(self, "Ölçüm doğrulama", "Bu ölçüm zaten kilitli.")
            return
        note, accepted = QInputDialog.getMultiLineText(self, "Ölçüm doğrulama", "Doğrulama notu (isteğe bağlı):")
        if not accepted:
            return
        self.repository.verify_and_lock_cobb_measurement(int(measurement["id"]), self.actor or "Yerel Hekim", note)
        self.repository.record_audit_event(self.patient_id, "cobb_measurement_verified", f"Kayıt #{measurement['id']} doğrulandı ve kilitlendi", actor=self.actor, actor_role=self.actor_role)
        self.accept()

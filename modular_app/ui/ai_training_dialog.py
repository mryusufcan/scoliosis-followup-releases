from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from ai.training_dataset import TrainingDatasetError, export_training_dataset, list_training_labels
from modular_app.services.system_services import APP_VERSION


class AITrainingDataDialog(QDialog):
    """Review canonical four-point labels and export a metadata-free dataset."""

    capture_requested = Signal()

    def __init__(
        self,
        repository,
        active_dicom_path: str = "",
        actor: str = "",
        actor_role: str = "",
        parent=None,
    ):
        super().__init__(parent)
        self.repository = repository
        self.active_dicom_path = str(active_dicom_path or "")
        self.actor = str(actor or "")
        self.actor_role = str(actor_role or "")
        self.rows = []
        self.setWindowTitle("AI Eğitim Verisi Hazırlama — Deneysel")
        self.resize(940, 480)

        root = QVBoxLayout(self)
        title = QLabel("<b>AI Cobb Eğitim Etiketleri</b>")
        title.setStyleSheet("font-size: 15px;")
        root.addWidget(title)
        explanation = QLabel(
            "Her örnek özgün DICOM piksel düzeninde dört noktayla işaretlenir. "
            "Yalnızca Hekim/Yönetici tarafından doğrulanıp kilitlenen etiketler dışa aktarılır. "
            "Dışa aktarım DICOM başlıklarını değil, kimliksiz gri PNG ve normalize noktaları içerir."
        )
        explanation.setWordWrap(True)
        explanation.setStyleSheet("color:#bdc3c7;")
        root.addWidget(explanation)
        active_text = Path(self.active_dicom_path).name if self.active_dicom_path else "Aktif DICOM yok"
        self.active_label = QLabel(f"<b>İşaretlenecek aktif görüntü:</b> {active_text}")
        root.addWidget(self.active_label)

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(
            ["Kayıt", "Hasta", "Görüntü", "Cobb", "Doğrulayan", "Durum", "Açıklama"]
        )
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.horizontalHeader().setStretchLastSection(True)
        root.addWidget(self.table)

        self.summary = QLabel()
        self.summary.setStyleSheet("color:#95a5a6;")
        root.addWidget(self.summary)

        buttons = QHBoxLayout()
        capture = QPushButton("Aktif Görüntüde 4 Nokta İşaretle")
        capture.setEnabled(bool(self.active_dicom_path))
        capture.clicked.connect(self.request_capture)
        verify = QPushButton("Seçili Etiketi Doğrula ve Kilitle")
        verify.clicked.connect(self.verify_selected)
        export = QPushButton("Hazır Etiketleri Eğitim Verisi Olarak Dışa Aktar")
        export.clicked.connect(self.export_ready_labels)
        close = QPushButton("Kapat")
        close.clicked.connect(self.reject)
        buttons.addWidget(capture)
        buttons.addStretch()
        buttons.addWidget(verify)
        buttons.addWidget(export)
        buttons.addWidget(close)
        root.addLayout(buttons)
        self.refresh()

    def refresh(self):
        self.rows = list_training_labels(self.repository)
        self.table.setRowCount(0)
        for review in self.rows:
            row_index = self.table.rowCount()
            self.table.insertRow(row_index)
            status_text = "Hazır" if review.ready else "Bekliyor"
            values = [
                review.measurement_id,
                review.patient_id,
                Path(review.dicom_path).name,
                f"{review.angle_degrees:.2f}°",
                review.verified_by or "—",
                status_text,
                review.message,
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setData(Qt.ItemDataRole.UserRole, review.measurement_id)
                self.table.setItem(row_index, column, item)
        ready = sum(1 for row in self.rows if row.ready)
        waiting = len(self.rows) - ready
        self.summary.setText(f"Toplam {len(self.rows)} eğitim etiketi  |  Hazır: {ready}  |  Bekleyen/hatalı: {waiting}")

    def selected_review(self):
        index = self.table.currentRow()
        if not 0 <= index < len(self.rows):
            return None
        return self.rows[index]

    def request_capture(self):
        if not self.active_dicom_path:
            QMessageBox.information(self, "AI eğitim etiketi", "Önce bir DICOM görüntüsü açın.")
            return
        self.capture_requested.emit()
        self.accept()

    def verify_selected(self):
        review = self.selected_review()
        if review is None:
            QMessageBox.information(self, "AI eğitim etiketi", "Önce bir etiket satırı seçin.")
            return
        if self.actor_role not in {"Yönetici", "Hekim"}:
            QMessageBox.warning(self, "AI eğitim etiketi", "Etiketi yalnızca Hekim veya Yönetici doğrulayabilir.")
            return
        if review.ready:
            QMessageBox.information(self, "AI eğitim etiketi", "Bu etiket zaten doğrulanıp kilitlenmiş.")
            return
        if review.status != "unverified":
            QMessageBox.warning(self, "AI eğitim etiketi", review.message)
            return
        answer = QMessageBox.question(
            self,
            "AI eğitim etiketini doğrula",
            "Dört noktanın ve Cobb açısının doğru olduğunu onaylıyor musunuz?\n\n"
            "Onaylanan kayıt kilitlenir ve eğitim dışa aktarımına uygun hale gelir.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        verifier = self.actor or "Yerel Hekim"
        self.repository.verify_and_lock_cobb_measurement(
            review.measurement_id,
            verifier,
            "AI eğitim etiketi uzman tarafından doğrulandı.",
        )
        self.repository.record_audit_event(
            review.patient_id,
            "ai_training_label_verified",
            f"Cobb kayıt #{review.measurement_id} AI eğitim etiketi olarak doğrulandı",
            actor=self.actor,
            actor_role=self.actor_role,
        )
        self.refresh()

    def export_ready_labels(self):
        if not any(row.ready for row in self.rows):
            QMessageBox.information(self, "AI eğitim verisi", "Dışa aktarılabilecek doğrulanmış etiket yok.")
            return
        parent = QFileDialog.getExistingDirectory(self, "AI eğitim verisinin kaydedileceği üst klasörü seçin")
        if not parent:
            return
        output = Path(parent) / f"scoliosis_ai_training_{datetime.now():%Y%m%d_%H%M%S}"
        try:
            manifest = export_training_dataset(
                self.repository,
                output,
                application_version=APP_VERSION,
            )
        except (TrainingDatasetError, OSError) as exc:
            QMessageBox.warning(self, "AI eğitim verisi", str(exc))
            return
        ready_count = sum(1 for row in self.rows if row.ready)
        self.repository.record_audit_event(
            "SYSTEM",
            "ai_training_dataset_exported",
            f"{ready_count} doğrulanmış etiket kimliksiz eğitim verisi olarak dışa aktarıldı",
            actor=self.actor,
            actor_role=self.actor_role,
        )
        QMessageBox.information(
            self,
            "AI eğitim verisi hazır",
            f"{ready_count} doğrulanmış örnek dışa aktarıldı.\n\n{manifest}",
        )

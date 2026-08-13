from __future__ import annotations

from PySide6.QtWidgets import QDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QPlainTextEdit, QVBoxLayout

from modular_app.database.exam_repository import ExamRepository


class PatientCardDialog(QDialog):
    """Local follow-up card; it never changes the source DICOM tags."""

    def __init__(self, repository: ExamRepository, patient_id: str, patient_name: str, actor: str = "", parent=None):
        super().__init__(parent)
        self.repo, self.patient_id, self.actor = repository, str(patient_id), str(actor)
        self.setWindowTitle("Hasta Kartı")
        self.resize(620, 480)
        self.setStyleSheet("background:#242424;color:#ecf0f1;")
        profile = repository.get_patient_profile(patient_id)
        root = QVBoxLayout(self)
        root.addWidget(QLabel(f"<b>Hasta Kartı</b>  |  {patient_name or 'Hasta'}  |  ID: {patient_id}"))
        root.addWidget(QLabel("DICOM kimlik bilgileri değiştirilmez; aşağıdaki alanlar yerel takip notlarıdır."))
        form = QFormLayout()
        self.diagnosis = QLineEdit(str(profile.get("diagnosis", "")))
        self.physician = QLineEdit(str(profile.get("referring_physician", "")))
        self.follow_up = QLineEdit(str(profile.get("next_follow_up_date", "")))
        self.follow_up.setPlaceholderText("YYYYMMDD veya YYYY-AA-GG")
        self.plan = QPlainTextEdit(str(profile.get("treatment_plan", "")))
        self.notes = QPlainTextEdit(str(profile.get("notes", "")))
        self.plan.setMaximumBlockCount(1000)
        self.notes.setMaximumBlockCount(1000)
        form.addRow("Tanı / klinik başlık", self.diagnosis)
        form.addRow("Sorumlu hekim", self.physician)
        form.addRow("Planlanan kontrol", self.follow_up)
        form.addRow("Tedavi / takip planı", self.plan)
        form.addRow("Notlar", self.notes)
        root.addLayout(form)
        buttons = QHBoxLayout()
        save = QPushButton("Kartı Kaydet")
        save.clicked.connect(self.save)
        close = QPushButton("Kapat")
        close.clicked.connect(self.reject)
        buttons.addStretch(); buttons.addWidget(save); buttons.addWidget(close)
        root.addLayout(buttons)

    def save(self):
        profile = {
            "diagnosis": self.diagnosis.text().strip(),
            "referring_physician": self.physician.text().strip(),
            "next_follow_up_date": self.follow_up.text().strip(),
            "treatment_plan": self.plan.toPlainText().strip(),
            "notes": self.notes.toPlainText().strip(),
        }
        self.repo.save_patient_profile(self.patient_id, profile, self.actor)
        self.repo.record_audit_event(self.patient_id, "patient_card_saved", "Yerel hasta kartı güncellendi", actor=self.actor)
        QMessageBox.information(self, "Hasta kartı", "Yerel hasta kartı kaydedildi.")
        self.accept()

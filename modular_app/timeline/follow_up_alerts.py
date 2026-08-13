from __future__ import annotations

from PySide6.QtWidgets import QDialog, QDoubleSpinBox, QHBoxLayout, QLabel, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout

from modular_app.database.exam_repository import ExamRepository


class FollowUpAlertsDialog(QDialog):
    def __init__(self, repository: ExamRepository, patient_id: str, parent=None):
        super().__init__(parent)
        self.repo, self.patient_id = repository, str(patient_id)
        self.setWindowTitle("Takip Uyarıları")
        self.resize(700, 340)
        self.setStyleSheet("background:#242424;color:#ecf0f1;")
        root = QVBoxLayout(self)
        root.addWidget(QLabel(f"<b>Takip Uyarıları</b>  |  Hasta ID: {patient_id}"))
        setting = repository.get_setting("follow_up/cobb_alert_threshold", "5")
        controls = QHBoxLayout()
        controls.addWidget(QLabel("Cobb değişim eşiği:"))
        self.threshold = QDoubleSpinBox(); self.threshold.setRange(0.1, 90.0); self.threshold.setDecimals(1)
        self.threshold.setSuffix("°")
        try:
            self.threshold.setValue(float(setting))
        except ValueError:
            self.threshold.setValue(5.0)
        refresh = QPushButton("Uyarıları Güncelle")
        refresh.clicked.connect(self.load)
        controls.addWidget(self.threshold); controls.addWidget(refresh); controls.addStretch()
        root.addLayout(controls)
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Durum", "Kontrol", "Ayrıntı"])
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        root.addWidget(self.table)
        root.addWidget(QLabel("Bu uyarılar otomatik klinik karar veya tanı değildir; yetkili uzman değerlendirmesi gerekir."))
        self.load()

    def load(self):
        threshold = float(self.threshold.value())
        self.repo.set_setting("follow_up/cobb_alert_threshold", str(threshold))
        rows = self.repo.follow_up_alerts(self.patient_id, threshold)
        self.table.setRowCount(0)
        for row in rows:
            index = self.table.rowCount(); self.table.insertRow(index)
            for column, value in enumerate((row["severity"], row["kind"], row["details"])):
                self.table.setItem(index, column, QTableWidgetItem(str(value)))
        if not rows:
            self.table.setRowCount(1)
            self.table.setItem(0, 0, QTableWidgetItem("Bilgi"))
            self.table.setItem(0, 1, QTableWidgetItem("Takip uyarısı"))
            self.table.setItem(0, 2, QTableWidgetItem("Tanımlı eşiği aşan yerel takip uyarısı bulunmadı."))

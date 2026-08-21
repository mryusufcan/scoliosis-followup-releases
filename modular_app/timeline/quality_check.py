from __future__ import annotations

from PySide6.QtWidgets import QDialog, QDoubleSpinBox, QHBoxLayout, QLabel, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout

from modular_app.database.exam_repository import ExamRepository


class QualityCheckDialog(QDialog):
    def __init__(self, repository: ExamRepository, patient_id: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Veri Kalite Kontrolü")
        self.resize(700, 360)
        self.setStyleSheet("background:#242424;color:#ecf0f1;")
        self.repository, self.patient_id = repository, str(patient_id)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"<b>Veri Kalite Kontrolü</b>  |  Hasta ID: {patient_id}"))
        controls = QHBoxLayout()
        controls.addWidget(QLabel("Tekrar ölçüm fark eşiği:"))
        self.repeatability_threshold = QDoubleSpinBox()
        self.repeatability_threshold.setRange(0.1, 30.0)
        self.repeatability_threshold.setDecimals(1)
        self.repeatability_threshold.setSuffix("°")
        try:
            self.repeatability_threshold.setValue(float(repository.get_setting("quality/cobb_repeatability_threshold", "3") or 3))
        except ValueError:
            self.repeatability_threshold.setValue(3.0)
        refresh = QPushButton("Kontrolü Yenile")
        refresh.clicked.connect(self.load)
        controls.addWidget(self.repeatability_threshold)
        controls.addWidget(refresh)
        controls.addStretch()
        layout.addLayout(controls)
        table = QTableWidget(0, 3)
        table.setHorizontalHeaderLabels(["Durum", "Kontrol", "Ayrıntı"])
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.horizontalHeader().setStretchLastSection(True)
        self.table = table
        layout.addWidget(table)
        self.summary = QLabel()
        layout.addWidget(self.summary)
        self.load()

    def load(self):
        self.repository.set_setting("quality/cobb_repeatability_threshold", str(float(self.repeatability_threshold.value())))
        issues = self.repository.quality_issues(self.patient_id)
        self.table.setRowCount(0)
        for issue in issues:
            row = self.table.rowCount(); self.table.insertRow(row)
            for column, value in enumerate((issue["severity"], issue["kind"], issue["details"])):
                self.table.setItem(row, column, QTableWidgetItem(str(value)))
        self.summary.setText("Sorun bulunmadı." if not issues else f"{len(issues)} bilgi/uyarı bulundu. Bu ekran veri değiştirmez.")

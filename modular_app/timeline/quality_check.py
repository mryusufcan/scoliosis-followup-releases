from __future__ import annotations

from PySide6.QtWidgets import QDialog, QLabel, QTableWidget, QTableWidgetItem, QVBoxLayout

from modular_app.database.exam_repository import ExamRepository


class QualityCheckDialog(QDialog):
    def __init__(self, repository: ExamRepository, patient_id: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Veri Kalite Kontrolü")
        self.resize(700, 360)
        self.setStyleSheet("background:#242424;color:#ecf0f1;")
        issues = repository.quality_issues(patient_id)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"<b>Veri Kalite Kontrolü</b>  |  Hasta ID: {patient_id}"))
        table = QTableWidget(0, 3)
        table.setHorizontalHeaderLabels(["Durum", "Kontrol", "Ayrıntı"])
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.horizontalHeader().setStretchLastSection(True)
        for issue in issues:
            row = table.rowCount(); table.insertRow(row)
            for column, value in enumerate((issue["severity"], issue["kind"], issue["details"])):
                table.setItem(row, column, QTableWidgetItem(str(value)))
        layout.addWidget(table)
        layout.addWidget(QLabel("Sorun bulunmadı." if not issues else f"{len(issues)} bilgi/uyarı bulundu. Bu ekran veri değiştirmez."))

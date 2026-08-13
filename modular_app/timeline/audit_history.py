from __future__ import annotations

from PySide6.QtWidgets import QDialog, QLabel, QTableWidget, QTableWidgetItem, QVBoxLayout

from modular_app.database.exam_repository import ExamRepository


class AuditHistoryDialog(QDialog):
    """Read-only per-patient event list stored by the modular integration layer."""

    def __init__(self, repository: ExamRepository, patient_id: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("İşlem Geçmişi")
        self.resize(760, 380)
        self.setStyleSheet("background:#242424;color:#ecf0f1;")
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"<b>İşlem Geçmişi</b>  |  Hasta ID: {patient_id}"))
        table = QTableWidget(0, 5)
        table.setHorizontalHeaderLabels(["Zaman", "İşlem", "Ayrıntı", "Kullanıcı", "Rol"])
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.horizontalHeader().setStretchLastSection(True)
        rows = repository.list_audit_events(patient_id)
        for row in rows:
            index = table.rowCount()
            table.insertRow(index)
            for column, value in enumerate((
                row.get("created_at", ""), row.get("event_type", ""), row.get("details", ""),
                row.get("actor", "") or "—", row.get("actor_role", "") or "—",
            )):
                table.setItem(index, column, QTableWidgetItem(str(value)))
        layout.addWidget(table)
        layout.addWidget(QLabel(f"{len(rows)} işlem kayıtlı."))

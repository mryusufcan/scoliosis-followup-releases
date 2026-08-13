from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QAbstractItemView, QDialog, QHBoxLayout, QLabel, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout

from modular_app.database.exam_repository import ExamRepository


class FollowUpSummaryDialog(QDialog):
    """Read-only summary of a patient's exams and locally recorded follow-up data."""

    exam_selected = Signal(dict)
    exams_selected_for_overlay = Signal(list)

    def __init__(self, repository: ExamRepository, patient_id: str, patient_name: str = "", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Hasta Takip Özeti")
        self.resize(900, 440)
        self.setStyleSheet("background:#242424;color:#ecf0f1;")

        layout = QVBoxLayout(self)
        label_name = patient_name or "Hasta"
        layout.addWidget(QLabel(f"<b>Hasta Takip Özeti</b>  |  {label_name}  |  ID: {patient_id}"))

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels([
            "Tetkik tarihi", "Bölge", "Modalite", "Tetkik", "Dosya", "Son Cobb", "Overlay kaydı",
        ])
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.rows = repository.list_patient_follow_up(patient_id)
        for row in self.rows:
            index = self.table.rowCount()
            self.table.insertRow(index)
            angle = row.get("latest_cobb")
            values = [
                row.get("exam_date", ""),
                row.get("body_part", ""),
                row.get("modality", ""),
                row.get("study_description", ""),
                Path(row.get("dicom_path", "")).name,
                f"{float(angle):.2f}°" if angle is not None else "—",
                str(row.get("overlay_session_count", 0)),
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setData(256, row.get("id"))
                self.table.setItem(index, column, item)
        self.table.cellDoubleClicked.connect(self._open_selected)
        layout.addWidget(self.table)
        layout.addWidget(QLabel(f"{len(self.rows)} tetkik listeleniyor."))
        buttons = QHBoxLayout()
        open_button = QPushButton("Seçili Tetkiki Aç")
        open_button.clicked.connect(self._open_selected)
        overlay_button = QPushButton("Seçili İki Tetkiki Overlay'e Gönder")
        overlay_button.clicked.connect(self._send_selected_to_overlay)
        buttons.addStretch()
        buttons.addWidget(open_button)
        buttons.addWidget(overlay_button)
        layout.addLayout(buttons)

    def _open_selected(self, *_args) -> None:
        index = self.table.currentRow()
        if 0 <= index < len(self.rows):
            self.exam_selected.emit(self.rows[index])
            self.accept()

    def _send_selected_to_overlay(self) -> None:
        indexes = sorted({item.row() for item in self.table.selectedItems()})
        if len(indexes) != 2:
            return
        self.exams_selected_for_overlay.emit([self.rows[index] for index in indexes])
        self.accept()

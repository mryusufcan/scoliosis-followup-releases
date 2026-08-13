from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QAbstractItemView, QDialog, QHBoxLayout, QInputDialog, QLabel, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout

from modular_app.database.exam_repository import ExamRepository


class PatientManagerDialog(QDialog):
    """Searchable local index of patients imported from DICOM metadata."""
    patient_selected = Signal(dict)

    def __init__(self, repository: ExamRepository, parent=None):
        super().__init__(parent)
        self.repo = repository
        self.rows: list[dict] = []
        self.setWindowTitle("Hasta Listesi")
        self.resize(760, 430)
        self.setStyleSheet("background:#242424;color:#ecf0f1;")
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<b>Hasta Listesi</b>  |  DICOM kaynak bilgileri salt okunurdur."))
        self.search = QLineEdit()
        self.search.setPlaceholderText("Hasta adı veya ID ara")
        self.search.textChanged.connect(self.load_patients)
        layout.addWidget(self.search)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Hasta ID", "Hasta adı", "Tetkik sayısı", "Son tetkik"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.cellDoubleClicked.connect(self.open_selected)
        layout.addWidget(self.table)
        buttons = QHBoxLayout()
        open_button = QPushButton("Seçili Hastayı Aç")
        open_button.clicked.connect(self.open_selected)
        rename_button = QPushButton("Görünen Adı Düzenle")
        rename_button.clicked.connect(self.edit_display_name)
        buttons.addStretch(); buttons.addWidget(open_button); buttons.addWidget(rename_button)
        layout.addLayout(buttons)
        self.load_patients()

    def load_patients(self, *_args) -> None:
        self.rows = self.repo.list_patients(self.search.text())
        self.table.setRowCount(0)
        for index, row in enumerate(self.rows):
            self.table.insertRow(index)
            for column, value in enumerate((row.get("patient_id", ""), row.get("patient_name", ""), row.get("exam_count", 0), row.get("latest_exam_date", ""))):
                self.table.setItem(index, column, QTableWidgetItem(str(value)))

    def open_selected(self, *_args) -> None:
        index = self.table.currentRow()
        if 0 <= index < len(self.rows):
            self.patient_selected.emit(self.rows[index])
            self.accept()

    def edit_display_name(self) -> None:
        index = self.table.currentRow()
        if not 0 <= index < len(self.rows):
            return
        patient = self.rows[index]
        name, accepted = QInputDialog.getText(
            self, "Görünen hasta adı", "Yerel görünen ad (DICOM etiketi değişmez):", text=str(patient.get("patient_name", ""))
        )
        if accepted and name.strip():
            self.repo.set_patient_display_name(patient["patient_id"], name)
            self.repo.record_audit_event(patient["patient_id"], "patient_display_name_updated", "Yerel görünen ad güncellendi")
            self.load_patients()

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout

from modular_app.database.exam_repository import ExamRepository


VERTEBRA_LEVELS = [f"C{i}" for i in range(1, 8)] + [f"T{i}" for i in range(1, 13)] + [f"L{i}" for i in range(1, 6)] + ["S1"]


class VertebraLabelsDialog(QDialog):
    def __init__(self, repository: ExamRepository, patient_id: str, dicom_path: str, parent=None):
        super().__init__(parent)
        self.repo, self.patient_id, self.dicom_path = repository, str(patient_id), str(dicom_path)
        self.rows: list[dict] = []
        self.setWindowTitle("Omur Etiketleri")
        self.resize(720, 380)
        self.setStyleSheet("background:#242424;color:#ecf0f1;")
        root = QVBoxLayout(self)
        root.addWidget(QLabel(f"<b>Omur Etiketleri</b>  |  {Path(dicom_path).name}"))
        root.addWidget(QLabel("Etiket eklemek için ana görünümde Omur Etiketleme modunu açıp görüntüye tıklayın."))
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Seviye", "X", "Y", "Not", "Ekleyen"])
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        root.addWidget(self.table)
        buttons = QHBoxLayout()
        delete = QPushButton("Seçili Etiketi Kaldır")
        delete.clicked.connect(self.delete_selected)
        refresh = QPushButton("Yenile")
        refresh.clicked.connect(self.load)
        buttons.addWidget(refresh); buttons.addStretch(); buttons.addWidget(delete)
        root.addLayout(buttons)
        self.load()

    def load(self):
        self.rows = self.repo.list_vertebra_labels(self.patient_id, self.dicom_path)
        self.table.setRowCount(0)
        for index, row in enumerate(self.rows):
            self.table.insertRow(index)
            values = (row["vertebra"], f"{float(row['x']):.1f}", f"{float(row['y']):.1f}", row["note"], row["created_by"])
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value)); item.setData(256, row["id"])
                self.table.setItem(index, column, item)

    def delete_selected(self):
        index = self.table.currentRow()
        if not 0 <= index < len(self.rows):
            return
        self.repo.delete_vertebra_label(int(self.rows[index]["id"]))
        self.load()

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView, QDialog, QHBoxLayout, QInputDialog, QLabel, QMessageBox, QPushButton,
    QTableWidget, QTableWidgetItem, QVBoxLayout,
)

from modular_app.database.exam_repository import ExamRepository


class ComparisonSessionDialog(QDialog):
    """Small, read-only list of previously saved Overlay sessions."""

    session_selected = Signal(dict)

    def __init__(self, repository: ExamRepository, patient_id: str, parent=None):
        super().__init__(parent)
        self.repo = repository
        self.patient_id = str(patient_id)
        self._rows: list[dict] = []
        self.setWindowTitle("Kayıtlı Overlay Oturumları")
        self.resize(860, 420)
        self.setStyleSheet("background:#242424;color:#ecf0f1;")

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"<b>Kayıtlı Overlay Oturumları</b>  |  Hasta ID: {self.patient_id}"))

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Kayıt tarihi", "Referans görüntü", "Karşılaştırma görüntüsü", "Hizalama", "Teknik skor", "Not"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.cellDoubleClicked.connect(self._open_selected)
        layout.addWidget(self.table, 1)

        self.info = QLabel()
        self.info.setStyleSheet("color:#95a5a6;")
        layout.addWidget(self.info)

        buttons = QHBoxLayout()
        self.open_button = QPushButton("Seçili Oturumu Aç")
        self.open_button.setEnabled(False)
        self.open_button.clicked.connect(self._open_selected)
        self.table.itemSelectionChanged.connect(lambda: self.open_button.setEnabled(self.table.currentRow() >= 0))
        self.delete_button = QPushButton("Seçili Oturumu Kaldır")
        self.delete_button.setEnabled(False)
        self.delete_button.clicked.connect(self._delete_selected)
        self.table.itemSelectionChanged.connect(lambda: self.delete_button.setEnabled(self.table.currentRow() >= 0))
        self.note_button = QPushButton("Notu Düzenle")
        self.note_button.setEnabled(False)
        self.note_button.clicked.connect(self._edit_note)
        self.table.itemSelectionChanged.connect(lambda: self.note_button.setEnabled(self.table.currentRow() >= 0))
        close_button = QPushButton("Kapat")
        close_button.clicked.connect(self.reject)
        buttons.addStretch()
        buttons.addWidget(self.open_button)
        buttons.addWidget(self.note_button)
        buttons.addWidget(self.delete_button)
        buttons.addWidget(close_button)
        layout.addLayout(buttons)
        self.load_sessions()

    def load_sessions(self) -> None:
        self._rows = self.repo.list_comparison_sessions(self.patient_id)
        self.table.setRowCount(0)
        for row in self._rows:
            index = self.table.rowCount()
            self.table.insertRow(index)
            values = [
                row.get("created_at", ""),
                Path(row.get("reference_path", "")).name,
                Path(row.get("comparison_path", "")).name,
                f"X {row.get('overlay_offset_x', 0):+.0f} | Y {row.get('overlay_offset_y', 0):+.0f} | Z {row.get('overlay_scale', 1):.2f}x",
                f"%{float(row['alignment_score']):.1f}" if row.get("alignment_score") is not None else "—",
                row.get("notes", ""),
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setData(Qt.ItemDataRole.UserRole, row.get("id"))
                self.table.setItem(index, column, item)
        self.info.setText(f"{len(self._rows)} kayıtlı Overlay oturumu.")

    def _open_selected(self, *_args) -> None:
        index = self.table.currentRow()
        if 0 <= index < len(self._rows):
            self.session_selected.emit(self._rows[index])
            self.accept()

    def _delete_selected(self) -> None:
        index = self.table.currentRow()
        if not 0 <= index < len(self._rows):
            return
        answer = QMessageBox.question(
            self,
            "Overlay oturumunu kaldır",
            "Yalnızca kaydedilmiş hizalama ayarları silinecek; DICOM dosyalarına dokunulmayacak.\n\nDevam edilsin mi?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.repo.delete_comparison_session(int(self._rows[index]["id"]))
        self.repo.record_audit_event(self.patient_id, "overlay_session_deleted", f"Kayıt #{self._rows[index]['id']}")
        self.load_sessions()

    def _edit_note(self) -> None:
        index = self.table.currentRow()
        if not 0 <= index < len(self._rows):
            return
        row = self._rows[index]
        note, accepted = QInputDialog.getMultiLineText(
            self, "Overlay notu", "Karşılaştırma notu:", str(row.get("notes", ""))
        )
        if not accepted:
            return
        self.repo.update_comparison_session_notes(int(row["id"]), note)
        self.repo.record_audit_event(self.patient_id, "overlay_note_updated", f"Kayıt #{row['id']}")
        self.load_sessions()

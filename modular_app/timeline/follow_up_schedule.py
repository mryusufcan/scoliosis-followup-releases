from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QDialog, QHBoxLayout, QLabel, QLineEdit, QPushButton, QSpinBox,
    QTableWidget, QTableWidgetItem, QVBoxLayout,
)

from modular_app.database.exam_repository import ExamRepository


class FollowUpScheduleDialog(QDialog):
    """Read-only worklist for follow-up dates stored in local patient cards."""

    patient_selected = Signal(dict)

    def __init__(self, repository: ExamRepository, parent=None):
        super().__init__(parent)
        self.repository = repository
        self.all_rows: list[dict] = []
        self.rows: list[dict] = []
        self.setWindowTitle("Yaklaşan Kontroller")
        self.resize(820, 430)
        self.setStyleSheet("background:#242424;color:#ecf0f1;")

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<b>Yaklaşan / Gecikmiş Kontroller</b>  |  Yerel hasta kartlarındaki planlanan kontrol tarihleri"))
        controls = QHBoxLayout()
        controls.addWidget(QLabel("Gösterilecek dönem:"))
        self.days = QSpinBox()
        self.days.setRange(0, 365)
        self.days.setValue(30)
        self.days.setSuffix(" gün")
        self.days.valueChanged.connect(self.load)
        controls.addWidget(self.days)
        refresh = QPushButton("Yenile")
        refresh.clicked.connect(self.load)
        controls.addWidget(refresh)
        controls.addSpacing(8)
        controls.addWidget(QLabel("Durum:"))
        self.status_filter = QComboBox()
        self.status_filter.addItems(["Tümü", "Gecikmiş", "Bugün", "Yaklaşan", "Tarih hatalı"])
        self.status_filter.currentTextChanged.connect(self._apply_filters)
        controls.addWidget(self.status_filter)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Hasta adı veya ID ara")
        self.search.textChanged.connect(self._apply_filters)
        controls.addWidget(self.search)
        controls.addStretch()
        layout.addLayout(controls)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Hasta ID", "Hasta", "Planlanan kontrol", "Durum", "Tanı / başlık"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.cellDoubleClicked.connect(self._open_selected)
        layout.addWidget(self.table, 1)
        self.summary = QLabel()
        self.summary.setStyleSheet("color:#95a5a6;")
        layout.addWidget(self.summary)
        buttons = QHBoxLayout()
        open_button = QPushButton("Seçili Hastayı Aç")
        open_button.clicked.connect(self._open_selected)
        close_button = QPushButton("Kapat")
        close_button.clicked.connect(self.accept)
        buttons.addStretch(); buttons.addWidget(open_button); buttons.addWidget(close_button)
        layout.addLayout(buttons)
        self.load()

    def load(self, *_args) -> None:
        self.all_rows = self.repository.list_follow_up_schedule(self.days.value())
        self._apply_filters()

    def _apply_filters(self, *_args) -> None:
        selected = self.status_filter.currentText()
        query = self.search.text().strip().lower()
        def accepted(row: dict) -> bool:
            remaining = row.get("days_until")
            matches_status = (
                selected == "Tümü"
                or (selected == "Gecikmiş" and remaining is not None and int(remaining) < 0)
                or (selected == "Bugün" and remaining == 0)
                or (selected == "Yaklaşan" and remaining is not None and int(remaining) > 0)
                or (selected == "Tarih hatalı" and remaining is None)
            )
            return matches_status and (not query or query in str(row.get("patient_id", "")).lower() or query in str(row.get("patient_name", "")).lower())
        self.rows = [row for row in self.all_rows if accepted(row)]
        self.table.setRowCount(0)
        overdue = sum(1 for row in self.all_rows if row.get("days_until") is not None and int(row["days_until"]) < 0)
        today = sum(1 for row in self.all_rows if row.get("days_until") == 0)
        upcoming = sum(1 for row in self.all_rows if row.get("days_until") is not None and int(row["days_until"]) > 0)
        invalid = sum(1 for row in self.all_rows if row.get("days_until") is None)
        for index, row in enumerate(self.rows):
            self.table.insertRow(index)
            values = (
                row.get("patient_id", ""), row.get("patient_name", ""), row.get("next_follow_up_date", ""),
                row.get("status", ""), row.get("diagnosis", ""),
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if row.get("days_until") is not None and int(row["days_until"]) < 0:
                    item.setForeground(QColor("#e74c3c"))
                elif row.get("days_until") == 0:
                    item.setForeground(QColor("#f39c12"))
                self.table.setItem(index, column, item)
        self.summary.setText(
            f"Gösterilen: {len(self.rows)}  |  Gecikmiş: {overdue}  |  Bugün: {today}  |  Yaklaşan: {upcoming}  |  Tarih hatalı: {invalid}. "
            "Tarih biçimi geçersiz kayıtlar Hasta Kartı'ndan düzeltilebilir."
        )

    def _open_selected(self, *_args) -> None:
        index = self.table.currentRow()
        if 0 <= index < len(self.rows):
            self.patient_selected.emit(self.rows[index])
            self.accept()

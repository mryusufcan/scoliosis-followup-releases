from __future__ import annotations

import os
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QDialog, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QVBoxLayout,
)
from modular_app.database.exam_repository import ExamRepository
from modular_app.ui.ui_clarity import configure_action, create_context_banner


class ExamTimelineDialog(QDialog):
    """Non-invasive exam-history window driven by ExamRepository."""

    exam_selected = Signal(dict)

    def __init__(self, repository: ExamRepository, patient_id: str,
                 patient_name: str = "", parent=None):
        super().__init__(parent)
        self.repo = repository
        self.patient_id = str(patient_id or "")
        self._rows: list[dict] = []
        self.setWindowTitle("Tetkik Geçmişi")
        self.setObjectName("workflowDialog")
        self.resize(920, 520)

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        context_banner, self.context_label = create_context_banner(
            "Tetkik Geçmişi",
            f"{patient_name or 'Hasta'} · ID: {self.patient_id} · Bir tetkik seçin ve karşılaştırmaya gönderin.",
            object_name="workflowContextBanner",
        )
        root.addWidget(context_banner)
        title = QLabel(f"<b>{patient_name or 'Hasta'}</b>  |  PatientID: {self.patient_id}")
        title.setObjectName("dialogSubtitle")
        root.addWidget(title)

        self.demo_mode = QCheckBox("Demo modu: diğer hastaların tetkiklerini de göster")
        self.demo_mode.setToolTip("Sadece test amaçlıdır; klinik kullanımda kapalı bırakın.")
        self.demo_mode.toggled.connect(self.load_patient)
        root.addWidget(self.demo_mode)

        filters = QHBoxLayout()
        self.date_filter = QLineEdit()
        self.date_filter.setPlaceholderText("Tarih ara (YYYYMMDD)")
        self.date_filter.setToolTip("Örneğin 20260818 yazarak belirli tarihi filtreleyin")
        self.region_filter = QComboBox()
        self.region_filter.addItem("Tüm bölgeler")
        self.modality_filter = QComboBox()
        self.modality_filter.addItem("Tüm modaliteler")
        for control in (self.date_filter, self.region_filter, self.modality_filter):
            filters.addWidget(control)
        self.date_filter.textChanged.connect(self._apply_filters)
        self.region_filter.currentTextChanged.connect(self._apply_filters)
        self.modality_filter.currentTextChanged.connect(self._apply_filters)
        root.addLayout(filters)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Tarih", "Bölge", "Modalite", "Tetkik", "Dosya", "Not"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.cellDoubleClicked.connect(self._double_click)
        root.addWidget(self.table, 1)

        self.info = QLabel()
        self.info.setStyleSheet("color:#95a5a6;")
        root.addWidget(self.info)

        bottom = QHBoxLayout()
        # Seçim ana görüntü listesini değiştirmeden, üst penceredeki
        # karşılaştırma köprüsüne iletilir.
        self.open_btn = QPushButton("Seçili Tetkiki Karşılaştırmaya Gönder")
        configure_action(
            self.open_btn,
            label="Seçili tetkiki karşılaştırmaya gönder",
            role="primary",
            tooltip="Seçili tetkiki ana çalışma alanında karşılaştırma için aç",
        )
        self.open_btn.clicked.connect(self._emit_selected)
        self.open_btn.setEnabled(False)
        self.table.itemSelectionChanged.connect(lambda: self.open_btn.setEnabled(self.table.currentRow() >= 0))
        close_btn = QPushButton("Kapat")
        configure_action(close_btn, label="Pencereyi kapat", role="quiet", tooltip="Bu pencereyi kapat")
        close_btn.clicked.connect(self.close)
        bottom.addStretch()
        bottom.addWidget(self.open_btn)
        bottom.addWidget(close_btn)
        root.addLayout(bottom)

        self.load_patient()

    def load_patient(self) -> None:
        self._rows = self.repo.list_exams() if self.demo_mode.isChecked() else self.repo.list_patient_exams(self.patient_id)
        self._refresh_filter_options()
        self._apply_filters()

    def _refresh_filter_options(self) -> None:
        region = self.region_filter.currentText()
        modality = self.modality_filter.currentText()
        regions = sorted({str(row.get("body_part", "")).strip() for row in self._rows if row.get("body_part")})
        modalities = sorted({str(row.get("modality", "")).strip() for row in self._rows if row.get("modality")})
        self.region_filter.blockSignals(True)
        self.modality_filter.blockSignals(True)
        self.region_filter.clear(); self.region_filter.addItem("Tüm bölgeler"); self.region_filter.addItems(regions)
        self.modality_filter.clear(); self.modality_filter.addItem("Tüm modaliteler"); self.modality_filter.addItems(modalities)
        self.region_filter.setCurrentText(region if region in regions else "Tüm bölgeler")
        self.modality_filter.setCurrentText(modality if modality in modalities else "Tüm modaliteler")
        self.region_filter.blockSignals(False)
        self.modality_filter.blockSignals(False)

    def _apply_filters(self) -> None:
        date = self.date_filter.text().strip()
        region = self.region_filter.currentText()
        modality = self.modality_filter.currentText()
        visible = [
            row for row in self._rows
            if (not date or date in str(row.get("exam_date", "")))
            and (region == "Tüm bölgeler" or str(row.get("body_part", "")) == region)
            and (modality == "Tüm modaliteler" or str(row.get("modality", "")) == modality)
        ]
        self.table.setRowCount(0)
        for row in visible:
            r = self.table.rowCount()
            self.table.insertRow(r)
            values = [
                row.get("exam_date", ""), row.get("body_part", ""),
                row.get("modality", ""), row.get("study_description", ""),
                row.get("dicom_path", ""), row.get("notes", ""),
            ]
            for c, value in enumerate(values):
                item = QTableWidgetItem(str(value or ""))
                item.setData(Qt.ItemDataRole.UserRole, row.get("id"))
                self.table.setItem(r, c, item)
        if self.demo_mode.isChecked():
            self.info.setText(f"Demo modu: {len(visible)} tetkik listeleniyor.")
        else:
            self.info.setText(f"{len(visible)} tetkik listeleniyor.")

    def _emit_selected(self) -> None:
        row = self.table.currentRow()
        filtered = self._filtered_rows()
        if 0 <= row < len(filtered):
            self.exam_selected.emit(filtered[row])
            self.accept()

    def _double_click(self, row: int, _column: int) -> None:
        filtered = self._filtered_rows()
        if 0 <= row < len(filtered):
            self.exam_selected.emit(filtered[row])
            self.accept()

    def _filtered_rows(self) -> list[dict]:
        date, region, modality = self.date_filter.text().strip(), self.region_filter.currentText(), self.modality_filter.currentText()
        return [row for row in self._rows if (not date or date in str(row.get("exam_date", ""))) and (region == "Tüm bölgeler" or str(row.get("body_part", "")) == region) and (modality == "Tüm modaliteler" or str(row.get("modality", "")) == modality)]

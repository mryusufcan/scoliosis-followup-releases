from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from modular_app.database.exam_repository import ExamRepository
from modular_app.domain.measurement_adapter import LegacyCobbRepositoryAdapter
from modular_app.ui.ui_clarity import configure_action
from modular_app.timeline.cobb_trend import CobbTrendWidget, MetricCard, _date_text
from modular_app.timeline.longitudinal_center import CurveSeries, build_snapshot, curve_label


class LongitudinalCenterDialog(QDialog):
    """Hasta ve Cobb eğrilerini aynı ekranda izleyen read-only takip merkezi."""

    def __init__(
        self,
        repository: ExamRepository,
        patient_id: str = "",
        *,
        activate_viewer_path: Callable[[str], None] | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.repository = repository
        self.adapter = LegacyCobbRepositoryAdapter(repository)
        self.activate_viewer_path = activate_viewer_path
        self.patient_id = str(patient_id or "")
        self.snapshot = build_snapshot(self.patient_id, [])
        self.selected_series: CurveSeries | None = None

        self.setWindowTitle("Longitudinal Takip Merkezi")
        self.setObjectName("workflowDialog")
        self.resize(1060, 720)
        self.setMinimumSize(900, 620)
        self.setStyleSheet(
            "QDialog { background:#242424; color:#ecf0f1; }"
            "QLabel { color:#bdc3c7; }"
            "QComboBox { background:#303030; color:#ecf0f1; border:1px solid #4a4a4a; border-radius:5px; padding:6px 8px; }"
            "QCheckBox { color:#bdc3c7; }"
            "QPushButton { background:#34495e; color:white; border:none; border-radius:5px; padding:7px 12px; }"
            "QPushButton:hover { background:#3e5870; }"
            "QPushButton:disabled { background:#303030; color:#777; }"
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(10)

        header = QHBoxLayout()
        title = QLabel("<b>Longitudinal Takip Merkezi</b>")
        title.setStyleSheet("font-size:18px; color:#ecf0f1;")
        header.addWidget(title)
        header.addSpacing(12)
        header.addWidget(QLabel("Hasta:"))
        self.patient_combo = QComboBox()
        self.patient_combo.setMinimumWidth(230)
        self.patient_combo.currentIndexChanged.connect(self._patient_changed)
        header.addWidget(self.patient_combo)
        header.addWidget(QLabel("Eğri:"))
        self.curve_combo = QComboBox()
        self.curve_combo.setMinimumWidth(240)
        self.curve_combo.currentIndexChanged.connect(self._curve_changed)
        header.addWidget(self.curve_combo)
        self.locked_only = QCheckBox("Yalnızca doğrulanmış")
        self.locked_only.toggled.connect(self._refresh)
        header.addWidget(self.locked_only)
        refresh = QPushButton("Veriyi Yenile")
        configure_action(refresh, label="Longitudinal takip verisini yenile", role="secondary", tooltip="Hasta ve eğri ölçümlerini yeniden yükle")
        refresh.clicked.connect(self._reload)
        header.addWidget(refresh)
        header.addStretch()
        root.addLayout(header)

        self.patient_summary = QLabel()
        self.patient_summary.setStyleSheet(
            "background:#2b2b2b; color:#95a5a6; border:1px solid #3b3b3b; "
            "border-radius:6px; padding:8px;"
        )
        self.patient_summary.setWordWrap(True)
        root.addWidget(self.patient_summary)

        cards = QGridLayout()
        cards.setHorizontalSpacing(8)
        cards.setVerticalSpacing(8)
        self.first_card = MetricCard("İlk ölçüm")
        self.latest_card = MetricCard("Son ölçüm")
        self.change_card = MetricCard("Toplam değişim")
        self.rate_card = MetricCard("Yıllık değişim")
        self.repeat_card = MetricCard("Tekrar uyarısı")
        self.count_card = MetricCard("Zaman noktası")
        for column, card in enumerate(
            (self.first_card, self.latest_card, self.change_card, self.rate_card, self.repeat_card, self.count_card)
        ):
            cards.addWidget(card, 0, column)
        root.addLayout(cards)

        self.chart = CobbTrendWidget([], self)
        root.addWidget(self.chart, 1)

        footer = QHBoxLayout()
        self.info_label = QLabel(
            "Yeşil: doğrulanmış/kilitli ölçüm · Turuncu: taslak ölçüm. "
            "Sayısal değişim klinik tanı veya prognoz değildir."
        )
        self.info_label.setWordWrap(True)
        self.info_label.setStyleSheet("color:#95a5a6; font-size:10px;")
        footer.addWidget(self.info_label, 1)
        self.overlay_button = QPushButton("Son Tetkiki Overlay'e Gönder")
        configure_action(self.overlay_button, label="Son tetkiki Overlay'e gönder", role="primary", tooltip="Seçili eğrinin son DICOM tetkikini ana çalışma alanında Overlay için aç")
        self.overlay_button.setEnabled(False)
        self.overlay_button.clicked.connect(self._send_to_overlay)
        footer.addWidget(self.overlay_button)
        close_button = QPushButton("Kapat")
        configure_action(close_button, label="Pencereyi kapat", role="quiet", tooltip="Bu pencereyi kapat")
        close_button.clicked.connect(self.close)
        footer.addWidget(close_button)
        root.addLayout(footer)

        self._populate_patients(preferred=self.patient_id)
        self._reload()

    def _populate_patients(self, preferred: str = "") -> None:
        rows = self.repository.list_patients()
        patient_ids = {str(row.get("patient_id", "")) for row in rows}
        if preferred and preferred not in patient_ids:
            rows.insert(0, {"patient_id": preferred, "patient_name": "", "exam_count": 0})

        self.patient_combo.blockSignals(True)
        self.patient_combo.clear()
        for row in rows:
            patient_id = str(row.get("patient_id", "") or "")
            name = str(row.get("patient_name", "") or "").strip()
            exam_count = int(row.get("exam_count", 0) or 0)
            label = f"{name} | {patient_id}" if name else patient_id
            if exam_count:
                label += f" ({exam_count} tetkik)"
            self.patient_combo.addItem(label, patient_id)
        target = preferred or (str(rows[0].get("patient_id", "")) if rows else "")
        index = self.patient_combo.findData(target)
        self.patient_combo.setCurrentIndex(index if index >= 0 else -1)
        self.patient_combo.blockSignals(False)
        self.patient_id = target

    def _patient_changed(self, index: int) -> None:
        if index < 0:
            self.patient_id = ""
        else:
            self.patient_id = str(self.patient_combo.itemData(index) or "")
        self._reload()

    def _reload(self) -> None:
        current_key = self.curve_combo.currentData()
        records = self.adapter.list_measurements(self.patient_id) if self.patient_id else []
        self.snapshot = build_snapshot(self.patient_id, records, locked_only=self.locked_only.isChecked())
        self._populate_curve_filter(current_key)
        self._refresh()

    def _populate_curve_filter(self, preferred_key=None) -> None:
        self.curve_combo.blockSignals(True)
        self.curve_combo.clear()
        for item in self.snapshot.series:
            self.curve_combo.addItem(curve_label(item.key), item.key)
        if self.snapshot.series:
            index = self.curve_combo.findData(preferred_key)
            self.curve_combo.setCurrentIndex(index if index >= 0 else 0)
        else:
            self.curve_combo.addItem("Kayıtlı Cobb eğrisi yok", None)
        self.curve_combo.blockSignals(False)

    def _curve_changed(self, _index: int) -> None:
        self._refresh()

    def _refresh(self) -> None:
        key = self.curve_combo.currentData()
        self.selected_series = next((item for item in self.snapshot.series if item.key == key), None)
        series = self.selected_series
        rows = [self._chart_row(record) for record in series.records] if series else []
        self.chart.set_rows(rows)
        self._update_cards(series)
        self.patient_summary.setText(
            f"Hasta: {self.patient_id or '—'} | "
            f"{len(self.snapshot.series)} eğri | {self.snapshot.total_measurements} zaman noktası | "
            f"{self.snapshot.total_hidden_repeats} aynı tarih tekrarı gizlendi."
        )
        latest = series.latest if series else None
        self.overlay_button.setEnabled(bool(latest and latest.source_context.dicom_path))

    @staticmethod
    def _chart_row(record) -> dict:
        return {
            "angle_degrees": record.value,
            "exam_date": record.exam_date,
            "is_locked": record.status.value == "verified",
            "upper_vertebra": record.upper_vertebra,
            "lower_vertebra": record.lower_vertebra,
            "curve_direction": record.curve_direction,
            "dicom_path": record.source_context.dicom_path,
        }

    def _update_cards(self, series: CurveSeries | None) -> None:
        cards = (self.first_card, self.latest_card, self.change_card, self.rate_card, self.repeat_card, self.count_card)
        if series is None or not series.records:
            for card in cards:
                card.set_value("—")
            self.repeat_card.set_value("Yok", "Aynı tarihte tekrar ölçüm yok", "#2ecc71")
            return

        first, latest = series.first, series.latest
        assert first is not None and latest is not None
        self.first_card.set_value(f"{first.value:.2f}°", _date_text(first.exam_date))
        self.latest_card.set_value(f"{latest.value:.2f}°", _date_text(latest.exam_date))

        delta = series.delta
        if delta is None:
            self.change_card.set_value("—", "En az iki zaman noktası gerekir")
        else:
            self.change_card.set_value(
                f"{delta:+.2f}°",
                "Sayısal fark; klinik yorum değildir",
                "#2ecc71" if delta < 0 else "#e67e22" if delta > 0 else "#bdc3c7",
            )

        rate = series.annualized_delta
        self.rate_card.set_value(
            f"{rate:+.2f}°/yıl" if rate is not None else "—",
            f"{series.date_span_days} gün üzerinden" if rate is not None else "Tarih aralığı hesaplanamadı",
        )
        if series.hidden_repeat_count:
            self.repeat_card.set_value(
                str(series.hidden_repeat_count),
                "Aynı tarihli tekrar grafikte tek temsilciyle gösterildi",
                "#f39c12",
            )
        else:
            self.repeat_card.set_value("Yok", "Aynı tarihte tekrar ölçüm yok", "#2ecc71")
        self.count_card.set_value(str(len(series.records)), "tekil sınav tarihi")

    def _send_to_overlay(self) -> None:
        if self.selected_series is None or self.selected_series.latest is None:
            return
        path = self.selected_series.latest.source_context.dicom_path
        if path and self.activate_viewer_path is not None:
            self.activate_viewer_path(path)
            self.info_label.setText("Son longitudinal ölçüm çalışma alanındaki Overlay akışına gönderildi.")


def open_longitudinal_center(
    repository: ExamRepository,
    patient_id: str = "",
    *,
    activate_viewer_path: Callable[[str], None] | None = None,
    parent=None,
) -> LongitudinalCenterDialog:
    dialog = LongitudinalCenterDialog(
        repository,
        patient_id,
        activate_viewer_path=activate_viewer_path,
        parent=parent,
    )
    dialog.show()
    dialog.raise_()
    dialog.activateWindow()
    return dialog

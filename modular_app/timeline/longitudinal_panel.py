"""İlerleme ve Takip Paneli QWidget'i.

Panel, LongitudinalService snapshot'ını aynı anda metrik kartlarına,
PyQtGraph trend görünümüne ve QAbstractTableModel tabanlı zaman çizelgesine
aktarır. Ana pencereyle bağlantı yalnızca sinyaller üzerinden yapılır.
"""
from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QAbstractItemModel, QItemSelectionModel, Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from modular_app.database.exam_repository import ExamRepository
from modular_app.timeline.cobb_trend import MetricCard
from modular_app.timeline.longitudinal_models import (
    ExamTimelineItem,
    FilterState,
    PanelSnapshot,
)
from modular_app.timeline.longitudinal_service import LongitudinalService, LongitudinalServiceError
from modular_app.timeline.timeline_model import ExamTimelineTableModel
from modular_app.timeline.trend_chart import CobbTrendPlot
from modular_app.ui.ui_clarity import configure_action, create_context_banner


class LongitudinalPanel(QWidget):
    """Hasta/eğri seçimi, trend ve tetkik zaman çizelgesini birleştiren panel."""

    exam_open_requested = Signal(object)
    overlay_requested = Signal(object)
    measurement_requested = Signal(object)
    csv_export_requested = Signal(object)
    pdf_export_requested = Signal(object)
    error_occurred = Signal(str)

    def __init__(
        self,
        repository: ExamRepository,
        *,
        patient_id: str = "",
        service: LongitudinalService | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.repository = repository
        self.service = service or LongitudinalService(repository)
        self.patient_id = str(patient_id or "")
        self.snapshot: PanelSnapshot | None = None
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.setInterval(160)
        self._refresh_timer.timeout.connect(self._refresh_snapshot)

        self.setObjectName("longitudinalPanel")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._build_ui()
        self.load_patients(preferred_patient_id=self.patient_id)

    def _build_ui(self) -> None:
        self.setStyleSheet(
            "QWidget#longitudinalPanel { background:#11161D; color:#F1F5F9; }"
            "QFrame#longitudinalContext { background:#171E27; border:1px solid #2A3542; border-radius:8px; }"
            "QFrame#longitudinalSection { background:#171E27; border:1px solid #2A3542; border-radius:8px; }"
            "QLabel { color:#AAB7C5; }"
            "QComboBox, QLineEdit { background:#1E2833; color:#F1F5F9; border:1px solid #2A3542; border-radius:4px; padding:5px 7px; }"
            "QComboBox:focus, QLineEdit:focus { border:1px solid #36C5D8; }"
            "QPushButton { background:#1E2833; color:#F1F5F9; border:1px solid #2A3542; border-radius:4px; padding:6px 10px; }"
            "QPushButton:hover { background:#263846; border-color:#36C5D8; }"
            "QPushButton:disabled { color:#718096; background:#151C24; }"
            "QCheckBox { color:#AAB7C5; spacing:5px; }"
            "QTableView { background:#0B0F14; alternate-background-color:#111923; color:#F1F5F9; border:1px solid #2A3542; gridline-color:#25303B; selection-background-color:#17424D; selection-color:#F1F5F9; }"
            "QHeaderView::section { background:#1E2833; color:#AAB7C5; padding:7px 5px; border:0px; border-bottom:1px solid #2A3542; font-weight:600; }"
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        banner, self.context_label = create_context_banner(
            "İlerleme ve Takip Paneli",
            "Hasta ve eğri seçin; grafik ve tetkik zaman çizelgesi aynı veri snapshot'ı ile güncellenir.",
            object_name="workflowContextBanner",
        )
        root.addWidget(banner)

        root.addWidget(self._build_filter_frame())
        root.addWidget(self._build_context_frame())
        root.addWidget(self._build_metric_frame())
        root.addWidget(self._build_chart_frame(), 2)
        root.addWidget(self._build_timeline_frame(), 2)
        root.addWidget(self._build_action_bar())

    def _build_filter_frame(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("longitudinalSection")
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(6)

        layout.addWidget(QLabel("Hasta:"))
        self.patient_combo = QComboBox()
        self.patient_combo.setMinimumWidth(240)
        self.patient_combo.currentIndexChanged.connect(self._patient_changed)
        layout.addWidget(self.patient_combo)

        layout.addWidget(QLabel("Eğri:"))
        self.curve_combo = QComboBox()
        self.curve_combo.setMinimumWidth(220)
        self.curve_combo.currentIndexChanged.connect(self._curve_changed)
        layout.addWidget(self.curve_combo)

        self.locked_only = QCheckBox("Yalnızca doğrulanmış")
        self.locked_only.toggled.connect(self._schedule_refresh)
        layout.addWidget(self.locked_only)

        layout.addWidget(QLabel("Tarih:"))
        self.date_from_edit = QLineEdit()
        self.date_from_edit.setPlaceholderText("Başlangıç YYYYMMDD")
        self.date_from_edit.setMaximumWidth(150)
        self.date_from_edit.textChanged.connect(self._schedule_refresh)
        layout.addWidget(self.date_from_edit)
        self.date_to_edit = QLineEdit()
        self.date_to_edit.setPlaceholderText("Bitiş YYYYMMDD")
        self.date_to_edit.setMaximumWidth(150)
        self.date_to_edit.textChanged.connect(self._schedule_refresh)
        layout.addWidget(self.date_to_edit)

        layout.addWidget(QLabel("Ara:"))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Tetkik, seri, bölge veya dosya")
        self.search_edit.setMinimumWidth(180)
        self.search_edit.textChanged.connect(self._schedule_refresh)
        layout.addWidget(self.search_edit, 1)

        self.refresh_button = QPushButton("Yenile")
        configure_action(
            self.refresh_button,
            label="Takip verisini yenile",
            role="secondary",
            tooltip="Seçili hasta ve eğri için takip verisini yeniden yükle",
        )
        self.refresh_button.clicked.connect(self._refresh_snapshot)
        layout.addWidget(self.refresh_button)
        return frame

    def _build_context_frame(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("longitudinalContext")
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(10, 7, 10, 7)
        layout.setSpacing(12)
        self.patient_summary = QLabel("Hasta seçilmedi.")
        self.patient_summary.setWordWrap(True)
        layout.addWidget(self.patient_summary, 1)
        self.warning_label = QLabel("")
        self.warning_label.setWordWrap(True)
        self.warning_label.setStyleSheet("color:#F2B84B;")
        layout.addWidget(self.warning_label, 1)
        return frame

    def _build_metric_frame(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("longitudinalSection")
        layout = QGridLayout(frame)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setHorizontalSpacing(7)
        layout.setVerticalSpacing(4)
        self.first_card = MetricCard("İlk ölçüm", frame)
        self.latest_card = MetricCard("Son ölçüm", frame)
        self.change_card = MetricCard("Toplam değişim", frame)
        self.rate_card = MetricCard("Yıllık fark", frame)
        self.repeat_card = MetricCard("Tekrar", frame)
        self.count_card = MetricCard("Zaman noktası", frame)
        for column, card in enumerate(
            (
                self.first_card,
                self.latest_card,
                self.change_card,
                self.rate_card,
                self.repeat_card,
                self.count_card,
            )
        ):
            layout.addWidget(card, 0, column)
        return frame

    def _build_chart_frame(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("longitudinalSection")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(8, 6, 8, 8)
        layout.setSpacing(4)
        title_row = QHBoxLayout()
        title = QLabel("<b>Cobb Trend Grafiği</b>")
        title_row.addWidget(title)
        title_row.addStretch()
        self.chart_status = QLabel("Yeşil: doğrulandı · Amber: taslak")
        self.chart_status.setStyleSheet("color:#718096; font-size:10px;")
        title_row.addWidget(self.chart_status)
        layout.addLayout(title_row)
        self.chart = CobbTrendPlot(frame)
        self.chart.point_activated.connect(self._on_point_activated)
        self.chart.point_hovered.connect(self._on_point_hovered)
        layout.addWidget(self.chart, 1)
        return frame

    def _build_timeline_frame(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("longitudinalSection")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(8, 6, 8, 8)
        layout.setSpacing(4)
        header = QHBoxLayout()
        title = QLabel("<b>Tetkik Zaman Çizelgesi</b>")
        header.addWidget(title)
        header.addStretch()
        self.timeline_status = QLabel("0 tetkik")
        self.timeline_status.setStyleSheet("color:#718096; font-size:10px;")
        header.addWidget(self.timeline_status)
        layout.addLayout(header)

        self.timeline_model = ExamTimelineTableModel(parent=frame)
        self.timeline_table = QTableView(frame)
        self.timeline_table.setModel(self.timeline_model)
        self.timeline_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.timeline_table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.timeline_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.timeline_table.setSortingEnabled(True)
        self.timeline_table.setAlternatingRowColors(True)
        self.timeline_table.setWordWrap(False)
        self.timeline_table.setMinimumHeight(190)
        self.timeline_table.verticalHeader().setVisible(False)
        self.timeline_table.horizontalHeader().setStretchLastSection(False)
        self.timeline_table.horizontalHeader().setDefaultSectionSize(110)
        self.timeline_table.setColumnWidth(0, 105)
        self.timeline_table.setColumnWidth(1, 100)
        self.timeline_table.setColumnWidth(2, 85)
        self.timeline_table.setColumnWidth(3, 210)
        self.timeline_table.setColumnWidth(4, 95)
        self.timeline_table.setColumnWidth(5, 105)
        self.timeline_table.setColumnWidth(6, 75)
        self.timeline_table.setColumnWidth(7, 70)
        self.timeline_table.doubleClicked.connect(self._open_index)
        self.timeline_table.selectionModel().selectionChanged.connect(self._selection_changed)
        layout.addWidget(self.timeline_table, 1)
        return frame

    def _build_action_bar(self) -> QWidget:
        bar = QWidget(self)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        self.open_button = QPushButton("Seçili Tetkiki Aç")
        configure_action(
            self.open_button,
            label="Seçili tetkiki aç",
            role="secondary",
            tooltip="Tek seçili tetkiki ana görüntüleyicide aç",
        )
        self.open_button.clicked.connect(self._open_selected)
        layout.addWidget(self.open_button)

        self.overlay_button = QPushButton("İki Tetkiki Overlay'e Gönder")
        configure_action(
            self.overlay_button,
            label="İki tetkiki Overlay'e gönder",
            role="primary",
            tooltip="Tam iki seçili tetkiki mevcut Overlay akışına gönder",
        )
        self.overlay_button.clicked.connect(self._send_selected_to_overlay)
        layout.addWidget(self.overlay_button)

        self.measurement_button = QPushButton("Ölçüm Ayrıntısı")
        self.measurement_button.clicked.connect(self._show_selected_measurement)
        layout.addWidget(self.measurement_button)

        self.csv_button = QPushButton("CSV")
        self.csv_button.setToolTip("Filtrelenmiş zaman çizelgesini CSV dışa aktarımına gönder")
        self.csv_button.clicked.connect(lambda: self.csv_export_requested.emit(self.snapshot))
        layout.addWidget(self.csv_button)
        self.pdf_button = QPushButton("PDF")
        self.pdf_button.setToolTip("Filtrelenmiş takip özetini PDF dışa aktarımına gönder")
        self.pdf_button.clicked.connect(lambda: self.pdf_export_requested.emit(self.snapshot))
        layout.addWidget(self.pdf_button)

        layout.addStretch()
        self.action_status = QLabel("")
        self.action_status.setWordWrap(True)
        self.action_status.setStyleSheet("color:#AAB7C5;")
        layout.addWidget(self.action_status, 1)
        self._refresh_action_state()
        return bar

    def load_patients(self, *, preferred_patient_id: str = "") -> None:
        options = self.service.list_patients()
        preferred = str(preferred_patient_id or self.patient_id or "")
        self.patient_combo.blockSignals(True)
        self.patient_combo.clear()
        for option in options:
            self.patient_combo.addItem(option.label, option.patient_id)
        if preferred and self.patient_combo.findData(preferred) < 0:
            self.patient_combo.insertItem(0, preferred, preferred)
        index = self.patient_combo.findData(preferred)
        if index < 0 and self.patient_combo.count():
            index = 0
        self.patient_combo.setCurrentIndex(index)
        self.patient_combo.blockSignals(False)
        self.patient_id = str(self.patient_combo.currentData() or "")
        self._populate_curves()
        self._refresh_snapshot()

    def set_patient(self, patient_id: str) -> None:
        index = self.patient_combo.findData(str(patient_id or ""))
        if index >= 0:
            self.patient_combo.setCurrentIndex(index)
        else:
            self.patient_id = str(patient_id or "")
            self._populate_curves()
            self._refresh_snapshot()

    def set_snapshot(self, snapshot: PanelSnapshot) -> None:
        """Dışarıdan hazırlanmış snapshot'ı panel bileşenlerine uygula."""
        self.snapshot = snapshot
        self.patient_id = snapshot.patient_id
        self._update_from_snapshot(snapshot)

    def _patient_changed(self, _index: int) -> None:
        self.patient_id = str(self.patient_combo.currentData() or "")
        self._populate_curves()
        self._refresh_snapshot()

    def _curve_changed(self, _index: int) -> None:
        self._refresh_snapshot()

    def _populate_curves(self) -> None:
        if not self.patient_id:
            self.curve_combo.blockSignals(True)
            self.curve_combo.clear()
            self.curve_combo.addItem("Hasta seçilmedi", None)
            self.curve_combo.blockSignals(False)
            return
        try:
            options = self.service.list_curves(
                self.patient_id,
                locked_only=self.locked_only.isChecked(),
            )
        except LongitudinalServiceError as exc:
            self._show_error(exc.message)
            options = ()
        current_key = self.curve_combo.currentData()
        self.curve_combo.blockSignals(True)
        self.curve_combo.clear()
        for option in options:
            self.curve_combo.addItem(option.label, option.key)
        if not options:
            self.curve_combo.addItem("Kayıtlı Cobb eğrisi yok", None)
        preferred_index = self.curve_combo.findData(current_key)
        self.curve_combo.setCurrentIndex(preferred_index if preferred_index >= 0 else 0)
        self.curve_combo.blockSignals(False)

    def _schedule_refresh(self, *_args) -> None:
        self._refresh_timer.start()

    def _refresh_snapshot(self) -> None:
        if not self.patient_id:
            self.snapshot = None
            self.timeline_model.clear()
            self.chart.set_points(())
            self._update_empty_state()
            return
        filters = FilterState(
            patient_id=self.patient_id,
            curve_key=self.curve_combo.currentData(),
            locked_only=self.locked_only.isChecked(),
            date_from=self.date_from_edit.text().strip(),
            date_to=self.date_to_edit.text().strip(),
            search_text=self.search_edit.text().strip(),
        )
        try:
            snapshot = self.service.load_snapshot(filters)
        except LongitudinalServiceError as exc:
            self.snapshot = None
            self._show_error(exc.message)
            self.timeline_model.clear()
            self.chart.set_points(())
            self._update_empty_state()
            return
        self.set_snapshot(snapshot)

    def _update_from_snapshot(self, snapshot: PanelSnapshot) -> None:
        self.timeline_model.set_rows(snapshot.exams)
        self.chart.set_points(snapshot.points)
        self._update_metrics(snapshot)
        selected_label = snapshot.selected_series.label if snapshot.selected_series else "eğri seçilmedi"
        self.patient_summary.setText(
            f"Hasta: {snapshot.patient_name or '—'} | PatientID: {snapshot.patient_id or '—'} | "
            f"Seçili: {selected_label} | {snapshot.total_exams} tetkik | "
            f"{snapshot.total_measurements} zaman noktası | {snapshot.total_hidden_repeats} tekrar gizlendi"
        )
        self.timeline_status.setText(f"{snapshot.total_exams} tetkik")
        warnings = list(snapshot.warnings)
        self.warning_label.setText(" | ".join(warnings))
        self.warning_label.setVisible(bool(warnings))
        self.context_label.setText(
            "Grafik noktası veya zaman çizelgesi satırı seçilebilir. Tek tetkik açılır; iki tetkik Overlay'e gönderilir."
        )
        self.action_status.setText("")
        self._refresh_action_state()

    def _update_empty_state(self) -> None:
        for card in (
            self.first_card,
            self.latest_card,
            self.change_card,
            self.rate_card,
            self.repeat_card,
            self.count_card,
        ):
            card.set_value("—")
        self.patient_summary.setText("Hasta veya kayıtlı longitudinal ölçüm bulunamadı.")
        self.timeline_status.setText("0 tetkik")
        self.warning_label.setText("")
        self.warning_label.setVisible(False)
        self._refresh_action_state()

    def _update_metrics(self, snapshot: PanelSnapshot) -> None:
        summary = snapshot.summary
        if summary.first_value is None or summary.latest_value is None:
            self.first_card.set_value("—")
            self.latest_card.set_value("—")
            self.change_card.set_value("—", "En az iki farklı tarih gerekir")
            self.rate_card.set_value("—", "Tarih aralığı hesaplanamadı")
            self.repeat_card.set_value(
                str(summary.hidden_repeat_count),
                "Aynı tarihli tekrar" if summary.hidden_repeat_count else "Tekrar yok",
                "#F2B84B" if summary.hidden_repeat_count else "#43C59E",
            )
            self.count_card.set_value(str(summary.measurement_count), "tekil tarih")
            return

        self.first_card.set_value(f"{summary.first_value:.2f}°", _date_text(summary.first_date))
        self.latest_card.set_value(f"{summary.latest_value:.2f}°", _date_text(summary.latest_date))
        delta = summary.delta
        if delta is None:
            self.change_card.set_value("—", "En az iki farklı tarih gerekir")
        else:
            self.change_card.set_value(
                f"{delta:+.2f}°",
                "Sayısal fark; klinik yorum değildir",
                "#43C59E" if delta < 0 else "#F2B84B" if delta > 0 else "#AAB7C5",
            )
        self.rate_card.set_value(
            f"{summary.annualized_delta:+.2f}°/yıl" if summary.annualized_delta is not None else "—",
            f"{summary.date_span_days} gün üzerinden" if summary.date_span_days is not None else "Tarih aralığı hesaplanamadı",
        )
        self.repeat_card.set_value(
            str(summary.hidden_repeat_count),
            "Aynı tarihli tekrar" if summary.hidden_repeat_count else "Tekrar yok",
            "#F2B84B" if summary.hidden_repeat_count else "#43C59E",
        )
        self.count_card.set_value(str(summary.measurement_count), "tekil sınav tarihi")

    def _on_point_activated(self, point) -> None:
        self._select_exam_id(getattr(point, "exam_id", None))
        if getattr(point, "measurement_id", None) is not None:
            self.measurement_requested.emit(point)
        self.action_status.setText(
            f"Grafik noktası seçildi: {_date_text(getattr(point, 'exam_date', ''))} · "
            f"{float(getattr(point, 'value', 0.0)):.2f}°"
        )
        self._refresh_action_state()

    def _on_point_hovered(self, point) -> None:
        if point is not None:
            self.chart_status.setText(
                f"{_date_text(point.exam_date)} · {point.value:.2f}° · "
                f"{'doğrulandı' if str(point.status).casefold() == 'verified' else 'taslak'}"
            )
        else:
            self.chart_status.setText("Yeşil: doğrulandı · Amber: taslak")

    def _selection_changed(self, *_args) -> None:
        self._refresh_action_state()

    def _refresh_action_state(self) -> None:
        indexes = self.timeline_table.selectionModel().selectedRows() if hasattr(self, "timeline_table") else []
        items = [self.timeline_model.item_at(index.row()) for index in indexes]
        items = [item for item in items if item is not None]
        self.open_button.setEnabled(len(items) == 1 and bool(items[0].source_exists))
        self.overlay_button.setEnabled(len(items) == 2 and all(item.source_exists for item in items))
        self.measurement_button.setEnabled(len(items) == 1 and items[0].latest_measurement_id is not None)
        self.csv_button.setEnabled(self.snapshot is not None)
        self.pdf_button.setEnabled(self.snapshot is not None)

    def _selected_items(self) -> list[ExamTimelineItem]:
        indexes = self.timeline_table.selectionModel().selectedRows()
        items = [self.timeline_model.item_at(index.row()) for index in indexes]
        return [item for item in items if item is not None]

    def _open_index(self, index) -> None:
        item = self.timeline_model.item_at(index.row())
        if item is None:
            return
        self._select_exam_id(item.exam_id)
        self._open_selected()

    def _open_selected(self) -> None:
        items = self._selected_items()
        if len(items) != 1:
            self._show_error("Görüntüleyicide açmak için tek bir tetkik seçin.")
            return
        item = items[0]
        if not item.source_exists:
            self._show_error("Seçili tetkikin kaynak DICOM dosyası bulunamadı.")
            return
        self.exam_open_requested.emit(item)
        self.action_status.setText(f"Tetkik açma isteği gönderildi: {_date_text(item.exam_date)}")

    def _send_selected_to_overlay(self) -> None:
        items = self._selected_items()
        if len(items) != 2:
            self._show_error("Overlay için tam iki tetkik seçin.")
            return
        if not all(item.source_exists for item in items):
            self._show_error("Overlay için iki tetkikin de kaynak DICOM dosyası bulunmalıdır.")
            return
        self.overlay_requested.emit(items)
        self.action_status.setText("İki tetkik Overlay akışına gönderildi.")

    def _show_selected_measurement(self) -> None:
        items = self._selected_items()
        if len(items) != 1 or items[0].latest_measurement_id is None:
            self._show_error("Ölçüm ayrıntısı için ölçümü olan tek bir tetkik seçin.")
            return
        try:
            detail = self.service.get_measurement_detail(
                self.patient_id,
                items[0].latest_measurement_id,
            )
        except LongitudinalServiceError as exc:
            self._show_error(exc.message)
            return
        self.measurement_requested.emit(detail)
        self.action_status.setText(f"Ölçüm ayrıntısı seçildi: #{detail.measurement_id}")

    def _select_exam_id(self, exam_id: int | None) -> None:
        if exam_id is None:
            return
        for row in range(self.timeline_model.rowCount()):
            item = self.timeline_model.item_at(row)
            if item is not None and item.exam_id == int(exam_id):
                self.timeline_table.selectRow(row)
                self.timeline_table.scrollTo(self.timeline_model.index(row, 0))
                return

    def _show_error(self, message: str) -> None:
        self.error_occurred.emit(str(message))
        self.action_status.setText(str(message))
        self.warning_label.setText(str(message))
        self.warning_label.setVisible(True)


def _date_text(value: object) -> str:
    raw = str(value or "").strip()
    for fmt in ("%Y%m%d", "%Y-%m-%d"):
        try:
            from datetime import datetime

            return datetime.strptime(raw, fmt).strftime("%d.%m.%Y")
        except ValueError:
            pass
    return raw or "—"


class LongitudinalPanelDialog(QDialog):
    """LongitudinalPanel'i ana uygulama menüsünden açmak için pencere kabuğu."""

    exam_open_requested = Signal(object)
    overlay_requested = Signal(object)
    measurement_requested = Signal(object)
    csv_export_requested = Signal(object)
    pdf_export_requested = Signal(object)
    error_occurred = Signal(str)

    def __init__(
        self,
        repository: ExamRepository,
        *,
        patient_id: str = "",
        service: LongitudinalService | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("İlerleme ve Takip Paneli")
        self.setObjectName("workflowDialog")
        self.resize(1280, 900)
        self.setMinimumSize(1000, 700)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        self.panel = LongitudinalPanel(
            repository,
            patient_id=patient_id,
            service=service,
            parent=self,
        )
        layout.addWidget(self.panel)
        self.panel.exam_open_requested.connect(self.exam_open_requested)
        self.panel.overlay_requested.connect(self.overlay_requested)
        self.panel.measurement_requested.connect(self.measurement_requested)
        self.panel.csv_export_requested.connect(self.csv_export_requested)
        self.panel.pdf_export_requested.connect(self.pdf_export_requested)
        self.panel.error_occurred.connect(self.error_occurred)


__all__ = ["LongitudinalPanel", "LongitudinalPanelDialog"]

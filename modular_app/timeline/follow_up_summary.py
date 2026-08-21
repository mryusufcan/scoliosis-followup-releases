from __future__ import annotations

from pathlib import Path
from datetime import datetime

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QAbstractItemView, QDialog, QHBoxLayout, QLabel, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout

from modular_app.database.exam_repository import ExamRepository
from modular_app.ui.ui_clarity import configure_action, create_context_banner


def _parse_exam_date(value: object):
    raw = str(value or "").strip()
    if len(raw) == 8 and raw.isdigit():
        try:
            return datetime.strptime(raw, "%Y%m%d").date()
        except ValueError:
            return None
    return None


def _pair_text(row: dict) -> str:
    upper = str(row.get("upper_vertebra", "") or "").strip()
    lower = str(row.get("lower_vertebra", "") or "").strip()
    return f"{upper}–{lower}" if upper and lower else "—"


def _pair_summary_rows(repository: ExamRepository, patient_id: str) -> list[dict]:
    """Build one longitudinal summary row per end-vertebra pair."""
    try:
        threshold = abs(float(repository.get_setting("follow_up/cobb_alert_threshold", "5") or 5))
    except (TypeError, ValueError):
        threshold = 5.0

    series_map = repository.longitudinal_cobb_series(patient_id)
    summaries = []

    for (upper, lower, direction), series in sorted(series_map.items()):
        if not series:
            continue

        first = series[0]
        latest = series[-1]
        first_angle = float(first.get("angle_degrees", 0.0))
        latest_angle = float(latest.get("angle_degrees", 0.0))
        delta = latest_angle - first_angle

        first_date_obj = _parse_exam_date(first.get("exam_date"))
        latest_date_obj = _parse_exam_date(latest.get("exam_date"))
        days_between = None
        rate_per_year = None
        if first_date_obj is not None and latest_date_obj is not None:
            days_between = (latest_date_obj - first_date_obj).days
            if days_between > 0 and len(series) >= 2:
                rate_per_year = delta / days_between * 365.25

        summaries.append({
            "pair": f"{upper}–{lower}",
            "direction": direction if direction and direction != "Belirtilmedi" else "—",
            "first_date": str(first.get("exam_date", "") or "—"),
            "latest_date": str(latest.get("exam_date", "") or "—"),
            "first_angle": first_angle,
            "latest_angle": latest_angle,
            "delta": delta,
            "days_between": days_between,
            "rate_per_year": rate_per_year,
            "count": len(series),
            "latest_locked": bool(latest.get("is_locked")),
            "alert": len(series) >= 2 and abs(delta) >= threshold,
            "threshold": threshold,
        })

    return summaries


class FollowUpSummaryDialog(QDialog):
    """Read-only summary of a patient's exams and locally recorded follow-up data."""

    exam_selected = Signal(dict)
    exams_selected_for_overlay = Signal(list)

    def __init__(self, repository: ExamRepository, patient_id: str, patient_name: str = "", parent=None):
        super().__init__(parent)
        self.repository = repository
        self.patient_id = str(patient_id)
        self.setWindowTitle("Hasta Takip Özeti")
        self.setObjectName("workflowDialog")
        self.resize(1180, 620)

        layout = QVBoxLayout(self)
        label_name = patient_name or "Hasta"
        context_banner, self.context_label = create_context_banner(
            "Hasta Takip Özeti",
            f"{label_name} · PatientID: {patient_id} · Önce eğri özetini inceleyin, sonra tetkik seçin.",
            object_name="workflowContextBanner",
        )
        layout.addWidget(context_banner)
        subtitle = QLabel(f"<b>{label_name}</b>  |  PatientID: {patient_id}")
        subtitle.setObjectName("dialogSubtitle")
        layout.addWidget(subtitle)

        layout.addWidget(QLabel("<b>1. Eğri Bazlı Cobb Özeti</b>"))
        self.pair_table = QTableWidget(0, 11)
        self.pair_table.setHorizontalHeaderLabels([
            "Vertebra", "Eğri yönü", "İlk tarih", "Son tarih", "İlk Cobb", "Son Cobb",
            "Δ", "Süre", "°/yıl", "Ölçüm", "Durum"
        ])
        self.pair_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.pair_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.pair_table.horizontalHeader().setStretchLastSection(True)

        self.pair_rows = _pair_summary_rows(repository, patient_id)
        for summary in self.pair_rows:
            row_index = self.pair_table.rowCount()
            self.pair_table.insertRow(row_index)

            if summary["count"] < 2:
                delta_text = "—"
                status_text = "Tek ölçüm"
            else:
                delta_text = f"{summary['delta']:+.2f}°"
                status_text = (
                    f"⚠ Eşik aşıldı ({summary['threshold']:.1f}°)"
                    if summary["alert"]
                    else "Eşik içinde"
                )

            latest_text = f"{summary['latest_angle']:.2f}°"
            if summary["latest_locked"]:
                latest_text += " ✓"
            else:
                latest_text += " (taslak)"

            if summary["days_between"] is None or summary["days_between"] <= 0:
                duration_text = "—"
            elif summary["days_between"] < 365:
                duration_text = f"{summary['days_between']} gün"
            else:
                duration_text = f"{summary['days_between'] / 365.25:.2f} yıl"

            rate_text = (
                "—"
                if summary["rate_per_year"] is None
                else f"{summary['rate_per_year']:+.2f}°/yıl"
            )

            values = [
                summary["pair"],
                summary["direction"],
                summary["first_date"],
                summary["latest_date"],
                f"{summary['first_angle']:.2f}°",
                latest_text,
                delta_text,
                duration_text,
                rate_text,
                str(summary["count"]),
                status_text,
            ]

            for column, value in enumerate(values):
                self.pair_table.setItem(row_index, column, QTableWidgetItem(str(value)))

        self.pair_table.resizeColumnsToContents()
        self.pair_table.setMaximumHeight(190)
        layout.addWidget(self.pair_table)

        pair_alert_count = sum(1 for row in self.pair_rows if row["alert"])
        pair_note = (
            f"{len(self.pair_rows)} eğri serisi izleniyor"
            + (f" | {pair_alert_count} sayısal eşik uyarısı" if pair_alert_count else "")
            + ". Δ ve °/yıl yalnızca sayısal değişim göstergeleridir; klinik yorum veya tanı değildir."
        )
        pair_note_label = QLabel(pair_note)
        pair_note_label.setWordWrap(True)
        pair_note_label.setStyleSheet("color:#95a5a6;")
        layout.addWidget(pair_note_label)

        layout.addWidget(QLabel("<b>2. Tetkik Listesi — bir veya iki satır seçin</b>"))

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
            if angle is None:
                angle_text = "—"
            elif bool(row.get("latest_cobb_locked")):
                angle_text = f"{float(angle):.2f}°  ✓"
            else:
                angle_text = f"{float(angle):.2f}°  (taslak)"
            values = [
                row.get("exam_date", ""),
                row.get("body_part", ""),
                row.get("modality", ""),
                row.get("study_description", ""),
                Path(row.get("dicom_path", "")).name,
                angle_text,
                str(row.get("overlay_session_count", 0)),
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setData(256, row.get("id"))
                self.table.setItem(index, column, item)
        self.table.cellDoubleClicked.connect(self._open_selected)
        layout.addWidget(self.table)
        layout.addWidget(QLabel(f"{len(self.rows)} tetkik listeleniyor. ✓ işareti hekim/yönetici tarafından doğrulanıp kilitlenen ölçümü gösterir."))
        buttons = QHBoxLayout()
        open_button = QPushButton("Seçili Tetkiki Aç")
        configure_action(open_button, label="Seçili tetkiki aç", role="secondary", tooltip="Seçili tetkiki çalışma alanında aç")
        open_button.clicked.connect(self._open_selected)
        overlay_button = QPushButton("İki Tetkiki Overlay Karşılaştırmaya Gönder")
        configure_action(overlay_button, label="İki tetkiki Overlay karşılaştırmaya gönder", role="primary", tooltip="Tam iki seçili tetkiki Overlay karşılaştırma modunda aç")
        overlay_button.clicked.connect(self._send_selected_to_overlay)
        self.open_button = open_button
        self.overlay_button = overlay_button
        self.table.itemSelectionChanged.connect(self._refresh_action_state)
        self._refresh_action_state()
        buttons.addStretch()
        buttons.addWidget(open_button)
        buttons.addWidget(overlay_button)
        layout.addLayout(buttons)

    def _refresh_action_state(self) -> None:
        selected_count = len({item.row() for item in self.table.selectedItems()})
        self.open_button.setEnabled(selected_count == 1)
        self.overlay_button.setEnabled(selected_count == 2)
        if selected_count == 0:
            self.context_label.setText("Bir tetkik seçin; tek seçim açılır, iki seçim Overlay karşılaştırmaya gönderilir.")
        elif selected_count == 1:
            self.context_label.setText("1 tetkik seçildi. Açmak için seçili tetkiki açın veya ikinci tetkiki seçerek Overlay karşılaştırma yapın.")
        else:
            self.context_label.setText("2 tetkik seçildi. Overlay karşılaştırmaya gönderebilirsiniz.")

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

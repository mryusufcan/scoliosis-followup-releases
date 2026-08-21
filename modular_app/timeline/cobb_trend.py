from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from modular_app.database.exam_repository import ExamRepository
from modular_app.ui.ui_clarity import configure_action


def _date_text(value: object) -> str:
    """DICOM YYYYMMDD tarihini kullanıcı dostu biçime çevir."""
    raw = str(value or "").strip()
    if len(raw) == 8 and raw.isdigit():
        try:
            return datetime.strptime(raw, "%Y%m%d").strftime("%d.%m.%Y")
        except ValueError:
            pass
    return raw or "—"



def _pair_key(row: dict) -> tuple[str, str, str]:
    return (
        str(row.get("upper_vertebra", "") or "").strip(),
        str(row.get("lower_vertebra", "") or "").strip(),
        str(row.get("curve_direction", "") or "").strip(),
    )


def _pair_text(row: dict) -> str:
    upper, lower, direction = _pair_key(row)
    if not (upper and lower):
        return "Vertebra seçilmemiş"
    suffix = "" if not direction or direction == "Belirtilmedi" else f" | {direction}"
    return f"{upper}–{lower}{suffix}"



def _one_measurement_per_exam(rows: list[dict]) -> tuple[list[dict], int]:
    """Collapse repeat measurements from the same exam date for longitudinal trend."""
    by_date: dict[str, list[dict]] = {}
    for row in rows:
        key = str(row.get("exam_date", "") or "").strip()
        if not key:
            key = f"NO_DATE:{row.get('dicom_path', '')}"
        by_date.setdefault(key, []).append(row)

    selected: list[dict] = []
    hidden_repeat_count = 0

    for group in by_date.values():
        hidden_repeat_count += max(0, len(group) - 1)
        group_sorted = sorted(
            group,
            key=lambda row: (
                bool(row.get("is_locked")),
                str(row.get("created_at", "") or ""),
                int(row.get("id", 0) or 0),
            ),
            reverse=True,
        )
        selected.append(group_sorted[0])

    selected.sort(
        key=lambda row: (
            str(row.get("exam_date", "") or ""),
            str(row.get("created_at", "") or ""),
            int(row.get("id", 0) or 0),
        )
    )
    return selected, hidden_repeat_count


def _annualized_rate(rows: list[dict]) -> tuple[float | None, int | None]:
    if len(rows) < 2:
        return None, None
    first_raw = str(rows[0].get("exam_date", "") or "").strip()
    latest_raw = str(rows[-1].get("exam_date", "") or "").strip()
    if not (len(first_raw) == 8 and first_raw.isdigit() and len(latest_raw) == 8 and latest_raw.isdigit()):
        return None, None
    try:
        first_date = datetime.strptime(first_raw, "%Y%m%d").date()
        latest_date = datetime.strptime(latest_raw, "%Y%m%d").date()
    except ValueError:
        return None, None
    days = (latest_date - first_date).days
    if days <= 0:
        return None, days
    delta = float(rows[-1].get("angle_degrees", 0.0)) - float(rows[0].get("angle_degrees", 0.0))
    return delta / days * 365.25, days


class MetricCard(QFrame):
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setStyleSheet(
            "QFrame { background:#2d2d2d; border:1px solid #414141; border-radius:8px; }"
            "QLabel { border:none; background:transparent; }"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(2)

        self.title_label = QLabel(title)
        self.title_label.setStyleSheet("color:#95a5a6; font-size:10px;")
        self.value_label = QLabel("—")
        self.value_label.setStyleSheet("color:#ecf0f1; font-size:17px; font-weight:700;")
        self.detail_label = QLabel("")
        self.detail_label.setStyleSheet("color:#7f8c8d; font-size:9px;")

        layout.addWidget(self.title_label)
        layout.addWidget(self.value_label)
        layout.addWidget(self.detail_label)

    def set_value(self, value: str, detail: str = "", accent: str | None = None) -> None:
        self.value_label.setText(value)
        color = accent or "#ecf0f1"
        self.value_label.setStyleSheet(
            f"color:{color}; font-size:17px; font-weight:700; border:none; background:transparent;"
        )
        self.detail_label.setText(detail)


class CobbTrendWidget(QWidget):
    """Bağımlılıksız, tarih sıralı Cobb trend grafiği."""

    def __init__(self, rows: list[dict], parent=None):
        super().__init__(parent)
        self.rows = list(rows)
        self.setMinimumHeight(350)

    def set_rows(self, rows: list[dict]) -> None:
        self.rows = list(rows)
        self.update()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.fillRect(self.rect(), QColor("#202020"))

        if not self.rows:
            painter.setPen(QColor("#95a5a6"))
            painter.setFont(QFont("Segoe UI", 11))
            painter.drawText(
                self.rect(),
                Qt.AlignmentFlag.AlignCenter,
                "Grafik için kayıtlı Cobb ölçümü bulunmuyor.",
            )
            return

        left, right, top, bottom = 64, 30, 26, 72
        chart = self.rect().adjusted(left, top, -right, -bottom)
        if chart.width() <= 20 or chart.height() <= 20:
            return

        values = [float(row.get("angle_degrees", 0.0)) for row in self.rows]
        lower, upper = min(values), max(values)

        if abs(upper - lower) < 0.1:
            padding = 5.0
        else:
            padding = max(3.0, (upper - lower) * 0.20)

        lower = max(0.0, lower - padding)
        upper = upper + padding
        span = max(1.0, upper - lower)

        # Yatay grid çizgileri ve derece etiketleri
        grid_pen = QPen(QColor("#353535"), 1)
        axis_pen = QPen(QColor("#69727a"), 1)
        painter.setFont(QFont("Segoe UI", 8))

        for step in range(5):
            ratio = step / 4.0
            y = chart.bottom() - ratio * chart.height()
            value = lower + ratio * span
            painter.setPen(grid_pen)
            painter.drawLine(chart.left(), int(y), chart.right(), int(y))
            painter.setPen(QColor("#95a5a6"))
            painter.drawText(QRectF(4, y - 9, left - 10, 18), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, f"{value:.1f}°")

        painter.setPen(axis_pen)
        painter.drawLine(chart.bottomLeft(), chart.bottomRight())
        painter.drawLine(chart.bottomLeft(), chart.topLeft())

        count = len(values)
        points = []
        for index, (row, value) in enumerate(zip(self.rows, values)):
            x = chart.center().x() if count == 1 else chart.left() + index * chart.width() / (count - 1)
            y = chart.bottom() - (value - lower) / span * chart.height()
            points.append((float(x), float(y), row, value))

        # Trend çizgisi
        if len(points) > 1:
            painter.setPen(QPen(QColor("#3498db"), 3))
            for first, second in zip(points, points[1:]):
                painter.drawLine(int(first[0]), int(first[1]), int(second[0]), int(second[1]))

        # Noktalar, değerler ve tarihler
        date_count = len(points)
        label_every = 1 if date_count <= 7 else max(1, date_count // 6)

        for index, (x, y, row, value) in enumerate(points):
            locked = bool(row.get("is_locked"))
            color = QColor("#2ecc71") if locked else QColor("#f39c12")

            painter.setPen(QPen(color, 2))
            painter.setBrush(color)
            painter.drawEllipse(int(x - 5), int(y - 5), 10, 10)

            painter.setPen(QColor("#ecf0f1"))
            painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            painter.drawText(
                QRectF(x - 28, y - 26, 56, 18),
                Qt.AlignmentFlag.AlignCenter,
                f"{value:.1f}°",
            )

            if index % label_every == 0 or index == date_count - 1:
                date = _date_text(row.get("exam_date", ""))
                painter.setPen(QColor("#95a5a6"))
                painter.setFont(QFont("Segoe UI", 8))
                painter.save()
                painter.translate(x - 5, chart.bottom() + 12)
                painter.rotate(-35)
                painter.drawText(QRectF(-4, 0, 88, 18), Qt.AlignmentFlag.AlignLeft, date)
                painter.restore()

        # Başlık
        painter.setPen(QColor("#bdc3c7"))
        painter.setFont(QFont("Segoe UI", 9))
        painter.drawText(chart.left(), 18, "Cobb açısı (°)")


class CobbTrendDialog(QDialog):
    def __init__(self, repository: ExamRepository, patient_id: str, parent=None):
        super().__init__(parent)
        self.repository = repository
        self.patient_id = patient_id
        self.setWindowTitle("Cobb Trend Grafiği")
        self.setObjectName("workflowDialog")
        self.resize(940, 620)
        self.setMinimumSize(800, 520)
        self.setStyleSheet(
            "QDialog { background:#242424; color:#ecf0f1; }"
            "QCheckBox { color:#bdc3c7; }"
            "QPushButton { background:#34495e; color:white; border:none; border-radius:5px; padding:7px 12px; }"
            "QPushButton:hover { background:#3e5870; }"
        )

        self.rows = repository.list_cobb_measurements(patient_id)
        self.hidden_repeat_count = 0

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(10)

        header = QHBoxLayout()
        title = QLabel("<b>Cobb Trend Grafiği</b>")
        title.setStyleSheet("font-size:16px;")
        patient = QLabel(f"Hasta ID: {patient_id}")
        patient.setStyleSheet("color:#95a5a6;")
        header.addWidget(title)
        header.addSpacing(10)
        header.addWidget(patient)
        header.addStretch()

        header.addWidget(QLabel("Vertebra çifti:"))
        self.pair_combo = QComboBox()
        self.pair_combo.setMinimumWidth(150)
        self.pair_combo.currentIndexChanged.connect(self._refresh)
        header.addWidget(self.pair_combo)

        self.locked_only = QCheckBox("Yalnızca doğrulanıp kilitlenen ölçümler")
        self.locked_only.toggled.connect(self._refresh)
        header.addWidget(self.locked_only)

        refresh_button = QPushButton("Veriyi Yenile")
        configure_action(refresh_button, label="Cobb trend verisini yenile", role="secondary", tooltip="Hasta ve eğri ölçümlerini yeniden yükle")
        refresh_button.clicked.connect(self._reload)
        header.addWidget(refresh_button)
        root.addLayout(header)

        cards = QGridLayout()
        cards.setHorizontalSpacing(8)
        cards.setVerticalSpacing(8)

        self.first_card = MetricCard("İlk ölçüm")
        self.latest_card = MetricCard("Son ölçüm")
        self.change_card = MetricCard("Toplam değişim")
        self.range_card = MetricCard("Min / Maks")
        self.count_card = MetricCard("Ölçüm sayısı")
        self.rate_card = MetricCard("Yıllık değişim")

        cards.addWidget(self.first_card, 0, 0)
        cards.addWidget(self.latest_card, 0, 1)
        cards.addWidget(self.change_card, 0, 2)
        cards.addWidget(self.range_card, 0, 3)
        cards.addWidget(self.count_card, 0, 4)
        cards.addWidget(self.rate_card, 0, 5)
        root.addLayout(cards)

        self.summary_label = QLabel()
        self.summary_label.setWordWrap(True)
        self.summary_label.setStyleSheet(
            "background:#2b2b2b; color:#bdc3c7; border:1px solid #3b3b3b; "
            "border-radius:6px; padding:8px;"
        )
        root.addWidget(self.summary_label)

        self.chart = CobbTrendWidget([], self)
        root.addWidget(self.chart, 1)

        legend = QLabel(
            "Yeşil: doğrulanıp kilitlenmiş ölçüm   ·   Turuncu: taslak ölçüm   |   "
            "Δ ve °/yıl yalnızca sayısal değişim göstergeleridir; klinik iyileşme/kötüleşme yorumu üretmez."
        )
        legend.setWordWrap(True)
        legend.setStyleSheet("color:#95a5a6; font-size:10px;")
        root.addWidget(legend)

        self._populate_pair_filter()
        self._refresh()

    def _reload(self) -> None:
        current_key = self.pair_combo.currentData()
        self.rows = self.repository.list_cobb_measurements(self.patient_id)
        self._populate_pair_filter(preferred_key=current_key)
        self._refresh()

    def _populate_pair_filter(self, preferred_key=None) -> None:
        # Repository newest-first döndüğü için ilk görülen çift en güncel kullanılan
        # son-vertebra çiftidir. Farklı çiftler hiçbir zaman tek çizgide birleştirilmez.
        keys = []
        seen = set()
        for row in self.rows:
            key = _pair_key(row)
            if key in seen:
                continue
            seen.add(key)
            keys.append(key)

        self.pair_combo.blockSignals(True)
        self.pair_combo.clear()
        for key in keys:
            upper, lower, direction = key
            if upper and lower:
                suffix = "" if not direction or direction == "Belirtilmedi" else f" | {direction}"
                label = f"{upper}–{lower}{suffix}"
            else:
                label = "Vertebra seçilmemiş / eski kayıt"
            self.pair_combo.addItem(label, key)

        if keys:
            target = preferred_key if preferred_key in keys else keys[0]
            index = self.pair_combo.findData(target)
            self.pair_combo.setCurrentIndex(max(0, index))
        self.pair_combo.blockSignals(False)

    def _filtered_rows(self) -> list[dict]:
        selected_pair = self.pair_combo.currentData()
        rows = [row for row in self.rows if _pair_key(row) == selected_pair]
        if self.locked_only.isChecked():
            rows = [row for row in rows if bool(row.get("is_locked"))]

        # Aynı tarihteki tekrar ölçümler longitudinial zaman noktası değildir.
        # Geçmiş ekranında hepsi korunur; trendde tarih başına tek temsilci seçilir.
        rows, self.hidden_repeat_count = _one_measurement_per_exam(rows)
        return rows

    def _refresh(self) -> None:
        rows = self._filtered_rows()
        self.chart.set_rows(rows)
        self._update_cards(rows)
        summary = self._summary(rows)
        if self.hidden_repeat_count:
            summary += (
                f" Aynı tetkik tarihindeki {self.hidden_repeat_count} tekrar ölçüm "
                "longitudinal grafiğe ayrı zaman noktası olarak eklenmedi."
            )
        self.summary_label.setText(summary)

    def _update_cards(self, rows: list[dict]) -> None:
        if not rows:
            for card in (self.first_card, self.latest_card, self.change_card, self.range_card, self.count_card, self.rate_card):
                card.set_value("—")
            return

        values = [float(row.get("angle_degrees", 0.0)) for row in rows]
        first = rows[0]
        latest = rows[-1]

        pair = _pair_text(first)
        self.first_card.set_value(
            f"{float(first.get('angle_degrees', 0.0)):.2f}°",
            f"{_date_text(first.get('exam_date'))} | {pair}",
        )
        self.latest_card.set_value(
            f"{float(latest.get('angle_degrees', 0.0)):.2f}°",
            f"{_date_text(latest.get('exam_date'))} | {_pair_text(latest)}",
        )

        delta = values[-1] - values[0]
        if abs(delta) < 0.05:
            direction = "Belirgin sayısal değişim yok"
            accent = "#bdc3c7"
        elif delta < 0:
            direction = "Açı azalmış"
            accent = "#2ecc71"
        else:
            direction = "Açı artmış"
            accent = "#e67e22"

        self.change_card.set_value(f"{delta:+.2f}°", direction, accent)
        self.range_card.set_value(f"{min(values):.1f}° / {max(values):.1f}°", "minimum / maksimum")

        locked = sum(1 for row in rows if bool(row.get("is_locked")))
        detail = f"{locked} kilitli"
        if self.hidden_repeat_count:
            detail += f" | {self.hidden_repeat_count} tekrar ayrıldı"
        self.count_card.set_value(str(len(rows)), detail)

        rate, days = _annualized_rate(rows)
        if rate is None:
            rate_detail = "En az iki farklı tarih gerekir"
            self.rate_card.set_value("—", rate_detail)
        else:
            self.rate_card.set_value(
                f"{rate:+.2f}°/yıl",
                f"{days} gün üzerinden yıllıklandırılmış",
            )

    @staticmethod
    def _summary(rows: list[dict]) -> str:
        if not rows:
            return "Henüz kayıtlı Cobb ölçümü yok."

        if len(rows) == 1:
            row = rows[0]
            return (
                f"{_pair_text(row)} | Tek ölçüm mevcut: {float(row.get('angle_degrees', 0.0)):.2f}° "
                f"({_date_text(row.get('exam_date'))}). Trend değerlendirmesi için birden fazla ölçüm gerekir."
            )

        first, latest = rows[0], rows[-1]
        first_angle = float(first.get("angle_degrees", 0.0))
        latest_angle = float(latest.get("angle_degrees", 0.0))
        delta = latest_angle - first_angle

        if abs(delta) < 0.05:
            direction = "Sayısal Cobb açısı başlangıca göre değişmemiş görünüyor."
        elif delta < 0:
            direction = f"Sayısal Cobb açısı başlangıca göre {abs(delta):.2f}° azalmış."
        else:
            direction = f"Sayısal Cobb açısı başlangıca göre {delta:.2f}° artmış."

        return (
            f"{_pair_text(first)} | {_date_text(first.get('exam_date'))} → {_date_text(latest.get('exam_date'))}: "
            f"{first_angle:.2f}° → {latest_angle:.2f}°. {direction} "
            "Bu özet klinik yorum veya tanı değildir."
        )

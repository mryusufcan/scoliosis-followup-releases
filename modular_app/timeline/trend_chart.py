"""PyQtGraph tabanlı etkileşimli longitudinal Cobb trend grafiği."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from modular_app.timeline.longitudinal_models import TrendPoint

try:
    import pyqtgraph as pg
except ImportError:  # pragma: no cover - dağıtım ortamı eksik bağımlılığı görünür kılar
    pg = None


if pg is not None:

    class ExamDateAxisItem(pg.AxisItem):
        """Ordinal gün değerlerini kısa tarih etiketlerine çeviren eksen."""

        def __init__(self, orientation: str = "bottom"):
            super().__init__(orientation=orientation)
            self._positions: list[float] = []
            self._labels: list[str] = []

        def set_date_labels(self, positions: list[float], labels: list[str]) -> None:
            self._positions = list(positions)
            self._labels = list(labels)
            self.picture = None
            self.update()

        def tickValues(self, minVal, maxVal, size):  # noqa: N802, ANN001
            if not self._positions:
                return super().tickValues(minVal, maxVal, size)
            visible = [
                (position, label)
                for position, label in zip(self._positions, self._labels)
                if minVal - 1e-6 <= position <= maxVal + 1e-6
            ]
            if not visible:
                return []
            # Bir etiketi yaklaşık 105 px'ten sık göstermeyerek tarihlerinin
            # üst üste binmesini önle. Noktalar ve veri çizgisi değişmez.
            max_ticks = max(2, min(8, int(max(size, 210) / 105)))
            if len(visible) > max_ticks:
                step = (len(visible) - 1) / float(max_ticks - 1)
                selected = [visible[round(index * step)] for index in range(max_ticks)]
            else:
                selected = visible
            spacing = max(
                (selected[-1][0] - selected[0][0]) / max(len(selected) - 1, 1),
                1.0,
            )
            return [(spacing, [position for position, _label in selected])]

        def tickStrings(self, values, scale, spacing):  # noqa: N802, ANN001
            if not self._positions:
                return [str(round(value)) for value in values]
            result: list[str] = []
            for value in values:
                nearest_index = min(
                    range(len(self._positions)),
                    key=lambda index: abs(self._positions[index] - value),
                )
                distance = abs(self._positions[nearest_index] - value)
                result.append(self._labels[nearest_index] if distance <= max(spacing * 0.55, 1.0) else "")
            return result


class CobbTrendPlot(QWidget):
    """Longitudinal TrendPoint listesini interaktif grafik olarak gösterir.

    PyQtGraph kurulu değilse panelin tamamı çökmek yerine açıklayıcı bir
    placeholder gösterilir. Bu fallback, mevcut QPainter tabanlı
    `CobbTrendWidget` ile kademeli geçişi mümkün kılar.
    """

    point_activated = Signal(object)
    point_hovered = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._points: list[TrendPoint] = []
        self._x_values: list[float] = []
        self._plot = None
        self._line = None
        self._scatter = None
        self._empty_label: QLabel | None = None
        self._selected_point: TrendPoint | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        if pg is None:
            self._empty_label = QLabel(
                "PyQtGraph bağımlılığı bulunamadı.\n"
                "Trend grafiği için mevcut QPainter görünümü kullanılabilir."
            )
            self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._empty_label.setStyleSheet("color:#AAB7C5; background:#0B0F14; padding:24px;")
            layout.addWidget(self._empty_label)
            return

        self._axis = ExamDateAxisItem(orientation="bottom")
        self._plot = pg.PlotWidget(axisItems={"bottom": self._axis})
        self._plot.setObjectName("cobbTrendPlot")
        self._plot.setBackground("#0B0F14")
        self._plot.showGrid(x=True, y=True, alpha=0.22)
        self._plot.setLabel("left", "Cobb açısı", units="°", color="#AAB7C5")
        self._plot.setLabel("bottom", "Tetkik tarihi", color="#AAB7C5")
        self._plot.getPlotItem().hideButtons()
        self._plot.setMouseEnabled(x=True, y=True)
        self._plot.setMinimumHeight(300)
        layout.addWidget(self._plot)

    @property
    def available(self) -> bool:
        return pg is not None and self._plot is not None

    def set_points(self, points: list[TrendPoint] | tuple[TrendPoint, ...]) -> None:
        self._points = list(points)
        self._selected_point = None
        if not self.available:
            return
        assert self._plot is not None
        self._plot.clear()
        self._line = None
        self._scatter = None
        self._x_values = []

        if not self._points:
            self._show_empty_text()
            return

        self._hide_empty_text()
        self._x_values = [_date_position(point.exam_date, index) for index, point in enumerate(self._points)]
        y_values = [float(point.value) for point in self._points]
        labels = [_date_label(point.exam_date) for point in self._points]
        self._axis.set_date_labels(self._x_values, labels)

        if len(self._points) > 1:
            self._line = self._plot.plot(
                self._x_values,
                y_values,
                pen=pg.mkPen("#36C5D8", width=2),
            )

        spots = []
        for x, point in zip(self._x_values, self._points):
            verified = str(point.status).casefold() == "verified"
            spots.append(
                {
                    "pos": (x, float(point.value)),
                    "data": point,
                    "brush": pg.mkBrush("#43C59E" if verified else "#F2B84B"),
                    "pen": pg.mkPen("#F1F5F9", width=1),
                    "size": 10,
                }
            )
        self._scatter = pg.ScatterPlotItem(spots=spots)
        self._scatter.sigClicked.connect(self._on_scatter_clicked)
        self._scatter.sigHovered.connect(self._on_scatter_hovered)
        self._plot.addItem(self._scatter)
        self._plot.setXRange(min(self._x_values), max(self._x_values), padding=0.08)
        self._plot.enableAutoRange(axis="y", enable=True)

    def selected_point(self) -> TrendPoint | None:
        return self._selected_point

    def clear_selection(self) -> None:
        self._selected_point = None
        if self._scatter is None:
            return
        for spot in self._scatter.points():
            point = spot.data()
            verified = str(getattr(point, "status", "")).casefold() == "verified"
            spot.setBrush(pg.mkBrush("#43C59E" if verified else "#F2B84B"))
            spot.setSize(10)
        self._scatter.updateSpots()

    def _on_scatter_clicked(self, _plot, spots, _event=None) -> None:
        if not spots:
            return
        point = spots[0].data()
        if not isinstance(point, TrendPoint):
            return
        self._selected_point = point
        self._highlight(point)
        self.point_activated.emit(point)

    def _on_scatter_hovered(self, _plot, spots, _event=None) -> None:
        point: TrendPoint | None = None
        if spots:
            candidate = spots[0].data()
            if isinstance(candidate, TrendPoint):
                point = candidate
        if point is not None:
            self._plot.setToolTip(_point_tooltip(point))
        else:
            self._plot.setToolTip("")
        self.point_hovered.emit(point)

    def _highlight(self, selected: TrendPoint) -> None:
        if self._scatter is None:
            return
        for spot in self._scatter.points():
            point = spot.data()
            is_selected = point is selected
            verified = str(getattr(point, "status", "")).casefold() == "verified"
            spot.setSize(14 if is_selected else 10)
            spot.setPen(pg.mkPen("#FFFFFF" if is_selected else "#F1F5F9", width=2 if is_selected else 1))
            spot.setBrush(
                pg.mkBrush("#36C5D8" if is_selected else "#43C59E" if verified else "#F2B84B")
            )
        self._scatter.updateSpots()

    def _show_empty_text(self) -> None:
        if self._plot is None or pg is None:
            return
        text = pg.TextItem(
            "Grafik için kayıtlı Cobb ölçümü bulunmuyor.",
            color="#AAB7C5",
            anchor=(0.5, 0.5),
        )
        text.setPos(0, 0)
        self._plot.addItem(text)
        self._empty_plot_text = text

    def _hide_empty_text(self) -> None:
        text = getattr(self, "_empty_plot_text", None)
        if text is not None and self._plot is not None:
            self._plot.removeItem(text)
        self._empty_plot_text = None


def _date_position(raw: str, index: int) -> float:
    for fmt in ("%Y%m%d", "%Y-%m-%d"):
        try:
            return float(datetime.strptime(str(raw or ""), fmt).date().toordinal())
        except ValueError:
            pass
    # Geçersiz tarihleri de kaybetmeden sıralı bir nominal konum ver.
    return float(index)


def _date_label(raw: str) -> str:
    for fmt in ("%Y%m%d", "%Y-%m-%d"):
        try:
            return datetime.strptime(str(raw or ""), fmt).strftime("%d.%m.%Y")
        except ValueError:
            pass
    return str(raw or "—")


def _point_tooltip(point: TrendPoint) -> str:
    status = "Doğrulandı" if str(point.status).casefold() == "verified" else "Taslak"
    source = point.dicom_path or "Kaynak yolu yok"
    return (
        f"Tarih: {_date_label(point.exam_date)}\n"
        f"Cobb: {point.value:.2f}°\n"
        f"Durum: {status}\n"
        f"Eğri: {'–'.join(part for part in point.curve_key[:2] if part) or 'Belirtilmemiş'}\n"
        f"Kaynak: {source}"
    )


__all__ = ["CobbTrendPlot"]

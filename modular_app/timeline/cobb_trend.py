from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QDialog, QLabel, QVBoxLayout, QWidget

from modular_app.database.exam_repository import ExamRepository


class CobbTrendWidget(QWidget):
    """Dependency-free line chart for locally recorded Cobb values."""

    def __init__(self, rows: list[dict], parent=None):
        super().__init__(parent)
        self.rows = list(reversed(rows))
        self.setMinimumHeight(300)

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#242424"))
        if not self.rows:
            painter.setPen(QColor("#95a5a6"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Grafik için en az bir Cobb ölçümü gerekir.")
            return

        left, right, top, bottom = 58, 24, 28, 54
        chart = self.rect().adjusted(left, top, -right, -bottom)
        values = [float(row["angle_degrees"]) for row in self.rows]
        lower, upper = min(values), max(values)
        padding = max(2.0, (upper - lower) * 0.15)
        lower, upper = max(0.0, lower - padding), upper + padding
        span = max(1.0, upper - lower)

        painter.setPen(QPen(QColor("#6c7a89"), 1))
        painter.drawLine(chart.bottomLeft(), chart.bottomRight())
        painter.drawLine(chart.bottomLeft(), chart.topLeft())
        painter.setPen(QColor("#95a5a6"))
        painter.drawText(6, chart.top() + 5, f"{upper:.1f}")
        painter.drawText(6, chart.bottom() + 5, f"{lower:.1f}")

        count = len(values)
        points = []
        for index, (row, value) in enumerate(zip(self.rows, values)):
            x = chart.center().x() if count == 1 else chart.left() + index * chart.width() / (count - 1)
            y = chart.bottom() - (value - lower) / span * chart.height()
            points.append((x, y, row, value))

        if len(points) > 1:
            painter.setPen(QPen(QColor("#3498db"), 2))
            for first, second in zip(points, points[1:]):
                painter.drawLine(int(first[0]), int(first[1]), int(second[0]), int(second[1]))

        for x, y, row, value in points:
            painter.setPen(QPen(QColor("#2ecc71"), 2))
            painter.setBrush(QColor("#2ecc71"))
            painter.drawEllipse(int(x - 4), int(y - 4), 8, 8)
            painter.setPen(QColor("#ecf0f1"))
            painter.drawText(int(x - 20), int(y - 10), f"{value:.1f}")
            date = str(row.get("exam_date", ""))
            painter.setPen(QColor("#95a5a6"))
            painter.drawText(int(x - 26), chart.bottom() + 22, date[-6:] if len(date) >= 6 else date)


class CobbTrendDialog(QDialog):
    def __init__(self, repository: ExamRepository, patient_id: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Cobb Trend Grafiği")
        self.resize(760, 430)
        self.setStyleSheet("background:#242424;color:#ecf0f1;")
        rows = repository.list_cobb_measurements(patient_id)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"<b>Cobb Trend Grafiği</b>  |  Hasta ID: {patient_id}"))
        layout.addWidget(CobbTrendWidget(rows))
        layout.addWidget(QLabel("Grafik yalnızca kaydedilmiş ölçümleri gösterir; klinik yorum üretmez."))

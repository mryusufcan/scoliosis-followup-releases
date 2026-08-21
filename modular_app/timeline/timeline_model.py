"""QTableView için longitudinal tetkik zaman çizelgesi modeli."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PySide6.QtGui import QColor, QBrush

from modular_app.timeline.longitudinal_models import ExamTimelineItem


class ExamTimelineTableModel(QAbstractTableModel):
    """ExamTimelineItem listesini tablo hücrelerine dönüştüren model.

    Model doğrudan SQLite veya Qt dialog bilgisi bilmez. Satır seçiminden sonra
    panel, `item_at()` veya UserRole üzerinden kararlı exam_id değerini alır.
    """

    COLUMN_KEYS = (
        "exam_date",
        "body_part",
        "modality",
        "study_description",
        "latest_cobb",
        "status",
        "source",
        "overlay",
    )
    HEADERS = (
        "Tetkik tarihi",
        "Bölge",
        "Modalite",
        "Tetkik / Seri",
        "Son Cobb",
        "Durum",
        "Kaynak",
        "Overlay",
    )

    ROLE_ITEM = Qt.ItemDataRole.UserRole
    ROLE_EXAM_ID = Qt.ItemDataRole.UserRole + 1
    ROLE_MEASUREMENT_ID = Qt.ItemDataRole.UserRole + 2

    def __init__(self, rows: list[ExamTimelineItem] | None = None, parent=None):
        super().__init__(parent)
        self._rows: list[ExamTimelineItem] = list(rows or [])

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(self.HEADERS)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid() or not (0 <= index.row() < len(self._rows)):
            return None

        item = self._rows[index.row()]
        column = index.column()

        if role == self.ROLE_ITEM:
            return item
        if role == self.ROLE_EXAM_ID:
            return item.exam_id
        if role == self.ROLE_MEASUREMENT_ID:
            return item.latest_measurement_id
        if role == Qt.ItemDataRole.DisplayRole:
            return self._display_value(item, column)
        if role == Qt.ItemDataRole.ToolTipRole:
            return self._tooltip(item, column)
        if role == Qt.ItemDataRole.ForegroundRole:
            return self._foreground(item, column)
        if role == Qt.ItemDataRole.TextAlignmentRole:
            if column in (0, 2, 4, 5, 6, 7):
                return int(Qt.AlignmentFlag.AlignCenter)
            return int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        if role == Qt.ItemDataRole.FontRole and column == 4 and item.latest_cobb is not None:
            from PySide6.QtGui import QFont

            font = QFont()
            font.setBold(True)
            return font
        return None

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal:
            return self.HEADERS[section] if 0 <= section < len(self.HEADERS) else None
        return str(section + 1)

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable

    def set_rows(self, rows: list[ExamTimelineItem] | tuple[ExamTimelineItem, ...]) -> None:
        self.beginResetModel()
        self._rows = list(rows)
        self.endResetModel()

    def clear(self) -> None:
        self.set_rows([])

    def item_at(self, row: int) -> ExamTimelineItem | None:
        return self._rows[row] if 0 <= row < len(self._rows) else None

    def rows(self) -> tuple[ExamTimelineItem, ...]:
        return tuple(self._rows)

    def sort(self, column: int, order: Qt.SortOrder = Qt.SortOrder.AscendingOrder) -> None:
        if not 0 <= column < len(self.COLUMN_KEYS):
            return
        key = self.COLUMN_KEYS[column]
        reverse = order == Qt.SortOrder.DescendingOrder

        def sort_value(item: ExamTimelineItem):
            if key == "latest_cobb":
                return item.latest_cobb if item.latest_cobb is not None else float("-inf")
            if key == "status":
                return item.status_label.casefold()
            if key == "source":
                return (not item.source_exists, item.source_name.casefold())
            if key == "overlay":
                return item.overlay_session_count
            return str(getattr(item, key, "") or "").casefold()

        self.layoutAboutToBeChanged.emit()
        self._rows.sort(key=sort_value, reverse=reverse)
        self.layoutChanged.emit()

    @staticmethod
    def _display_value(item: ExamTimelineItem, column: int) -> str:
        if column == 0:
            return _format_date(item.exam_date)
        if column == 1:
            return item.body_part or "—"
        if column == 2:
            return item.modality or "—"
        if column == 3:
            return item.study_description or item.source_name or "—"
        if column == 4:
            if item.latest_cobb is None:
                return "—"
            return f"{item.latest_cobb:.2f}°"
        if column == 5:
            return item.status_label
        if column == 6:
            return "Hazır" if item.source_exists else "Eksik"
        if column == 7:
            return str(item.overlay_session_count)
        return ""

    @staticmethod
    def _tooltip(item: ExamTimelineItem, column: int) -> str:
        source = item.dicom_path or "Kaynak yolu yok"
        measurement = (
            f"Ölçüm #{item.latest_measurement_id} · {item.measurement_count} kayıt"
            if item.latest_measurement_id is not None
            else "Bu tetkik için Cobb ölçümü yok"
        )
        base = (
            f"Tetkik: {_format_date(item.exam_date)}\n"
            f"PatientID: {item.patient_id}\n"
            f"Kaynak: {source}\n"
            f"{measurement}\n"
            f"Overlay oturumu: {item.overlay_session_count}"
        )
        if item.notes:
            base += f"\nNot: {item.notes}"
        if column == 6 and not item.source_exists:
            base += "\nUyarı: Kaynak dosya bulunamadı; görüntüleyicide açılamaz."
        return base

    @staticmethod
    def _foreground(item: ExamTimelineItem, column: int) -> QBrush | None:
        if column == 5:
            return QBrush(QColor("#43C59E" if item.latest_cobb_locked else "#F2B84B"))
        if column == 6 and not item.source_exists:
            return QBrush(QColor("#E06C75"))
        if column == 4 and item.latest_cobb is not None:
            return QBrush(QColor("#F1F5F9"))
        return None


def _format_date(value: object) -> str:
    raw = str(value or "").strip()
    for fmt in ("%Y%m%d", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, fmt).strftime("%d.%m.%Y")
        except ValueError:
            pass
    return raw or "—"


__all__ = ["ExamTimelineTableModel"]

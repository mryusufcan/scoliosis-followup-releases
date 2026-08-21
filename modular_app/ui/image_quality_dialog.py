"""Teknik görüntü kalite / uygunluk kontrolü.

Bu modül tanı koymaz. Görüntüleme ve takip iş akışında kullanıcıya
teknik uyarı üretir: PixelSpacing, projeksiyon, parlaklık/kontrast,
olası kenar kırpılması ve seçili takip çiftinin metadata uyumu.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

import numpy as np
import pydicom
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QPushButton, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QHeaderView
)


@dataclass
class QualityItem:
    severity: str
    title: str
    detail: str


def _safe_text(ds, name: str) -> str:
    try:
        return str(getattr(ds, name, "") or "").strip()
    except Exception:
        return ""


def _projection(ds) -> str:
    raw = _safe_text(ds, "ViewPosition").upper()
    if raw:
        if "LAT" in raw:
            return "LAT"
        if raw in {"AP", "PA"}:
            return raw

    text = " ".join(
        _safe_text(ds, name)
        for name in ("SeriesDescription", "StudyDescription", "ProtocolName")
    ).upper()

    if "LATERAL" in text or " LAT " in f" {text} ":
        return "LAT"
    if " PA " in f" {text} " or text.startswith("PA"):
        return "PA"
    if " AP " in f" {text} " or text.startswith("AP"):
        return "AP"
    return ""


def _pixmap_gray(app, path: str):
    try:
        from PySide6.QtGui import QImage
        pixmap = app.get_image_pixmap(path)
        if pixmap is None or pixmap.isNull():
            return None
        image = pixmap.toImage().convertToFormat(QImage.Format.Format_Grayscale8)
        width, height = image.width(), image.height()
        if width <= 0 or height <= 0:
            return None
        stride = image.bytesPerLine()
        raw = bytes(image.bits())
        arr = np.frombuffer(raw, dtype=np.uint8).reshape((height, stride))[:, :width]
        return np.ascontiguousarray(arr)
    except Exception:
        return None


def _image_checks(app, path: str) -> list[QualityItem]:
    items: list[QualityItem] = []
    name = os.path.basename(path)

    try:
        ds = pydicom.dcmread(path, stop_before_pixels=True)
    except Exception:
        return [
            QualityItem(
                "Bilgi",
                "DICOM metadata",
                f"{name}: DICOM metadata okunamadı; yalnız görsel metrikler değerlendirilebilir.",
            )
        ]

    spacing = getattr(ds, "PixelSpacing", None)
    if spacing is not None and len(spacing) >= 2:
        try:
            row, col = float(spacing[0]), float(spacing[1])
            if row > 0 and col > 0:
                items.append(
                    QualityItem(
                        "OK",
                        "PixelSpacing",
                        f"{row:.4g} × {col:.4g} mm/piksel — gerçek mesafe ölçümü kullanılabilir.",
                    )
                )
            else:
                items.append(
                    QualityItem(
                        "Uyarı",
                        "PixelSpacing",
                        "PixelSpacing mevcut ancak geçersiz/0 değeri içeriyor.",
                    )
                )
        except Exception:
            items.append(QualityItem("Uyarı", "PixelSpacing", "PixelSpacing okunamadı."))
    else:
        items.append(
            QualityItem(
                "Uyarı",
                "PixelSpacing",
                "PixelSpacing yok. Mesafe ölçümü px olarak gösterilir.",
            )
        )

    projection = _projection(ds)
    if projection:
        items.append(QualityItem("OK", "Projeksiyon", f"Projeksiyon: {projection}"))
    else:
        items.append(
            QualityItem(
                "Bilgi",
                "Projeksiyon",
                "AP / PA / LAT bilgisi metadata veya seri açıklamasından belirlenemedi.",
            )
        )

    rows = int(getattr(ds, "Rows", 0) or 0)
    cols = int(getattr(ds, "Columns", 0) or 0)
    if rows > 0 and cols > 0:
        items.append(QualityItem("OK", "Matris", f"{cols} × {rows} piksel"))

    arr = _pixmap_gray(app, path)
    if arr is None or arr.size == 0:
        items.append(
            QualityItem(
                "Bilgi",
                "Piksel kalite analizi",
                "Görüntü piksel verisi analiz edilemedi.",
            )
        )
        return items

    sy = max(1, arr.shape[0] // 1200)
    sx = max(1, arr.shape[1] // 1200)
    sample = arr[::sy, ::sx].astype(np.float32)

    mean = float(sample.mean())
    std = float(sample.std())
    low_clip = float(np.mean(sample <= 4) * 100.0)
    high_clip = float(np.mean(sample >= 251) * 100.0)

    if mean < 28:
        items.append(
            QualityItem(
                "Uyarı",
                "Parlaklık",
                f"Ortalama gri seviye çok düşük ({mean:.0f}/255). Görüntü aşırı karanlık görünüyor.",
            )
        )
    elif mean > 227:
        items.append(
            QualityItem(
                "Uyarı",
                "Parlaklık",
                f"Ortalama gri seviye çok yüksek ({mean:.0f}/255). Görüntü aşırı parlak görünüyor.",
            )
        )
    else:
        items.append(QualityItem("OK", "Parlaklık", f"Ortalama gri seviye {mean:.0f}/255."))

    if std < 18:
        items.append(
            QualityItem(
                "Uyarı",
                "Kontrast",
                f"Gri seviye dağılımı dar (σ={std:.1f}). Düşük kontrast olabilir.",
            )
        )
    else:
        items.append(QualityItem("OK", "Kontrast", f"Gri seviye dağılımı σ={std:.1f}."))

    if low_clip > 35 or high_clip > 20:
        items.append(
            QualityItem(
                "Uyarı",
                "Kırpılma / saturasyon",
                f"Siyah uç: %{low_clip:.1f} | beyaz uç: %{high_clip:.1f}. Belirgin piksel saturasyonu olabilir.",
            )
        )
    else:
        items.append(
            QualityItem(
                "OK",
                "Kırpılma / saturasyon",
                f"Siyah uç: %{low_clip:.1f} | beyaz uç: %{high_clip:.1f}.",
            )
        )

    p10, p90 = np.percentile(sample, [10, 90])
    threshold = float(p10 + 0.28 * max(1.0, p90 - p10))
    mask = sample > threshold
    band = max(2, min(sample.shape) // 50)
    edge_fraction = float(
        np.mean(
            np.concatenate(
                [
                    mask[:band, :].ravel(),
                    mask[-band:, :].ravel(),
                    mask[:, :band].ravel(),
                    mask[:, -band:].ravel(),
                ]
            )
        )
        * 100.0
    )

    if edge_fraction > 52:
        items.append(
            QualityItem(
                "Bilgi",
                "Anatomi kenar teması",
                f"İçerik görüntü kenarlarına yüksek oranda temas ediyor (%{edge_fraction:.0f}). Olası kırpılmayı görsel olarak kontrol edin.",
            )
        )
    else:
        items.append(
            QualityItem(
                "OK",
                "Anatomi kenar teması",
                f"Kenar teması %{edge_fraction:.0f}; belirgin kırpılma sinyali yok.",
            )
        )

    return items


def _pair_checks(paths: list[str]) -> list[QualityItem]:
    if len(paths) != 2:
        return []

    try:
        first = pydicom.dcmread(paths[0], stop_before_pixels=True)
        second = pydicom.dcmread(paths[1], stop_before_pixels=True)
    except Exception:
        return [
            QualityItem(
                "Bilgi",
                "Takip çifti",
                "Seçili iki görüntünün DICOM metadata karşılaştırması yapılamadı.",
            )
        ]

    items: list[QualityItem] = []

    first_patient = _safe_text(first, "PatientID")
    second_patient = _safe_text(second, "PatientID")
    if first_patient and second_patient and first_patient != second_patient:
        items.append(
            QualityItem(
                "Uyarı",
                "Hasta eşleşmesi",
                f"PatientID farklı: {first_patient} ≠ {second_patient}. Bu çift longitudinal takip için uygun değil.",
            )
        )
    elif first_patient and second_patient:
        items.append(
            QualityItem("OK", "Hasta eşleşmesi", f"Aynı PatientID: {first_patient}")
        )
    else:
        items.append(
            QualityItem(
                "Bilgi",
                "Hasta eşleşmesi",
                "PatientID iki görüntüde de güvenilir biçimde doğrulanamadı.",
            )
        )

    first_uid = _safe_text(first, "StudyInstanceUID")
    second_uid = _safe_text(second, "StudyInstanceUID")
    first_date = _safe_text(first, "StudyDate")
    second_date = _safe_text(second, "StudyDate")

    if first_uid and second_uid and first_uid == second_uid:
        items.append(
            QualityItem(
                "Bilgi",
                "Tetkik zamanı",
                "İki görüntü aynı StudyInstanceUID içinde. Longitudinal takip yerine aynı tetkik/seri parçaları olabilir.",
            )
        )
    elif first_date and second_date and first_date == second_date:
        items.append(
            QualityItem(
                "Bilgi",
                "Tetkik zamanı",
                f"İki görüntünün StudyDate değeri aynı: {first_date}.",
            )
        )
    elif first_date and second_date:
        items.append(
            QualityItem(
                "OK",
                "Tetkik zamanı",
                f"Farklı tetkik tarihleri: {first_date} → {second_date}",
            )
        )

    first_projection = _projection(first)
    second_projection = _projection(second)
    if first_projection and second_projection:
        if first_projection == second_projection:
            items.append(
                QualityItem(
                    "OK",
                    "Projeksiyon uyumu",
                    f"{first_projection} ↔ {second_projection}",
                )
            )
        elif {first_projection, second_projection} <= {"AP", "PA"}:
            items.append(
                QualityItem(
                    "Bilgi",
                    "Projeksiyon uyumu",
                    f"{first_projection} ↔ {second_projection} — AP/PA farkı karşılaştırmada dikkate alınmalı.",
                )
            )
        else:
            items.append(
                QualityItem(
                    "Uyarı",
                    "Projeksiyon uyumu",
                    f"{first_projection} ↔ {second_projection}. LAT ile AP/PA longitudinal overlay için uygun değildir.",
                )
            )
    else:
        items.append(
            QualityItem(
                "Bilgi",
                "Projeksiyon uyumu",
                "İki görüntüden en az birinde projeksiyon belirlenemedi.",
            )
        )

    return items


class ImageQualityDialog(QDialog):
    def __init__(self, app, parent=None):
        super().__init__(parent or app)
        self.app = app
        self.setWindowTitle("Görüntü Kalite Kontrolü")
        self.resize(760, 520)

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        title = QLabel("<b>Teknik Görüntü Kalite / Uygunluk Kontrolü</b>")
        title.setStyleSheet("font-size:15px;")
        root.addWidget(title)

        note = QLabel(
            "Bu ekran tanı koymaz. Ölçüm ve longitudinal karşılaştırma öncesinde "
            "teknik metadata ve görüntü özellikleri için yardımcı kontrol sağlar."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color:#9eabb4;")
        root.addWidget(note)

        self.source_label = QLabel()
        self.source_label.setWordWrap(True)
        root.addWidget(self.source_label)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Durum", "Kontrol", "Sonuç"])
        self.table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        root.addWidget(self.table, 1)

        bottom = QHBoxLayout()
        self.summary = QLabel()
        bottom.addWidget(self.summary, 1)

        refresh = QPushButton("Yeniden Kontrol Et")
        refresh.clicked.connect(self.refresh)
        bottom.addWidget(refresh)

        close = QPushButton("Kapat")
        close.clicked.connect(self.accept)
        bottom.addWidget(close)
        root.addLayout(bottom)

        self.refresh()

    def _current_paths(self) -> tuple[list[str], list[str]]:
        current = []
        path = getattr(self.app, "viewer_current_path", None)
        if path and os.path.isfile(path):
            current = [os.path.abspath(path)]

        pair = []
        try:
            pair = [
                os.path.abspath(p)
                for p in self.app._selected_window_paths()
                if p and os.path.isfile(p)
            ]
        except Exception:
            pass

        return current, pair

    def refresh(self):
        current, pair = self._current_paths()
        items: list[QualityItem] = []

        if current:
            self.source_label.setText(
                f"Görüntüleyici: <b>{os.path.basename(current[0])}</b>"
            )
            items.extend(_image_checks(self.app, current[0]))
        elif len(pair) == 2:
            self.source_label.setText(
                "Takip çifti: <b>"
                + os.path.basename(pair[0])
                + "</b> ↔ <b>"
                + os.path.basename(pair[1])
                + "</b>"
            )
            items.extend(_image_checks(self.app, pair[0]))
            items.extend(_image_checks(self.app, pair[1]))
        else:
            self.source_label.setText(
                "Önce Görüntüleyici’de bir görüntü açın veya "
                "Skolyoz Takip’te iki görüntü seçin."
            )

        if len(pair) == 2:
            items.append(
                QualityItem(
                    "Bilgi",
                    "— Takip Çifti —",
                    "Seçili iki görüntü için longitudinal uygunluk kontrolleri",
                )
            )
            items.extend(_pair_checks(pair))

        self.table.setRowCount(len(items))
        colors = {"OK": "#73c991", "Bilgi": "#7fb3cf", "Uyarı": "#e6b566"}

        for row, item in enumerate(items):
            for col, value in enumerate([item.severity, item.title, item.detail]):
                cell = QTableWidgetItem(value)
                if col == 0:
                    cell.setForeground(QColor(colors.get(item.severity, "#d7e0e6")))
                    cell.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(row, col, cell)

        warnings = sum(1 for item in items if item.severity == "Uyarı")
        infos = sum(1 for item in items if item.severity == "Bilgi")
        oks = sum(1 for item in items if item.severity == "OK")

        critical_titles = {"Hasta eşleşmesi", "Projeksiyon uyumu"}
        critical_warnings = sum(
            1
            for item in items
            if item.severity == "Uyarı" and item.title in critical_titles
        )

        if not items:
            self.summary.setText("Kontrol edilecek görüntü yok.")
            self.summary.setStyleSheet("")
        elif critical_warnings:
            self.summary.setText(
                f"Teknik kontrol: Dikkat · {warnings} uyarı · {infos} bilgi"
            )
            self.summary.setStyleSheet(
                "color:#e57373; font-weight:700;"
            )
        elif warnings:
            self.summary.setText(
                f"Teknik kontrol: Uygun · {warnings} uyarı · {infos} bilgi"
            )
            self.summary.setStyleSheet(
                "color:#e6b566; font-weight:700;"
            )
        else:
            self.summary.setText(
                f"Teknik kontrol: Uygun · {infos} bilgi"
            )
            self.summary.setStyleSheet(
                "color:#73c991; font-weight:700;"
            )

"""Viewer ölçüm, işaretleme, oturum ve dışa aktarma davranışları."""

# VIEWER_RECORDS_STAGE25
import datetime
import json
import math
import os
from pathlib import Path

import pydicom
from PySide6.QtCore import QPointF, QRectF, Qt

from PySide6.QtGui import QFont, QImage, QPageSize, QPainter, QPdfWriter, QPen
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGraphicsItem,
    QLabel,
    QInputDialog,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
)

def activate_viewer_markup(app, mode):
    if app.viewer_pixmap_item is None:
        app.statusBar().showMessage("İşaretlemek için önce bir görüntü açın.")
        return
    app.viewer_markup_mode = mode
    app.viewer_markup_start = None
    app.viewer_cobb_mode_active = False
    app.viewer_length_mode_active = False
    app._refresh_viewer_cobb_button()
    app._refresh_viewer_length_button()
    app.viewer_view.refresh_cursor()
    message = "Görüntü üzerinde metnin konumunu seçin." if mode == "text" else "Ok için başlangıç noktasını seçin."
    app.statusBar().showMessage(message)


def handle_viewer_markup_click(app, pos):
    if not app.viewer_markup_mode or not app.viewer_current_path:
        return
    if app.viewer_markup_mode == "text":
        text, accepted = QInputDialog.getText(app, "Metin işaretlemesi", "Metin:")
        if accepted and text.strip():
            before = app._capture_edit_state()
            record = {"type": "text", "path": app.viewer_current_path, "position": app._viewer_point_data(pos), "text": text.strip()}
            app.viewer_markup_records.append(record)
            app._draw_viewer_markup(record)
            app._history_commit("Metin işaretlemesi", before)
        app.viewer_markup_mode = None
        app.viewer_view.refresh_cursor()
        return
    if app.viewer_markup_start is None:
        app.viewer_markup_start = pos
        app.statusBar().showMessage("Ok için bitiş noktasını seçin.")
        return
    before = app._capture_edit_state()
    record = {
        "type": "arrow", "path": app.viewer_current_path,
        "start": app._viewer_point_data(app.viewer_markup_start), "end": app._viewer_point_data(pos),
    }
    app.viewer_markup_records.append(record)
    app._draw_viewer_markup(record)
    app._history_commit("Ok işaretlemesi", before)
    app.viewer_markup_start = None
    app.viewer_markup_mode = None
    app.viewer_view.refresh_cursor()
    app.statusBar().showMessage("Ok işaretlemesi eklendi.")


def _draw_viewer_markup(app, record):
    if record.get("type") == "text":
        point = app._viewer_point_from_data(record["position"])
        item = app.viewer_scene.addText(str(record.get("text", "")), QFont("Segoe UI", 11, QFont.Bold))
        item.setDefaultTextColor(Qt.magenta)
        item.setPos(point)
        item.setZValue(80)
        item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True)
        app.viewer_markup_items.append(item)
        return
    start, end = app._viewer_point_from_data(record["start"]), app._viewer_point_from_data(record["end"])
    pen = QPen(Qt.magenta, 3)
    line = app.viewer_scene.addLine(start.x(), start.y(), end.x(), end.y(), pen)
    line.setZValue(80)
    app.viewer_markup_items.append(line)
    angle = math.atan2(end.y() - start.y(), end.x() - start.x())
    arrow_size = 14
    for direction in (math.pi * 0.82, -math.pi * 0.82):
        point = QPointF(end.x() + arrow_size * math.cos(angle + direction), end.y() + arrow_size * math.sin(angle + direction))
        head = app.viewer_scene.addLine(end.x(), end.y(), point.x(), point.y(), pen)
        head.setZValue(80)
        app.viewer_markup_items.append(head)


def _render_viewer_saved_items(app, path):
    path = os.path.abspath(path)
    for record in app.viewer_markup_records:
        if os.path.abspath(str(record.get("path", ""))) == path:
            app._draw_viewer_markup(record)
    for record in app.viewer_measurement_records:
        if os.path.abspath(str(record.get("path", ""))) == path:
            app._draw_viewer_measurement(record)


def clear_viewer_markups(app):
    before = app._capture_edit_state()
    for item in app.viewer_markup_items:
        app.viewer_scene.removeItem(item)
    app.viewer_markup_items.clear()
    if app.viewer_current_path:
        app.viewer_markup_records = [
            row for row in app.viewer_markup_records
            if os.path.abspath(str(row.get("path", ""))) != app.viewer_current_path
        ]
    app.viewer_markup_mode = None
    app.viewer_markup_start = None
    app.viewer_view.refresh_cursor()
    app._history_commit("İşaretlemeleri temizle", before)
    app.statusBar().showMessage("Bu görüntüdeki işaretlemeler temizlendi.")


def _draw_viewer_measurement(app, record):
    measurement_type = record.get("type")
    if measurement_type == "cobb":
        points = [app._viewer_point_from_data(point) for point in record.get("points", [])]
        if len(points) != 4:
            return
        for point in points:
            marker = app.viewer_scene.addEllipse(point.x() - 4, point.y() - 4, 8, 8, QPen(Qt.red, 4))
            marker.setZValue(70); app.viewer_cobb_items.append(marker)
        first = app.viewer_scene.addLine(points[0].x(), points[0].y(), points[1].x(), points[1].y(), QPen(Qt.red, 4))
        second = app.viewer_scene.addLine(points[2].x(), points[2].y(), points[3].x(), points[3].y(), QPen(Qt.cyan, 3))
        first.setZValue(70); second.setZValue(70); app.viewer_cobb_items.extend([first, second])
        label = app.viewer_scene.addText(str(record.get("label", "Cobb")), QFont("Segoe UI", 12, QFont.Bold))
        label.setDefaultTextColor(Qt.yellow); label.setPos(points[2]); label.setZValue(75)
        label.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True); app.viewer_cobb_items.append(label)
    elif measurement_type == "length":
        start, end = app._viewer_point_from_data(record["start"]), app._viewer_point_from_data(record["end"])
        for point in (start, end):
            marker = app.viewer_scene.addEllipse(point.x() - 4, point.y() - 4, 8, 8, QPen(Qt.green, 4))
            marker.setZValue(70); app.viewer_length_items.append(marker)
        line = app.viewer_scene.addLine(start.x(), start.y(), end.x(), end.y(), QPen(Qt.green, 3))
        line.setZValue(70); app.viewer_length_items.append(line)
        label = app.viewer_scene.addText(str(record.get("label", "")), QFont("Segoe UI", 11, QFont.Bold))
        label.setDefaultTextColor(Qt.green); label.setPos(end); label.setZValue(75)
        label.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True); app.viewer_length_items.append(label)


def _clear_viewer_cobb_preview(app):
    """Remove only the unfinished Cobb preview, preserving saved measurements."""
    preview_items = list(getattr(app, "viewer_cobb_preview_items", []))
    for item in preview_items:
        app.viewer_scene.removeItem(item)
        if item in app.viewer_cobb_items:
            app.viewer_cobb_items.remove(item)
    if hasattr(app, "viewer_cobb_preview_items"):
        app.viewer_cobb_preview_items.clear()


def handle_viewer_cobb_click(app, pos: QPointF):
    if not app.viewer_cobb_mode_active:
        return
    app.viewer_cobb_points.append(pos)
    point = app.viewer_scene.addEllipse(pos.x() - 4, pos.y() - 4, 8, 8, QPen(Qt.red, 4))
    point.setZValue(70)
    app.viewer_cobb_items.append(point)
    app.viewer_cobb_preview_items.append(point)

    n = len(app.viewer_cobb_points)
    if n < 4:
        remaining = 4 - n
        if n == 1:
            message = "Cobb ölçümü: üst vertebra çizgisinin ikinci noktasını seçin."
        elif n == 2:
            first, second = app.viewer_cobb_points
            line = app.viewer_scene.addLine(first.x(), first.y(), second.x(), second.y(), QPen(Qt.red, 4))
            line.setZValue(70)
            app.viewer_cobb_items.append(line)
            app.viewer_cobb_preview_items.append(line)
            message = "Cobb ölçümü: alt vertebra çizgisinin ilk noktasını seçin."
        else:
            message = "Cobb ölçümü: alt vertebra çizgisinin ikinci noktasını seçin."
        app.statusBar().showMessage(f"{message} Kalan nokta: {remaining}.")
        return

    third, fourth = app.viewer_cobb_points[2:]
    second_line = app.viewer_scene.addLine(third.x(), third.y(), fourth.x(), fourth.y(), QPen(Qt.cyan, 3))
    second_line.setZValue(70)
    app.viewer_cobb_items.append(second_line)
    app.viewer_cobb_preview_items.append(second_line)
    first, second = app.viewer_cobb_points[:2]
    v1 = (second.x() - first.x(), second.y() - first.y())
    v2 = (fourth.x() - third.x(), fourth.y() - third.y())
    length1, length2 = math.hypot(*v1), math.hypot(*v2)
    if length1 <= 0 or length2 <= 0:
        _clear_viewer_cobb_preview(app)
        app.viewer_cobb_points.clear()
        app.viewer_cobb_mode_active = False
        app._refresh_viewer_cobb_button()
        app.viewer_view.refresh_cursor()
        app.statusBar().showMessage("Cobb ölçümü geçersiz: aynı noktalarla sıfır uzunluklu çizgi oluşturulamaz.")
        return

    cosine = max(-1.0, min(1.0, (v1[0] * v2[0] + v1[1] * v2[1]) / (length1 * length2)))
    angle = math.degrees(math.acos(cosine))
    label_text = f"Cobb: {angle:.1f}°"
    label = app.viewer_scene.addText(label_text, QFont("Segoe UI", 12, QFont.Bold))
    label.setDefaultTextColor(Qt.yellow)
    label.setPos(third)
    label.setZValue(75)
    label.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True)
    app.viewer_cobb_items.append(label)
    app.statusBar().showMessage(
        f"Cobb açısı hesaplandı: {angle:.1f}°. Sonuç manuel ölçümdür; klinik doğrulama gerekir."
    )
    before = app._capture_edit_state()
    app.viewer_measurement_records.append({
        "type": "cobb", "path": app.viewer_current_path,
        "points": [app._viewer_point_data(point) for point in app.viewer_cobb_points],
        "label": label_text,
        "value": round(float(angle), 3),
        "unit": "°",
        "measurement_source": "manual",
        "verification_status": "draft",
        "verification_note": "Manuel ölçüm; klinik doğrulama gerekir.",
    })
    app._history_commit("Cobb ölçümü", before)
    app.viewer_cobb_preview_items.clear()
    app.viewer_cobb_points.clear()
    app.viewer_cobb_mode_active = False
    app._refresh_viewer_cobb_button()
    app.viewer_view.refresh_cursor()


def _request_cobb_save_details(
    app,
    *,
    side: str | None = None,
    upper_vertebra: str | None = None,
    lower_vertebra: str | None = None,
    curve_direction: str | None = None,
):
    """Collect the minimum clinical context in one compact, themed dialog."""
    dialog = QDialog(app)
    dialog.setWindowTitle("Cobb ölçümünü kaydet")
    dialog.setModal(True)
    dialog.setMinimumWidth(360)
    layout = QVBoxLayout(dialog)
    image_name = Path(str(getattr(app, "viewer_current_path", "") or "")).name or "Aktif görüntü"
    intro = QLabel(
        f"Görüntü: {image_name}\n"
        "Bu kayıt taslak olarak saklanır. Klinik doğrulama yapılmadan tanısal sonuç olarak kullanılmamalıdır."
    )
    intro.setWordWrap(True)
    intro.setProperty("uiContext", True)
    layout.addWidget(intro)

    form = QFormLayout()
    side_box = QComboBox()
    side_options = [("Sağ", "right"), ("Sol", "left"), ("Merkez", "center")]
    for label, value in side_options:
        side_box.addItem(label, value)
    requested_side = str(side or "right").strip()
    for index, (_, value) in enumerate(side_options):
        if value == requested_side:
            side_box.setCurrentIndex(index)
            break
    upper_edit = QLineEdit(str(upper_vertebra or ""))
    upper_edit.setPlaceholderText("Örn. T5")
    lower_edit = QLineEdit(str(lower_vertebra or ""))
    lower_edit.setPlaceholderText("Örn. T11")
    direction_edit = QLineEdit(str(curve_direction or ""))
    direction_edit.setPlaceholderText("Örn. sağ")
    form.addRow("Taraf:", side_box)
    form.addRow("Üst vertebra:", upper_edit)
    form.addRow("Alt vertebra:", lower_edit)
    form.addRow("Eğri yönü:", direction_edit)
    layout.addLayout(form)

    buttons = QDialogButtonBox(
        QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
    )
    buttons.button(QDialogButtonBox.StandardButton.Save).setText("Taslak Olarak Kaydet")
    buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("İptal")
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    layout.addWidget(buttons)

    if dialog.exec() != QDialog.DialogCode.Accepted:
        return None
    upper = upper_edit.text().strip()
    lower = lower_edit.text().strip()
    if not upper or not lower:
        QMessageBox.warning(
            app,
            "Cobb kaydı eksik",
            "Üst ve alt vertebra alanları doldurulmadan taslak kaydedilemez.",
        )
        return None
    return {
        "side": str(side_box.currentData() or "right"),
        "upper_vertebra": upper,
        "lower_vertebra": lower,
        "curve_direction": direction_edit.text().strip(),
    }


def save_viewer_cobb_measurement(
    app,
    *,
    side: str | None = None,
    upper_vertebra: str | None = None,
    lower_vertebra: str | None = None,
    curve_direction: str | None = None,
):
    """Persist the latest manual viewer Cobb record as an unlocked draft.

    The source DICOM is read-only. Only normalized measurement evidence and its
    source identifiers are written to the existing ExamRepository.
    """
    current_path = os.path.abspath(str(getattr(app, "viewer_current_path", "") or ""))
    if not current_path or not os.path.isfile(current_path):
        app.statusBar().showMessage("Cobb kaydı için önce geçerli bir görüntü açın.")
        return None

    pending = [
        row for row in getattr(app, "viewer_measurement_records", [])
        if row.get("type") == "cobb"
        and os.path.abspath(str(row.get("path", ""))) == current_path
        and not row.get("repository_measurement_id")
    ]
    if not pending:
        app.statusBar().showMessage("Bu görüntüde kaydedilecek taslak Cobb ölçümü yok.")
        return None
    record = pending[-1]

    repository = getattr(app, "exam_repository", None)
    if repository is None:
        app.statusBar().showMessage("Takip veritabanı hazır değil; Cobb kaydı oluşturulamadı.")
        return None

    if any(value is None for value in (side, upper_vertebra, lower_vertebra, curve_direction)):
        details = _request_cobb_save_details(
            app,
            side=side,
            upper_vertebra=upper_vertebra,
            lower_vertebra=lower_vertebra,
            curve_direction=curve_direction,
        )
        if details is None:
            return None
        side = details["side"]
        upper_vertebra = details["upper_vertebra"]
        lower_vertebra = details["lower_vertebra"]
        curve_direction = details["curve_direction"]
    side = str(side or "right").strip() or "right"
    upper_vertebra = str(upper_vertebra or "").strip()
    lower_vertebra = str(lower_vertebra or "").strip()
    curve_direction = str(curve_direction or "").strip()
    if not upper_vertebra or not lower_vertebra:
        app.statusBar().showMessage("Cobb kaydı için üst ve alt vertebra bilgisi gerekir.", 5000)
        return None

    try:
        dataset = pydicom.dcmread(current_path, stop_before_pixels=True, force=True)
        patient_id = str(getattr(dataset, "PatientID", "UNKNOWN") or "UNKNOWN").strip() or "UNKNOWN"
        patient_name = str(getattr(dataset, "PatientName", "") or "").strip()
        exam_date = str(getattr(dataset, "StudyDate", "UNKNOWN") or "UNKNOWN").strip() or "UNKNOWN"
        body_part = str(getattr(dataset, "BodyPartExamined", "") or "").strip()
        modality = str(getattr(dataset, "Modality", "DX") or "DX").strip() or "DX"
        study_description = str(
            getattr(dataset, "StudyDescription", None)
            or getattr(dataset, "SeriesDescription", "")
            or ""
        ).strip()
        source_uid = str(getattr(dataset, "SOPInstanceUID", "") or "").strip()
        points = [
            {"x": float(point[0]), "y": float(point[1])}
            for point in record.get("points", [])
        ]
        if len(points) != 4:
            raise ValueError("Cobb kaydı dört nokta kanıtı içermelidir.")
        repository.add_exam(
            patient_id=patient_id,
            patient_name=patient_name,
            exam_date=exam_date,
            body_part=body_part,
            modality=modality,
            study_description=study_description,
            dicom_path=current_path,
        )
        measurement_id = repository.add_cobb_measurement(
            patient_id=patient_id,
            dicom_path=current_path,
            exam_date=exam_date,
            side=side,
            angle_degrees=float(record.get("value", 0.0)),
            source_sop_instance_uid=source_uid,
            points=points,
            measurement_method="manual_4_point",
            measurement_version="1",
            created_by=str(getattr(app, "current_user_name", "Yerel kullanıcı") or "Yerel kullanıcı"),
            upper_vertebra=str(upper_vertebra or "").strip(),
            lower_vertebra=str(lower_vertebra or "").strip(),
            curve_direction=str(curve_direction or "").strip(),
        )
    except Exception as exc:
        app.statusBar().showMessage(f"Cobb kaydı oluşturulamadı: {exc}", 5000)
        return None

    record.update({
        "repository_measurement_id": int(measurement_id),
        "verification_status": "draft",
        "persisted_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "persisted_by": str(getattr(app, "current_user_name", "Yerel kullanıcı") or "Yerel kullanıcı"),
        "side": side,
        "upper_vertebra": str(upper_vertebra or "").strip(),
        "lower_vertebra": str(lower_vertebra or "").strip(),
        "curve_direction": str(curve_direction or "").strip(),
        "source_sop_instance_uid": source_uid,
    })
    app._refresh_viewer_cobb_button()
    app.statusBar().showMessage(
        f"Cobb ölçümü takip geçmişine taslak olarak kaydedildi (#{measurement_id}). Klinik doğrulama gerekir."
    )
    return int(measurement_id)



def handle_viewer_length_click(app, pos: QPointF):

    if not app.viewer_length_mode_active:
        return
    if app.viewer_length_start is None:
        app.viewer_length_start = pos
        marker = app.viewer_scene.addEllipse(pos.x() - 4, pos.y() - 4, 8, 8, QPen(Qt.green, 4))
        marker.setZValue(70)
        app.viewer_length_items.append(marker)
        app.statusBar().showMessage("Mesafe Ölçümü: bitiş noktasını seçin.")
        return

    start = app.viewer_length_start
    end = pos
    end_marker = app.viewer_scene.addEllipse(end.x() - 4, end.y() - 4, 8, 8, QPen(Qt.green, 4))
    line = app.viewer_scene.addLine(start.x(), start.y(), end.x(), end.y(), QPen(Qt.green, 3))
    end_marker.setZValue(70)
    line.setZValue(70)
    app.viewer_length_items.extend([end_marker, line])

    dx, dy = end.x() - start.x(), end.y() - start.y()
    spacing = app._viewer_pixel_spacing()
    if spacing is None:
        text = f"{math.hypot(dx, dy):.1f} px"
        status_text = f"Pixel Spacing yok; mesafe yalnızca piksel olarak gösteriliyor: {text}"
        unit = "px"
    else:
        row_mm, column_mm = spacing
        if app.viewer_rotation % 180:
            x_mm, y_mm = row_mm, column_mm
        else:
            x_mm, y_mm = column_mm, row_mm
        distance_mm = math.hypot(dx * x_mm, dy * y_mm)
        text = f"{distance_mm / 10:.2f} cm" if distance_mm >= 100 else f"{distance_mm:.1f} mm"
        status_text = f"Ölçülen mesafe: {text}"
        unit = "cm" if distance_mm >= 100 else "mm"

    label = app.viewer_scene.addText(text, QFont("Segoe UI", 11, QFont.Bold))

    label.setDefaultTextColor(Qt.green)
    label.setPos(end)
    label.setZValue(75)
    label.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True)
    app.viewer_length_items.append(label)
    app.viewer_length_start = None
    app.viewer_length_mode_active = False
    app._refresh_viewer_length_button()
    app.viewer_view.refresh_cursor()
    before = app._capture_edit_state()
    app.viewer_measurement_records.append({
        "type": "length", "path": app.viewer_current_path,
        "start": app._viewer_point_data(start), "end": app._viewer_point_data(end), "label": text,
        "unit": unit,
        "measurement_source": "manual",
        "verification_status": "draft",
        "verification_note": "Manuel ölçüm; klinik doğrulama gerekir.",
    })
    app._history_commit("Mesafe ölçümü", before)
    app.statusBar().showMessage(status_text)


def clear_viewer_measurements(app, notify=True):
    before = app._capture_edit_state()
    for item in app.viewer_cobb_items:
        app.viewer_scene.removeItem(item)
    for item in app.viewer_length_items:
        app.viewer_scene.removeItem(item)
        app.viewer_cobb_items.clear()
    app.viewer_cobb_points.clear()
    if hasattr(app, "viewer_cobb_preview_items"):
        app.viewer_cobb_preview_items.clear()

    app.viewer_length_items.clear()
    app.viewer_length_start = None
    app.viewer_cobb_mode_active = False
    app.viewer_length_mode_active = False
    if app.viewer_current_path:
        app.viewer_measurement_records = [
            row for row in app.viewer_measurement_records
            if os.path.abspath(str(row.get("path", ""))) != app.viewer_current_path
        ]
    app._refresh_viewer_cobb_button()
    app._refresh_viewer_length_button()
    app.viewer_view.refresh_cursor()
    if notify:
        app._history_commit("Ölçümleri temizle", before)
        app.statusBar().showMessage("Görüntüleyici ölçümleri temizlendi.")


def clear_viewer_files(app):
    app.stop_viewer_cine()
    app.viewer_file_tree.clear()
    app.viewer_scene.clear()
    app.viewer_current_path = None
    app.viewer_pixmap_item = None
    app.viewer_cobb_points.clear()
    app.viewer_cobb_items.clear()
    app.viewer_length_start = None
    app.viewer_length_items.clear()
    app.viewer_annotation_items.clear()
    app.viewer_markup_items.clear()
    app.viewer_markup_records.clear()
    app.viewer_measurement_records.clear()
    app.viewer_markup_mode = None
    app.viewer_markup_start = None
    app.viewer_cobb_mode_active = False
    app.viewer_length_mode_active = False
    app._refresh_viewer_cobb_button()
    app._refresh_viewer_length_button()
    app._viewer_fit_scale = 0.0
    app.viewer_frame_index = 0
    app.viewer_frame_count = 1
    app._viewer_only_pixmap_cache.clear()
    app._viewer_dataset_cache.clear()
    app._viewer_frame_counts.clear()
    app._refresh_viewer_frame_controls()
    app._update_viewer_window_label()
    app._update_viewer_zoom_label()
    app.viewer_info_label.setText("DICOM veya görüntü dosyası açın.")
    app.statusBar().showMessage("Görüntüleyici listesi temizlendi.")


def _viewer_session_paths(app):
    return [
        os.path.abspath(item.data(0, Qt.UserRole))
        for item in app._viewer_file_items()
        if item.data(0, Qt.UserRole)
    ]


def save_viewer_session(app):
    paths = app._viewer_session_paths()
    if not paths:
        app.statusBar().showMessage("Oturum kaydı için önce en az bir görüntü açın.")
        return
    suggested = "goruntuleyici_oturumu.json"
    output, _ = QFileDialog.getSaveFileName(app, "Görüntüleyici oturumunu kaydet", suggested, "Görüntüleyici oturumu (*.json)")
    if not output:
        return
    if not output.lower().endswith(".json"):
        output += ".json"
    session = {
        "format": "ScoliosisFollowUpViewerSession",
        "version": 1,
        "paths": paths,
        "current_path": app.viewer_current_path,
        "brightness": app.viewer_brightness_value,
        "window_settings": {path: list(value) for path, value in app.viewer_window_settings.items() if path in paths},
        "rotation": app.viewer_rotation,
        "flip_horizontal": app.viewer_flip_horizontal,
        "flip_vertical": app.viewer_flip_vertical,
        "inverted": app.viewer_inverted,
        "annotations_visible": app.viewer_annotations_visible,
        "markups": app.viewer_markup_records,
        "measurements": app.viewer_measurement_records,
        "saved_at": datetime.datetime.now().isoformat(timespec="seconds"),
    }
    try:
        with open(output, "w", encoding="utf-8") as handle:
            json.dump(session, handle, ensure_ascii=False, indent=2)
        app.statusBar().showMessage(f"Görüntüleyici oturumu kaydedildi: {output}")
    except OSError as exc:
        QMessageBox.warning(app, "Oturum kaydı", f"Oturum kaydedilemedi:\n{exc}")


def load_viewer_session(app):
    source, _ = QFileDialog.getOpenFileName(app, "Görüntüleyici oturumunu aç", "", "Görüntüleyici oturumu (*.json)")
    if not source:
        return
    try:
        with open(source, "r", encoding="utf-8") as handle:
            session = json.load(handle)
        if session.get("format") != "ScoliosisFollowUpViewerSession":
            raise ValueError("Bu dosya desteklenen bir görüntüleyici oturumu değil.")
        paths = [os.path.abspath(str(path)) for path in session.get("paths", []) if os.path.isfile(str(path))]
        if not paths:
            raise ValueError("Oturumdaki görüntü dosyaları bu bilgisayarda bulunamadı.")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        QMessageBox.warning(app, "Oturum aç", f"Oturum açılamadı:\n{exc}")
        return

    app.clear_viewer_files()
    app.viewer_brightness_value = int(session.get("brightness", 0))
    app.viewer_brightness_slider.blockSignals(True)
    app.viewer_brightness_slider.setValue(app.viewer_brightness_value)
    app.viewer_brightness_slider.blockSignals(False)
    app.viewer_brightness_label.setText(str(app.viewer_brightness_value))
    app.viewer_window_settings = {
        os.path.abspath(path): (float(value[0]), float(value[1]))
        for path, value in dict(session.get("window_settings", {})).items()
        if isinstance(value, (list, tuple)) and len(value) == 2
    }
    app.viewer_rotation = int(session.get("rotation", 0)) % 360
    app.viewer_flip_horizontal = bool(session.get("flip_horizontal", False))
    app.viewer_flip_vertical = bool(session.get("flip_vertical", False))
    app.viewer_inverted = bool(session.get("inverted", False))
    app.viewer_invert_action.blockSignals(True)
    app.viewer_invert_action.setChecked(app.viewer_inverted)
    app.viewer_invert_action.blockSignals(False)
    app.viewer_annotations_visible = bool(session.get("annotations_visible", True))
    app.btn_viewer_annotations.blockSignals(True)
    app.btn_viewer_annotations.setChecked(app.viewer_annotations_visible)
    app.btn_viewer_annotations.blockSignals(False)
    app.viewer_markup_records = [row for row in session.get("markups", []) if isinstance(row, dict)]
    app.viewer_measurement_records = [row for row in session.get("measurements", []) if isinstance(row, dict)]
    app._add_viewer_paths(paths)
    current = os.path.abspath(str(session.get("current_path", paths[0])))
    for item in app._viewer_file_items():
        if os.path.abspath(str(item.data(0, Qt.UserRole))) == current:
            app.viewer_file_tree.setCurrentItem(item)
            break
    else:
        app.viewer_file_tree.setCurrentItem(app._viewer_file_items()[0])
    app.statusBar().showMessage(f"Görüntüleyici oturumu açıldı: {os.path.basename(source)}")


def show_viewer_markup_summary(app):
    if not app.viewer_current_path:
        app.statusBar().showMessage("Liste için önce bir görüntü açın.")
        return
    current = app.viewer_current_path
    markups = [row for row in app.viewer_markup_records if os.path.abspath(str(row.get("path", ""))) == current]
    measures = [row for row in app.viewer_measurement_records if os.path.abspath(str(row.get("path", ""))) == current]
    lines = [f"Metin/ok işaretlemesi: {len(markups)}", f"Ölçüm: {len(measures)}"]
    for index, row in enumerate(measures, 1):
        lines.append(f"{index}. {'Cobb' if row.get('type') == 'cobb' else 'Mesafe'} — {row.get('label', '—')}")
    QMessageBox.information(app, "Ölçüm / İşaretleme Listesi", "\n".join(lines))


def _viewer_export_image(app):
    if app.viewer_pixmap_item is None:
        return None
    source = app.viewer_pixmap_item.sceneBoundingRect()
    if source.isEmpty():
        return None
    longest_side = max(source.width(), source.height())
    scale = min(1.0, 4096.0 / longest_side) if longest_side else 1.0
    width = max(1, int(round(source.width() * scale)))
    height = max(1, int(round(source.height() * scale)))
    image = QImage(width, height, QImage.Format_ARGB32)
    image.fill(Qt.black)
    painter = QPainter(image)
    app.viewer_scene.render(painter, QRectF(0, 0, width, height), source)
    painter.end()
    return image


def export_viewer_snapshot(app, format_name):
    if app.viewer_pixmap_item is None:
        app.statusBar().showMessage("Dışa aktarmak için önce bir görüntü açın.")
        return
    is_pdf = str(format_name).lower() == "pdf"
    extension = "pdf" if is_pdf else "png"
    label = "PDF" if is_pdf else "PNG"
    suggested = f"{os.path.splitext(os.path.basename(app.viewer_current_path))[0]}_viewer.{extension}"
    output_path, _ = QFileDialog.getSaveFileName(app, f"Görüntüleyiciyi {label} olarak kaydet", suggested, f"{label} (*.{extension})")
    if not output_path:
        return
    if not output_path.lower().endswith(f".{extension}"):
        output_path += f".{extension}"
    image = app._viewer_export_image()
    if image is None:
        QMessageBox.warning(app, "Dışa aktar", "Görüntü dışa aktarılamadı.")
        return
    try:
        if is_pdf:
            writer = QPdfWriter(output_path)
            writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
            writer.setResolution(150)
            painter = QPainter(writer)
            page = QRectF(painter.viewport())
            ratio = min(page.width() / image.width(), page.height() / image.height())
            target = QRectF(
                page.x() + (page.width() - image.width() * ratio) / 2,
                page.y() + (page.height() - image.height() * ratio) / 2,
                image.width() * ratio,
                image.height() * ratio,
            )
            painter.drawImage(target, image)
            painter.end()
        elif not image.save(output_path, "PNG"):
            raise RuntimeError("PNG dosyası yazılamadı.")
        app.statusBar().showMessage(f"Görüntüleyici {label} olarak kaydedildi: {output_path}")
    except Exception as exc:
        QMessageBox.warning(app, "Dışa aktar", f"{label} oluşturulamadı:\n{exc}")


"""Skolyoz Takip dosya agaci, W/L, overlay ve Cobb davranislari."""

# WORKSPACE_ACTIONS_STAGE26
import math
import os
import numpy as np

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QFont, QIcon, QPen, QTransform
from PySide6.QtWidgets import QGraphicsPixmapItem, QListWidgetItem, QMenu, QTreeWidgetItem
from modular_app.ui.ui_clarity import set_context


def calculate_acute_cobb_angle(first: QPointF, second: QPointF, third: QPointF, fourth: QPointF) -> float:
    """Return the smaller 0–90° angle between two non-zero endplate lines."""
    first_vector = (second.x() - first.x(), second.y() - first.y())
    second_vector = (fourth.x() - third.x(), fourth.y() - third.y())
    first_length = math.hypot(*first_vector)
    second_length = math.hypot(*second_vector)
    if first_length <= 0.0 or second_length <= 0.0:
        raise ValueError("Cobb çizgilerinin uzunluğu sıfır olamaz.")
    cosine = max(-1.0, min(1.0, (first_vector[0] * second_vector[0] + first_vector[1] * second_vector[1]) / (first_length * second_length)))
    raw_angle = math.degrees(math.acos(cosine))
    return min(raw_angle, 180.0 - raw_angle)


def _study_tree_file_items(app):
    items = []

    def collect(parent):
        for index in range(parent.childCount()):
            child = parent.child(index)
            if child.data(0, Qt.UserRole):
                items.append(child)
            else:
                collect(child)

    for index in range(app.study_tree_widget.topLevelItemCount()):
        top_level = app.study_tree_widget.topLevelItem(index)
        if top_level.data(0, Qt.UserRole):
            items.append(top_level)
        else:
            collect(top_level)
    return items


def _study_tree_find_or_add(app, parent, title):
    count = app.study_tree_widget.topLevelItemCount() if parent is None else parent.childCount()
    get_item = app.study_tree_widget.topLevelItem if parent is None else parent.child
    for index in range(count):
        candidate = get_item(index)
        if candidate.text(0) == title and not candidate.data(0, Qt.UserRole):
            return candidate

    group = QTreeWidgetItem([title])
    group.setFlags(group.flags() & ~Qt.ItemFlag.ItemIsSelectable)
    if parent is None:
        app.study_tree_widget.addTopLevelItem(group)
    else:
        parent.addChild(group)
    group.setExpanded(True)
    return group


def _study_tree_group(app, metadata):
    if metadata is None:
        patient_title, study_title, series_title = "Diğer dosyalar", "DICOM dışı", "Görüntüler"
    else:
        patient_title = f"{metadata['patient_name']} | ID: {metadata['patient_id']}"
        study_title = " | ".join(part for part in (metadata['study_date'], metadata['description']) if part) or "Tetkik"
        series_title = " | ".join(
            part for part in (metadata['modality'], metadata['body_part'], metadata['laterality']) if part
        ) or "Seri"
    patient_group = app._study_tree_find_or_add(None, patient_title)
    study_group = app._study_tree_find_or_add(patient_group, study_title)
    return app._study_tree_find_or_add(study_group, series_title)


def _add_path_to_study_tree(app, path, model_item=None):
    absolute_path = os.path.abspath(path)
    for item in app._study_tree_file_items():
        item_path = str(item.data(0, Qt.UserRole) or "")
        if item_path and os.path.abspath(item_path) == absolute_path:
            return item

    pixmap = app.get_image_pixmap(absolute_path)
    metadata = app._viewer_metadata(absolute_path)
    label = os.path.basename(absolute_path)
    if metadata is not None:
        series_label = metadata["description"] or metadata["body_part"]
        if series_label:
            label += f"\n{series_label[:36]}"
    item = QTreeWidgetItem([label])
    item.setIcon(0, QIcon(pixmap) if not pixmap.isNull() else QIcon())
    item.setData(0, Qt.UserRole, absolute_path)
    item.setToolTip(0, absolute_path)
    app._study_tree_group(metadata).addChild(item)
    return item


def _ensure_tracking_path(app, path):
    absolute_path = os.path.abspath(path)
    app._remember_shared_paths([absolute_path])
    for index in range(app.study_list_widget.count()):
        item = app.study_list_widget.item(index)
        item_path = str(item.data(Qt.UserRole) or "")
        if item_path and os.path.abspath(item_path) == absolute_path:
            app._add_path_to_study_tree(absolute_path, item)
            return item, False

    key = os.path.basename(absolute_path)
    if key in app.loaded_files and os.path.abspath(app.loaded_files[key]) != absolute_path:
        key = f"{os.path.basename(absolute_path)}  |  {os.path.dirname(absolute_path)}"
    app.loaded_files[key] = absolute_path

    pixmap = app.get_image_pixmap(absolute_path)
    item = QListWidgetItem(QIcon(pixmap) if not pixmap.isNull() else QIcon(), key)
    item.setData(Qt.UserRole, absolute_path)
    app.study_list_widget.addItem(item)
    app._add_path_to_study_tree(absolute_path, item)
    return item, True


def _sync_study_tree_selection_from_model(app):
    selected_paths = {
        os.path.abspath(str(item.data(Qt.UserRole)))
        for item in app.study_list_widget.selectedItems()
        if item.data(Qt.UserRole)
    }
    app._study_tree_syncing = True
    try:
        app.study_tree_widget.clearSelection()
        for item in app._study_tree_file_items():
            path = str(item.data(0, Qt.UserRole) or "")
            if path and os.path.abspath(path) in selected_paths:
                item.setSelected(True)
    finally:
        app._study_tree_syncing = False


def _on_study_model_selection_changed(app):
    if app._study_tree_syncing:
        return
    app._sync_study_tree_selection_from_model()
    app.update_viewers()


def _on_study_tree_selection_changed(app):
    if app._study_tree_syncing:
        return
    selected_paths = {
        os.path.abspath(str(item.data(0, Qt.UserRole)))
        for item in app.study_tree_widget.selectedItems()
        if item.data(0, Qt.UserRole)
    }
    app._study_tree_syncing = True
    try:
        app.study_list_widget.clearSelection()
        for index in range(app.study_list_widget.count()):
            item = app.study_list_widget.item(index)
            path = str(item.data(Qt.UserRole) or "")
            if path and os.path.abspath(path) in selected_paths:
                item.setSelected(True)
    finally:
        app._study_tree_syncing = False
    app.update_viewers()


def show_study_file_context_menu(app, pos):
    clicked = app.study_tree_widget.itemAt(pos)
    if clicked is None or not clicked.data(0, Qt.UserRole):
        return
    if not clicked.isSelected():
        app.study_tree_widget.clearSelection()
        clicked.setSelected(True)
    selected = [item for item in app.study_tree_widget.selectedItems() if item.data(0, Qt.UserRole)]
    menu = QMenu(app)
    action = menu.addAction("Skolyoz Takip'ten kaldır")
    pool_action = menu.addAction("Ortak havuzdan ve tüm modüllerden kaldır")
    chosen = menu.exec(app.study_tree_widget.viewport().mapToGlobal(pos))
    paths = {os.path.abspath(str(item.data(0, Qt.UserRole))) for item in selected}
    if chosen == pool_action:
        app._remove_paths_from_all_modules(paths)
        app.statusBar().showMessage(f"{len(paths)} dosya ortak havuzdan kaldırıldı. Diskteki dosyalar silinmedi.")
        return
    if chosen != action:
        return
    app._study_tree_syncing = True
    try:
        for row in range(app.study_list_widget.count() - 1, -1, -1):
            model_item = app.study_list_widget.item(row)
            model_path = str(model_item.data(Qt.UserRole) or "")
            if model_path and os.path.abspath(model_path) in paths:
                app.study_list_widget.takeItem(row)
        for item in list(selected):
            app._remove_tree_item_and_empty_groups(app.study_tree_widget, item)
    finally:
        app._study_tree_syncing = False
    app.loaded_files = {
        key: value for key, value in app.loaded_files.items()
        if os.path.abspath(str(value)) not in paths
    }
    app.update_viewers()
    app.statusBar().showMessage(f"Skolyoz Takip'ten {len(paths)} dosya kaldırıldı. Diskteki dosyalar silinmedi.")


def _activate_viewer_path_for_tracking(app, path):
    if not path or not os.path.isfile(path):
        return
    item, added = app._ensure_tracking_path(path)
    app._study_tree_syncing = True
    try:
        app.study_list_widget.clearSelection()
        item.setSelected(True)
        app.study_list_widget.setCurrentItem(item)
    finally:
        app._study_tree_syncing = False
    app._sync_study_tree_selection_from_model()
    app.update_viewers()

    register_paths = getattr(app, "_register_paths", None)
    if added and callable(register_paths) and app._viewer_is_dicom(path):
        register_paths([path])


def _selected_window_paths(app):
    paths = []
    for item in app.study_list_widget.selectedItems():
        path = item.data(Qt.UserRole)
        if path and os.path.exists(path):
            paths.append(path)
        elif item.text() in app.loaded_files:
            paths.append(app.loaded_files[item.text()])
    return paths


def apply_window_preset(app, preset):
    paths = app._selected_window_paths()
    if not paths:
        app.statusBar().showMessage("Pencere ayarı için önce tetkik seçin.")
        return
    presets = {
        "soft": (300.0, 1200.0),
        "bone": (2000.0, 4000.0),
    }
    if preset == "original":
        for path in paths:
            app.window_settings.pop(os.path.abspath(path), None)
        app._viewer_pixmap_cache.clear()
        wc, ww = app._default_window(paths[0])
        app.lbl_windowing.setText(f"W/L: Orijinal | WW {ww:.0f} | WL {wc:.0f}")
        app.update_viewers()
        app.statusBar().showMessage("W/L preset uygulandı: Orijinal")
        return
    for path in paths:
        app.window_settings[os.path.abspath(path)] = presets[preset]
    app._viewer_pixmap_cache.clear()
    wc, ww = app.window_settings[os.path.abspath(paths[0])]
    app.lbl_windowing.setText(f"W/L: WW {ww:.0f} | WL {wc:.0f} | Orta fare ile ayarla")
    app.update_viewers()
    app.statusBar().showMessage(f"W/L preset uygulandı: {preset}")


def reset_window_level(app):
    paths = app._selected_window_paths()
    if not paths:
        app.statusBar().showMessage("Pencere ayarını sıfırlamak için önce tetkik seçin.")
        return
    for path in paths:
        app.window_settings.pop(os.path.abspath(path), None)
    app._viewer_pixmap_cache.clear()
    wc, ww = app._default_window(paths[0])
    app.lbl_windowing.setText(f"W/L: WW {ww:.0f} | WL {wc:.0f} | Orta fare ile ayarla")
    app.update_viewers()
    app.statusBar().showMessage("W/L sıfırlandı; DICOM varsayılanına dönüldü.")


def adjust_window_level(app, side, dx, dy):
    paths = app._selected_window_paths()
    if not paths:
        return
    target_paths = paths[:2] if app.current_mode == 'overlay' else ([paths[1]] if side == 'right' and len(paths) >= 2 else [paths[0]])
    for path in target_paths:
        key = os.path.abspath(path)
        wc, ww = app.window_settings.get(key, app._default_window(path))
        ww = float(np.clip(ww * (1.0 + dx * 0.01), 8.0, 20000.0))
        wc -= dy * max(1.0, ww) * 0.005
        app.window_settings[key] = (float(wc), ww)
    app._viewer_pixmap_cache.clear()
    wc, ww = app.window_settings[os.path.abspath(target_paths[0])]
    app.lbl_windowing.setText(f"W/L: WW {ww:.0f} | WL {wc:.0f} | Orta fare ile ayarla")
    app.update_viewers()


def update_viewers(app):
    selected_items = app.study_list_widget.selectedItems()
    selected_paths = []
    for item in selected_items:
        path = item.data(Qt.UserRole)
        if path and os.path.exists(path):
            selected_paths.append(path)
        elif item.text() in app.loaded_files:
            selected_paths.append(app.loaded_files[item.text()])

    if not selected_paths:
        next_step = "Tetkik Yükle ile başlayın. Sonra bir görüntü seçerek inceleme veya iki görüntü seçerek karşılaştırma yapın."
    elif len(selected_paths) == 1:
        next_step = "1 tetkik seçildi. Yan yana/Overlay için ikinci tetkiki seçin veya Cobb Ölç ile tek görüntü ölçümü yapın."
    else:
        mode_text = "Overlay karşılaştırma" if app.current_mode == "overlay" else "Yan yana karşılaştırma"
        next_step = f"{len(selected_paths)} tetkik seçildi · {mode_text}. Sıradaki adım: Otomatik Hizala, sonra ölçüm veya rapor."
    set_context(getattr(app, "tracking_context_label", None), next_step)

    app.scene_left.clear()
    app.scene_right.clear()
    app.overlay_item = None
    app.cobb_points.clear()

    if app.current_mode == 'side_by_side':
        app.view_right.setVisible(True)
        if len(selected_paths) >= 1:
            pix_left = app.get_image_pixmap(selected_paths[0])
            if not pix_left.isNull():
                app.scene_left.addPixmap(pix_left)
                app.view_left.fitInView(app.scene_left.itemsBoundingRect(), Qt.KeepAspectRatio)
        if len(selected_paths) >= 2:
            pix_right = app.get_image_pixmap(selected_paths[1])
            if not pix_right.isNull():
                app.scene_right.addPixmap(pix_right)
                app.view_right.fitInView(app.scene_right.itemsBoundingRect(), Qt.KeepAspectRatio)
        # Yan Yana modunda da seçim değiştiğinde Otomatik Hizala butonunun
        # aktif/pasif durumunu güncelle. Önceki sürüm burada erken return
        # yaptığı için buton ilk oluşturulduğu disabled durumda kalıyordu.
        app._refresh_auto_align_button()
        return

    if app.current_mode == 'overlay':
        app.view_right.setVisible(False)
        if not selected_paths:
            return
        pix_base = app.get_image_pixmap(selected_paths[0])
        if pix_base.isNull():
            return
        base_item = app.scene_left.addPixmap(pix_base)
        base_item.setZValue(0)

        if len(selected_paths) >= 2:
            pix_overlay = app.get_image_pixmap(selected_paths[1])
            if not pix_overlay.isNull():
                base_w = max(1, pix_base.width())
                pix_overlay = pix_overlay.scaledToWidth(base_w, Qt.SmoothTransformation)
                initial_scale = 1.0
                app._overlay_initial_scale = initial_scale
                app.overlay_item = app.scene_left.addPixmap(pix_overlay)
                app.overlay_item.setZValue(1)
                app.overlay_item.setOpacity(app.overlay_opacity)
                app._apply_overlay_transform()
                app.overlay_item.setToolTip("Sol fare ile sürükleyerek overlay'i hizalayın")

        app.view_left.fitInView(pix_base.rect(), Qt.KeepAspectRatio)
        app._update_overlay_label()

    app._refresh_auto_align_button()



def _apply_overlay_transform(app):
    """Apply translation + uniform scale + rotation as one exact Qt transform."""
    item = getattr(app, "overlay_item", None)
    if item is None:
        return

    scale = float(getattr(app, "overlay_scale", 1.0) or 1.0)
    rotation = float(getattr(app, "overlay_rotation", 0.0) or 0.0)
    dx = float(getattr(app, "overlay_offset_x", 0.0) or 0.0)
    dy = float(getattr(app, "overlay_offset_y", 0.0) or 0.0)

    radians = math.radians(rotation)
    c = math.cos(radians)
    s = math.sin(radians)

    transform = QTransform()
    transform.setMatrix(
        scale * c,  scale * s, 0.0,
       -scale * s,  scale * c, 0.0,
        dx,           dy,       1.0,
    )
    item.setTransform(transform, combine=False)


def _update_overlay_label(app):
    if hasattr(app, 'lbl_overlay_offset'):
        app.lbl_overlay_offset.setText(
            f"Yatay {app.overlay_offset_x:+.0f} | Dikey {app.overlay_offset_y:+.0f} | "
            f"Ölçek {app.overlay_scale:.2f}x | Döndürme {getattr(app, 'overlay_rotation', 0.0):+.1f}°"
        )


def move_overlay(app, dx, dy):
    if app.current_mode != 'overlay' or app.overlay_item is None:
        return
    app.overlay_offset_x += float(dx)
    app.overlay_offset_y += float(dy)
    app._apply_overlay_transform()
    app._sync_overlay_sliders()
    app._update_overlay_label()


def _sync_overlay_sliders(app):
    for name, value in (
        ('overlay_x_slider', int(round(app.overlay_offset_x))),
        ('overlay_y_slider', int(round(app.overlay_offset_y))),
        ('overlay_zoom_slider', int(round(app.overlay_scale * 100.0))),
        ('overlay_rotation_slider', int(round(getattr(app, 'overlay_rotation', 0.0) * 10.0))),
    ):
        slider = getattr(app, name, None)
        if slider is not None:
            slider.blockSignals(True)
            slider.setValue(max(slider.minimum(), min(slider.maximum(), value)))
            slider.blockSignals(False)


def on_overlay_x_changed(app, value):
    app.overlay_offset_x = float(value)
    if app.overlay_item is not None:
        app._apply_overlay_transform()
    app._update_overlay_label()


def on_overlay_y_changed(app, value):
    app.overlay_offset_y = float(value)
    if app.overlay_item is not None:
        app._apply_overlay_transform()
    app._update_overlay_label()


def on_overlay_zoom_changed(app, value):
    app.overlay_scale = max(0.5, float(value) / 100.0)
    if app.overlay_item is not None:
        app._apply_overlay_transform()
    app._update_overlay_label()



def on_overlay_rotation_changed(app, value):
    app.overlay_rotation = float(value) / 10.0
    if app.overlay_item is not None:
        app._apply_overlay_transform()
    app._update_overlay_label()


def on_overlay_opacity_changed(app, value):
    app.overlay_opacity = value / 100.0
    if app.overlay_item is not None:
        app.overlay_item.setOpacity(app.overlay_opacity)



def _pixmap_to_gray_array(pixmap):
    """Safe QPixmap -> contiguous uint8 grayscale NumPy array."""
    from PySide6.QtGui import QImage
    image = pixmap.toImage().convertToFormat(QImage.Format.Format_Grayscale8)
    width = image.width()
    height = image.height()
    if width <= 0 or height <= 0:
        return None
    raw = bytes(image.bits())
    stride = image.bytesPerLine()
    array = np.frombuffer(raw, dtype=np.uint8).reshape((height, stride))[:, :width]
    return np.ascontiguousarray(array)


def _registration_gray_from_path(app, path):
    """Load a registration image independently of the visible overlay rendering."""
    try:
        if app._viewer_is_dicom(path):
            import pydicom
            ds = pydicom.dcmread(path)
            arr = np.asarray(ds.pixel_array)
            if arr.ndim > 2:
                # Multi-frame / color-like data: use the first grayscale frame.
                arr = arr[0] if arr.shape[0] <= 64 else arr[..., 0]
            arr = np.asarray(arr, dtype=np.float32)
            if arr.ndim != 2:
                arr = np.squeeze(arr)
            if arr.ndim != 2:
                raise ValueError(f"Beklenmeyen DICOM matris boyutu: {arr.shape}")

            finite = arr[np.isfinite(arr)]
            if finite.size == 0:
                raise ValueError("DICOM piksel matrisi boş.")
            lo, hi = np.percentile(finite, (1.0, 99.0))
            if hi <= lo:
                lo, hi = float(finite.min()), float(finite.max())
            if hi <= lo:
                return np.zeros(arr.shape, dtype=np.uint8)

            arr = np.clip((arr - lo) * (255.0 / (hi - lo)), 0, 255)
            if str(getattr(ds, "PhotometricInterpretation", "")).upper() == "MONOCHROME1":
                arr = 255.0 - arr
            return np.ascontiguousarray(arr.astype(np.uint8))
    except Exception:
        # Fall back to the application's rendered pixmap for non-DICOM or
        # unsupported DICOM variants.
        pass

    pixmap = app.get_image_pixmap(path)
    if pixmap.isNull():
        return None
    return _pixmap_to_gray_array(pixmap)


def _registration_view_position(path):
    """Best-effort AP/PA/LAT label used only to reject obvious mismatches."""
    try:
        import pydicom
        ds = pydicom.dcmread(path, stop_before_pixels=True)
        value = str(getattr(ds, "ViewPosition", "") or "").upper().strip()
        if value:
            return value
        description = " ".join(
            str(getattr(ds, name, "") or "")
            for name in ("SeriesDescription", "StudyDescription", "ProtocolName")
        ).upper()
        if "LAT" in description or "LATERAL" in description:
            return "LAT"
        if "PA" in description:
            return "PA"
        if "AP" in description:
            return "AP"
    except Exception:
        pass
    return ""


def _refresh_auto_align_button(app):
    """Keep the button clickable; validation is reported when the user clicks it."""
    button = getattr(app, "btn_overlay_auto_align", None)
    if button is None:
        return
    paths = app._selected_window_paths()
    if len(paths) != 2:
        button.setEnabled(False)
        button.setToolTip("Otomatik hizalama için tam olarak iki tetkik seçin.")
        return
    button.setEnabled(True)

    try:
        meta0 = app._viewer_metadata(paths[0])
        meta1 = app._viewer_metadata(paths[1])
        pid0 = str((meta0 or {}).get("patient_id", "") or "").strip()
        pid1 = str((meta1 or {}).get("patient_id", "") or "").strip()
        known0 = pid0 and pid0.upper() not in {"UNKNOWN", "BILINMIYOR", "BİLİNMİYOR"}
        known1 = pid1 and pid1.upper() not in {"UNKNOWN", "BILINMIYOR", "BİLİNMİYOR"}
        if known0 and known1 and pid0 != pid1:
            button.setToolTip("Farklı hastalara ait görüntüler otomatik hizalanamaz.")
            return
    except Exception:
        pass

    button.setToolTip("İki seçili tetkiki otomatik X/Y/Zoom ile hizala")



def _registration_pair_metadata(path):
    """Return only metadata needed to decide whether two studies are comparable."""
    result = {
        "patient_id": "",
        "study_uid": "",
        "series_uid": "",
        "view_position": "",
        "study_date": "",
    }
    try:
        import pydicom
        ds = pydicom.dcmread(path, stop_before_pixels=True)
        result["patient_id"] = str(getattr(ds, "PatientID", "") or "").strip()
        result["study_uid"] = str(getattr(ds, "StudyInstanceUID", "") or "").strip()
        result["series_uid"] = str(getattr(ds, "SeriesInstanceUID", "") or "").strip()
        result["study_date"] = str(getattr(ds, "StudyDate", "") or "").strip()
        result["view_position"] = _registration_view_position(path)
    except Exception:
        pass
    return result


def _registration_overlap_ratio(ref_shape, mov_shape, scale, dx, dy):
    """Axis-aligned overlap ratio after scale/translation, normalized to moving area."""
    ref_h, ref_w = ref_shape[:2]
    mov_h, mov_w = mov_shape[:2]
    left = float(dx)
    top = float(dy)
    right = left + float(mov_w) * float(scale)
    bottom = top + float(mov_h) * float(scale)

    inter_left = max(0.0, left)
    inter_top = max(0.0, top)
    inter_right = min(float(ref_w), right)
    inter_bottom = min(float(ref_h), bottom)

    if inter_right <= inter_left or inter_bottom <= inter_top:
        return 0.0

    intersection = (inter_right - inter_left) * (inter_bottom - inter_top)
    moving_area = max(1.0, (right - left) * (bottom - top))
    return float(intersection / moving_area)


def auto_align_overlay(app):
    """Automatic X/Y/Zoom registration with explicit diagnostics."""
    from PySide6.QtWidgets import QMessageBox, QApplication

    app.statusBar().showMessage("Otomatik hizalama başlatıldı…")
    QApplication.processEvents()

    try:
        if getattr(app, 'overlay_locked', False):
            QMessageBox.information(app, "Otomatik hizalama", "Overlay hizalaması kilitli. Önce kilidi açın.")
            return False

        paths = app._selected_window_paths()
        if len(paths) != 2:
            QMessageBox.information(
                app, "Otomatik hizalama",
                f"Tam olarak iki görüntü seçmelisiniz.\nŞu an seçili görüntü sayısı: {len(paths)}"
            )
            return False

        # Clinical-pair guard: tracking registration is intended for the same
        # patient at different examinations, not neighboring images/pieces from
        # the same acquisition.
        pair_ref = _registration_pair_metadata(paths[0])
        pair_mov = _registration_pair_metadata(paths[1])

        pid_ref = pair_ref["patient_id"]
        pid_mov = pair_mov["patient_id"]
        known_pid_ref = pid_ref and pid_ref.upper() not in {"UNKNOWN", "BILINMIYOR", "BİLİNMİYOR"}
        known_pid_mov = pid_mov and pid_mov.upper() not in {"UNKNOWN", "BILINMIYOR", "BİLİNMİYOR"}

        if known_pid_ref and known_pid_mov and pid_ref != pid_mov:
            QMessageBox.warning(
                app, "Otomatik hizalama",
                "Seçilen görüntüler farklı hastalara ait. Otomatik hizalama yapılmadı."
            )
            return False

        if (
            pair_ref["study_uid"] and pair_mov["study_uid"]
            and pair_ref["study_uid"] == pair_mov["study_uid"]
        ):
            QMessageBox.information(
                app, "Otomatik hizalama",
                "Bu iki görüntü aynı DICOM tetkikine (aynı StudyInstanceUID) ait.\n\n"
                "Takip registration'ı için aynı hastanın farklı tarihlerde çekilmiş "
                "aynı projeksiyondaki grafilerini seçin."
            )
            return False

        # Same-patient guard.
        try:
            meta_ref = app._viewer_metadata(paths[0])
            meta_mov = app._viewer_metadata(paths[1])
            patient_ref = str((meta_ref or {}).get("patient_id", "") or "").strip()
            patient_mov = str((meta_mov or {}).get("patient_id", "") or "").strip()
            known_ref = patient_ref and patient_ref.upper() not in {"UNKNOWN", "BILINMIYOR", "BİLİNMİYOR"}
            known_mov = patient_mov and patient_mov.upper() not in {"UNKNOWN", "BILINMIYOR", "BİLİNMİYOR"}
            if known_ref and known_mov and patient_ref != patient_mov:
                QMessageBox.warning(
                    app, "Otomatik hizalama",
                    "Seçilen görüntüler farklı hastalara ait. Otomatik hizalama yapılmadı."
                )
                return False
        except Exception:
            pass

        # Reject an obvious AP/PA vs LAT mismatch.
        view_ref = _registration_view_position(paths[0])
        view_mov = _registration_view_position(paths[1])
        lateral = {"LAT", "LATERAL", "LL", "RL"}
        frontal = {"AP", "PA"}
        if view_ref and view_mov:
            ref_is_lat = view_ref in lateral or "LAT" in view_ref
            mov_is_lat = view_mov in lateral or "LAT" in view_mov
            ref_is_front = view_ref in frontal
            mov_is_front = view_mov in frontal
            if (ref_is_lat and mov_is_front) or (mov_is_lat and ref_is_front):
                QMessageBox.warning(
                    app, "Otomatik hizalama",
                    f"Projeksiyonlar uyumlu değil: {view_ref} ↔ {view_mov}.\n"
                    "Aynı projeksiyondaki takip grafilerini seçin."
                )
                return False
            if ref_is_lat != mov_is_lat and not (ref_is_front and mov_is_front):
                QMessageBox.warning(
                    app, "Otomatik hizalama",
                    f"Projeksiyon uyumu doğrulanamadı: {view_ref} ↔ {view_mov}.\n"
                    "Takip karşılaştırması için aynı projeksiyonu seçin."
                )
                return False

        try:
            import cv2
        except Exception as exc:
            QMessageBox.warning(
                app, "Otomatik hizalama",
                "OpenCV bulunamadı.\n\npip install opencv-python\n\n" + str(exc)
            )
            return False

        ref = _registration_gray_from_path(app, paths[0])
        mov = _registration_gray_from_path(app, paths[1])
        if ref is None or mov is None:
            raise RuntimeError("Seçili görüntüler piksel matrisine dönüştürülemedi.")

        # Match the displayed geometry: moving image is normalized to reference width.
        target_w = max(1, int(ref.shape[1]))
        mov_h = max(1, int(round(mov.shape[0] * target_w / max(1, mov.shape[1]))))
        mov = cv2.resize(mov, (target_w, mov_h), interpolation=cv2.INTER_AREA)

        max_dim = max(ref.shape[0], ref.shape[1], mov.shape[0], mov.shape[1])
        work_scale = min(1.0, 1200.0 / max(1, max_dim))
        if work_scale < 1.0:
            ref_work = cv2.resize(ref, None, fx=work_scale, fy=work_scale, interpolation=cv2.INTER_AREA)
            mov_work = cv2.resize(mov, None, fx=work_scale, fy=work_scale, interpolation=cv2.INTER_AREA)
        else:
            ref_work, mov_work = ref, mov

        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        ref_work = clahe.apply(ref_work)
        mov_work = clahe.apply(mov_work)

        # Limit feature search to the central anatomy; collimation borders/text
        # otherwise dominate radiograph feature matching.
        def central_mask(img):
            h, w = img.shape[:2]
            mask = np.zeros((h, w), dtype=np.uint8)
            x0, x1 = int(w * 0.12), int(w * 0.88)
            y0, y1 = int(h * 0.05), int(h * 0.95)
            mask[y0:y1, x0:x1] = 255
            return mask

        orb = cv2.ORB_create(nfeatures=5000, scaleFactor=1.2, nlevels=8, fastThreshold=7)
        kp_ref, des_ref = orb.detectAndCompute(ref_work, central_mask(ref_work))
        kp_mov, des_mov = orb.detectAndCompute(mov_work, central_mask(mov_work))

        if des_ref is None or des_mov is None or len(kp_ref) < 12 or len(kp_mov) < 12:
            QMessageBox.information(
                app, "Otomatik hizalama",
                f"Yeterli anatomik özellik bulunamadı.\n"
                f"Referans özellik: {len(kp_ref) if kp_ref is not None else 0}\n"
                f"Karşılaştırma özellik: {len(kp_mov) if kp_mov is not None else 0}"
            )
            return False

        matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)
        pairs = matcher.knnMatch(des_mov, des_ref, k=2)
        good = []
        for pair in pairs:
            if len(pair) == 2:
                m, n = pair
                if m.distance < 0.78 * n.distance:
                    good.append(m)

        if len(good) < 10:
            QMessageBox.information(
                app, "Otomatik hizalama",
                f"Anatomik eşleşme yetersiz: {len(good)} eşleşme.\n\n"
                "Bu iki görüntü farklı anatomi, farklı projeksiyon veya çok farklı çekim alanı içeriyor olabilir."
            )
            return False

        src = np.float32([kp_mov[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
        dst = np.float32([kp_ref[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)

        matrix, inliers = cv2.estimateAffinePartial2D(
            src, dst,
            method=cv2.RANSAC,
            ransacReprojThreshold=5.0,
            maxIters=4000,
            confidence=0.995,
            refineIters=25,
        )
        if matrix is None or inliers is None:
            QMessageBox.information(app, "Otomatik hizalama", "Güvenilir dönüşüm hesaplanamadı.")
            return False

        mask = inliers.ravel().astype(bool)
        inlier_count = int(mask.sum())
        inlier_ratio = inlier_count / max(1, len(good))
        if inlier_count < 8 or inlier_ratio < 0.22:
            QMessageBox.information(
                app, "Otomatik hizalama",
                f"Hizalama güveni düşük: {inlier_count}/{len(good)} "
                f"(%{inlier_ratio * 100:.0f}).\nMevcut hizalama değiştirilmedi."
            )
            return False

        a, b = float(matrix[0, 0]), float(matrix[1, 0])
        estimated_scale = float((a * a + b * b) ** 0.5)
        rotation_deg = float(math.degrees(math.atan2(b, a)))

        if not (0.50 <= estimated_scale <= 1.60):
            QMessageBox.information(
                app, "Otomatik hizalama",
                f"Hesaplanan ölçek güvenli aralık dışında: {estimated_scale:.2f}x."
            )
            return False

        if abs(rotation_deg) > 15.0:
            QMessageBox.information(
                app, "Otomatik hizalama",
                f"Hesaplanan rotasyon güvenli aralık dışında: {rotation_deg:+.1f}°.\n"
                "Takip grafileri için ±15° sınırı uygulanıyor."
            )
            return False

        # Use the exact affine translation. Scale and rotation are dimensionless;
        # only translation must be converted back from the work resolution.
        dx_work = float(matrix[0, 2])
        dy_work = float(matrix[1, 2])
        dx = dx_work / max(work_scale, 1e-6)
        dy = dy_work / max(work_scale, 1e-6)

        ref_h, ref_w = ref.shape[:2]
        # A true longitudinal follow-up pair should not need an extreme global
        # translation once the moving image width has already been normalized.
        max_dx = max(80.0, ref_w * 0.35)
        max_dy = max(120.0, ref_h * 0.35)
        if abs(dx) > max_dx or abs(dy) > max_dy:
            QMessageBox.information(
                app, "Otomatik hizalama",
                "Hesaplanan kaydırma anatomik takip için aşırı büyük.\n\n"
                f"ΔX {dx:+.0f} (sınır ±{max_dx:.0f})\n"
                f"ΔY {dy:+.0f} (sınır ±{max_dy:.0f})\n\n"
                "Bu çift aynı çekimin farklı parçaları veya farklı kapsamlı görüntüler olabilir."
            )
            return False

        # Inliers must be distributed over a meaningful part of the anatomy.
        dst_inliers = dst.reshape(-1, 2)[mask]
        span_x = float(np.ptp(dst_inliers[:, 0])) if len(dst_inliers) else 0.0
        span_y = float(np.ptp(dst_inliers[:, 1])) if len(dst_inliers) else 0.0
        span_x_ratio = span_x / max(1.0, ref_work.shape[1])
        span_y_ratio = span_y / max(1.0, ref_work.shape[0])

        if span_y_ratio < 0.22 or span_x_ratio < 0.08:
            QMessageBox.information(
                app, "Otomatik hizalama",
                "Eşleşmeler anatomik olarak yeterince yaygın değil.\n\n"
                f"Yatay yayılım: %{span_x_ratio * 100:.0f}\n"
                f"Dikey yayılım: %{span_y_ratio * 100:.0f}\n\n"
                "Yanlış pozitif hizalama riski nedeniyle sonuç uygulanmadı."
            )
            return False

        overlap = _registration_overlap_ratio(
            ref.shape, mov.shape, estimated_scale, dx, dy
        )
        if overlap < 0.55:
            QMessageBox.information(
                app, "Otomatik hizalama",
                f"Görüntü örtüşmesi yetersiz: %{overlap * 100:.0f}.\n\n"
                "Takip grafilerinin benzer anatomik kapsamda olması gerekir."
            )
            return False

        before = app._capture_edit_state()
        app.overlay_offset_x = dx
        app.overlay_offset_y = dy
        app.overlay_scale = estimated_scale
        app.overlay_rotation = rotation_deg
        app._sync_overlay_sliders()

        if getattr(app, 'current_mode', '') != 'overlay':
            app.set_overlay_mode()
        else:
            app.update_viewers()

        app._history_commit("Overlay otomatik hizala", before)

        message = (
            f"Otomatik hizalama tamamlandı.\n\n"
            f"ΔX: {dx:+.0f}\nΔY: {dy:+.0f}\nZoom: {estimated_scale:.2f}x\n"
            f"Rotasyon: {rotation_deg:+.1f}°\n"
            f"Güven: %{inlier_ratio * 100:.0f} ({inlier_count}/{len(good)})\n"
            f"Örtüşme: %{overlap * 100:.0f}\n"
            f"Eşleşme yayılımı: X %{span_x_ratio * 100:.0f} | Y %{span_y_ratio * 100:.0f}"
        )
        app.statusBar().showMessage(message.replace("\n", " | "))
        QMessageBox.information(app, "Otomatik hizalama", message)
        return True

    except Exception as exc:
        import traceback
        traceback.print_exc()
        QMessageBox.critical(
            app, "Otomatik hizalama hatası",
            f"Registration sırasında hata oluştu:\n\n{type(exc).__name__}: {exc}"
        )
        app.statusBar().showMessage(f"Otomatik hizalama hatası: {type(exc).__name__}: {exc}")
        return False


def reset_overlay_adjustment(app):
    before = app._capture_edit_state()
    app.overlay_offset_x = 0.0
    app.overlay_offset_y = 0.0
    app.overlay_opacity = 0.50
    app.overlay_scale = 1.0
    app.overlay_rotation = 0.0
    app._sync_overlay_sliders()
    if hasattr(app, 'overlay_opacity_slider'):
        app.overlay_opacity_slider.blockSignals(True)
        app.overlay_opacity_slider.setValue(50)
        app.overlay_opacity_slider.blockSignals(False)
    app.update_viewers()
    app._history_commit("Overlay sıfırla", before)
    app.statusBar().showMessage("Overlay hizalaması, zoom ve saydamlık sıfırlandı.")


def _repolish_button(button):
    """QSS dynamic property değişikliğini anında görünüme uygular."""
    if button is None:
        return
    style = button.style()
    style.unpolish(button)
    style.polish(button)
    button.update()


def _set_tracking_button_state(button, property_name, active):
    if button is None:
        return
    button.setProperty(property_name, bool(active))
    _repolish_button(button)


def set_side_by_side_mode(app):
    app.current_mode = "side_by_side"
    _set_tracking_button_state(app.btn_side_by_side, "trackingActive", True)
    _set_tracking_button_state(app.btn_overlay, "trackingActive", False)
    app.update_viewers()
    app.statusBar().showMessage("Yan yana karşılaştırma aktif.")


def set_overlay_mode(app):
    app.current_mode = "overlay"
    _set_tracking_button_state(app.btn_overlay, "trackingActive", True)
    _set_tracking_button_state(app.btn_side_by_side, "trackingActive", False)
    app.update_viewers()
    app.statusBar().showMessage("Overlay karşılaştırma aktif.")


def toggle_cobb_measurement(app):
    app.cobb_mode_active = not app.cobb_mode_active
    for v in (getattr(app, 'view_left', None), getattr(app, 'view_right', None), getattr(app, 'stitch_view', None)):
        if v is not None:
            v.refresh_cursor()
    if app.cobb_mode_active:
        _set_tracking_button_state(app.btn_measure_cobb, "trackingMeasurementActive", True)
        app.cobb_points.clear()
        app.cobb_target_side = None
        app.statusBar().showMessage("Cobb Ölçümü: Lütfen ölçüm yapmak istediğiniz ekrana tıklayarak başlayın.")
    else:
        _set_tracking_button_state(app.btn_measure_cobb, "trackingMeasurementActive", False)
        app.statusBar().showMessage("Cobb Açısı Ölçüm Modu kapatıldı.")


def handle_cobb_click(app, side: str, pos: QPointF):
    if app.cobb_target_side is None:
        app.cobb_target_side = side
    elif app.cobb_target_side != side:
        return

    app.cobb_points.append(pos)
    if side == 'left':
        target_scene = app.scene_left
    elif side == 'right':
        target_scene = app.scene_right
    else:
        target_scene = app.stitch_scene

    pen = QPen(Qt.red, 4)
    marker = target_scene.addEllipse(pos.x() - 4, pos.y() - 4, 8, 8, pen)
    app.cobb_items.append(marker)

    n = len(app.cobb_points)
    if n == 2:
        line = target_scene.addLine(app.cobb_points[0].x(), app.cobb_points[0].y(),
                             app.cobb_points[1].x(), app.cobb_points[1].y(), pen)
        app.cobb_items.append(line)

        app.statusBar().showMessage(f"Cobb Ölçümü ({side.upper()}): Alt omurga için 2 nokta daha belirleyin.")
    elif n == 4:
        pen_blue = QPen(Qt.cyan, 3)
        line = target_scene.addLine(app.cobb_points[2].x(), app.cobb_points[2].y(),
                             app.cobb_points[3].x(), app.cobb_points[3].y(), pen_blue)
        app.cobb_items.append(line)

        try:
            angle_deg = calculate_acute_cobb_angle(*app.cobb_points)
        except ValueError:
            app.statusBar().showMessage("Cobb Ölçümü: Çizgi uzunluğu sıfır olamaz; ölçüm kaydedilmedi.")
        else:

            app.statusBar().showMessage(f"📐 Hesaplanan Cobb Açısı ({side.upper()}): {angle_deg:.2f}°")

            text_item = target_scene.addText(f"Cobb: {angle_deg:.2f}°", QFont("Segoe UI", 14, QFont.Bold))
            text_item.setDefaultTextColor(Qt.yellow)
            text_item.setPos(app.cobb_points[2])
            app.cobb_items.append(text_item)

        app.cobb_points.clear()
        app.cobb_target_side = None
        app.cobb_mode_active = False
        _set_tracking_button_state(app.btn_measure_cobb, "trackingMeasurementActive", False)
        if hasattr(app, 'chk_cobb_mode'):
            app.chk_cobb_mode.blockSignals(True)
            app.chk_cobb_mode.setChecked(False)
            app.chk_cobb_mode.blockSignals(False)
        for v in (getattr(app, 'view_left', None), getattr(app, 'view_right', None), getattr(app, 'stitch_view', None)):
            if v is not None:
                v.refresh_cursor()


def clear_cobb_measurement(app):
    app.cobb_points.clear()
    app.cobb_target_side = None
    app.cobb_mode_active = False
    _set_tracking_button_state(app.btn_measure_cobb, "trackingMeasurementActive", False)
    if hasattr(app, 'chk_cobb_mode'):
        app.chk_cobb_mode.blockSignals(True)
        app.chk_cobb_mode.setChecked(False)
        app.chk_cobb_mode.blockSignals(False)
    for item in list(getattr(app, "cobb_items", [])):
        for scene in (getattr(app, 'scene_left', None), getattr(app, 'scene_right', None), getattr(app, 'stitch_scene', None)):
            if scene is not None and item.scene() is scene:
                scene.removeItem(item)
    app.cobb_items.clear()
    for v in (getattr(app, 'view_left', None), getattr(app, 'view_right', None), getattr(app, 'stitch_view', None)):
        if v is not None:
            v.refresh_cursor()
    app.statusBar().showMessage("Ölçüm temizlendi.")

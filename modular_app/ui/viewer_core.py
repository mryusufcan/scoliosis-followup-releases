"""Viewer dosya agaci, metadata ve render orkestrasyonu."""

# VIEWER_CORE_STAGE26
import math
import os
import pydicom

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import QGraphicsItem, QMenu, QMessageBox, QTreeWidgetItem
from modular_app.ui.ui_clarity import set_context
from modular_app.performance_utils import cache_get, cache_put
from modular_app.ui.dicom_codec import codec_status


# AÇILAN GÖRÜNTÜLER AĞACI — önizlemesiz hiyerarşi satırları yoğun kalır;
# küçük resim taşıyan gerçek dosya satırları ise okunabilir yüksekliği korur.
VIEWER_TREE_GROUP_ROW_HEIGHT = 22
VIEWER_TREE_PREVIEW_ROW_HEIGHT = 64

def _add_viewer_paths(app, paths):
    known_paths = {
        os.path.abspath(item.data(0, Qt.UserRole))
        for item in app._viewer_file_items()
        if item.data(0, Qt.UserRole)
    }
    added = 0
    first_added_item = None
    new_tracking_paths = []
    for path in paths:
        absolute_path = os.path.abspath(path)
        app._remember_shared_paths([absolute_path])
        if absolute_path in known_paths:
            continue
        # Dosyaları listeye eklerken tam Pixel Data decode etmeyin. Metadata
        # header cache'ten okunur; ilk seçili görüntünün gerçek render'ı
        # render_viewer_file içindeki asenkron preload yoluna bırakılır.
        metadata = app._viewer_metadata(absolute_path)

        list_label = os.path.basename(absolute_path)
        if metadata is not None:
            series_label = metadata["description"] or metadata["body_part"]
            if series_label:
                list_label += f"\n{series_label[:36]}"
        item = QTreeWidgetItem([list_label])
        item.setToolTip(0, f"{absolute_path}\nÖnizleme seçildiğinde arka planda hazırlanır.")
        # Dosya satırı tam görüntü decode edilmeden hemen görünür.
        item.setSizeHint(0, QSize(0, VIEWER_TREE_PREVIEW_ROW_HEIGHT))
        item.setData(0, Qt.UserRole, absolute_path)

        parent = app._viewer_tree_group(metadata)

        parent.addChild(item)
        _, added_to_tracking = app._ensure_tracking_path(absolute_path)
        if added_to_tracking:
            new_tracking_paths.append(absolute_path)
        if first_added_item is None:
            first_added_item = item
        known_paths.add(absolute_path)
        added += 1
    register_paths = getattr(app, "_register_paths", None)
    if new_tracking_paths and callable(register_paths):
        dicom_paths = [path for path in new_tracking_paths if app._viewer_is_dicom(path)]
        if dicom_paths:
            register_paths(dicom_paths)
    return added, first_added_item


def _viewer_file_items(app):
    items = []

    def collect(parent):
        for index in range(parent.childCount()):
            child = parent.child(index)
            if child.data(0, Qt.UserRole):
                items.append(child)
            else:
                collect(child)

    for index in range(app.viewer_file_tree.topLevelItemCount()):
        top_level = app.viewer_file_tree.topLevelItem(index)
        if top_level.data(0, Qt.UserRole):
            items.append(top_level)
        else:
            collect(top_level)
    return items


def _viewer_tree_find_or_add(app, parent, title):
    count = app.viewer_file_tree.topLevelItemCount() if parent is None else parent.childCount()
    get_item = app.viewer_file_tree.topLevelItem if parent is None else parent.child
    for index in range(count):
        candidate = get_item(index)
        if candidate.text(0) == title and not candidate.data(0, Qt.UserRole):
            return candidate

    group = QTreeWidgetItem([title])
    group.setFlags(group.flags() & ~Qt.ItemFlag.ItemIsSelectable)
    # Hasta / tetkik / seri düğümlerinde önizleme yoktur. Sabit, kısa satır
    # boyutu tek hastalık listelerde gereksiz dikey kaydırmayı önler.
    group.setSizeHint(0, QSize(0, VIEWER_TREE_GROUP_ROW_HEIGHT))
    if parent is None:
        app.viewer_file_tree.addTopLevelItem(group)
    else:
        parent.addChild(group)
    group.setExpanded(True)
    return group


def _viewer_tree_group(app, metadata):
    if metadata is None:
        patient_title, study_title, series_title = "Diğer dosyalar", "DICOM dışı", "Görüntüler"
    else:
        patient_title = f"{metadata['patient_name']} | ID: {metadata['patient_id']}"
        study_parts = [metadata['study_date'], metadata['description']]
        study_title = " | ".join(part for part in study_parts if part) or "Tetkik"
        series_parts = [metadata['modality'], metadata['body_part'], metadata['laterality']]
        series_title = " | ".join(part for part in series_parts if part) or "Seri"

    patient_group = app._viewer_tree_find_or_add(None, patient_title)
    study_group = app._viewer_tree_find_or_add(patient_group, study_title)
    return app._viewer_tree_find_or_add(study_group, series_title)


def _remove_tree_item_and_empty_groups(app, tree, item):
    parent = item.parent()
    if parent is None:
        index = tree.indexOfTopLevelItem(item)
        if index >= 0:
            tree.takeTopLevelItem(index)
        return
    parent.removeChild(item)
    while parent is not None and parent.childCount() == 0:
        grand = parent.parent()
        if grand is None:
            index = tree.indexOfTopLevelItem(parent)
            if index >= 0:
                tree.takeTopLevelItem(index)
            break
        grand.removeChild(parent)
        parent = grand


def show_viewer_file_context_menu(app, pos):
    clicked = app.viewer_file_tree.itemAt(pos)
    if clicked is None or not clicked.data(0, Qt.UserRole):
        return
    if not clicked.isSelected():
        app.viewer_file_tree.clearSelection()
        clicked.setSelected(True)
    selected = [item for item in app.viewer_file_tree.selectedItems() if item.data(0, Qt.UserRole)]
    menu = QMenu(app)
    action = menu.addAction("Görüntüleyiciden kaldır")
    pool_action = menu.addAction("Ortak havuzdan ve tüm modüllerden kaldır")
    chosen = menu.exec(app.viewer_file_tree.viewport().mapToGlobal(pos))
    paths = [os.path.abspath(str(item.data(0, Qt.UserRole))) for item in selected]
    if chosen == pool_action:
        app._remove_paths_from_all_modules(paths)
        app.statusBar().showMessage(f"{len(paths)} dosya ortak havuzdan kaldırıldı. Diskteki dosyalar silinmedi.")
        return
    if chosen != action:
        return
    for item in list(selected):
        app._remove_tree_item_and_empty_groups(app.viewer_file_tree, item)
    for path in paths:
        app._clear_viewer_path_caches(path)

    if app.viewer_current_path and os.path.abspath(app.viewer_current_path) in paths:
        app.stop_viewer_cine()
        app.viewer_scene.clear()
        app.viewer_current_path = None
        app.viewer_pixmap_item = None
        app.viewer_info_label.setText("Önce bir görüntü açın.")
        set_context(getattr(app, "viewer_context_label", None), "Görüntü Aç ile bir DICOM seçin. Ardından inceleme veya ölçüm işlemine geçin.")

    remaining = app._viewer_file_items()
    if remaining:
        app.viewer_file_tree.setCurrentItem(remaining[0])
        app.statusBar().showMessage(f"Görüntüleyiciden {len(paths)} dosya kaldırıldı. Diskteki dosyalar silinmedi.")


def show_selected_viewer_file(app):
    selected = [item for item in app.viewer_file_tree.selectedItems() if item.data(0, Qt.UserRole)]
    if not selected:
        return
    path = selected[0].data(0, Qt.UserRole)
    app._activate_viewer_path_for_tracking(path)
    app.render_viewer_file(path, fit=True)


def render_viewer_file(app, path, fit=False, allow_preload=True):

    if not path:
        return
    absolute_path = os.path.abspath(path)
    is_new_file = absolute_path != app.viewer_current_path
    if is_new_file:
        app.stop_viewer_cine()
        app.viewer_frame_count = app._viewer_frame_count_for_path(absolute_path)
        app.viewer_frame_index = 0

    # Do not block the GUI on the first DICOM pixel decode. Existing cache hits
    # and non-DICOM image paths retain the synchronous path below.
    if (
        allow_preload
        and getattr(app, "_viewer_preload_enabled", False)
        and app._viewer_is_dicom(absolute_path)
    ):
        cache_key = app._viewer_pixmap_cache_key(absolute_path, app.viewer_frame_index)
        if cache_get(app._viewer_only_pixmap_cache, cache_key) is None:
            if is_new_file:
                app.viewer_scene.clear()
                app.viewer_cobb_points.clear()
                app.viewer_cobb_items.clear()
                if hasattr(app, "viewer_cobb_preview_items"):
                    app.viewer_cobb_preview_items.clear()
                app.viewer_length_start = None
                app.viewer_length_items.clear()
                app.viewer_annotation_items.clear()
                app.viewer_markup_items.clear()
                app.viewer_pixmap_item = None
                app.viewer_current_path = absolute_path
                if app.viewer_cobb_mode_active:
                    app.viewer_cobb_mode_active = False
                    app._refresh_viewer_cobb_button()
                if app.viewer_length_mode_active:
                    app.viewer_length_mode_active = False
                    app._refresh_viewer_length_button()
                app.viewer_view.refresh_cursor()
            app.request_viewer_preload(path, fit=fit)
            return

    pixmap = app.get_viewer_file_pixmap(path)

    if pixmap.isNull():
        app.viewer_info_label.setText("Görüntü açılamadı.")
        return

    if is_new_file or app.viewer_pixmap_item is None:
        app.viewer_scene.clear()
        app.viewer_cobb_points.clear()
        app.viewer_cobb_items.clear()
        if hasattr(app, "viewer_cobb_preview_items"):
            app.viewer_cobb_preview_items.clear()
        app.viewer_length_start = None

        app.viewer_length_items.clear()
        app.viewer_annotation_items.clear()
        app.viewer_markup_items.clear()
        app.viewer_pixmap_item = app.viewer_scene.addPixmap(pixmap)
        app.viewer_current_path = os.path.abspath(path)
        if app.viewer_cobb_mode_active:
            app.viewer_cobb_mode_active = False
            app._refresh_viewer_cobb_button()
        if app.viewer_length_mode_active:
            app.viewer_length_mode_active = False
            app._refresh_viewer_length_button()
        app.viewer_view.refresh_cursor()
    else:
        app.viewer_pixmap_item.setPixmap(pixmap)

    app._add_viewer_annotations(path, pixmap)
    if is_new_file:
        app._render_viewer_saved_items(path)
    app._update_viewer_window_label()
    app._refresh_viewer_frame_controls()
    app.viewer_info_label.setText(f"{os.path.basename(path)}  |  {pixmap.width()} × {pixmap.height()} px")

    set_context(
        getattr(app, "viewer_context_label", None),
        f"Aktif görüntü: {os.path.basename(path)} · Sıradaki adım: Görüntüyü Sığdır, W/L ayarla veya ölçüm aracı seç.",
    )

    if fit:
        app.fit_viewer_image()
    else:
        app._update_viewer_zoom_label()


def _viewer_header_for_path(app, file_path):
    """Return a cached, pixel-free DICOM header for repeated viewer queries."""
    path = os.path.abspath(file_path)
    cache = getattr(app, "_viewer_header_cache", None)
    if cache is None:
        cache = {}
        app._viewer_header_cache = cache
    if path in cache:
        return cache_get(cache, path)

    try:
        header = pydicom.dcmread(path, stop_before_pixels=True)
    except Exception:
        header = None
    cache_put(
        cache,
        path,
        header,
        max_entries=getattr(app, "_viewer_header_cache_limit", 32),
    )
    return header


def _path_cache_limit(app):
    return max(1, int(getattr(app, "_viewer_path_cache_limit", 128)))


def _viewer_is_dicom(app, file_path):
    path = os.path.abspath(file_path)
    if path in app._viewer_dicom_flags:
        return cache_get(app._viewer_dicom_flags, path)
    ds = _viewer_header_for_path(app, path)
    is_dicom = ds is not None and (hasattr(ds, "SOPClassUID") or hasattr(ds, "Rows"))
    cache_put(app._viewer_dicom_flags, path, is_dicom, max_entries=_path_cache_limit(app))
    return is_dicom


def _viewer_frame_count_for_path(app, file_path):
    path = os.path.abspath(file_path)
    if path in app._viewer_frame_counts:
        return cache_get(app._viewer_frame_counts, path)
    count = 1
    if app._viewer_is_dicom(path):
        ds = _viewer_header_for_path(app, path)
        if ds is not None:
            try:
                count = max(1, int(getattr(ds, "NumberOfFrames", 1) or 1))
            except Exception:
                pass
    cache_put(app._viewer_frame_counts, path, count, max_entries=_path_cache_limit(app))
    return count


def _viewer_pixel_spacing(app):
    if not app.viewer_current_path or not app._viewer_is_dicom(app.viewer_current_path):
        return None
    try:
        path = os.path.abspath(app.viewer_current_path)
        ds = app._viewer_dataset_cache.get(path)
        if ds is None:
            ds = _viewer_header_for_path(app, path)
        if ds is None:
            return None
        spacing = getattr(ds, "PixelSpacing", None)
        if spacing is None or len(spacing) < 2:
            return None
        values = (float(spacing[0]), float(spacing[1]))
        if any(value <= 0 or not math.isfinite(value) for value in values):
            return None
        return values
    except Exception:
        return None


def clear_viewer_path_caches(app, file_path):
    """Evict every viewer-side cache entry associated with one absolute path."""
    path = os.path.abspath(str(file_path))
    for cache_name in (
        "_viewer_header_cache",
        "_viewer_dicom_flags",
        "_viewer_metadata_cache",
        "_viewer_frame_counts",
        "_viewer_dataset_cache",
        "_default_window_cache",
    ):
        cache = getattr(app, cache_name, None)
        if isinstance(cache, dict):
            cache.pop(path, None)

    pixmap_cache = getattr(app, "_viewer_only_pixmap_cache", None)
    if isinstance(pixmap_cache, dict):
        for key in list(pixmap_cache):
            if isinstance(key, tuple) and key and os.path.abspath(str(key[0])) == path:
                pixmap_cache.pop(key, None)

    decoded_cache = getattr(app, "_viewer_decoded_array_cache", None)
    if isinstance(decoded_cache, dict):
        for key in list(decoded_cache):
            if isinstance(key, tuple) and key and os.path.abspath(str(key[0])) == path:
                decoded_cache.pop(key, None)

    # A removed active path must not leave a worker result queued for a scene
    # that no longer represents that file.
    current = os.path.abspath(str(getattr(app, "viewer_current_path", "") or ""))
    controller = getattr(app, "_viewer_preload_controller", None)
    if controller is not None:
        cancel_path = getattr(controller, "cancel_path", None)
        if callable(cancel_path):
            cancel_path(path)
    if current == path and controller is not None:
        controller.cancel(slot="viewer")
        pending = getattr(app, "_viewer_preload_pending", None)
        if isinstance(pending, dict):
            pending.clear()


def show_viewer_dicom_info(app):

    if not app.viewer_current_path:
        app.statusBar().showMessage("Bilgi için önce bir dosya açın.")
        return
    metadata = app._viewer_metadata(app.viewer_current_path)
    if metadata is None:
        QMessageBox.information(app, "Görüntü bilgileri", f"Dosya: {os.path.basename(app.viewer_current_path)}\n\nBu dosya DICOM olarak okunamadı.")
        return
    spacing = app._viewer_pixel_spacing()
    spacing_text = "—" if spacing is None else f"{spacing[0]:.4g} × {spacing[1]:.4g} mm/piksel"
    default_wc, default_ww = app._default_window(app.viewer_current_path)
    wc, ww = app.viewer_window_settings.get(app.viewer_current_path, (default_wc, default_ww))
    header = _viewer_header_for_path(app, app.viewer_current_path)
    transfer_uid = str(getattr(getattr(header, "file_meta", None), "TransferSyntaxUID", "") or "")
    decoder_status = codec_status(transfer_uid) if transfer_uid else None
    decoder_name = decoder_status.selected_plugin if decoder_status and decoder_status.selected_plugin else "otomatik/fallback"
    text = "\n".join([
        f"Hasta: {metadata['patient_name']}",
        f"Hasta ID: {metadata['patient_id']}",
        f"Tetkik tarihi: {metadata['study_date']}",
        f"Modalite: {metadata['modality']}",
        f"Bölge / seri: {metadata['body_part'] or metadata['description'] or '—'}",
        f"Kare: {app.viewer_frame_index + 1}/{app.viewer_frame_count}",
        f"Pixel Spacing: {spacing_text}",
        f"Aktif W/L: WW {ww:.0f} | WL {wc:.0f}",
        f"Transfer Syntax: {transfer_uid or '—'}",
        f"Decoder: {decoder_name}",
        f"Dosya: {app.viewer_current_path}",
    ])
    QMessageBox.information(app, "DICOM Bilgileri", text)


def _viewer_metadata(app, file_path):
    path = os.path.abspath(file_path)
    if path in app._viewer_metadata_cache:
        return cache_get(app._viewer_metadata_cache, path)
    if not app._viewer_is_dicom(path):
        cache_put(app._viewer_metadata_cache, path, None, max_entries=_path_cache_limit(app))
        return None
    try:
        ds = _viewer_header_for_path(app, path)
        if ds is None:
            data = None
        else:
            def value(name, default="—"):
                item = getattr(ds, name, None)
                text = str(item).strip() if item not in (None, "") else ""
                return text or default

            data = {
                "patient_name": value("PatientName"),
                "patient_id": value("PatientID"),
                "study_date": value("StudyDate"),
                "modality": value("Modality"),
                "body_part": value("BodyPartExamined", ""),
                "description": value("StudyDescription", value("SeriesDescription", "")),
                "laterality": value("ImageLaterality", value("Laterality", "")),
            }
    except Exception:
        data = None
    cache_put(app._viewer_metadata_cache, path, data, max_entries=_path_cache_limit(app))
    return data


def _clear_viewer_annotations(app):
    for item in app.viewer_annotation_items:
        app.viewer_scene.removeItem(item)
    app.viewer_annotation_items.clear()


def _add_viewer_annotations(app, file_path, pixmap):
    app._clear_viewer_annotations()
    if not app.viewer_annotations_visible:
        return
    metadata = app._viewer_metadata(file_path)
    if metadata is None:
        lines = [
            f"Dosya: {os.path.basename(file_path)}",
            f"Görüntü: {pixmap.width()} × {pixmap.height()} px",
        ]
    else:
        default_wc, default_ww = app._default_window(file_path)
        wc, ww = app.viewer_window_settings.get(os.path.abspath(file_path), (default_wc, default_ww))
        body_part = metadata["body_part"] or metadata["description"] or "—"
        lines = [
            f"Hasta: {metadata['patient_name']}   ID: {metadata['patient_id']}",
            f"Tarih: {metadata['study_date']}   {metadata['modality']}   Bölge: {body_part}",
            f"WW: {ww:.0f}   WL: {wc:.0f}   {pixmap.width()} × {pixmap.height()} px",
        ]
        if app.viewer_frame_count > 1:
            lines.append(f"Kare: {app.viewer_frame_index + 1}/{app.viewer_frame_count}")
        if metadata["laterality"]:
            lines.append(f"Taraf: {metadata['laterality']}")

    annotation = app.viewer_scene.addText("\n".join(lines), QFont("Segoe UI", 9))
    annotation.setDefaultTextColor(Qt.white)
    annotation.setPos(36, 36)
    annotation.setZValue(50)
    annotation.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True)
    app.viewer_annotation_items.append(annotation)


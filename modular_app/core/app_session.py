"""Uygulama oturumu, ortak dosya havuzu ve undo/redo yonetimi."""

# APP_SESSION_STAGE29
import copy
import datetime
import json
import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMessageBox


def shutdown_runtime(app):
    """Stop render timers and cancel worker callbacks before the window closes."""
    setattr(app, "_background_closing", True)
    background_pool = getattr(app, "_background_pool", None)
    if background_pool is not None:
        background_pool.clear()
    for timer_name in (
        "_viewer_render_timer",
        "_workspace_render_timer",
        "_stitch_render_timer",
        "_stitch_full_render_timer",
        "viewer_cine_timer",
    ):
        timer = getattr(app, timer_name, None)
        if timer is not None and timer.isActive():
            timer.stop()

    controller = getattr(app, "_viewer_preload_controller", None)
    if controller is not None:
        controller.shutdown()
    preload_pool = getattr(app, "_viewer_preload_pool", None)
    if preload_pool is not None:
        preload_pool.clear()
    pending = getattr(app, "_viewer_preload_pending", None)
    if isinstance(pending, dict):
        pending.clear()


def closeEvent(app, event):

    """Kapanırken çalışma oturumunun kaydedilip kaydedilmeyeceğini sor."""
    has_work = bool(app._shared_pool_paths())
    has_work = has_work or bool(getattr(app, "viewer_measurement_records", []))
    has_work = has_work or bool(getattr(app, "viewer_markup_records", []))
    has_work = has_work or any(getattr(app, "stitch_files", {}).values())

    if not has_work:
        # Önceki kayıt kullanıcı tarafından tekrar istenmediği için temizle.
        try:
            path = app._auto_session_path()
            if os.path.isfile(path):
                os.remove(path)
        except OSError:
            pass
        shutdown_runtime(app)
        event.accept()
        return

    box = QMessageBox(app)
    box.setIcon(QMessageBox.Question)
    box.setWindowTitle("Çalışma oturumunu kaydet")
    box.setText("Açık çalışma oturumu kaydedilsin mi?")
    box.setInformativeText(
        "Evet: Sonraki açılışta dosyalar, ölçümler ve çalışma durumu geri gelir.\n"
        "Hayır: Oturum kaydedilmez ve sonraki açılış temiz başlar.\n"
        "İptal: Uygulamayı kapatma."
    )
    yes_button = box.addButton("Evet, Kaydet", QMessageBox.YesRole)
    no_button = box.addButton("Hayır, Kaydetme", QMessageBox.NoRole)
    cancel_button = box.addButton("İptal", QMessageBox.RejectRole)
    box.setDefaultButton(yes_button)
    box.exec()

    clicked = box.clickedButton()
    if clicked is cancel_button:
        event.ignore()
        return

    if clicked is yes_button:
        app._save_auto_session()
    else:
        # Kullanıcı kaydetme dediyse eski autosession da silinir; aksi halde
        # istemediği eski çalışma bir sonraki açılışta tekrar gelebilirdi.
        try:
            path = app._auto_session_path()
            if os.path.isfile(path):
                os.remove(path)
        except OSError:
            pass

    shutdown_runtime(app)
    event.accept()


def _auto_session_path(app):

    """Otomatik oturumu proje dosyalarından ayrı, kullanıcıya ait yazılabilir alanda tutar."""
    root = os.environ.get("LOCALAPPDATA")
    if root:
        folder = os.path.join(root, "ScoliosisFollowUp")
    else:
        folder = os.path.join(os.path.expanduser("~"), ".scoliosis_followup")
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, "autosession.json")


def _build_auto_session(app):
    shared_paths = app._shared_pool_paths()
    viewer_paths = app._viewer_session_paths() if hasattr(app, "viewer_file_tree") else []
    selected_study_paths = []
    if hasattr(app, "study_list_widget"):
        selected_study_paths = [
            os.path.abspath(str(item.data(Qt.UserRole)))
            for item in app.study_list_widget.selectedItems()
            if item.data(Qt.UserRole)
        ]

    stitch_files = {}
    for part in ("servical", "dorsal", "lumbar", "extra"):
        path = app.stitch_files.get(part) if hasattr(app, "stitch_files") else None
        stitch_files[part] = os.path.abspath(path) if path and os.path.isfile(path) else None


    geometry = app.geometry()
    return {
        "format": "ScoliosisFollowUpAutoSession",
        "version": 1,
        "saved_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "shared_paths": shared_paths,
        "viewer_paths": viewer_paths,
        "viewer_current_path": app.viewer_current_path,
        "viewer_brightness": int(app.viewer_brightness_value),
        "viewer_window_settings": {
            path: list(value)
            for path, value in app.viewer_window_settings.items()
            if os.path.isfile(path)
        },
        "viewer_rotation": int(app.viewer_rotation),
        "viewer_flip_horizontal": bool(app.viewer_flip_horizontal),
        "viewer_flip_vertical": bool(app.viewer_flip_vertical),
        "viewer_inverted": bool(app.viewer_inverted),
        "viewer_annotations_visible": bool(app.viewer_annotations_visible),
        "viewer_markups": copy.deepcopy(app.viewer_markup_records),
        "viewer_measurements": copy.deepcopy(app.viewer_measurement_records),
        "selected_study_paths": selected_study_paths,
        "current_mode": str(getattr(app, "current_mode", "side_by_side")),
        "overlay": {
            "x": float(app.overlay_offset_x),
            "y": float(app.overlay_offset_y),
            "scale": float(app.overlay_scale),
            "opacity": float(app.overlay_opacity),
        },
        "stitch_files": stitch_files,
        "stitch_part_offsets": copy.deepcopy(getattr(app, "stitch_part_offsets", {})),
        "active_stitch_part": str(getattr(app, "active_stitch_part", "dorsal")),
        "active_tab": int(app.tabs.currentIndex()) if hasattr(app, "tabs") else 0,
        "window_geometry": [geometry.x(), geometry.y(), geometry.width(), geometry.height()],
    }


def _save_auto_session(app):
    """Uygulama kapanırken sessizce çalışma durumunu kaydeder."""
    # Tamamen boş bir çalışma alanı da bilinçli bir durumdur; eski session'ın
    # yeniden gelmemesi için onu da kaydederiz.
    try:
        payload = app._build_auto_session()
        destination = app._auto_session_path()
        temporary = destination + ".tmp"
        with open(temporary, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
        os.replace(temporary, destination)
    except Exception as exc:
        # Kapanışı engelleme; yalnızca konsolda teşhis bırak.
        print(f"[AutoSession] Kaydedilemedi: {exc}")


def _restore_auto_session(app):
    """Son otomatik oturumu sessizce geri yükler; eksik dosyaları atlar."""
    source = app._auto_session_path()
    if not os.path.isfile(source):
        return
    try:
        with open(source, "r", encoding="utf-8") as handle:
            session = json.load(handle)
        if session.get("format") != "ScoliosisFollowUpAutoSession":
            return

        shared_paths = [
            os.path.abspath(str(path))
            for path in session.get("shared_paths", [])
            if path and os.path.isfile(str(path))
        ]
        viewer_paths = [
            os.path.abspath(str(path))
            for path in session.get("viewer_paths", [])
            if path and os.path.isfile(str(path))
        ]

        app.shared_image_paths = []
        app._remember_shared_paths(shared_paths)

        # Takip modülü ortak havuzun tamamını görsün.
        for path in shared_paths:
            app._ensure_tracking_path(path)

        # Görüntüleyici ayarları ve kayıtları görüntü seçilmeden önce yüklenir;
        # böylece ilk render'da ölçüm/işaretlemeler de çizilebilir.
        app.viewer_brightness_value = int(session.get("viewer_brightness", 0))
        app.viewer_brightness_slider.blockSignals(True)
        app.viewer_brightness_slider.setValue(app.viewer_brightness_value)
        app.viewer_brightness_slider.blockSignals(False)
        app.viewer_brightness_label.setText(str(app.viewer_brightness_value))

        app.viewer_window_settings = {
            os.path.abspath(path): (float(value[0]), float(value[1]))
            for path, value in dict(session.get("viewer_window_settings", {})).items()
            if os.path.isfile(path) and isinstance(value, (list, tuple)) and len(value) == 2
        }
        app.viewer_rotation = int(session.get("viewer_rotation", 0)) % 360
        app.viewer_flip_horizontal = bool(session.get("viewer_flip_horizontal", False))
        app.viewer_flip_vertical = bool(session.get("viewer_flip_vertical", False))
        app.viewer_inverted = bool(session.get("viewer_inverted", False))
        app.viewer_invert_action.blockSignals(True)
        app.viewer_invert_action.setChecked(app.viewer_inverted)
        app.viewer_invert_action.blockSignals(False)

        app.viewer_annotations_visible = bool(session.get("viewer_annotations_visible", True))
        app.btn_viewer_annotations.blockSignals(True)
        app.btn_viewer_annotations.setChecked(app.viewer_annotations_visible)
        app.btn_viewer_annotations.blockSignals(False)
        app.viewer_markup_records = [
            row for row in session.get("viewer_markups", []) if isinstance(row, dict)
        ]
        app.viewer_measurement_records = [
            row for row in session.get("viewer_measurements", []) if isinstance(row, dict)
        ]

        if viewer_paths:
            app._add_viewer_paths(viewer_paths)
            current = os.path.abspath(str(session.get("viewer_current_path") or viewer_paths[0]))
            target_item = None
            for item in app._viewer_file_items():
                item_path = str(item.data(0, Qt.UserRole) or "")
                if item_path and os.path.abspath(item_path) == current:
                    target_item = item
                    break
            if target_item is None:
                items = app._viewer_file_items()
                target_item = items[0] if items else None
            if target_item is not None:
                app.viewer_file_tree.setCurrentItem(target_item)

        # Takip seçimlerini geri getir.
        selected = {
            os.path.abspath(str(path))
            for path in session.get("selected_study_paths", [])
            if path and os.path.isfile(str(path))
        }
        if selected and hasattr(app, "study_list_widget"):
            app.study_list_widget.blockSignals(True)
            try:
                for index in range(app.study_list_widget.count()):
                    item = app.study_list_widget.item(index)
                    path = str(item.data(Qt.UserRole) or "")
                    item.setSelected(bool(path and os.path.abspath(path) in selected))
            finally:
                app.study_list_widget.blockSignals(False)
            app._sync_study_tree_selection_from_model()

        overlay = dict(session.get("overlay", {}))
        app.overlay_offset_x = float(overlay.get("x", 0.0))
        app.overlay_offset_y = float(overlay.get("y", 0.0))
        app.overlay_scale = float(overlay.get("scale", 1.0))
        app.overlay_opacity = float(overlay.get("opacity", 0.5))
        app._sync_overlay_sliders()
        opacity_slider = getattr(app, "overlay_opacity_slider", None)
        if opacity_slider is not None:
            opacity_slider.blockSignals(True)
            opacity_slider.setValue(int(round(app.overlay_opacity * 100)))
            opacity_slider.blockSignals(False)

        # Birleştirme slotlarını geri yükle.
        saved_stitch = dict(session.get("stitch_files", {}))
        labels = {"servical": "Üst", "dorsal": "Orta", "lumbar": "Alt", "extra": "4. Parça"}
        for part in ("servical", "dorsal", "lumbar", "extra"):
            path = saved_stitch.get(part)
            path = os.path.abspath(str(path)) if path and os.path.isfile(str(path)) else None
            app.stitch_files[part] = path
            button = app.stitch_load_buttons.get(part)
            remove_button = app.stitch_remove_buttons.get(part)
            if button is not None:
                button.setText(f"{labels[part]} ✓" if path else f"{labels[part]} Yükle")
            if remove_button is not None:
                remove_button.setVisible(bool(path))

        offsets = session.get("stitch_part_offsets", {})
        for part in ("servical", "dorsal", "lumbar", "extra"):
            value = offsets.get(part)
            if isinstance(value, (list, tuple)) and len(value) == 2:
                app.stitch_part_offsets[part] = [float(value[0]), float(value[1])]
        active_part = str(session.get("active_stitch_part", "dorsal"))
        if active_part in app.stitch_files:
            app.active_stitch_part = active_part
        if any(app.stitch_files.values()):
            app._refresh_stitch_part_buttons()
            app.update_stitched_spine()


        mode = str(session.get("current_mode", "side_by_side"))
        if mode in {"side_by_side", "overlay"}:
            app.current_mode = mode
            app.update_viewers()

        tab_index = int(session.get("active_tab", 0))
        if hasattr(app, "tabs") and 0 <= tab_index < app.tabs.count():
            app.tabs.setCurrentIndex(tab_index)

        geometry = session.get("window_geometry")
        if isinstance(geometry, (list, tuple)) and len(geometry) == 4:
            x, y, width, height = [int(value) for value in geometry]
            if width >= 800 and height >= 500:
                app.setGeometry(x, y, width, height)

        # Yeni oturum geçmişi temiz başlar; önceki oturumun Ctrl+Z zinciri taşınmaz.
        app._undo_stack.clear()
        app._redo_stack.clear()
        app._update_history_actions()
        app.statusBar().showMessage(
            f"Son çalışma oturumu geri yüklendi ({len(shared_paths)} dosya)."
        )
    except Exception as exc:
        # Bozuk session uygulamanın açılmasını engellememeli.
        print(f"[AutoSession] Geri yüklenemedi: {exc}")


def _remember_shared_paths(app, paths):
    """Dosyaları ortak uygulama havuzuna tekilleştirerek ekler."""
    known = {os.path.abspath(path) for path in getattr(app, "shared_image_paths", [])}
    added = 0
    for raw_path in paths or []:
        path = os.path.abspath(str(raw_path or ""))
        if not path or not os.path.isfile(path) or path in known:
            continue
        app.shared_image_paths.append(path)
        known.add(path)
        added += 1
    return added


def _shared_pool_paths(app):
    """Ortak havuzdaki mevcut dosyaları sıralı ve tekil döndürür."""
    cleaned = []
    seen = set()
    for raw_path in getattr(app, "shared_image_paths", []):
        path = os.path.abspath(str(raw_path or ""))
        if not path or path in seen or not os.path.isfile(path):
            continue
        seen.add(path)
        cleaned.append(path)
    app.shared_image_paths = cleaned
    return list(cleaned)


def _forget_shared_paths(app, paths):
    targets = {os.path.abspath(str(path)) for path in paths if path}
    app.shared_image_paths = [
        path for path in app._shared_pool_paths()
        if os.path.abspath(path) not in targets
    ]


def _remove_paths_from_all_modules(app, paths):
    """Ortak havuzdan kaldırılan dosyaları tüm çalışma görünümlerinden çıkarır; diske dokunmaz."""
    targets = {os.path.abspath(str(path)) for path in paths if path}
    if not targets:
        return
    app._forget_shared_paths(targets)

    # Görüntüleyici ağacı
    if hasattr(app, "viewer_file_tree"):
        for item in list(app._viewer_file_items()):
            path = str(item.data(0, Qt.UserRole) or "")
            if path and os.path.abspath(path) in targets:
                app._remove_tree_item_and_empty_groups(app.viewer_file_tree, item)
    if getattr(app, "viewer_current_path", None) and os.path.abspath(app.viewer_current_path) in targets:
        app.stop_viewer_cine()
        controller = getattr(app, "_viewer_preload_controller", None)
        if controller is not None:
            controller.cancel(slot="viewer")
        app.viewer_scene.clear()
        app.viewer_current_path = None
        app.viewer_pixmap_item = None
        app.viewer_info_label.setText("DICOM veya görüntü dosyası açın.")

    # Skolyoz takip modeli ve ağacı
    if hasattr(app, "study_list_widget"):
        for row in range(app.study_list_widget.count() - 1, -1, -1):
            item = app.study_list_widget.item(row)
            path = str(item.data(Qt.UserRole) or "")
            if path and os.path.abspath(path) in targets:
                app.study_list_widget.takeItem(row)
    if hasattr(app, "study_tree_widget"):
        for item in list(app._study_tree_file_items()):
            path = str(item.data(0, Qt.UserRole) or "")
            if path and os.path.abspath(path) in targets:
                app._remove_tree_item_and_empty_groups(app.study_tree_widget, item)
    app.loaded_files = {
        key: value for key, value in app.loaded_files.items()
        if os.path.abspath(str(value)) not in targets
    }

    # Birleştirme slotları
    for part in ("servical", "dorsal", "lumbar", "extra"):
        path = app.stitch_files.get(part) if hasattr(app, "stitch_files") else None
        if path and os.path.abspath(path) in targets:
            app.remove_stitch_part(part)

        # İlgili önbellekler. Viewer tarafındaki tüm path cache'leri tek helper
    # üzerinden temizlenir; stitch cache'leri de aynı yaşam döngüsünde boşaltılır.
    for path in targets:
        clear_viewer = getattr(app, "_clear_viewer_path_caches", None)
        if callable(clear_viewer):
            clear_viewer(path)
        else:
            app._viewer_dataset_cache.pop(path, None)
            app._viewer_frame_counts.pop(path, None)
            for key in list(app._viewer_only_pixmap_cache):
                if isinstance(key, tuple) and key and os.path.abspath(str(key[0])) == path:
                    app._viewer_only_pixmap_cache.pop(key, None)
            for key in list(getattr(app, "_viewer_decoded_array_cache", {})):
                if isinstance(key, tuple) and key and os.path.abspath(str(key[0])) == path:
                    app._viewer_decoded_array_cache.pop(key, None)
        app._stitch_pixmap_cache.pop(path, None)
        app._stitch_array_cache.pop(path, None)
        app._stitch_gray_cache.pop(path, None)
        app._stitch_gray_flag_cache.pop(path, None)

    if hasattr(app, "update_viewers"):
        app.update_viewers()


def _capture_edit_state(app):
    """Undo/Redo için yalnızca kullanıcı düzenlemelerini kopyalar; DICOM piksel verisini kopyalamaz."""
    return {
        "measurements": copy.deepcopy(app.viewer_measurement_records),
        "markups": copy.deepcopy(app.viewer_markup_records),
        "overlay": (
            float(app.overlay_offset_x), float(app.overlay_offset_y),
            float(app.overlay_scale), float(app.overlay_opacity),
        ),
    }


def _history_commit(app, label, before):
    after = app._capture_edit_state()
    if before == after:
        return
    app._undo_stack.append((str(label), before, after))
    if len(app._undo_stack) > app._history_limit:
        app._undo_stack.pop(0)
    app._redo_stack.clear()
    app._update_history_actions()


def _update_history_actions(app):
    """Undo/Redo arayüzünü günceller.

    Modüler başlatıcı eski Tools menüsünü kaldırabildiği için o menüye bağlı
    QAction nesneleri C++ tarafında silinmiş olabilir. Butonlar ve bağımsız
    QShortcut'lar çalışmaya devam eder; silinmiş QAction'lara dokunmayız.
    """
    can_undo = bool(app._undo_stack)
    can_redo = bool(app._redo_stack)

    for name, enabled in (("btn_undo", can_undo), ("btn_redo", can_redo)):
        widget = getattr(app, name, None)
        if widget is not None:
            widget.setEnabled(enabled)

    for name, enabled, text in (
        ("action_undo", can_undo, f"Geri Al: {app._undo_stack[-1][0]}" if can_undo else "Geri Al"),
        ("action_redo", can_redo, f"İleri Al: {app._redo_stack[-1][0]}" if can_redo else "İleri Al"),
    ):
        action = getattr(app, name, None)
        if action is None:
            continue
        try:
            action.setEnabled(enabled)
            action.setText(text)
        except RuntimeError:
            # run_modular.py Tools menüsünü kaldırdığında QAction da silinir.
            setattr(app, name, None)


def _apply_edit_state(app, state):
    app.viewer_measurement_records = copy.deepcopy(state.get("measurements", []))
    app.viewer_markup_records = copy.deepcopy(state.get("markups", []))
    overlay = state.get("overlay", (0.0, 0.0, 1.0, 0.5))
    app.overlay_offset_x, app.overlay_offset_y, app.overlay_scale, app.overlay_opacity = map(float, overlay)

    # Aynı görüntü açıkken render_viewer_file() kayıtlı çizimleri yeniden
    # oluşturmuyor. Bu yüzden sadece düzenleme katmanlarını sahneden kaldırıp
    # kayıt listesinden tekrar çiziyoruz; ana DICOM pixmap'ine dokunmuyoruz.
    if app.viewer_current_path and app.viewer_pixmap_item is not None:
        for collection_name in ("viewer_cobb_items", "viewer_length_items", "viewer_markup_items"):
            collection = getattr(app, collection_name, [])
            for item in list(collection):
                try:
                    if item.scene() is app.viewer_scene:
                        app.viewer_scene.removeItem(item)
                except RuntimeError:
                    pass
            collection.clear()

        app.viewer_cobb_points.clear()
        app.viewer_length_start = None
        app.viewer_markup_start = None
        app._render_viewer_saved_items(app.viewer_current_path)

    app._sync_overlay_sliders()
    opacity_slider = getattr(app, "overlay_opacity_slider", None)
    if opacity_slider is not None:
        opacity_slider.blockSignals(True)
        opacity_slider.setValue(int(round(app.overlay_opacity * 100)))
        opacity_slider.blockSignals(False)

    if app.current_mode == "overlay":
        if app.overlay_item is not None:
            app.overlay_item.setPos(app.overlay_offset_x, app.overlay_offset_y)
            app.overlay_item.setOpacity(app.overlay_opacity)
            initial_scale = float(getattr(app, "_overlay_initial_scale", 1.0) or 1.0)
            app.overlay_item.setScale(initial_scale * app.overlay_scale)
        else:
            app.update_viewers()

    app._update_overlay_label()
    if getattr(app, "viewer_view", None) is not None:
        app.viewer_view.viewport().update()
    if getattr(app, "view_left", None) is not None:
        app.view_left.viewport().update()


def undo_last_action(app):
    if not app._undo_stack:
        app.statusBar().showMessage("Geri alınacak işlem yok.")
        return
    label, before, after = app._undo_stack.pop()
    app._redo_stack.append((label, before, after))
    app._apply_edit_state(before)
    app._update_history_actions()
    app.statusBar().showMessage(f"Geri alındı: {label}")


def redo_last_action(app):
    if not app._redo_stack:
        app.statusBar().showMessage("İleri alınacak işlem yok.")
        return
    label, before, after = app._redo_stack.pop()
    app._undo_stack.append((label, before, after))
    app._apply_edit_state(after)
    app._update_history_actions()
    app.statusBar().showMessage(f"Yeniden uygulandı: {label}")


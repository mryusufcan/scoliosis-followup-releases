"""Goruntuleyici UI davranis/callback fonksiyonlari."""

# VIEWER_ACTIONS_STAGE24
import os

import numpy as np
from PySide6.QtCore import Qt

def _refresh_viewer_frame_controls(app):
    is_multiframe = app.viewer_frame_count > 1
    app.viewer_frame_controls.setVisible(is_multiframe)
    app.viewer_frame_slider.blockSignals(True)
    app.viewer_frame_slider.setRange(0, max(0, app.viewer_frame_count - 1))
    app.viewer_frame_slider.setValue(min(app.viewer_frame_index, app.viewer_frame_count - 1))
    app.viewer_frame_slider.blockSignals(False)
    app.viewer_frame_label.setText(f"{app.viewer_frame_index + 1}/{app.viewer_frame_count}")
    app.btn_viewer_cine.setText("■" if app.viewer_cine_timer.isActive() else "▶")


def set_viewer_frame(app, frame_index):
    if not app.viewer_current_path or app.viewer_frame_count <= 1:
        return
    index = max(0, min(int(frame_index), app.viewer_frame_count - 1))
    if index == app.viewer_frame_index:
        return
    app.viewer_frame_index = index
    app.clear_viewer_measurements(notify=False)
    app.render_viewer_file(app.viewer_current_path, fit=False)
    app.statusBar().showMessage(f"Çok kareli DICOM: {index + 1}/{app.viewer_frame_count}.")


def advance_viewer_frame(app):
    if not app.viewer_current_path or app.viewer_frame_count <= 1:
        app.stop_viewer_cine()
        return
    app.set_viewer_frame((app.viewer_frame_index + 1) % app.viewer_frame_count)


def toggle_viewer_cine(app):
    if app.viewer_frame_count <= 1:
        app.statusBar().showMessage("Bu görüntü tek karelidir.")
        return
    if app.viewer_cine_timer.isActive():
        app.stop_viewer_cine()
        app.statusBar().showMessage("Cine oynatma durduruldu.")
    else:
        app.viewer_cine_timer.start()
        app._refresh_viewer_frame_controls()
        app.statusBar().showMessage("Cine oynatma başladı.")


def stop_viewer_cine(app):
    if app.viewer_cine_timer.isActive():
        app.viewer_cine_timer.stop()
    if hasattr(app, 'btn_viewer_cine'):
        app.btn_viewer_cine.setText("▶")


def rotate_viewer(app, degrees):
    if app.viewer_pixmap_item is None:
        app.statusBar().showMessage("Döndürmek için önce bir görüntü açın.")
        return
    app.viewer_rotation = (app.viewer_rotation + int(degrees)) % 360
    app._refresh_viewer_after_transform("Görüntü döndürüldü.")


def flip_viewer_horizontal(app):
    if app.viewer_pixmap_item is None:
        app.statusBar().showMessage("Çevirmek için önce bir görüntü açın.")
        return
    app.viewer_flip_horizontal = not app.viewer_flip_horizontal
    app._refresh_viewer_after_transform("Görüntü yatay çevrildi.")


def flip_viewer_vertical(app):
    if app.viewer_pixmap_item is None:
        app.statusBar().showMessage("Çevirmek için önce bir görüntü açın.")
        return
    app.viewer_flip_vertical = not app.viewer_flip_vertical
    app._refresh_viewer_after_transform("Görüntü dikey çevrildi.")


def set_viewer_inverted(app, enabled):
    app.viewer_inverted = bool(enabled)
    if app.viewer_pixmap_item is not None:
        app._refresh_viewer_after_transform("Negatif görünüm güncellendi.")


def reset_viewer_transform(app):
    if app.viewer_pixmap_item is None:
        return
    app.viewer_rotation = 0
    app.viewer_flip_horizontal = False
    app.viewer_flip_vertical = False
    app.viewer_inverted = False
    app.viewer_invert_action.blockSignals(True)
    app.viewer_invert_action.setChecked(False)
    app.viewer_invert_action.blockSignals(False)
    app._refresh_viewer_after_transform("Görüntü araçları sıfırlandı.")


def _refresh_viewer_after_transform(app, message):
    app.clear_viewer_measurements(notify=False)
    app.clear_viewer_markups()
    app._viewer_only_pixmap_cache.clear()
    app.render_viewer_file(app.viewer_current_path, fit=True)
    app.statusBar().showMessage(message)


def set_viewer_annotations_visible(app, visible):
    app.viewer_annotations_visible = bool(visible)
    if app.viewer_current_path:
        app.render_viewer_file(app.viewer_current_path, fit=False)


def apply_viewer_window_preset(app, preset):
    if not app.viewer_current_path:
        app.statusBar().showMessage("Pencere ayarı için önce bir DICOM açın.")
        return
    if not app._viewer_is_dicom(app.viewer_current_path):
        app.statusBar().showMessage("Pencere ayarı yalnızca DICOM görüntülerinde kullanılabilir.")
        return
    if preset == "original":
        app.viewer_window_settings.pop(app.viewer_current_path, None)
    else:
        presets = {"soft": (300.0, 1200.0), "bone": (2000.0, 4000.0)}
        app.viewer_window_settings[app.viewer_current_path] = presets[preset]
    # Cache key W/L değerini içerir; toplu clear yerine mevcut girişleri koru.
    # Bounded cache, hızlı preset geri dönüşlerinde yeniden decode/render ihtiyacını
    # azaltırken eski pixmap'ın uygulanmasını engeller.
    app.render_viewer_file(app.viewer_current_path, fit=False)
    app.statusBar().showMessage("Görüntüleyici W/L ayarı güncellendi.")


def on_viewer_brightness_changed(app, value):
    app.viewer_brightness_value = int(value)
    app.viewer_brightness_label.setText(str(int(value)))
    if app.viewer_current_path:
        # Brightness cache key'in parçasıdır; eski key güvenle saklanabilir.
        # Böylece slider geri hareketlerinde mevcut bounded cache kullanılabilir.
        app.schedule_viewer_render()


def adjust_viewer_window_level(app, dx, dy):
    if not app.viewer_current_path or not app._viewer_is_dicom(app.viewer_current_path):
        return
    default_wc, default_ww = app._default_window(app.viewer_current_path)
    wc, ww = app.viewer_window_settings.get(app.viewer_current_path, (default_wc, default_ww))
    ww = float(np.clip(ww * (1.0 + dx * 0.01), 8.0, 20000.0))
    wc = float(wc - dy * max(1.0, ww) * 0.005)
    app.viewer_window_settings[app.viewer_current_path] = (wc, ww)
    # W/L cache key'in parçasıdır; stale pixmap eşleşmez, cache topluca silinmez.
    app._update_viewer_window_label()
    app.schedule_viewer_render()


def _update_viewer_window_label(app):
    if not app.viewer_current_path:
        app.viewer_window_label.setText("W/L: —")
        return
    if not app._viewer_is_dicom(app.viewer_current_path):
        app.viewer_window_label.setText("W/L: normal görüntü")
        return
    default_wc, default_ww = app._default_window(app.viewer_current_path)
    wc, ww = app.viewer_window_settings.get(app.viewer_current_path, (default_wc, default_ww))
    app.viewer_window_label.setText(f"W/L: WW {ww:.0f} | WL {wc:.0f}")


def adjust_viewer_zoom(app, factor):
    if app.viewer_pixmap_item is None:
        return
    current_scale = abs(app.viewer_view.transform().m11())
    fit_scale = app._viewer_fit_scale or current_scale or 1.0
    target_scale = current_scale * float(factor)
    if target_scale < fit_scale * 0.35 or target_scale > fit_scale * 12.0:
        return
    app.viewer_view.scale(float(factor), float(factor))
    app._update_viewer_zoom_label()


def _update_viewer_zoom_label(app):
    if app.viewer_pixmap_item is None:
        app.viewer_zoom_label.setText("Sığdır")
        return
    current_scale = abs(app.viewer_view.transform().m11())
    fit_scale = app._viewer_fit_scale or current_scale or 1.0
    percent = (current_scale / fit_scale) * 100.0
    app.viewer_zoom_label.setText("Sığdır" if abs(percent - 100.0) < 0.5 else f"%{percent:.0f}")


def fit_viewer_image(app):
    rect = app.viewer_pixmap_item.sceneBoundingRect() if app.viewer_pixmap_item is not None else app.viewer_scene.itemsBoundingRect()
    if not rect.isNull():
        app.viewer_view.fitInView(rect, Qt.KeepAspectRatio)
        app._viewer_fit_scale = abs(app.viewer_view.transform().m11())
        app._update_viewer_zoom_label()


def _repolish_measurement_button(button, active):
    if button is None:
        return
    button.setProperty("uiMeasurementActive", bool(active))
    style = button.style()
    style.unpolish(button)
    style.polish(button)
    button.update()


def _refresh_viewer_cobb_button(app):
    active = bool(app.viewer_cobb_mode_active)
    app.btn_viewer_cobb.setText("Cobb Aktif" if active else "Cobb Ölç")
    _repolish_measurement_button(app.btn_viewer_cobb, active)
    save_button = getattr(app, "btn_viewer_cobb_save", None)
    if save_button is not None:
        current_path = os.path.abspath(str(getattr(app, "viewer_current_path", "") or ""))
        has_pending = any(
            row.get("type") == "cobb"
            and os.path.abspath(str(row.get("path", ""))) == current_path
            and not row.get("repository_measurement_id")
            for row in getattr(app, "viewer_measurement_records", [])
        )
        save_button.setEnabled(bool(current_path and has_pending))
        save_button.setToolTip(
            "Son manuel Cobb ölçümünü takip geçmişine taslak olarak kaydet"
            if has_pending else
            "Kaydetmek için önce bu görüntüde dört noktalı manuel Cobb ölçümü oluşturun"
        )





def toggle_viewer_cobb_measurement(app):
    if app.viewer_pixmap_item is None:
        app.statusBar().showMessage("Cobb ölçümü için önce bir görüntü açın.")
        return
    app.viewer_cobb_mode_active = not app.viewer_cobb_mode_active
    if app.viewer_cobb_mode_active:
        app.viewer_length_mode_active = False
        app.viewer_length_start = None
        app._refresh_viewer_length_button()
    app.viewer_cobb_points.clear()
    app._refresh_viewer_cobb_button()
    app.viewer_view.refresh_cursor()
    if app.viewer_cobb_mode_active:
        app.statusBar().showMessage("Cobb Ölçümü: üst vertebra için iki, alt vertebra için iki nokta seçin.")
    else:
        app.statusBar().showMessage("Cobb ölçüm modu kapatıldı.")


def _refresh_viewer_length_button(app):
    active = bool(app.viewer_length_mode_active)
    app.btn_viewer_length.setText("Mesafe Aktif" if active else "Mesafe Ölç")
    _repolish_measurement_button(app.btn_viewer_length, active)


def toggle_viewer_length_measurement(app):
    if app.viewer_pixmap_item is None:
        app.statusBar().showMessage("Mesafe ölçümü için önce bir görüntü açın.")
        return
    app.viewer_length_mode_active = not app.viewer_length_mode_active
    if app.viewer_length_mode_active:
        app.viewer_cobb_mode_active = False
        app.viewer_cobb_points.clear()
        app._refresh_viewer_cobb_button()
    app.viewer_length_start = None
    app._refresh_viewer_length_button()
    app.viewer_view.refresh_cursor()
    if app.viewer_length_mode_active:
        app.statusBar().showMessage("Mesafe Ölçümü: başlangıç ve bitiş noktasını seçin.")
    else:
        app.statusBar().showMessage("Mesafe ölçüm modu kapatıldı.")


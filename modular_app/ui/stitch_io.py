"""Stitching dosya yukleme, render ve kaydetme orkestrasyonu."""

# STITCH_IO_STAGE28
import datetime
import os

import numpy as np
import pydicom

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QLabel,
    QMessageBox, QVBoxLayout,
)

from modular_app.ui.dicom_viewer_components import (
    DicomPreviewDialog,
    StudySelectionDialog,
    process_dicom_array,
)
from modular_app.performance_utils import cache_get, cache_put, cache_put_array
from modular_app.ui.ui_clarity import set_context

def open_preview_dialog(app, part_name):
    """Tek bir görüntü parçası için önizlemeli DICOM seçici açar."""
    initial_dir = app.last_stitch_folder or ""
    current_path = app.stitch_files.get(part_name)
    if current_path:
        initial_dir = os.path.dirname(current_path)
    elif not initial_dir:
        for path in app.stitch_files.values():
            if path:
                initial_dir = os.path.dirname(path)
                break

    labels = {
        "servical": "Üst",
        "dorsal": "Orta",
        "lumbar": "Alt",
        "extra": "4. Parça",
    }
    label = labels.get(part_name, part_name.capitalize())

    dialog = DicomPreviewDialog(label, initial_dir=initial_dir, parent=app)
    if dialog.exec() != QDialog.Accepted:
        return

    new_path = getattr(dialog, "selected_file_path", None)
    if not new_path:
        return
    new_path = os.path.abspath(new_path)
    app._remember_shared_paths([new_path])

    pix = app.get_image_pixmap(new_path)
    if pix.isNull():
        QMessageBox.warning(
            app,
            "Görüntü yüklenemedi",
            f"{label} parçası okunamadı:\n{new_path}",
        )
        return

    old_path = app.stitch_files.get(part_name)
    app.stitch_files[part_name] = new_path
    app.last_stitch_folder = os.path.dirname(new_path)

    if old_path and old_path != new_path:
        app._stitch_pixmap_cache.pop(old_path, None)
        app._stitch_array_cache.pop(old_path, None)
        app._stitch_gray_cache.pop(old_path, None)
        app._stitch_gray_flag_cache.pop(old_path, None)
        app._auto_align_cache = {
            k: v for k, v in app._auto_align_cache.items() if old_path not in k
        }

    btn = app.stitch_load_buttons.get(part_name)
    if btn is not None:
        btn.setText(f"{label} ✓")
    rem = app.stitch_remove_buttons.get(part_name)
    if rem is not None:
        rem.setVisible(True)

    manual_state = app.stitch_controller.fresh_manual_state()
    app.manual_stage_index = manual_state["stage_index"]
    app.manual_points = manual_state["points"]
    app.manual_junction_offsets = manual_state["junction_offsets"]
    app.is_stitched_completed = False
    app._stitch_final_verified = False
    app._stitch_final_quality_snapshot = None
    app.stitch_part_offsets[part_name] = [0.0, 0.0]
    app._refresh_stitch_part_buttons()
    app.update_stitched_spine()
    app.statusBar().showMessage(f"{label} parçası yüklendi: {os.path.basename(new_path)}")


def open_viewer_selection_for_stitcher(app):
    """Ortak çalışma alanındaki dosyaları birleştirme parçalarına aktarır.

    Kullanıcı Üst/Orta/Alt/4. Parça eşleştirmesini açıkça yapar; dosya
    sırasından bölge tahmin edilmez.
    """
    # Birleştirme seçicisi artık tüm modüllerin ortak dosya havuzunu kullanır.
    initial_paths = app._shared_pool_paths()
    app._remember_shared_paths([path for path in app.stitch_files.values() if path])
    initial_paths = app._shared_pool_paths()

    if len(initial_paths) < 2:
        QMessageBox.information(
            app,
            "Açık görüntü gerekli",
            "Önce Görüntüleyici'de birleştirilecek en az iki görüntüyü açın. "
            "Açılan dosyalar burada yeniden klasör taramadan kullanılacaktır.",
        )
        return

    dialog = StitchPartAssignmentDialog(initial_paths, app.stitch_files, app)
    if dialog.exec() != QDialog.Accepted:
        return
    _assign_stitch_paths(app, dialog.assignments())


class StitchPartAssignmentDialog(QDialog):
    """Let the user map shared images to anatomical stitch slots explicitly."""

    PARTS = (("servical", "Üst"), ("dorsal", "Orta"), ("lumbar", "Alt"), ("extra", "4. Parça (isteğe bağlı)"))

    def __init__(self, paths, current, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Açık Görüntüleri Birleştirme Sırasına Ata")
        self.setMinimumWidth(620)
        self._paths = [os.path.abspath(path) for path in paths if os.path.isfile(path)]
        root = QVBoxLayout(self)
        root.addWidget(QLabel(
            "Görüntüleri yukarıdan aşağıya doğru sıralayın. "
            "En az iki farklı görüntü gereklidir; 4. parça isteğe bağlıdır."
        ))
        form = QFormLayout()
        self.combos = {}
        for key, label in self.PARTS:
            combo = QComboBox()
            combo.addItem("— Kullanılmayacak —", "")
            for path in self._paths:
                combo.addItem(f"{os.path.basename(path)}  |  {os.path.dirname(path)}", path)
            existing = os.path.abspath(str((current or {}).get(key) or ""))
            existing_index = combo.findData(existing)
            if existing_index >= 0:
                combo.setCurrentIndex(existing_index)
            self.combos[key] = combo
            form.addRow(f"{label}:", combo)
        root.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("Seçimleri Kullan")
        buttons.button(QDialogButtonBox.Cancel).setText("İptal")
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def assignments(self):
        return {key: str(combo.currentData() or "") for key, combo in self.combos.items()}

    def _validate_and_accept(self):
        chosen = [path for path in self.assignments().values() if path]
        if len(chosen) < 2:
            QMessageBox.warning(self, "Eksik seçim", "Birleştirme için en az iki görüntü seçin.")
            return
        if len(set(chosen)) != len(chosen):
            QMessageBox.warning(self, "Tekrarlanan görüntü", "Aynı görüntü iki farklı parçaya atanamaz.")
            return
        self.accept()


def _assign_stitch_paths(app, assignments):
    """Apply the anatomical mapping explicitly confirmed by the user."""
    selected = {
        key: os.path.abspath(path)
        for key, path in dict(assignments or {}).items()
        if key in {"servical", "dorsal", "lumbar", "extra"} and path and os.path.isfile(path)
    }
    app._remember_shared_paths(selected.values())
    if len(selected) < 2:
        app.statusBar().showMessage("Hiç dosya seçilmedi.")
        return

    targets = ["servical", "dorsal", "lumbar", "extra"]
    assigned = 0
    new_files = dict(app.stitch_files)

    for key in targets:
        path = selected.get(key)
        if not path:
            new_files[key] = None
            continue

        pix = app.get_image_pixmap(path)
        if pix.isNull():
            QMessageBox.warning(
                app, "Dosya okunamadı",
                f"{key.capitalize()} için seçilen dosya okunamadı:\n{path}"
            )
            continue

        old_path = new_files.get(key)
        new_files[key] = path
        if old_path and old_path != path:
            app._stitch_pixmap_cache.pop(old_path, None)
            app._stitch_array_cache.pop(old_path, None)
        assigned += 1

    if assigned == 0:
        app.statusBar().showMessage("Seçilen dosyalardan hiçbiri yüklenemedi.")
        return

    app.stitch_files = new_files

    names = {
        "servical": "Üst",
        "dorsal": "Orta",
        "lumbar": "Alt",
        "extra": "4. Parça",
    }
    for key, label in names.items():
        loaded = bool(app.stitch_files.get(key))
        btn = app.stitch_load_buttons.get(key)
        rem = app.stitch_remove_buttons.get(key)
        if btn is not None:
            btn.setText(f"{label} ✓" if loaded else f"{label} Yükle")
        if rem is not None:
            rem.setVisible(loaded)

    app._refresh_stitch_part_buttons()

    manual_state = app.stitch_controller.fresh_manual_state()
    app.manual_stage_index = manual_state["stage_index"]
    app.manual_points = manual_state["points"]
    app.manual_junction_offsets = manual_state["junction_offsets"]
    app.is_stitched_completed = False
    app._stitch_final_verified = False
    app._stitch_final_quality_snapshot = None
    for key in ("servical", "dorsal", "lumbar", "extra"):
        if not app.stitch_files.get(key):
            app.stitch_part_offsets[key] = [0.0, 0.0]
    app._refresh_stitch_part_buttons()

    app.update_stitched_spine()

    loaded_names = [names[k] for k in targets if app.stitch_files.get(k)]
    app.statusBar().showMessage(
        f"Birleştirme için {assigned} dosya yüklendi: "
        + (" → ".join(loaded_names) if loaded_names else "yok")
    )


def handle_shortcut_move(app, dx, dy):
    if app.tabs.currentIndex() == 1 and app.is_stitched_completed:
        app.adjust_stitch_offset(dx, dy)


def _render_interactive_preview(app):
    if not app.is_stitched_completed:
        return
    app._stitch_interactive = True
    app.update_stitched_spine()


def _render_full_after_move(app):
    app._stitch_interactive = False
    app.update_stitched_spine()



def _quality_text(status):
    return {
        "good": "İyi",
        "warning": "Orta",
        "poor": "Düşük",
        "unknown": "—",
    }.get(status, "—")


def _quality_style(status):
    if status == "good":
        return "color:#2ecc71;font-weight:bold;font-size:10px;"
    if status == "warning":
        return "color:#f1c40f;font-weight:bold;font-size:10px;"
    if status == "poor":
        return "color:#e74c3c;font-weight:bold;font-size:10px;"
    return "color:#95a5a6;font-size:10px;"


def _refresh_junction_quality_labels(app, valid_parts, quality):
    junctions = list((quality or {}).get("junctions", []))
    labels = [
        getattr(app, "lbl_junction_quality_1", None),
        getattr(app, "lbl_junction_quality_2", None),
        getattr(app, "lbl_junction_quality_3", None),
    ]

    for idx, label in enumerate(labels):
        if label is None:
            continue

        if idx < len(junctions) and idx + 1 < len(valid_parts):
            row = junctions[idx]
            display_names = {"servical": "Üst", "dorsal": "Orta", "lumbar": "Alt", "extra": "4. Parça"}
            upper = display_names.get(str(valid_parts[idx]), str(valid_parts[idx]).capitalize())
            lower = display_names.get(str(valid_parts[idx + 1]), str(valid_parts[idx + 1]).capitalize())
            raw = row.get("raw_score")
            if raw is not None and abs(float(raw) - float(row["score"])) >= 0.03:
                label.setText(
                    f"{upper} → {lower}: {row['score']:.2f} | {_quality_text(row['status'])} "
                    f"(ham {float(raw):.2f})"
                )
            else:
                label.setText(
                    f"{upper} → {lower}: {row['score']:.2f} | {_quality_text(row['status'])}"
                )
            label.setStyleSheet(_quality_style(row["status"]))
        else:
            label.setText(f"{idx + 1}. birleşim: —")
            label.setStyleSheet(_quality_style("unknown"))

    overall = getattr(app, "lbl_junction_quality_overall", None)
    if overall is not None:
        status = (quality or {}).get("status", "unknown")
        avg = (quality or {}).get("average_score")
        if avg is None:
            overall.setText("Genel: —")
        else:
            overall.setText(
                f"Genel: {avg:.2f} | {_quality_text(status)}"
            )
        overall.setStyleSheet(_quality_style(status))


def update_stitched_spine(app):
    if getattr(app, "manual_mode_active", False):
        app.render_manual_pick_view()
        return

    active_parts = [
        p for p in ["servical", "dorsal", "lumbar", "extra"]
        if app.stitch_files.get(p) is not None
    ]

    if not active_parts:
        app.stitch_scene.clear()
        app._stitch_result_item = None
        return

    pixmaps = []
    arrays = []
    valid_parts = []
    for part in active_parts:
        path = app.stitch_files[part]
        pix = cache_get(app._stitch_pixmap_cache, path)
        if pix is None or pix.isNull():
            pix = app.get_image_pixmap(path)
            if pix.isNull():
                app.statusBar().showMessage(f"{part.capitalize()} görüntüsü okunamadı; birleştirme durduruldu.")
                return
            cache_put(
                app._stitch_pixmap_cache,
                path,
                pix,
                getattr(app, "_stitch_pixmap_cache_limit", 6),
            )

        arr = cache_get(app._stitch_array_cache, path)
        if arr is None:
            arr = app._qimage_to_numpy(pix.toImage())
            cache_put_array(
                app._stitch_array_cache,
                path,
                arr,
                getattr(app, "_stitch_array_cache_bytes", 256 * 1024 * 1024),
            )

        if path not in app._stitch_gray_flag_cache:
            is_gray = bool(
                arr.ndim == 3 and arr.shape[2] >= 4 and
                np.array_equal(arr[..., 0], arr[..., 1]) and
                np.array_equal(arr[..., 1], arr[..., 2])
            )
            app._stitch_gray_flag_cache[path] = is_gray
            if is_gray:
                cache_put_array(
                    app._stitch_gray_cache,
                    path,
                    arr[..., 0].astype(np.float32, copy=True),
                    getattr(app, "_stitch_gray_cache_bytes", 256 * 1024 * 1024),
                )

        pixmaps.append(pix)
        arrays.append(arr)
        valid_parts.append(part)

    if not pixmaps:
        return

    auto_align_on = (
        not getattr(app, "manual_mode_active", False)
        and (
            not hasattr(app, "chk_auto_align")
            or app.chk_auto_align.isChecked()
        )
    )

    junction_offsets = []
    rotated_any = False

    if len(arrays) > 1:
        for i in range(1, len(arrays)):
            upper = active_parts[i - 1]
            lower = active_parts[i]

            manual = app.manual_junction_offsets.get((upper, lower))
            if manual is not None:
                if len(manual) >= 3:
                    dx_m, target_y, angle_deg = manual
                else:
                    dx_m, dy_m = manual
                    target_y = arrays[i - 1].shape[0] - app.OVERLAP_PX + float(dy_m)
                    angle_deg = 0.0

                h_prev = arrays[i - 1].shape[0]
                h_curr = arrays[i].shape[0]

                dy = float(h_prev - float(target_y))
                dy = float(np.clip(
                    dy,
                    1.0,
                    float(max(1, min(h_prev - 1, h_curr - 1)))
                ))

                dx = float(dx_m)
                score = 1.0

                if abs(float(angle_deg)) > 1e-4:
                    arrays[i] = app._rotate_array(
                        arrays[i], float(angle_deg), fill=0
                    )
                    rotated_any = True

                junction_offsets.append((dx, dy, score))
                continue

            if auto_align_on:
                pair_key = (
                    app.stitch_files[upper],
                    app.stitch_files[lower],
                    arrays[i - 1].shape[:2],
                    arrays[i].shape[:2],
                )
                cached = cache_get(app._auto_align_cache, pair_key)
                if cached is None:
                    cached = app._auto_estimate_offset(
                        arrays[i - 1], arrays[i]
                    )[:3]
                    cache_put(
                        app._auto_align_cache,
                        pair_key,
                        cached,
                        getattr(app, "_auto_align_cache_limit", 12),
                    )
                dx, dy, score = cached
            else:
                dx = 0.0
                dy = float(max(1, int(arrays[i - 1].shape[0] * 0.20)))
                score = 0.0

            junction_offsets.append((dx, dy, score))

    if hasattr(app, "lbl_confidence"):
        if junction_offsets:
            avg_score = (
                sum(s for _, _, s in junction_offsets)
                / len(junction_offsets)
            )
            app.lbl_confidence.setText(
                f"Güven skoru: {avg_score:.2f}"
            )
        elif len(arrays) > 1:
            app.lbl_confidence.setText(
                "Güven skoru: — (manuel/kapalı)"
            )

    quality_inputs = []
    for idx, (dx, dy, raw_score) in enumerate(junction_offsets):
        if idx + 1 < len(arrays):
            final_score, edge_similarity, seam_diff = (
                app.stitch_engine.evaluate_junction_quality(
                    arrays[idx],
                    arrays[idx + 1],
                    dx,
                    dy,
                    raw_score,
                )
            )
        else:
            final_score = float(raw_score)
            edge_similarity = None
            seam_diff = None

        quality_inputs.append({
            "dx": float(dx),
            "dy": float(dy),
            "score": float(final_score),
            "raw_score": float(raw_score),
            "edge_similarity": edge_similarity,
            "seam_intensity_difference": seam_diff,
        })

    quality = app.stitch_engine.assess_alignment_quality(quality_inputs)
    app._last_stitch_quality = quality
    _refresh_junction_quality_labels(app, valid_parts, quality)
    status_text = {
        "good": "Kalite iyi. Dikiş bölgelerini kontrol edin; ardından sonucu onaylayıp kayda hazırlayın.",
        "warning": "Kalite orta. Manuel düzeltme veya dama tahtası kontrolü önerilir.",
        "poor": "Kalite düşük. Manuel hizalama gerekli; sonucu onaylamadan önce düzeltin.",
    }.get(quality.get("status"), "Kalite sonucu hesaplandı. Dikiş bölgelerini kontrol edin.")
    set_context(getattr(app, "stitch_context_label", None), status_text)

    if hasattr(app, "lbl_status_badge"):
        status = quality.get("status")
        if status == "good":
            app.lbl_status_badge.setText("Hizalama iyi — dikiş bölgesini kontrol edin")
            app.lbl_status_badge.setStyleSheet(
                "background-color:#1e4d36;color:#2ecc71;padding:5px 10px;"
                "border-radius:4px;font-weight:bold;font-size:11px;"
            )
        elif status == "warning":
            app.lbl_status_badge.setText("Hizalama orta — manuel kontrol önerilir")
            app.lbl_status_badge.setStyleSheet(
                "background-color:#5a4317;color:#f1c40f;padding:5px 10px;"
                "border-radius:4px;font-weight:bold;font-size:11px;"
            )
        elif status == "poor":
            app.lbl_status_badge.setText("Düşük güven — manuel hizalama gerekli")
            app.lbl_status_badge.setStyleSheet(
                "background-color:#5a2525;color:#e74c3c;padding:5px 10px;"
                "border-radius:4px;font-weight:bold;font-size:11px;"
            )

    confirm_button = getattr(app, "btn_confirm_finish", None)
    if confirm_button is not None:
        if quality.get("status") == "poor":
            confirm_button.setText("Düşük güven — kontrol ederek bitir")
            confirm_button.setStyleSheet(
                "background-color:#c0392b;color:white;font-weight:bold;"
                "padding:10px;border-radius:4px;margin-top:5px;"
            )
        elif quality.get("status") == "warning":
            confirm_button.setText("Kontrol Et ve Bitir")
            confirm_button.setStyleSheet(
                "background-color:#d68910;color:white;font-weight:bold;"
                "padding:10px;border-radius:4px;margin-top:5px;"
            )
        else:
            confirm_button.setText("Onayla ve Bitir")
            confirm_button.setStyleSheet(
                "background-color:#27ae60;color:white;font-weight:bold;"
                "padding:10px;border-radius:4px;margin-top:5px;"
            )

    render_scale = (
        float(getattr(app, "_stitch_preview_scale", 1.0))
        if getattr(app, "_stitch_interactive", False)
        else 1.0
    )

    gray_flags_for_render = dict(app._stitch_gray_flag_cache)
    if rotated_any:
        gray_flags_for_render = {
            path: False for path in gray_flags_for_render
        }

    checkerboard_on = (
        hasattr(app, "chk_checkerboard")
        and app.chk_checkerboard.isChecked()
    )

    result_arr = app.stitch_engine.compose_stitched(
        arrays=arrays,
        part_keys=valid_parts,
        paths=[app.stitch_files[p] for p in valid_parts],
        junction_offsets=junction_offsets,
        part_offsets=app.stitch_part_offsets,
        render_scale=render_scale,
        gray_flags=gray_flags_for_render,
        gray_cache=app._stitch_gray_cache,
        checkerboard=checkerboard_on,
    )
    if result_arr is None:
        return

    result_img = app._numpy_to_qimage(result_arr)

    app.final_result_qimage = result_img.copy()

    result_pixmap = QPixmap.fromImage(result_img)
    if app._stitch_result_item is None:
        app.stitch_scene.clear()
        app._stitch_result_item = app.stitch_scene.addPixmap(result_pixmap)
    else:
        app._stitch_result_item.setPixmap(result_pixmap)
    quality = getattr(app, "_last_stitch_quality", {}) or {}
    status = quality.get("status")
    avg_score = quality.get("average_score")

    if status == "poor":
        app.statusBar().showMessage(
            "Önizleme oluşturuldu ancak otomatik hizalama güveni düşük. "
            "Kaydetmeden önce manuel hizalama ve dama tahtası kontrolü yapın."
        )
    elif status == "warning":
        score_text = f"{avg_score:.2f}" if avg_score is not None else "—"
        app.statusBar().showMessage(
            f"Birleştirme önizlemesi hazır. Hizalama güveni orta ({score_text}); "
            "dikiş bölgesini kontrol edin."
        )
    else:
        app.statusBar().showMessage(
            " + ".join(p.capitalize() for p in valid_parts)
            + " görüntüleri lokal pozlama dengelemeli cosine feather ile birleştirildi."
        )


def _apply_final_image_adjustment(app):
    if app.final_result_qimage is None:
        return
    arr = app._qimage_to_numpy(app.final_result_qimage).astype(np.float32)
    factor = 1.0 + (app.final_contrast / 100.0)
    rgb = arr[..., :3]
    rgb = (rgb - 127.5) * factor + 127.5 + app.final_brightness
    arr[..., :3] = np.clip(rgb, 0, 255)
    qimg = app._numpy_to_qimage(arr.astype(np.uint8))
    app.stitch_scene.clear()
    app.stitch_scene.addPixmap(QPixmap.fromImage(qimg))


def _on_cobb_checkbox_toggled(app, checked):
    if checked != app.cobb_mode_active:
        app.toggle_cobb_measurement()



def validate_stitch_before_finish(app):
    """Return True when the technical stitch quality is acceptable to finish."""
    quality = getattr(app, "_last_stitch_quality", {}) or {}
    status = quality.get("status", "unknown")

    if status == "poor":
        junction_lines = []
        valid_parts = [
            p for p in ["servical", "dorsal", "lumbar", "extra"]
            if app.stitch_files.get(p) is not None
        ]
        for idx, row in enumerate(quality.get("junctions", [])):
            if idx + 1 >= len(valid_parts):
                continue
            junction_lines.append(
                f"{valid_parts[idx].capitalize()} → {valid_parts[idx + 1].capitalize()}: "
                f"{row['score']:.2f} ({_quality_text(row['status'])})"
            )

        message = (
            "En az bir birleşim noktasında otomatik hizalama güveni düşük.\\n\\n"
            + ("\\n".join(junction_lines) if junction_lines else "Kalite ayrıntısı yok.")
            + "\\n\\nDama tahtası ve manuel hizalama ile kontrol etmeden sonucu "
              "tamamlamanız önerilmez."
        )
        QMessageBox.warning(app, "Birleştirme kalite kontrolü", message)
        return False

    return True


def save_final_result(app):
    if app.final_result_qimage is None:
        QMessageBox.warning(app, "Kaydet", "Kaydedilecek bir sonuç bulunamadı.")
        return

    if not bool(getattr(app, "_stitch_final_verified", False)):
        QMessageBox.information(
            app,
            "Önce son doğrulama",
            "Kaydetmeden önce 'Onayla ve Bitir' ile birleşim kalite özetini "
            "kontrol edip final sonucu kilitleyin.",
        )
        return

    quality = (
        getattr(app, "_stitch_final_quality_snapshot", None)
        or getattr(app, "_last_stitch_quality", {})
        or {}
    )
    if quality.get("status") == "poor":
        answer = QMessageBox.warning(
            app,
            "Düşük hizalama güveni",
            "Otomatik hizalama güveni düşük görünüyor.\n\n"
            "Bu sonuç kaydedilebilir ancak önce manuel hizalama ve dama tahtası "
            "kontrolü önerilir.\n\nYine de kaydetmek istiyor musunuz?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
    path, _ = QFileDialog.getSaveFileName(app, "Sonucu Kaydet", "birlesik_omurga.png", "PNG Dosyası (*.png)")
    if not path:
        return
    if not path.lower().endswith(".png"):
        path += ".png"

    arr = app._qimage_to_numpy(app.final_result_qimage).astype(np.float32)
    factor = 1.0 + (app.final_contrast / 100.0)
    rgb = arr[..., :3]
    rgb = (rgb - 127.5) * factor + 127.5 + app.final_brightness
    arr[..., :3] = np.clip(rgb, 0, 255)
    out_arr = arr.astype(np.uint8)
    qimg = app._numpy_to_qimage(out_arr)
    ok_png = qimg.save(path, "PNG")

    dicom_path = path[:-4] + ".dcm"
    ok_dicom = False
    try:
        gray = (0.114 * out_arr[..., 0] + 0.587 * out_arr[..., 1] + 0.299 * out_arr[..., 2]).astype(np.uint8)
        ok_dicom = app._save_as_dicom(gray, dicom_path)
    except Exception as e:
        print(f"DICOM kaydetme hatası: {e}")

    if ok_png and ok_dicom:
        app.statusBar().showMessage(f"Kaydedildi: {path} ve {dicom_path}")
        app._offer_stitched_result_to_patient_history(dicom_path)
    elif ok_png:
        app.statusBar().showMessage(f"PNG kaydedildi ({path}); DICOM kaydı başarısız oldu.")
    else:
        app.statusBar().showMessage("Kaydetme başarısız oldu.")


def _stitch_source_patient_info(app):
    """Birleştirmede kullanılan DICOM'ların aynı hastaya ait olduğunu doğrula."""
    patient_ids = set()
    patient_names = set()
    readable = 0

    for source_path in app.stitch_files.values():
        if not source_path or not os.path.isfile(source_path):
            continue
        try:
            ds = pydicom.dcmread(source_path, stop_before_pixels=True)
        except Exception:
            continue

        readable += 1
        patient_id = str(getattr(ds, "PatientID", "") or "").strip()
        patient_name = str(getattr(ds, "PatientName", "") or "").strip()
        if patient_id:
            patient_ids.add(patient_id)
        if patient_name:
            patient_names.add(patient_name)

    return {
        "patient_ids": patient_ids,
        "patient_names": patient_names,
        "readable": readable,
    }


def _offer_stitched_result_to_patient_history(app, dicom_path):
    """Kaydedilmiş birleşik DICOM'u kullanıcı onayıyla ortak havuza ve hasta geçmişine ekle."""
    if not dicom_path or not os.path.isfile(dicom_path):
        return

    info = app._stitch_source_patient_info()
    patient_ids = info["patient_ids"]

    # Klinik güvenlik: farklı hastalara ait parçalar tek hastanın geçmişine yazılamaz.
    if len(patient_ids) > 1:
        QMessageBox.warning(
            app,
            "Hasta geçmişine eklenmedi",
            "Birleştirmede kullanılan DICOM parçalarının PatientID bilgileri birbiriyle uyuşmuyor.\n\n"
            "Birleşik DICOM diske kaydedildi ancak yanlış hastaya bağlanmaması için hasta geçmişine eklenmedi.",
        )
        return

    if not patient_ids:
        QMessageBox.information(
            app,
            "Hasta geçmişi",
            "Birleşik DICOM kaydedildi ancak kaynak görüntülerde güvenilir PatientID bulunamadığı için "
            "hasta geçmişine otomatik eklenmeyecek.",
        )
        return

    patient_id = next(iter(patient_ids))
    patient_name = next(iter(info["patient_names"]), "")
    patient_label = f"{patient_name} — {patient_id}" if patient_name else patient_id

    answer = QMessageBox.question(
        app,
        "Hasta geçmişine ekle",
        f"Birleştirilmiş omurga sonucu hasta geçmişine eklensin mi?\n\nHasta: {patient_label}\n"
        f"Dosya: {os.path.basename(dicom_path)}\n\n"
        "Evet derseniz sonuç ortak DICOM havuzuna, Görüntüleyiciye ve tetkik geçmişine eklenir.",
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.Yes,
    )
    if answer != QMessageBox.StandardButton.Yes:
        app.statusBar().showMessage(
            f"Birleşik DICOM kaydedildi; hasta geçmişine eklenmedi: {dicom_path}"
        )
        return

    try:
        # Ortak havuz + Skolyoz Takip
        app._remember_shared_paths([dicom_path])
        app._ensure_tracking_path(dicom_path)

        # Görüntüleyiciye ekleme. Modüler sürümde _add_viewer_paths yeni DICOM'u
        # _register_paths üzerinden ExamRepository'ye de kaydeder.
        added, item = app._add_viewer_paths([dicom_path])

        # Eğer dosya zaten görüntüleyicideyse _add_viewer_paths kayıt çağrısını
        # atlayabilir; bu durumda veritabanı hook'unu doğrudan bir kez çağır.
        if not added:
            register_paths = getattr(app, "_register_paths", None)
            if callable(register_paths):
                register_paths([dicom_path])

        # Oluşturulan kaydı seçili hale getirerek kullanıcıya görünür geri bildirim ver.
        tracking_item = None
        if hasattr(app, "study_list_widget"):
            for index in range(app.study_list_widget.count()):
                candidate = app.study_list_widget.item(index)
                candidate_path = str(candidate.data(Qt.UserRole) or "")
                if candidate_path and os.path.abspath(candidate_path) == os.path.abspath(dicom_path):
                    tracking_item = candidate
                    break

        if tracking_item is not None:
            app._study_tree_syncing = True
            try:
                app.study_list_widget.clearSelection()
                tracking_item.setSelected(True)
                app.study_list_widget.setCurrentItem(tracking_item)
            finally:
                app._study_tree_syncing = False
            app._sync_study_tree_selection_from_model()

        app.statusBar().showMessage(
            f"Birleştirilmiş omurga hasta geçmişine eklendi: {patient_label}"
        )
        QMessageBox.information(
            app,
            "Hasta geçmişine eklendi",
            f"Birleştirilmiş omurga kaydı {patient_label} için tetkik geçmişine eklendi.\n\n"
            "Kayıt türü: Secondary Capture DICOM\n"
            "Seri: Birleştirilmiş Omurga",
        )
    except Exception as exc:
        QMessageBox.warning(
            app,
            "Hasta geçmişine eklenemedi",
            f"DICOM dosyası diske kaydedildi ancak hasta geçmişine ekleme sırasında hata oluştu:\n{exc}",
        )


def _save_as_dicom(app, gray_arr, path):
    from pydicom.dataset import FileDataset, FileMetaDataset
    from pydicom.uid import generate_uid, SecondaryCaptureImageStorage, ExplicitVRLittleEndian

    ref_ds = None
    for p in app.stitch_files.values():
        if p:
            try:
                ref_ds = pydicom.dcmread(p, stop_before_pixels=True)
                break
            except Exception:
                continue

    file_meta = FileMetaDataset()
    file_meta.MediaStorageSOPClassUID = SecondaryCaptureImageStorage
    file_meta.MediaStorageSOPInstanceUID = generate_uid()
    file_meta.TransferSyntaxUID = ExplicitVRLittleEndian

    ds = FileDataset(path, {}, file_meta=file_meta, preamble=b"\x00" * 128)
    ds.SOPClassUID = SecondaryCaptureImageStorage
    ds.SOPInstanceUID = file_meta.MediaStorageSOPInstanceUID
    ds.Modality = "OT"
    ds.ConversionType = "WSD"

    now = datetime.datetime.now()
    ds.ContentDate = now.strftime("%Y%m%d")
    ds.ContentTime = now.strftime("%H%M%S")

    if ref_ds is not None:
        for tag in ("PatientName", "PatientID", "PatientBirthDate", "PatientSex",
                    "StudyInstanceUID", "StudyDate", "StudyID", "AccessionNumber"):
            if hasattr(ref_ds, tag):
                try:
                    setattr(ds, tag, getattr(ref_ds, tag))
                except Exception:
                    pass
    if not hasattr(ds, "StudyInstanceUID"):
        ds.StudyInstanceUID = generate_uid()
    ds.SeriesInstanceUID = generate_uid()
    ds.SeriesNumber = 1
    ds.InstanceNumber = 1
    ds.SeriesDescription = "Birlestirilmis Omurga"

    h, w = gray_arr.shape
    ds.Rows = h
    ds.Columns = w
    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = "MONOCHROME2"
    ds.BitsAllocated = 8
    ds.BitsStored = 8
    ds.HighBit = 7
    ds.PixelRepresentation = 0
    ds.RescaleSlope = 1
    ds.RescaleIntercept = 0
    ds.WindowCenter = 127.5
    ds.WindowWidth = 255
    ds.VOILUTFunction = "LINEAR"
    ds.PixelData = np.ascontiguousarray(gray_arr).tobytes()

    ds.save_as(path, enforce_file_format=True)
    return True


def load_dicoms(app):
    initial = app._shared_pool_paths()
    dialog = StudySelectionDialog(initial_files=initial, parent=app)
    if dialog.exec() != QDialog.Accepted:
        return

    selected = list(getattr(dialog, 'selected_paths', []))
    if not selected:
        return

    added = 0
    for file_name in selected:
        _, added_to_tracking = app._ensure_tracking_path(file_name)
        if added_to_tracking:
            app._add_viewer_paths([file_name])
            added += 1

    if added:
        app.study_list_widget.clearSelection()
        count = app.study_list_widget.count()
        for i in range(count - 1, max(-1, count - added - 1), -1):
            app.study_list_widget.item(i).setSelected(True)
        app.statusBar().showMessage(f"{added} görüntü yüklendi. Overlay için iki görüntüyü seçip 'Üst Üste'ye basın.")
    elif app.study_list_widget.count() > 0:
        app.study_list_widget.setCurrentRow(0)


def _default_window(app, file_path):
    key = os.path.abspath(file_path)
    if key in app._default_window_cache:
        return cache_get(app._default_window_cache, key)
    try:
        header_loader = getattr(app, "_viewer_header_for_path", None)
        if callable(header_loader):
            ds = header_loader(file_path)
        else:
            ds = pydicom.dcmread(file_path, stop_before_pixels=True)
        if ds is None:
            raise ValueError("DICOM başlığı okunamadı")
        wc = getattr(ds, 'WindowCenter', None)
        ww = getattr(ds, 'WindowWidth', None)
        if isinstance(wc, (list, pydicom.multival.MultiValue)):
            wc = wc[0] if wc else None
        if isinstance(ww, (list, pydicom.multival.MultiValue)):
            ww = ww[0] if ww else None
        if wc is None or ww is None:
            bits_stored = int(getattr(ds, 'BitsStored', 0) or 0)
            if bits_stored == 8 and int(getattr(ds, 'PixelRepresentation', 0) or 0) == 0:
                wc, ww = 127.5, 255.0
            else:
                wc, ww = 1000.0, 2000.0
        else:
            wc = float(wc)
            ww = max(1.0, float(ww))
    except Exception:
        wc, ww = 1000.0, 2000.0
    cache_put(
        app._default_window_cache,
        key,
        (wc, ww),
        getattr(app, "_default_window_cache_limit", 128),
    )
    return wc, ww


def get_image_pixmap(app, file_path):
    brightness_val = app.brightness_slider.value() if hasattr(app, 'brightness_slider') else 0
    default_wc, default_ww = app._default_window(file_path)
    wc, ww = app.window_settings.get(os.path.abspath(file_path), (default_wc, default_ww))
    cache_key = (os.path.abspath(file_path), int(brightness_val), round(float(wc), 3), round(float(ww), 3))
    cached = cache_get(app._viewer_pixmap_cache, cache_key)
    if cached is not None and not cached.isNull():
        return cached
    try:
        path = os.path.abspath(file_path)
        ds = cache_get(getattr(app, "_tracking_dataset_cache", {}), path)
        if ds is None:
            ds = pydicom.dcmread(path)
            cache_put(
                app._tracking_dataset_cache,
                path,
                ds,
                getattr(app, "_tracking_dataset_cache_limit", 2),
            )
        arr = process_dicom_array(
            ds,
            brightness_val,
            wc,
            ww,
            source_array=ds.pixel_array,
        )
        if arr is not None:
            height, width = arr.shape
            q_img = QImage(arr.data, width, height, width, QImage.Format_Grayscale8)
            pix = QPixmap.fromImage(q_img.copy())
            cache_put(
                app._viewer_pixmap_cache,
                cache_key,
                pix,
                getattr(app, "_viewer_pixmap_cache_limit", 10),
            )
            return pix
    except Exception:
        pixmap = QPixmap(file_path)
        if not pixmap.isNull():
            return pixmap
    return QPixmap()

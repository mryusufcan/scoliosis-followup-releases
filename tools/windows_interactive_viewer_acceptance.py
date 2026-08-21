from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from pathlib import Path

import pydicom
from PySide6.QtCore import QPointF

# This script intentionally does not force QT_QPA_PLATFORM=offscreen.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QApplication

from main import ScoliosisFollowUpApp
from modular_app.database.exam_repository import ExamRepository
from modular_app.run_modular import install_modules
from modular_app.ui import viewer_records


def main() -> int:
    app = QApplication.instance() or QApplication([])
    window = install_modules(ScoliosisFollowUpApp)()
    temp_db = tempfile.TemporaryDirectory()
    window.exam_repository = ExamRepository(Path(temp_db.name) / "acceptance.db")
    window.resize(1400, 900)
    window.show()
    app.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 100)

    samples = sorted((ROOT / "dev_data" / "dicom_samples").rglob("*"))
    samples = [path for path in samples if path.is_file()]
    if not samples:
        raise RuntimeError("dev_data/dicom_samples altında gerçek DICOM bulunamadı")
    path = str(samples[0].resolve())

    heartbeat_times: list[float] = []
    timer = QTimer(window)
    timer.setInterval(20)
    timer.timeout.connect(lambda: heartbeat_times.append(time.perf_counter()))
    timer.start()

    started = time.perf_counter()
    window.render_viewer_file(path, fit=True)
    app.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 5)
    loading_text = window.viewer_info_label.text()
    loading_observed = "hazırlanıyor" in loading_text.lower()

    deadline = time.perf_counter() + 20.0
    while time.perf_counter() < deadline and window.viewer_pixmap_item is None:
        app.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 20)
        time.sleep(0.01)

    finished = time.perf_counter()
    timer.stop()
    app.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 100)

    intervals_ms = [
        (right - left) * 1000.0
        for left, right in zip(heartbeat_times, heartbeat_times[1:])
    ]
    pixmap = window.viewer_pixmap_item.pixmap() if window.viewer_pixmap_item is not None else None
    # Gerçek pencerede dört noktalı ölçüm sonrası kayıt butonunun etkinleşmesini
    # ve ölçümün üretim veritabanına dokunmadan geçici SQLite'a yazılmasını doğrula.
    window.viewer_cobb_mode_active = True
    window._refresh_viewer_cobb_button()
    cobb_points = (
        QPointF(30, 30),
        QPointF(130, 30),
        QPointF(30, 90),
        QPointF(116.6025, 140),
    )
    for point in cobb_points:
        viewer_records.handle_viewer_cobb_click(window, point)
    app.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 50)
    cobb_save_enabled_before = bool(window.btn_viewer_cobb_save.isEnabled())
    cobb_measurement_id = window.save_viewer_cobb_measurement(
        side="right",
        upper_vertebra="T5",
        lower_vertebra="T11",
        curve_direction="right",
    )
    patient_id = str(
        getattr(pydicom.dcmread(path, stop_before_pixels=True, force=True), "PatientID", "UNKNOWN")
        or "UNKNOWN"
    ).strip() or "UNKNOWN"
    saved_measurements = window.exam_repository.list_cobb_measurements(patient_id)
    result = {
        "platform": sys.platform,
        "python": sys.version,
        "qt_platform": os.environ.get("QT_QPA_PLATFORM", "native"),
        "path": path,
        "loading_observed": loading_observed,
        "loading_text": loading_text,
        "scene_ready": pixmap is not None and not pixmap.isNull(),
        "scene_size": [pixmap.width(), pixmap.height()] if pixmap is not None else None,
        "current_path_matches": os.path.abspath(window.viewer_current_path or "") == os.path.abspath(path),
        "preload_request_count": int(window._viewer_preload_controller._next_id),
        "elapsed_ms": round((finished - started) * 1000.0, 2),
        "heartbeat_count": len(heartbeat_times),
        "heartbeat_max_gap_ms": round(max(intervals_ms, default=0.0), 2),
        "gui_responsive": len(heartbeat_times) >= 2 and max(intervals_ms, default=0.0) < 750.0,
        "cobb_save_button_enabled_before": cobb_save_enabled_before,
        "cobb_measurement_id": cobb_measurement_id,
        "cobb_saved_as_draft": bool(saved_measurements)
        and not bool(saved_measurements[-1].get("is_locked")),
        "cobb_save_button_disabled_after": not bool(window.btn_viewer_cobb_save.isEnabled()),
    }
    output = ROOT / "docs" / "roadmap" / "windows_interactive_viewer_acceptance.json"
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))

    if hasattr(window, "_viewer_preload_controller"):
        window._viewer_preload_controller.shutdown()
    # closeEvent'in kullanıcıya modal sormaması için kabul kaydını temizle.
    window.viewer_measurement_records.clear()
    window.viewer_markup_records.clear()
    window.close()
    app.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 100)
    temp_db.cleanup()
    return 0 if (
        result["scene_ready"]
        and result["current_path_matches"]
        and result["gui_responsive"]
        and result["cobb_save_button_enabled_before"]
        and result["cobb_measurement_id"]
        and result["cobb_saved_as_draft"]
        and result["cobb_save_button_disabled_after"]
    ) else 1


if __name__ == "__main__":
    raise SystemExit(main())

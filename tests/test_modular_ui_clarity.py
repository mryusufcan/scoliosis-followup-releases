from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QPointF  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from main import ScoliosisFollowUpApp  # noqa: E402
from modular_app.run_modular import install_modules  # noqa: E402


class ModularUiClarityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_tabs_have_task_oriented_names_and_tooltips(self):
        window = install_modules(ScoliosisFollowUpApp)()
        try:
            labels = [window.tabs.tabText(index) for index in range(window.tabs.count())]
            self.assertEqual(labels, [
                "Görüntüleyici", "Görüntü Birleştirme", "Takip ve Karşılaştırma",
            ])
            for index in range(window.tabs.count()):
                self.assertTrue(window.tabs.tabToolTip(index))
        finally:
            window.close()
            self.app.processEvents()

    def test_context_banners_and_primary_actions_are_present(self):
        window = install_modules(ScoliosisFollowUpApp)()
        try:
            self.assertIn("Görüntü Aç", window.viewer_context_label.text())
            self.assertIn("otomatik görünür", window.tracking_context_label.text())
            self.assertIn("parçaları yükleyin", window.stitch_context_label.text())
            self.assertEqual(window.btn_load_dicom.text(), "Tetkik Yükle")
            self.assertEqual(window.btn_pick_viewer_files.text(), "Açık Görüntüleri Kullan")
            self.assertEqual(window.btn_side_by_side.text(), "Yan Yana Karşılaştır")
            self.assertEqual(window.btn_overlay_auto_align.text(), "Otomatik Hizala")
            self.assertTrue(window.btn_load_dicom.property("uiPrimaryAction"))
            self.assertTrue(window.btn_viewer_cobb.property("uiMeasurementAction"))
        finally:
            window.close()
            self.app.processEvents()

    def test_toolbar_icons_and_tooltips_cover_all_workflows(self):
        window = install_modules(ScoliosisFollowUpApp)()
        try:
            viewer_actions = [
                window.btn_viewer_cobb,
                window.btn_viewer_length,
                window.btn_viewer_annotations,
            ]
            for button in viewer_actions:
                self.assertFalse(button.icon().isNull())
                self.assertEqual(button.iconSize().width(), 20)
                self.assertTrue(button.toolTip())

            for button in [
                window.btn_load_dicom,
                window.btn_side_by_side,
                window.btn_overlay,
                window.btn_measure_cobb,
                window.btn_overlay_auto_align,
                window.btn_overlay_reset,
            ]:
                self.assertFalse(button.icon().isNull())
                self.assertEqual(button.iconSize().width(), 20)
                self.assertTrue(button.toolTip())

            for button in [
                window.btn_pick_viewer_files,
                window.btn_stitch_action,
                window.btn_mode_off,
                window.btn_clear_pts,
                window.btn_move_up,
                window.btn_move_left,
                window.btn_move_zero,
                window.btn_move_right,
                window.btn_move_down,
            ]:
                self.assertFalse(button.icon().isNull())
                self.assertEqual(button.iconSize().width(), 20)
                self.assertTrue(button.toolTip())
        finally:
            window.close()
            self.app.processEvents()

    def test_cobb_four_point_flow_marks_manual_draft_and_clears_preview(self):
        window = install_modules(ScoliosisFollowUpApp)()
        try:
            window.viewer_current_path = "synthetic-cobb.dcm"
            window.viewer_pixmap_item = object()
            window.viewer_cobb_mode_active = True
            for point in [
                QPointF(10, 10),
                QPointF(110, 10),
                QPointF(10, 60),
                QPointF(110, 110),
            ]:
                window.handle_viewer_cobb_click(point)

            self.assertFalse(window.viewer_cobb_mode_active)
            self.assertEqual(window.viewer_cobb_points, [])
            self.assertEqual(len(window.viewer_measurement_records), 1)
            record = window.viewer_measurement_records[0]
            self.assertEqual(record["type"], "cobb")
            self.assertEqual(record["measurement_source"], "manual")
            self.assertEqual(record["verification_status"], "draft")
            self.assertEqual(record["unit"], "°")
            self.assertEqual(len(record["points"]), 4)
            self.assertIn("klinik doğrulama", record["verification_note"])
            self.assertFalse(window.viewer_cobb_preview_items)
        finally:
            window.viewer_measurement_records.clear()
            window.close()
            self.app.processEvents()

    def test_cobb_zero_length_is_rejected_without_record(self):
        window = install_modules(ScoliosisFollowUpApp)()
        try:
            window.viewer_current_path = "synthetic-invalid-cobb.dcm"
            window.viewer_pixmap_item = object()
            window.viewer_cobb_mode_active = True
            for point in [
                QPointF(10, 10),
                QPointF(10, 10),
                QPointF(20, 20),
                QPointF(40, 40),
            ]:
                window.handle_viewer_cobb_click(point)

            self.assertFalse(window.viewer_cobb_mode_active)
            self.assertFalse(window.viewer_cobb_points)
            self.assertFalse(window.viewer_cobb_preview_items)
            self.assertFalse(window.viewer_measurement_records)
            self.assertIn("geçersiz", window.statusBar().currentMessage())
        finally:
            window.close()
            self.app.processEvents()

    def test_invalid_pixel_spacing_falls_back_to_pixels(self):
        window = install_modules(ScoliosisFollowUpApp)()
        try:
            path = "synthetic-invalid-spacing.dcm"
            window.viewer_current_path = path
            window._viewer_dicom_flags[path] = True
            window._viewer_dataset_cache[path] = type("Dataset", (), {"PixelSpacing": [0, 0.5]})()
            self.assertIsNone(window._viewer_pixel_spacing())
        finally:
            window.close()
            self.app.processEvents()

    def test_menu_titles_are_clear_and_symbol_free(self):
        window = install_modules(ScoliosisFollowUpApp)()
        try:
            titles = [action.menu().title() for action in window.menuBar().actions() if action.menu() is not None]
            self.assertEqual(
                titles,
                ["Hasta", "Takip", "Görüntüleme", "Veri ve PACS", "Raporlar", "Gelişmiş", "Yardım"],
            )
            self.assertIn("min-width: 48px", self.app.styleSheet())
            for action in window.menuBar().actions():
                menu = action.menu()
                if menu is not None:
                    self.assertTrue(menu.toolTip())
        finally:
            window.close()
            self.app.processEvents()


if __name__ == "__main__":
    unittest.main()

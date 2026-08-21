from __future__ import annotations

import importlib.util
import json
import math
import os
import sys
import urllib.request
import subprocess
import hashlib
import csv
from datetime import datetime
from pathlib import Path

# The launcher lives in modular_app while optional PACS and validation modules
# remain at the project root. Keep both locations importable in development.
_BOOTSTRAP_ROOT = Path(__file__).resolve().parent.parent
if str(_BOOTSTRAP_ROOT) not in sys.path:
    sys.path.append(str(_BOOTSTRAP_ROOT))

from PySide6.QtCore import QEvent, QPointF, QSize, Qt, QTimer
from PySide6.QtWidgets import QStyle
from PySide6.QtWidgets import QApplication, QDialog, QFileDialog, QGraphicsItem, QInputDialog, QLineEdit, QMessageBox, QProgressDialog, QSplashScreen
from PySide6.QtGui import QActionGroup, QFont, QIcon, QPen, QPixmap

from modular_app.ui.ui_icons import make_icon
from modular_app.config.paths import (
    AI_RESOURCES_DIR, DATA_DIR, DB_PATH, LOG_PATH, PROJECT_ROOT,
    application_icon_path, startup_logo_path,
)
from modular_app.database.exam_repository import ExamRepository
from modular_app.timeline.exam_timeline import ExamTimelineDialog
from modular_app.timeline.comparison_sessions import ComparisonSessionDialog
from modular_app.timeline.cobb_history import CobbHistoryDialog
from modular_app.timeline.follow_up_summary import FollowUpSummaryDialog
from modular_app.timeline.cobb_trend import CobbTrendDialog
from modular_app.timeline.longitudinal_center_dialog import LongitudinalCenterDialog
from modular_app.timeline.longitudinal_panel import LongitudinalPanelDialog
from modular_app.timeline.audit_history import AuditHistoryDialog
from modular_app.timeline.patient_manager import PatientManagerDialog
from modular_app.timeline.quality_check import QualityCheckDialog
from modular_app.timeline.patient_card import PatientCardDialog
from modular_app.timeline.follow_up_alerts import FollowUpAlertsDialog
from modular_app.timeline.user_manager import UserManagerDialog
from modular_app.timeline.vertebra_labels import VERTEBRA_LEVELS, VertebraLabelsDialog
from modular_app.timeline.image_notes import ImageNotesDialog
from modular_app.timeline.follow_up_schedule import FollowUpScheduleDialog
from modular_app.ui.pacs_dialog import PacsDialog
from modular_app.ui.license_dialog import LicenseDialog
from modular_app.ui.ai_assistant_dialog import AICobbAssistantDialog
from modular_app.ui.ai_landmark_assistant_dialog import AILandmarkAssistantDialog
from modular_app.ui.ai_draft_review_dialog import AICobbDraftReviewDialog
from modular_app.ui.ai_model_candidate_review_dialog import AIModelCandidateReviewDialog
from modular_app.ui.ai_model_inspector_dialog import AIModelInspectorDialog
from modular_app.ui.ai_training_dialog import AITrainingDataDialog
from modular_app.ui.user_guide_dialog import UserGuideDialog
from modular_app.ui.image_quality_dialog import ImageQualityDialog
from modular_app.ui import workspace_actions
from modular_app.services.system_services import APP_VERSION, BackupError, backup_reminder_message, check_for_update, check_local_database_health, configure_logging, export_diagnostic_bundle, export_encrypted_backup, restore_encrypted_backup
from modular_app.services.license_policy import evaluate_license_gate
from modular_app.security.integrity import verify_distribution_integrity
from ai.model_runtime import CobbSuggestion, LocalCobbModel, calculate_cobb_angle
from ai.landmark_runtime import LandmarkSuggestion, LocalLandmarkModel
from ai.mazurowski_runtime import MazurowskiOnnxModel
from ai.draft_workflow import approve_ai_draft, create_ai_draft_record, persist_approved_ai_draft, reject_ai_draft
from modular_app.domain.contracts import CoordinateSystem, SourceContext
from modular_app.domain.measurement_adapter import LegacyCobbRepositoryAdapter
from ai.training_dataset import TRAINING_METHOD

BASE = Path(__file__).resolve().parent
DEFAULT_UPDATE_FEED = (
    "https://github.com/mryusufcan/scoliosis-followup-releases/"
    "releases/latest/download/update.json"
)
MODULAR_CHECKPOINT = BASE / "Scoliosis_FollowUp_OVERLAY_ALIGN_v9_PRESET_FIX_WW4000_WL2000.py"
# Bazı kopyalamalarda yalnızca modül klasörleri taşınmış olabilir. Bu durumda
# ana checkpoint güvenli geri dönüş noktasıdır; başlatıcı kapanmak yerine onu
# kullanarak modüler özellikleri uygulamaya bağlamaya devam eder.
CHECKPOINT = MODULAR_CHECKPOINT if MODULAR_CHECKPOINT.is_file() else PROJECT_ROOT / "main.py"




def create_startup_splash(app: QApplication, icon_path: Path) -> QSplashScreen | None:
    """Ekran/DPI bağımsız, odak çalmayan küçük bir açılış göstergesi üretir."""
    artwork_path = startup_logo_path()
    if not artwork_path.is_file():
        return None
    pixmap = QPixmap(str(artwork_path))
    if pixmap.isNull():
        return None

    # Qt 6 ekran geometrisini mantıksal piksel olarak verir; bu nedenle yüksek
    # DPI ekranlarda ayrıca cihaz-pikseli çarpımı yapmadan dengeli görünür.
    screen = app.primaryScreen()
    geometry = screen.availableGeometry() if screen is not None else None
    screen_width = geometry.width() if geometry is not None else 1280
    screen_height = geometry.height() if geometry is not None else 800
    target = QSize(
        max(260, min(560, int(screen_width * 0.30))),
        max(220, min(480, int(screen_height * 0.42))),
    )
    scaled = pixmap.scaled(target, Qt.KeepAspectRatio, Qt.SmoothTransformation)

    # WindowStaysOnTopHint kullanılmaz: splash diğer uygulamaları ve masaüstünü
    # kilitlemez. Mouse olaylarını da tutmayarak açılış sırasında etkileşimi
    # engellemez.
    splash = QSplashScreen(scaled)
    splash.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
    splash.setWindowFlag(Qt.WindowType.WindowDoesNotAcceptFocus, True)
    if icon_path.is_file():
        splash.setWindowIcon(QIcon(str(icon_path)))
    splash.showMessage("Scoliosis Follow-Up başlatılıyor…", Qt.AlignBottom | Qt.AlignHCenter, Qt.darkBlue)
    splash.show()
    app.processEvents()
    return splash


def load_checkpoint():
    if not CHECKPOINT.is_file():
        raise RuntimeError(f"Checkpoint bulunamadı: {CHECKPOINT}")
    spec = importlib.util.spec_from_file_location("scoliosis_checkpoint", CHECKPOINT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Checkpoint yüklenemedi: {CHECKPOINT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def schedule_runtime_license_check(app, window, gate_result):
    """Çevrimdışı/deneme süresi açık oturumda da dolunca yeniden denetler."""
    if gate_result.remaining is None:
        return
    milliseconds = max(1000, int(gate_result.remaining.total_seconds() * 1000))

    def enforce_at_expiry():
        refreshed = evaluate_license_gate(window.exam_repository)
        if refreshed.allowed:
            schedule_runtime_license_check(app, window, refreshed)
            return
        QMessageBox.warning(window, "Lisans süresi doldu", refreshed.message)
        window.close()
        app.quit()

    QTimer.singleShot(milliseconds, enforce_at_expiry)


def read_exam_metadata(path: str) -> dict:
    import pydicom
    ds = pydicom.dcmread(path, stop_before_pixels=True)

    def text(name, default=""):
        value = getattr(ds, name, default)
        if value is None:
            return default
        return str(value).strip()

    return {
        "patient_id": text("PatientID", "UNKNOWN") or "UNKNOWN",
        "patient_name": text("PatientName", ""),
        "exam_date": text("StudyDate", "UNKNOWN") or "UNKNOWN",
        "body_part": text("BodyPartExamined", ""),
        "modality": text("Modality", "DX") or "DX",
        "study_description": text("StudyDescription", "") or text("SeriesDescription", ""),
        "sop_instance_uid": text("SOPInstanceUID", ""),
        "dicom_path": path,
    }


def install_modules(AppClass):
    repo = ExamRepository(DB_PATH)

    class ModularApp(AppClass):
        def __init__(self):
            super().__init__()
            self.exam_repository = repo
            if not self._theme_settings.contains("ui/theme"):
                repository_theme = repo.get_setting("ui/theme", "")
                if repository_theme in {"dark", "light"}:
                    self.set_theme(repository_theme, persist=False)
            self._history_dialog = None
            self.setAcceptDrops(True)
            self.overlay_locked = False
            self.overlay_rotation = float(getattr(self, "overlay_rotation", 0.0) or 0.0)
            self.blink_enabled = False
            self.sync_views_enabled = False
            self._blink_visible = True
            self._blink_timer = QTimer(self)
            self._blink_timer.setInterval(500)
            self._blink_timer.timeout.connect(self._blink_tick)
            self._sync_timer = QTimer(self)
            self._sync_timer.setInterval(100)
            self._sync_timer.timeout.connect(self._sync_side_by_side_views)
            self.current_user_name = repo.get_setting("active_user_name", "Yerel Yönetici")
            self.current_user_role = repo.get_setting("active_user_role", "Yönetici")
            self.ai_cobb_model = LocalCobbModel(AI_RESOURCES_DIR / "vertebra_cobb")
            self.ai_landmark_model = LocalLandmarkModel(AI_RESOURCES_DIR / "vertebra_landmarks_experimental")
            self.mazurowski_ai_model = MazurowskiOnnxModel(
                AI_RESOURCES_DIR / "mazurowski" / "mazurowski_mask_rcnn.onnx"
            )
            self._ai_cobb_draft_items = []
            self._ai_landmark_draft_items = []
            self.ai_training_capture_active = False
            self.vertebra_label_mode_active = False
            self._vertebra_label_refresh_pending = False
            self._vertebra_label_viewports = []
            self._drop_viewports = []
            for view in (getattr(self, "view_left", None), getattr(self, "view_right", None)):
                if view is not None and view.viewport() is not None:
                    viewport = view.viewport()
                    viewport.installEventFilter(self)
                    self._vertebra_label_viewports.append(viewport)
            viewer = getattr(self, "viewer_view", None)
            if viewer is not None and viewer.viewport() is not None:
                viewer_viewport = viewer.viewport()
                viewer_viewport.setAcceptDrops(True)
                viewer_viewport.installEventFilter(self)
                self._drop_viewports.append(viewer_viewport)

            # ==========================================================
            # UI REFRESH STAGE 2 — sade, ikonlu ve kategori bazlı üst menü
            # ==========================================================
            menubar = self.menuBar()

            # Checkpoint / önceki modüler sürümden kalabilecek üst menüleri temizle.
            # Menüleri yeniden kurarken callback'lere dokunmuyoruz.
            for action in list(menubar.actions()):
                menu = action.menu()
                if menu is not None:
                    menubar.removeAction(action)

            # Ana pencerenin merkezi DARK_THEME_QSS teması menü ve alt menülere de uygulanır.
            # Burada yerel setStyleSheet kullanılmaması, tema token'larının tek kaynaktan
            # yönetilmesini ve alt menülerin aynı görsel dili korumasını sağlar.
            menubar.setObjectName("mainMenuBar")

            # Native Qt standard icons: monochrome/OS-consistent and font independent.
            _style = self.style()
            def _icon(sp):
                return _style.standardIcon(sp)

            # -------------------------
            # 👤 HASTA
            # -------------------------
            patient_menu = menubar.addMenu("Hasta")
            patient_menu.setToolTip("Hasta kartı, tetkik geçmişi ve görüntü notları")

            patient_card_action = patient_menu.addAction("Hasta Kartı")
            patient_card_action.triggered.connect(self.show_patient_card)

            history_action = patient_menu.addAction("Tetkik Geçmişi")
            history_action.triggered.connect(self.show_exam_history)

            image_notes_action = patient_menu.addAction("Görüntü Notları")
            image_notes_action.triggered.connect(self.show_image_notes)

            patient_menu.addSeparator()

            patient_list_action = patient_menu.addAction("Hasta Listesi ve Arama")
            patient_list_action.triggered.connect(self.show_patient_manager)

            # -------------------------
            # 📊 TAKİP
            # -------------------------
            tracking_menu = menubar.addMenu("Takip")
            tracking_menu.setToolTip("Cobb geçmişi, trendler, uyarılar ve kontrol takvimi")

            follow_up_action = tracking_menu.addAction("Takip Özeti")
            follow_up_action.triggered.connect(self.show_follow_up_summary)

            tracking_menu.addSeparator()

            cobb_history_action = tracking_menu.addAction("Cobb Geçmişi")
            cobb_history_action.triggered.connect(self.show_cobb_history)

            cobb_trend_action = tracking_menu.addAction("Cobb Trend Grafiği")
            cobb_trend_action.triggered.connect(self.show_cobb_trend)

            longitudinal_center_action = tracking_menu.addAction("Longitudinal Takip Merkezi")
            longitudinal_center_action.triggered.connect(self.show_longitudinal_center)

            longitudinal_panel_action = tracking_menu.addAction("İlerleme ve Takip Paneli")
            longitudinal_panel_action.setToolTip("Cobb trendi, metrikler ve tetkik zaman çizelgesini tek panelde göster")
            longitudinal_panel_action.triggered.connect(self.show_longitudinal_panel)

            tracking_menu.addSeparator()

            schedule_action = tracking_menu.addAction("Kontrol Takvimi")
            schedule_action.triggered.connect(self.show_follow_up_schedule)

            alerts_action = tracking_menu.addAction("Takip Uyarıları")
            alerts_action.triggered.connect(self.show_follow_up_alerts)

            # -------------------------
            # 🖥 GÖRÜNÜM
            # -------------------------
            view_menu = menubar.addMenu("Görüntüleme")
            view_menu.setToolTip("Görüntüleme modları, Overlay, kalite kontrolü ve tema")

            overlay_menu = view_menu.addMenu("Overlay İşlemleri")
            save_overlay_action = overlay_menu.addAction("Oturumu Kaydet")
            save_overlay_action.triggered.connect(self.save_overlay_session)

            open_overlay_action = overlay_menu.addAction("Kayıtlı Oturumlar")
            open_overlay_action.triggered.connect(self.show_comparison_sessions)

            score_action = overlay_menu.addAction("Teknik Uyum Skoru")
            score_action.triggered.connect(self.show_alignment_score)

            overlay_menu.addSeparator()
            export_dicom_action = overlay_menu.addAction("Secondary Capture DICOM")
            export_dicom_action.triggered.connect(self.export_overlay_secondary_capture)

            modes_menu = view_menu.addMenu("Görüntüleme Modları")
            blink_action = modes_menu.addAction("Blink Aç / Kapat")
            blink_action.triggered.connect(self.toggle_blink_mode)

            lock_action = modes_menu.addAction("Hizalamayı Kilitle / Aç")
            lock_action.triggered.connect(self.toggle_overlay_lock)

            sync_action = modes_menu.addAction("Yan Yana Senkron")
            sync_action.triggered.connect(self.toggle_sync_views)

            view_menu.addSeparator()

            self.recent_viewer_menu = view_menu.addMenu("Son Açılan Görüntüler")
            self.recent_viewer_menu.aboutToShow.connect(self._refresh_recent_viewer_menu)

            labeling_menu = view_menu.addMenu("Omur Etiketleri")
            label_mode_action = labeling_menu.addAction("Etiketleme Modu Aç / Kapat")
            label_mode_action.triggered.connect(self.toggle_vertebra_label_mode)

            labels_action = labeling_menu.addAction("Etiketleri Yönet")
            labels_action.triggered.connect(self.show_vertebra_labels)

            theme_menu = view_menu.addMenu("Tema")
            theme_group = QActionGroup(self)
            theme_group.setExclusive(True)
            self._theme_actions = {}
            for theme_key, theme_label in (("dark", "Koyu Tema"), ("light", "Açık Tema")):
                theme_action = theme_menu.addAction(theme_label)
                theme_action.setCheckable(True)
                theme_action.setChecked(getattr(self, "_theme_name", "dark") == theme_key)
                theme_action.setToolTip(
                    "Koyu arayüzü kullan" if theme_key == "dark" else "Açık arayüzü kullan"
                )
                theme_action.triggered.connect(
                    lambda checked=False, selected=theme_key: self.set_theme(selected)
                )
                theme_group.addAction(theme_action)
                self._theme_actions[theme_key] = theme_action

            # -------------------------
            # 🗄 VERİ / PACS
            # -------------------------
            view_menu.addSeparator()
            quality_action = view_menu.addAction("Görüntü Kalite Kontrolü")
            quality_action.setToolTip(
                "Aktif görüntü veya seçili takip çifti için teknik uygunluk kontrolü"
            )
            quality_action.triggered.connect(self.show_image_quality_control)

            data_menu = menubar.addMenu("Veri ve PACS")
            data_menu.setToolTip("PACS, veri kalite kontrolleri, yedek ve kullanıcılar")

            pacs_action = data_menu.addAction("PACS")
            pacs_action.triggered.connect(self.show_pacs)

            data_menu.addSeparator()

            quality_action = data_menu.addAction("Veri Kalite Kontrolü")
            quality_action.triggered.connect(self.show_quality_checks)

            dicom_quality_action = data_menu.addAction("DICOM Teknik Kontrolü")
            dicom_quality_action.triggered.connect(self.run_dicom_quality_check)

            data_menu.addSeparator()

            backup_action = data_menu.addAction("Veritabanı Yedeği")
            backup_action.triggered.connect(self.backup_database)

            restore_action = data_menu.addAction("Yedeği Geri Yükle")
            restore_action.triggered.connect(self.restore_database)

            users_action = data_menu.addAction("Kullanıcılar / Roller")
            users_action.triggered.connect(self.show_user_manager)

            # -------------------------
            # 📑 RAPORLAR
            # -------------------------
            reports_menu = menubar.addMenu("Raporlar")
            reports_menu.setToolTip("PDF/CSV takip raporları ve araştırma kopyaları")

            report_action = reports_menu.addAction("Takip Raporu PDF")
            report_action.triggered.connect(self.export_follow_up_pdf)

            csv_action = reports_menu.addAction("Takip Verisi CSV")
            csv_action.triggered.connect(self.export_follow_up_csv)

            reports_menu.addSeparator()

            anonymize_action = reports_menu.addAction("Araştırma Kopyası / Anonimleştir")
            anonymize_action.triggered.connect(self.export_anonymized_dicoms)

            audit_action = reports_menu.addAction("İşlem Geçmişi")
            audit_action.triggered.connect(self.show_audit_history)

            # -------------------------
            # 🧪 DENEYSEL
            # -------------------------
            experimental_menu = menubar.addMenu("Gelişmiş")
            experimental_menu.setToolTip("AI taslakları ve araştırma amaçlı araçlar")

            mazurowski_ai_action = experimental_menu.addAction("Yerel AI Cobb Asistanı")
            mazurowski_ai_action.setToolTip("Mazurowski omurga maskesi modelini çalıştırır; uzman onayı olmadan kayıt yapmaz")
            mazurowski_ai_action.triggered.connect(self.show_mazurowski_ai_assistant)

            self.ai_cobb_review_action = experimental_menu.addAction("AI Taslağını İncele / Onayla")
            self.ai_cobb_review_action.setEnabled(False)
            self.ai_cobb_review_action.triggered.connect(self.show_ai_cobb_draft_review)

            ai_developer_menu = experimental_menu.addMenu("AI Geliştirici Araçları")

            ai_landmark_action = ai_developer_menu.addAction("68-Landmark Omurga Taslağı")
            ai_landmark_action.setToolTip("Yerel 68-landmark modelini deneysel karşılaştırma amacıyla açar")
            ai_landmark_action.triggered.connect(self.show_ai_landmark_assistant)

            ai_cobb_action = ai_developer_menu.addAction("Eski Cobb Modeli Asistanı")
            ai_cobb_action.triggered.connect(self.show_ai_cobb_assistant)

            ai_model_inspector_action = ai_developer_menu.addAction("Model Paketini Denetle")
            ai_model_inspector_action.triggered.connect(self.show_ai_model_inspector)

            ai_model_candidate_review_action = ai_developer_menu.addAction("Aday Model Paketini İncele…")
            ai_model_candidate_review_action.setToolTip(
                "Seçilen klasörü yalnızca teknik kabul için denetler; modeli etkinleştirmez veya çalıştırmaz"
            )
            ai_model_candidate_review_action.triggered.connect(self.show_ai_model_candidate_review)

            ai_training_action = ai_developer_menu.addAction("Eğitim Verisi Yönetimi")
            ai_training_action.triggered.connect(self.show_ai_training_data)

            # -------------------------
            # ❓ YARDIM
            # -------------------------
            help_menu = menubar.addMenu("Yardım")
            help_menu.setToolTip("Kullanım rehberi, lisans, güncelleme ve tanı araçları")

            guide_action = help_menu.addAction("Kullanım Rehberi", self.show_user_guide)
            guide_action.setIcon(_icon(QStyle.SP_DialogHelpButton))
            help_menu.addSeparator()

            license_status_action = help_menu.addAction("Lisans Durumu", self.check_license_status)
            license_status_action.setIcon(_icon(QStyle.SP_DialogApplyButton))
            license_manage_action = help_menu.addAction("Lisans Yönetimi", self.show_license_manager)
            license_manage_action.setIcon(_icon(QStyle.SP_FileDialogInfoView))
            update_action = help_menu.addAction("Güncellemeleri Denetle", self.check_for_updates)
            update_action.setIcon(_icon(QStyle.SP_BrowserReload))

            help_menu.addSeparator()

            health_action = help_menu.addAction("Yerel Veri Sağlığı", self.show_local_data_health)
            health_action.setIcon(_icon(QStyle.SP_DialogApplyButton))
            bundle_action = help_menu.addAction("Tanı Paketini Dışa Aktar", self.export_diagnostic_bundle)
            bundle_action.setIcon(_icon(QStyle.SP_DialogSaveButton))
            log_action = help_menu.addAction("Hata Günlüğü Konumu", self.show_log_location)
            log_action.setIcon(_icon(QStyle.SP_DirOpenIcon))

            help_menu.addSeparator()
            about_action = help_menu.addAction("Hakkında", self.show_about)
            about_action.setIcon(_icon(QStyle.SP_MessageBoxInformation))

            # ==========================================================
            # UI REFRESH STAGE 3 — ana çalışma modüllerini görsel olarak ayır
            # ==========================================================
            tabs = getattr(self, "tabs", None)
            if tabs is not None:
                tab_titles = [
                    (getattr(self, "viewer_tab", None), "Görüntüleyici"),
                    (getattr(self, "stitcher_tab", None), "Görüntü Birleştirme"),
                    (getattr(self, "workspace_tab", None), "Takip ve Karşılaştırma"),
                ]
                for widget, title in tab_titles:
                    if widget is None:
                        continue
                    index = tabs.indexOf(widget)
                    if index >= 0:
                        tabs.setTabText(index, title)
                        tab_tooltips = {
                            "Görüntüleyici": "DICOM veya görüntüyü açın, inceleyin ve ölçün",
                            "Görüntü Birleştirme": "İki, üç veya dört görüntüyü hizalayın ve birleştirin",
                            "Takip ve Karşılaştırma": "Tetkikleri seçin, karşılaştırın, hizalayın ve ölçün",
                        }
                        tabs.setTabToolTip(index, tab_tooltips.get(title, title))
                        if widget is getattr(self, "viewer_tab", None):
                            tabs.setTabIcon(index, make_icon("viewer", 24))
                        elif widget is getattr(self, "stitcher_tab", None):
                            tabs.setTabIcon(index, make_icon("stitch", 24))
                        elif widget is getattr(self, "workspace_tab", None):
                            tabs.setTabIcon(index, make_icon("track", 24))

                tabs.setDocumentMode(True)
                tabs.tabBar().setIconSize(QSize(24, 24))
                tabs.setElideMode(Qt.ElideNone)
                # Sekme stilleri main.py içindeki merkezi DARK_THEME_QSS'ten gelir.
                # Burada yalnızca ikon, başlık ve tooltip davranışı düzenlenir.

                for widget, tooltip in [
                    (
                        getattr(self, "viewer_tab", None),
                        "DICOM görüntüleme, W/L, ölçüm, anotasyon ve dışa aktarım",
                    ),
                    (
                        getattr(self, "stitcher_tab", None),
                        "İki, üç veya dört görüntüyü hizala ve tek görüntü oluştur",
                    ),
                    (
                        getattr(self, "workspace_tab", None),
                        "Seri tetkikleri karşılaştır, Overlay kullan ve longitudinal takip yap",
                    ),
                ]:
                    if widget is None:
                        continue
                    index = tabs.indexOf(widget)
                    if index >= 0:
                        tabs.setTabToolTip(index, tooltip)

            # ==========================================================
            # UI REFRESH STAGE 6 — global spacing/font/color standardization
            # ==========================================================
            # Eski modüler stil ekleme bloğu kaldırıldı. Tüm standart widget stilleri
            # artık main.py içindeki DARK_THEME_QSS ve QPalette üzerinden yönetilir.
            # Özel görüntü canvas'ı ve ölçüm katmanları kendi çizim renklerini korur.

            self._sync_loaded_exams_to_database()

        def show_image_quality_control(self):
            ImageQualityDialog(self, self).exec()

        def show_user_guide(self):
            UserGuideDialog(self).exec()

        def check_license_status(self):
            """Lisans durumunu, çevrimdışı toleransı ve deneme süresini denetler."""
            result = evaluate_license_gate(self.exam_repository)
            expiry_line = (
                f"\n\nLisans son kullanım tarihi: {result.expires_at}"
                if result.expires_at
                else ""
            )
            message = f"{result.message}{expiry_line}"
            if result.allowed:
                QMessageBox.information(self, "Lisans kontrolü", message)
            else:
                QMessageBox.warning(self, "Lisans kontrolü", message)

        def show_license_manager(self):
            LicenseDialog(self.exam_repository, self).exec()

        def _fetch_update_feed(self, feed_url: str) -> dict:
            request = urllib.request.Request(
                feed_url,
                headers={
                    "User-Agent": f"ScoliosisFollowUp/{APP_VERSION}",
                    "Accept": "application/json",
                    "Cache-Control": "no-cache",
                },
            )
            with urllib.request.urlopen(request, timeout=20) as response:
                raw = response.read()
            data = json.loads(raw.decode("utf-8-sig"))
            if not isinstance(data, dict):
                raise RuntimeError("Güncelleme dosyası geçersiz.")
            return data

        def _download_update_installer(self, feed: dict) -> Path | None:
            version = str(feed.get("version") or "yeni").strip()
            download_url = str(
                feed.get("url")
                or feed.get("download_url")
                or feed.get("installer_url")
                or ""
            ).strip()
            if not download_url:
                QMessageBox.warning(
                    self,
                    "Güncelleme",
                    "Yeni sürüm bulundu ancak kurulum dosyası adresi update.json içinde yok.",
                )
                return None

            expected_sha256 = str(
                feed.get("sha256")
                or feed.get("installer_sha256")
                or feed.get("sha256sum")
                or ""
            ).strip().lower().replace("sha256:", "")

            # Güvenli varsayılan: installer hash'i yoksa çalıştırma.
            if not expected_sha256:
                QMessageBox.warning(
                    self,
                    "Güncelleme güvenliği",
                    "Yeni sürüm bulundu ancak kurulum dosyasının SHA-256 özeti yok.\n\n"
                    "Güvenlik nedeniyle uygulama içinden indirme başlatılmadı.",
                )
                return None

            update_dir = Path(
                os.environ.get("LOCALAPPDATA") or str(Path.home())
            ) / "ScoliosisFollowUp" / "updates"
            update_dir.mkdir(parents=True, exist_ok=True)

            safe_version = "".join(
                ch for ch in version if ch.isalnum() or ch in "._-"
            ) or "latest"
            target = update_dir / f"ScoliosisFollowUp_Setup_{safe_version}.exe"
            partial = target.with_suffix(".exe.part")

            request = urllib.request.Request(
                download_url,
                headers={"User-Agent": f"ScoliosisFollowUp/{APP_VERSION}"},
            )

            progress = QProgressDialog(
                "Yeni sürüm indiriliyor…",
                "İptal",
                0,
                100,
                self,
            )
            progress.setWindowTitle("Güncelleme indiriliyor")
            progress.setMinimumDuration(0)
            progress.setValue(0)
            progress.setAutoClose(False)
            progress.setAutoReset(False)

            sha = hashlib.sha256()
            try:
                with urllib.request.urlopen(request, timeout=30) as response:
                    total = int(response.headers.get("Content-Length") or 0)
                    downloaded = 0

                    with open(partial, "wb") as stream:
                        while True:
                            chunk = response.read(1024 * 256)
                            if not chunk:
                                break
                            stream.write(chunk)
                            sha.update(chunk)
                            downloaded += len(chunk)

                            if total > 0:
                                progress.setValue(
                                    min(99, int(downloaded * 100 / total))
                                )
                            QApplication.processEvents()

                            if progress.wasCanceled():
                                raise InterruptedError("İndirme iptal edildi.")

                actual_sha256 = sha.hexdigest().lower()
                if actual_sha256 != expected_sha256:
                    partial.unlink(missing_ok=True)
                    QMessageBox.critical(
                        self,
                        "Güncelleme doğrulanamadı",
                        "İndirilen kurulum dosyasının SHA-256 özeti beklenen değerle "
                        "eşleşmiyor.\n\nDosya çalıştırılmadı.",
                    )
                    return None

                partial.replace(target)
                progress.setValue(100)
                return target

            except InterruptedError:
                partial.unlink(missing_ok=True)
                self.statusBar().showMessage("Güncelleme indirmesi iptal edildi.")
                return None
            except Exception as exc:
                partial.unlink(missing_ok=True)
                QMessageBox.warning(
                    self,
                    "Güncelleme indirilemedi",
                    f"Kurulum dosyası indirilemedi.\n\nAyrıntı: {exc}",
                )
                return None
            finally:
                progress.close()

        def check_for_updates(self):
            """Tek tık kontrol; yeni sürüm varsa kullanıcı onayıyla indir ve kur."""
            saved_url = str(
                self.exam_repository.get_setting("updates/feed_url", "") or ""
            ).strip()
            feed_url = saved_url or DEFAULT_UPDATE_FEED

            if not saved_url:
                self.exam_repository.set_setting("updates/feed_url", feed_url)

            self.statusBar().showMessage("Güncellemeler denetleniyor…")
            QApplication.processEvents()

            try:
                available, message = check_for_update(feed_url, APP_VERSION)
            except Exception as exc:
                QMessageBox.warning(
                    self,
                    "Güncelleme denetimi",
                    "Güncelleme sunucusuna ulaşılamadı.\n\n"
                    f"Ayrıntı: {exc}",
                )
                self.statusBar().showMessage("Güncelleme denetimi başarısız.")
                return

            if not available:
                QMessageBox.information(
                    self,
                    "Güncelleme Denetimi",
                    f"Uygulama güncel.\n\nMevcut sürüm: {APP_VERSION}\n\n{message}",
                )
                self.statusBar().showMessage("Uygulama güncel.")
                return

            try:
                feed = self._fetch_update_feed(feed_url)
            except Exception as exc:
                QMessageBox.warning(
                    self,
                    "Güncelleme",
                    "Yeni sürüm bulundu ancak güncelleme ayrıntıları okunamadı.\n\n"
                    f"Ayrıntı: {exc}",
                )
                return

            new_version = str(feed.get("version") or "Yeni sürüm").strip()
            notes = str(
                feed.get("notes")
                or feed.get("changelog")
                or feed.get("message")
                or ""
            ).strip()

            prompt = QMessageBox(self)
            prompt.setWindowTitle("Yeni Sürüm Mevcut")
            prompt.setIcon(QMessageBox.Icon.Information)
            prompt.setText(f"<b>Scoliosis Follow-Up {new_version} hazır.</b>")
            detail = f"Mevcut sürüm: {APP_VERSION}\nYeni sürüm: {new_version}"
            if notes:
                detail += f"\n\n{notes}"
            prompt.setInformativeText(detail)

            download_btn = prompt.addButton(
                "İndir",
                QMessageBox.ButtonRole.AcceptRole,
            )
            later_btn = prompt.addButton(
                "Daha Sonra",
                QMessageBox.ButtonRole.RejectRole,
            )
            prompt.setDefaultButton(download_btn)
            prompt.exec()

            if prompt.clickedButton() is not download_btn:
                self.statusBar().showMessage("Güncelleme daha sonraya bırakıldı.")
                return

            installer = self._download_update_installer(feed)
            if installer is None:
                return

            done = QMessageBox(self)
            done.setWindowTitle("Güncelleme Hazır")
            done.setIcon(QMessageBox.Icon.Information)
            done.setText("<b>Yeni sürüm indirildi ve doğrulandı.</b>")
            done.setInformativeText(
                f"Kurulum dosyası:\n{installer}\n\n"
                "Şimdi kurulumu başlatmak ister misiniz?"
            )

            install_btn = done.addButton(
                "Şimdi Kur",
                QMessageBox.ButtonRole.AcceptRole,
            )
            folder_btn = done.addButton(
                "Klasörü Aç",
                QMessageBox.ButtonRole.ActionRole,
            )
            later_btn = done.addButton(
                "Daha Sonra",
                QMessageBox.ButtonRole.RejectRole,
            )
            done.setDefaultButton(install_btn)
            done.exec()

            if done.clickedButton() is folder_btn:
                try:
                    os.startfile(str(installer.parent))
                except Exception:
                    pass
                return

            if done.clickedButton() is not install_btn:
                self.statusBar().showMessage(
                    "Güncelleme indirildi; kurulum daha sonraya bırakıldı."
                )
                return

            try:
                subprocess.Popen([str(installer)], close_fds=True)
            except Exception as exc:
                QMessageBox.critical(
                    self,
                    "Kurulum başlatılamadı",
                    f"Kurulum dosyası çalıştırılamadı.\n\n{exc}",
                )
                return

            self.statusBar().showMessage("Kurulum başlatıldı. Uygulama kapatılıyor…")
            QApplication.processEvents()
            QApplication.quit()

        def show_log_location(self):
            log_path = LOG_PATH
            QMessageBox.information(self, "Hata günlüğü", f"Uygulama hata günlüğü:\n{log_path}\n\nKişisel hasta verilerini paylaşmadan önce günlüğü kontrol edin.")

        def show_local_data_health(self):
            health = check_local_database_health(
                DB_PATH,
                required_tables=("exams", "cobb_measurements", "app_settings", "patient_profiles"),
            )
            missing = self._missing_source_exams(limit=1000)
            backup = backup_reminder_message(self.exam_repository)
            text = health.message
            text += f"\n\nEksik kaynak DICOM: {len(missing)}"
            text += "\nŞifreli yedek: " + (backup or "Güncel görünüyor.")
            if health.ok:
                QMessageBox.information(self, "Yerel veri durumu", text)
            else:
                QMessageBox.warning(self, "Yerel veri durumu", text + "\n\nGeri yükleme için doğrulanmış şifreli yedek kullanın.")

        def _missing_source_exams(self, limit: int = 20) -> list[dict]:
            rows = []
            for exam in self.exam_repository.list_exams():
                if not os.path.isfile(str(exam.get("dicom_path", ""))):
                    rows.append(exam)
                    if len(rows) >= max(1, int(limit)):
                        break
            return rows

        def run_startup_safety_checks(self):
            """Display at most one daily reminder after the main window is ready."""
            health = check_local_database_health(
                DB_PATH,
                required_tables=("exams", "cobb_measurements", "app_settings", "patient_profiles"),
            )
            if not health.ok:
                QMessageBox.warning(self, "Yerel veri durumu", health.message + "\n\nUygulamayı kapatıp doğrulanmış şifreli yedekten geri yükleyin.")
                return
            backup = backup_reminder_message(self.exam_repository)
            missing = self._missing_source_exams()
            notices = []
            if backup:
                notices.append(backup + "\nHasta Takibi menüsünden şifreli yedek oluşturabilirsiniz.")
            if missing:
                names = ", ".join(Path(str(row.get("dicom_path", ""))).name for row in missing[:3])
                extra = "" if len(missing) <= 3 else f" ve en az {len(missing) - 3} kayıt daha"
                notices.append(f"İlk {len(missing)} kayıtlı kaynak DICOM bulunamadı: {names}{extra}.")
            if not notices:
                return
            now = datetime.now().astimezone()
            raw_last = self.exam_repository.get_setting("data_health/last_notice_at", "")
            try:
                last = datetime.fromisoformat(raw_last)
            except (TypeError, ValueError):
                last = None
            if last is not None and (now - last).total_seconds() < 24 * 3600:
                return
            self.exam_repository.set_setting("data_health/last_notice_at", now.isoformat())
            QMessageBox.information(self, "Yerel veri hatırlatması", "\n\n".join(notices))

        def export_diagnostic_bundle(self):
            suggested = f"scoliosis_tani_{datetime.now():%Y%m%d_%H%M%S}.zip"
            output, _ = QFileDialog.getSaveFileName(self, "Tanı paketini kaydet", suggested, "Tanı paketi (*.zip)")
            if not output:
                return
            if not output.lower().endswith(".zip"):
                output += ".zip"
            try:
                bundle = export_diagnostic_bundle(DATA_DIR, output)
                QMessageBox.information(
                    self, "Tanı paketi",
                    f"Tanı paketi oluşturuldu:\n{bundle}\n\nDICOM, veritabanı, hasta görüntüleri ve ham hata günlüğü pakete eklenmez.",
                )
            except Exception as exc:
                QMessageBox.warning(self, "Tanı paketi", f"Tanı paketi oluşturulamadı:\n{exc}")

        def _require_role(self, roles: set[str], action_name: str) -> bool:
            if self.current_user_role in roles:
                return True
            QMessageBox.warning(self, "Yetki gerekli", f"{action_name} için {', '.join(sorted(roles))} rolü gerekir.\nAktif rol: {self.current_user_role}")
            return False

        def show_user_manager(self):
            dialog = UserManagerDialog(
                self.exam_repository, self.current_user_name, self.current_user_role, self
            )
            dialog.active_user_selected.connect(self._set_active_user)
            dialog.exec()

        def _set_active_user(self, user):
            previous_name = self.current_user_name
            self.current_user_name = str(user.get("display_name", "Yerel Yönetici"))
            self.current_user_role = str(user.get("role", "Teknisyen"))
            self.exam_repository.set_setting("active_user_name", self.current_user_name)
            self.exam_repository.set_setting("active_user_role", self.current_user_role)
            self.exam_repository.record_audit_event(
                "SYSTEM", "active_user_changed",
                f"{previous_name or '—'} → {self.current_user_name}",
                actor=self.current_user_name, actor_role=self.current_user_role,
            )
            self.statusBar().showMessage(f"Aktif yerel kullanıcı: {self.current_user_name} ({self.current_user_role})")

        def show_patient_card(self):
            patient = self._current_patient()
            if not patient:
                QMessageBox.information(self, "Hasta kartı", "Önce bir DICOM/görüntü seçin.")
                return
            PatientCardDialog(
                self.exam_repository,
                patient["patient_id"],
                patient.get("patient_name", ""),
                self.current_user_name,
                editable=self.current_user_role in {"Yönetici", "Hekim"},
                parent=self,
            ).exec()

        def show_image_notes(self):
            patient = self._current_patient()
            if not patient:
                QMessageBox.information(self, "Görüntü notları", "Önce bir DICOM/görüntü seçin.")
                return
            paths = self._selected_paths_for_history()
            source_path = paths[0] if paths else str(getattr(self, "viewer_current_path", "") or "")
            if not source_path or not os.path.isfile(source_path):
                QMessageBox.information(self, "Görüntü notları", "Not için açık bir DICOM/görüntü bulunamadı.")
                return
            ImageNotesDialog(
                self.exam_repository,
                patient["patient_id"],
                source_path,
                self.current_user_name,
                self.current_user_role,
                self,
            ).exec()

        def show_follow_up_alerts(self):
            patient = self._current_patient()
            if not patient:
                QMessageBox.information(self, "Takip uyarıları", "Önce bir DICOM/görüntü seçin.")
                return
            FollowUpAlertsDialog(self.exam_repository, patient["patient_id"], self).exec()

        def show_about(self):
            box = QMessageBox(self)
            box.setWindowTitle("Hakkında")
            box.setTextFormat(Qt.TextFormat.RichText)
            box.setText(
                "<b>Scoliosis Follow-Up</b><br>"
                "Skolyoz takip, Overlay ve omurga birleştirme uygulaması.<br><br>"
                "<b>Geliştiren:</b> Yusuf Can ÖZDEMİR<br>"
                "<a href='https://bio.link/yusufcanozdemir'>https://bio.link/yusufcanozdemir</a>"
            )
            box.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
            box.exec()

        def load_dicoms(self):
            before = set(os.path.abspath(p) for p in self.loaded_files.values())
            super().load_dicoms()
            after = set(os.path.abspath(p) for p in self.loaded_files.values())
            new_paths = sorted(after - before)
            self._register_paths(new_paths)

        def _recent_viewer_paths(self) -> list[str]:
            try:
                raw = json.loads(self.exam_repository.get_setting("viewer/recent_paths", "[]"))
            except (TypeError, ValueError, json.JSONDecodeError):
                raw = []
            return [str(path) for path in raw if isinstance(path, str) and os.path.isfile(path)]

        def _remember_recent_viewer_paths(self, paths) -> None:
            current = self._recent_viewer_paths()
            for raw_path in reversed(list(paths)):
                path = os.path.abspath(str(raw_path))
                if not os.path.isfile(path):
                    continue
                current = [entry for entry in current if os.path.abspath(entry) != path]
                current.insert(0, path)
            self.exam_repository.set_setting("viewer/recent_paths", json.dumps(current[:12], ensure_ascii=False))

        def _refresh_recent_viewer_menu(self) -> None:
            menu = getattr(self, "recent_viewer_menu", None)
            if menu is None:
                return
            menu.clear()
            paths = self._recent_viewer_paths()
            if not paths:
                placeholder = menu.addAction("Henüz görüntü açılmadı")
                placeholder.setEnabled(False)
                return
            for path in paths:
                action = menu.addAction(Path(path).name)
                action.setToolTip(path)
                action.triggered.connect(lambda checked=False, source=path: self._open_recent_viewer_path(source))
            menu.addSeparator()
            clear_action = menu.addAction("Son Açılanlar Listesini Temizle")
            clear_action.triggered.connect(lambda: self.exam_repository.set_setting("viewer/recent_paths", "[]"))

        def _open_recent_viewer_path(self, path: str) -> None:
            if not os.path.isfile(path):
                self.statusBar().showMessage("Son açılan görüntü artık bulunamadı.")
                self._remember_recent_viewer_paths([])
                return
            added, item = self._add_viewer_paths([path])
            if item is not None:
                self.tabs.setCurrentWidget(self.viewer_tab)
                self.viewer_file_tree.setCurrentItem(item)
            self._remember_recent_viewer_paths([path])
            if not added and item is None:
                self.statusBar().showMessage("Görüntü açılamadı.")

        def _add_viewer_paths(self, paths):
            """Preserve checkpoint loading, then retain a small local recent list."""
            added, first_item = super()._add_viewer_paths(paths)
            if added:
                self._remember_recent_viewer_paths(paths)
            return added, first_item

        def dragEnterEvent(self, event):
            if event.mimeData().hasUrls() and any(url.isLocalFile() for url in event.mimeData().urls()):
                event.acceptProposedAction()
            else:
                event.ignore()

        def dropEvent(self, event):
            self._handle_dropped_urls(event.mimeData().urls(), event)

        def _handle_dropped_urls(self, urls, event=None):
            paths = [url.toLocalFile() for url in urls if url.isLocalFile() and os.path.isfile(url.toLocalFile())]
            if not paths:
                if event is not None:
                    event.ignore()
                return
            added, first_item = self._add_viewer_paths(paths)
            if first_item is not None:
                self.tabs.setCurrentWidget(self.viewer_tab)
                self.viewer_file_tree.setCurrentItem(first_item)
            self.statusBar().showMessage(
                f"Sürükle-bırak ile {added} dosya görüntüleyiciye eklendi." if added else "Bırakılan dosyalar açılamadı veya zaten listede."
            )
            if event is not None:
                event.acceptProposedAction()

        def _register_paths(self, paths):
            added = 0
            warnings = []
            exam_rows = []
            for path in paths:
                if not path or not os.path.isfile(path):
                    continue
                try:
                    from dicom.validation import validate_dicom_file
                    validation = validate_dicom_file(path)
                    if not validation.valid:
                        warnings.append(f"{os.path.basename(path)}: " + "; ".join(validation.errors))
                        continue
                    if validation.warnings:
                        warnings.append(f"{os.path.basename(path)}: " + "; ".join(validation.warnings))
                    data = read_exam_metadata(path)
                    exam_rows.append(data)
                    added += 1
                except Exception as exc:
                    warnings.append(f"{os.path.basename(path)}: doğrulama yapılamadı ({exc})")
            if exam_rows:
                # Klasörden çok sayıda görüntü alınırken her dosya için ayrı
                # SQLite bağlantısı açmak yerine tek transaction kullan.
                self.exam_repository.add_many(exam_rows)
            if added:
                self.statusBar().showMessage(f"{added} yeni tetkik geçmişe kaydedildi.")
            if warnings:
                # DICOM kalite bilgileri otomatik kayıt akışını bölmesin.
                # Popup kapatıldı; codec/transfer syntax bilgisi hata değildir.
                self.statusBar().showMessage(
                    f"{len(warnings)} DICOM teknik bilgi notu algılandı; işlem devam etti."
                )

        def _sync_loaded_exams_to_database(self):
            self._register_paths(list(self.loaded_files.values()))

        def _current_patient(self):
            paths = self._selected_paths_for_history()
            # Viewer'da açık olan dosya ortak seçime henüz yansımamış olsa bile
            # Hasta Takibi aynı aktif DICOM'u kullanabilsin.
            if not paths:
                viewer_path = str(getattr(self, "viewer_current_path", "") or "")
                if viewer_path and os.path.isfile(viewer_path):
                    paths = [viewer_path]
            if not paths:
                paths = list(self.loaded_files.values())[:1]
            if not paths:
                return None
            try:
                return read_exam_metadata(paths[0])
            except Exception:
                return None

        def _selected_paths_for_history(self):
            widget = getattr(self, "study_list_widget", None)
            if widget is None:
                return []
            paths = []
            for item in widget.selectedItems():
                path = item.data(Qt.ItemDataRole.UserRole)
                if path and os.path.exists(path):
                    paths.append(path)
            return paths

        def _active_ai_dicom_path(self):
            """Use the same active DICOM model shared by Viewer and follow-up."""
            candidates = []
            viewer_path = str(getattr(self, "viewer_current_path", "") or "")
            if viewer_path:
                candidates.append(viewer_path)
            candidates.extend(self._selected_paths_for_history())
            candidates.extend(list(getattr(self, "loaded_files", {}).values()))
            seen = set()
            for candidate in candidates:
                path = os.path.abspath(str(candidate or ""))
                if not path or path in seen or not os.path.isfile(path):
                    continue
                seen.add(path)
                try:
                    if self._viewer_is_dicom(path):
                        return path
                except Exception:
                    continue
            return ""

        def show_ai_cobb_assistant(self):
            """Open the local-only AI status and opt-in draft dialog."""
            dialog = AICobbAssistantDialog(self.ai_cobb_model, self._active_ai_dicom_path(), self)
            dialog.draft_requested.connect(self._apply_ai_cobb_draft)
            dialog.exec()

        def show_mazurowski_ai_assistant(self):
            """Run the local mask-curve model and submit its draft to expert review."""
            dialog = AICobbAssistantDialog(self.mazurowski_ai_model, self._active_ai_dicom_path(), self)
            dialog.draft_requested.connect(self._apply_ai_cobb_draft)
            dialog.exec()

        def show_ai_landmark_assistant(self):
            """Open an explicit experimental landmark draft flow; it cannot save measurements."""
            dialog = AILandmarkAssistantDialog(self.ai_landmark_model, self._active_ai_dicom_path(), self)
            dialog.draft_requested.connect(self._apply_ai_landmark_draft)
            dialog.cobb_draft_requested.connect(self._apply_ai_landmark_cobb_draft)
            dialog.exec()

        def _apply_ai_landmark_cobb_draft(self, suggestion: CobbSuggestion):
            """Show the landmark-derived Cobb candidate without enabling persistence."""
            self._apply_ai_cobb_draft(suggestion, allow_review=False)

        def show_ai_model_inspector(self):
            """Show local package status only; this action never fetches model files."""
            AIModelInspectorDialog(self.ai_cobb_model, self).exec()

        def show_ai_model_candidate_review(self):
            """Read a user-selected candidate folder without activating or running any model."""
            package_directory = QFileDialog.getExistingDirectory(
                self,
                "Aday AI Model Paketi Klasörünü Seçin",
                str(AI_RESOURCES_DIR),
            )
            if not package_directory:
                self.statusBar().showMessage("Aday AI model paketi incelemesi iptal edildi.")
                return
            AIModelCandidateReviewDialog(package_directory, self).exec()

        def show_ai_training_data(self):
            dialog = AITrainingDataDialog(
                self.exam_repository,
                self._active_ai_dicom_path(),
                self.current_user_name,
                self.current_user_role,
                self,
            )
            dialog.capture_requested.connect(self._start_ai_training_capture)
            dialog.exec()

        def _start_ai_training_capture(self):
            path = self._active_ai_dicom_path()
            if not path:
                QMessageBox.information(self, "AI eğitim etiketi", "Önce tek kareli bir DICOM görüntüsü açın.")
                return
            if os.path.abspath(str(getattr(self, "viewer_current_path", "") or "")) != os.path.abspath(path):
                self._add_viewer_paths([path])
                self.render_viewer_file(path, fit=True)
            if getattr(self, "tabs", None) is not None and getattr(self, "viewer_tab", None) is not None:
                self.tabs.setCurrentWidget(self.viewer_tab)
            if bool(
                int(getattr(self, "viewer_rotation", 0) or 0)
                or getattr(self, "viewer_flip_horizontal", False)
                or getattr(self, "viewer_flip_vertical", False)
            ):
                self.reset_viewer_transform()
            if getattr(self, "viewer_cobb_mode_active", False):
                super().toggle_viewer_cobb_measurement()
            self.ai_training_capture_active = True
            super().toggle_viewer_cobb_measurement()
            self.statusBar().showMessage(
                "AI eğitim etiketi: üst son-plağı soldan sağa 2 nokta, ardından alt son-plağı soldan sağa 2 nokta işaretleyin."
            )

        def toggle_viewer_cobb_measurement(self):
            was_training = bool(getattr(self, "ai_training_capture_active", False))
            super().toggle_viewer_cobb_measurement()
            if was_training and not getattr(self, "viewer_cobb_mode_active", False):
                self.ai_training_capture_active = False

        def _clear_ai_cobb_draft(self):
            scene = getattr(self, "viewer_scene", None)
            if scene is not None:
                for item in list(getattr(self, "_ai_cobb_draft_items", [])):
                    try:
                        scene.removeItem(item)
                    except RuntimeError:
                        pass
            self._ai_cobb_draft_items = []

        def _clear_ai_landmark_draft(self):
            scene = getattr(self, "viewer_scene", None)
            if scene is not None:
                for item in list(getattr(self, "_ai_landmark_draft_items", [])):
                    try:
                        scene.removeItem(item)
                    except RuntimeError:
                        pass
            self._ai_landmark_draft_items = []

        def _apply_ai_landmark_draft(self, suggestion: LandmarkSuggestion):
            """Draw experimental landmarks only; this method never creates a Cobb draft or database record."""
            path = os.path.abspath(str(suggestion.dicom_path or ""))
            if not path or not os.path.isfile(path):
                QMessageBox.warning(self, "Deneysel landmark taslağı", "Analiz edilen DICOM dosyası artık bulunamıyor.")
                return
            if os.path.abspath(str(getattr(self, "viewer_current_path", "") or "")) != path:
                self._add_viewer_paths([path])
                self.render_viewer_file(path, fit=True)
            if getattr(self, "tabs", None) is not None and getattr(self, "viewer_tab", None) is not None:
                self.tabs.setCurrentWidget(self.viewer_tab)
            if bool(int(getattr(self, "viewer_rotation", 0) or 0) or getattr(self, "viewer_flip_horizontal", False) or getattr(self, "viewer_flip_vertical", False)):
                QMessageBox.information(self, "Deneysel landmark taslağı", "Landmarklar özgün DICOM koordinatlarındadır. Taslağı göstermek için önce görüntü dönüşümünü sıfırlayın.")
                return
            scene = getattr(self, "viewer_scene", None)
            if scene is None or getattr(self, "viewer_pixmap_item", None) is None:
                QMessageBox.warning(self, "Deneysel landmark taslağı", "Görüntüleyici sahnesi hazırlanamadı.")
                return
            self._clear_ai_landmark_draft()
            normal_pen = QPen(Qt.GlobalColor.cyan, 2)
            warning_pen = QPen(Qt.GlobalColor.yellow, 3)
            for index, (x, y) in enumerate(suggestion.points):
                vertebra_index = index // 4
                confidence = suggestion.confidences[vertebra_index] if vertebra_index < len(suggestion.confidences) else 0.0
                pen = normal_pen if confidence >= 0.20 else warning_pen
                marker = scene.addEllipse(float(x) - 2.5, float(y) - 2.5, 5, 5, pen)
                marker.setZValue(80)
                marker.setData(0, "ai_landmark_draft")
                self._ai_landmark_draft_items.append(marker)
                if index % 4 == 0:
                    vertebra_label = scene.addText(str(index // 4 + 1), QFont("Segoe UI", 8, QFont.Bold))
                    vertebra_label.setDefaultTextColor(Qt.GlobalColor.cyan)
                    vertebra_label.setPos(float(x) + 3, float(y) + 3)
                    vertebra_label.setZValue(81)
                    vertebra_label.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True)
                    vertebra_label.setData(0, "ai_landmark_draft")
                    self._ai_landmark_draft_items.append(vertebra_label)
            banner = scene.addText("DENEYSEL AI LANDMARK TASLAĞI — 68 nokta — Ölçüm kaydedilmedi", QFont("Segoe UI", 11, QFont.Bold))
            banner.setDefaultTextColor(Qt.GlobalColor.cyan)
            banner.setPos(float(suggestion.points[0][0]), float(suggestion.points[0][1]))
            banner.setZValue(85)
            banner.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True)
            banner.setData(0, "ai_landmark_draft")
            self._ai_landmark_draft_items.append(banner)
            try:
                metadata = read_exam_metadata(path)
                self.exam_repository.record_audit_event(
                    metadata["patient_id"],
                    "ai_landmark_draft_displayed",
                    f"Deneysel 68 landmark taslağı; model {suggestion.model_version}; ölçüm geçmişine kaydedilmedi",
                    actor=self.current_user_name,
                    actor_role=self.current_user_role,
                )
            except Exception:
                pass
            self.statusBar().showMessage("Deneysel 68-landmark taslağı gösteriliyor. Cobb ölçümü veya kayıt oluşturulmadı; noktaları yalnızca görsel olarak inceleyin.")

        def _apply_ai_cobb_draft(self, suggestion: CobbSuggestion, *, allow_review: bool = True):
            """Draw an unverified AI suggestion without saving a measurement."""
            path = os.path.abspath(str(suggestion.dicom_path or ""))
            if not path or not os.path.isfile(path):
                QMessageBox.warning(self, "AI Cobb taslağı", "Analiz edilen DICOM dosyası artık bulunamıyor.")
                return
            if os.path.abspath(str(getattr(self, "viewer_current_path", "") or "")) != path:
                self._add_viewer_paths([path])
                self.render_viewer_file(path, fit=True)
            if getattr(self, "tabs", None) is not None and getattr(self, "viewer_tab", None) is not None:
                self.tabs.setCurrentWidget(self.viewer_tab)

            transformed = bool(
                int(getattr(self, "viewer_rotation", 0) or 0)
                or getattr(self, "viewer_flip_horizontal", False)
                or getattr(self, "viewer_flip_vertical", False)
            )
            if transformed:
                answer = QMessageBox.question(
                    self,
                    "Görüntü dönüşümünü sıfırla",
                    "AI noktaları özgün DICOM piksel düzenindedir. Taslağı doğru yerde göstermek için "
                    "döndürme/çevirme ayarları sıfırlansın mı?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.Yes,
                )
                if answer != QMessageBox.StandardButton.Yes:
                    return
                self.reset_viewer_transform()

            scene = getattr(self, "viewer_scene", None)
            if scene is None or getattr(self, "viewer_pixmap_item", None) is None:
                QMessageBox.warning(self, "AI Cobb taslağı", "Görüntüleyici sahnesi hazırlanamadı.")
                return
            self._clear_ai_cobb_draft()
            self._active_ai_cobb_suggestion = suggestion if allow_review else None
            review_action = getattr(self, "ai_cobb_review_action", None)
            if review_action is not None:
                review_action.setEnabled(bool(allow_review))
            points = [QPointF(float(x), float(y)) for x, y in suggestion.points]
            upper_pen = QPen(Qt.GlobalColor.magenta, 4)
            lower_pen = QPen(Qt.GlobalColor.yellow, 4)
            for index, point in enumerate(points):
                pen = upper_pen if index < 2 else lower_pen
                marker = scene.addEllipse(point.x() - 5, point.y() - 5, 10, 10, pen)
                marker.setZValue(82)
                marker.setData(0, "ai_cobb_draft")
                self._ai_cobb_draft_items.append(marker)
            for first, second, pen in ((points[0], points[1], upper_pen), (points[2], points[3], lower_pen)):
                line = scene.addLine(first.x(), first.y(), second.x(), second.y(), pen)
                line.setZValue(82)
                line.setData(0, "ai_cobb_draft")
                self._ai_cobb_draft_items.append(line)
            label = scene.addText(
                f"AI TASLAK — Cobb {suggestion.angle_degrees:.2f}° — Güven {suggestion.confidence:.2%}",
                QFont("Segoe UI", 12, QFont.Bold),
            )
            label.setDefaultTextColor(Qt.GlobalColor.yellow)
            label.setPos(points[2])
            label.setZValue(85)
            label.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True)
            label.setData(0, "ai_cobb_draft")
            self._ai_cobb_draft_items.append(label)

            try:
                metadata = read_exam_metadata(path)
                self.exam_repository.record_audit_event(
                    metadata["patient_id"],
                    "ai_cobb_draft_displayed",
                    f"Model {suggestion.model_version}; taslak {suggestion.angle_degrees:.2f} derece; "
                    f"güven {suggestion.confidence:.1%}; ölçüm geçmişine kaydedilmedi",
                    actor=self.current_user_name,
                    actor_role=self.current_user_role,
                )
            except Exception:
                pass
            if allow_review:
                self.statusBar().showMessage(
                    "AI Cobb taslağı gösteriliyor; kaydetmek veya reddetmek için Gelişmiş menüsündeki AI Taslağını İncele / Onayla seçeneğini kullanın."
                )
            else:
                self.statusBar().showMessage(
                    "Yerel landmark modelinden Cobb adayı gösteriliyor. Bu deneysel sonuç kaydedilemez; manuel Cobb aracıyla doğrulayın."
                )

        def _ai_draft_source_context(self, suggestion: CobbSuggestion) -> tuple[SourceContext, str]:
            """Build the immutable DICOM context required before any AI result can be saved."""
            import pydicom

            metadata = read_exam_metadata(suggestion.dicom_path)
            dataset = pydicom.dcmread(suggestion.dicom_path, stop_before_pixels=True)
            context = SourceContext(
                patient_id=metadata["patient_id"],
                sop_instance_uid=metadata["sop_instance_uid"],
                dicom_path=suggestion.dicom_path,
                image_width=int(getattr(dataset, "Columns", 0) or 0) or None,
                image_height=int(getattr(dataset, "Rows", 0) or 0) or None,
                coordinate_system=CoordinateSystem.IMAGE_PIXEL,
            )
            if context.patient_id == "UNKNOWN":
                raise ValueError("Hasta kimliği bulunamadığı için AI taslağı kalıcı ölçüm olarak kaydedilemez.")
            if not context.image_width or not context.image_height:
                raise ValueError("DICOM görüntü boyutu bulunamadığı için AI taslağı kalıcı ölçüm olarak kaydedilemez.")
            return context, metadata["exam_date"]

        def show_ai_cobb_draft_review(self):
            suggestion = getattr(self, "_active_ai_cobb_suggestion", None)
            if suggestion is None:
                QMessageBox.information(self, "AI Cobb taslağı", "Önce AI Cobb Asistanı ile bir taslak oluşturun.")
                return
            dialog = AICobbDraftReviewDialog(
                suggestion,
                self.current_user_name,
                self.current_user_role,
                self,
            )
            dialog.exec()
            if dialog.decision == "":
                return
            try:
                context, exam_date = self._ai_draft_source_context(suggestion)
                draft = create_ai_draft_record(
                    suggestion,
                    context,
                    app_version=APP_VERSION,
                    created_by=self.current_user_name,
                    exam_date=exam_date,
                )
                if dialog.decision == "approved":
                    approved = approve_ai_draft(
                        draft,
                        reviewer=self.current_user_name,
                        note=dialog.review_note,
                        reviewer_role=self.current_user_role,
                    )
                    adapter = LegacyCobbRepositoryAdapter(self.exam_repository, app_version=APP_VERSION)
                    measurement_id = persist_approved_ai_draft(adapter, approved)
                    self.exam_repository.record_audit_event(
                        context.patient_id,
                        "ai_cobb_draft_approved",
                        f"AI taslağı uzman onayıyla kaydedildi. Ölçüm #{measurement_id}; "
                        f"model {suggestion.model_version}; güven {suggestion.confidence:.1%}.",
                        actor=self.current_user_name,
                        actor_role=self.current_user_role,
                    )
                    self._clear_ai_cobb_draft()
                    self._active_ai_cobb_suggestion = None
                    if getattr(self, "ai_cobb_review_action", None) is not None:
                        self.ai_cobb_review_action.setEnabled(False)
                    self.statusBar().showMessage(f"AI taslağı uzman onayıyla kaydedildi: Cobb {approved.value:.2f}°")
                else:
                    review = reject_ai_draft(draft, reviewer=self.current_user_name, note=dialog.review_note)
                    self.exam_repository.record_audit_event(
                        context.patient_id,
                        "ai_cobb_draft_rejected",
                        f"AI taslağı reddedildi. Model {review.source_model_version}; neden: {review.note}",
                        actor=self.current_user_name,
                        actor_role=self.current_user_role,
                    )
                    self._clear_ai_cobb_draft()
                    self._active_ai_cobb_suggestion = None
                    if getattr(self, "ai_cobb_review_action", None) is not None:
                        self.ai_cobb_review_action.setEnabled(False)
                    self.statusBar().showMessage("AI taslağı reddedildi; ölçüm kaydedilmedi.")
            except Exception as exc:
                QMessageBox.warning(self, "AI Cobb taslağı", f"Onay işlemi tamamlanamadı: {exc}")

        def save_overlay_session(self):
            """Persist the active checkpoint overlay settings through the repository."""
            paths = self._selected_paths_for_history()
            if len(paths) != 2 or getattr(self, "current_mode", "") != "overlay":
                QMessageBox.information(
                    self,
                    "Overlay oturumu",
                    "Önce iki görüntüyü seçip Üst Üste (Overlay) Çakıştır moduna geçin.",
                )
                return
            try:
                reference_meta = read_exam_metadata(paths[0])
                comparison_meta = read_exam_metadata(paths[1])
            except Exception:
                QMessageBox.warning(self, "Overlay oturumu", "Seçilen DICOM bilgileri okunamadı.")
                return
            if reference_meta["patient_id"] != comparison_meta["patient_id"]:
                QMessageBox.warning(
                    self,
                    "Overlay oturumu",
                    "Farklı hastaların demo karşılaştırmaları oturum olarak kaydedilmez.",
                )
                return
            reference_wc, reference_ww = self.window_settings.get(os.path.abspath(paths[0]), self._default_window(paths[0]))
            comparison_wc, comparison_ww = self.window_settings.get(os.path.abspath(paths[1]), self._default_window(paths[1]))
            score = self._technical_alignment_score(paths[0], paths[1])
            session_id = self.exam_repository.add_comparison_session(
                patient_id=reference_meta["patient_id"],
                reference_path=paths[0],
                comparison_path=paths[1],
                overlay_offset_x=getattr(self, "overlay_offset_x", 0.0),
                overlay_offset_y=getattr(self, "overlay_offset_y", 0.0),
                overlay_scale=getattr(self, "overlay_scale", 1.0),
                overlay_opacity=getattr(self, "overlay_opacity", 0.5),
                overlay_rotation=getattr(self, "overlay_rotation", 0.0),
                reference_window_center=reference_wc,
                reference_window_width=reference_ww,
                comparison_window_center=comparison_wc,
                comparison_window_width=comparison_ww,
                alignment_score=score,
            )
            self.exam_repository.record_audit_event(reference_meta["patient_id"], "overlay_session_saved", f"Kayıt #{session_id}")
            self.statusBar().showMessage(f"Overlay oturumu kaydedildi (Kayıt #{session_id}).")

        @staticmethod
        def _technical_alignment_score(reference_path, comparison_path):
            """A normalized pixel-similarity heuristic, not a clinical quality decision."""
            try:
                import numpy as np
                import pydicom
                reference = pydicom.dcmread(reference_path).pixel_array.astype(np.float64)
                comparison = pydicom.dcmread(comparison_path).pixel_array.astype(np.float64)
                if reference.ndim > 2:
                    reference = reference[..., 0]
                if comparison.ndim > 2:
                    comparison = comparison[..., 0]
                height, width = reference.shape[:2]
                ys = np.linspace(0, comparison.shape[0] - 1, height).astype(int)
                xs = np.linspace(0, comparison.shape[1] - 1, width).astype(int)
                comparison = comparison[np.ix_(ys, xs)]
                reference = reference.ravel() - reference.mean()
                comparison = comparison.ravel() - comparison.mean()
                denominator = float(np.linalg.norm(reference) * np.linalg.norm(comparison))
                if denominator <= 0:
                    return None
                correlation = float(np.dot(reference, comparison) / denominator)
                return round(max(0.0, min(100.0, (correlation + 1.0) * 50.0)), 1)
            except Exception:
                return None

        def show_alignment_score(self):
            paths = self._selected_paths_for_history()
            if len(paths) != 2 or getattr(self, "current_mode", "") != "overlay":
                QMessageBox.information(self, "Teknik uyum skoru", "Önce iki görüntüyü Overlay modunda açın.")
                return
            score = self._technical_alignment_score(paths[0], paths[1])
            message = "Skor hesaplanamadı." if score is None else f"Teknik görüntü benzerliği: %{score:.1f}"
            QMessageBox.information(
                self, "Teknik uyum skoru",
                message + "\n\nBu gösterge yalnızca piksel benzerliğine dayanır; klinik uyum veya tanı anlamına gelmez.",
            )

        def export_overlay_secondary_capture(self):
            if not self._require_role({"Yönetici", "Hekim"}, "Secondary Capture DICOM dışa aktarma"):
                return
            paths = self._selected_paths_for_history()
            if len(paths) != 2 or getattr(self, "current_mode", "") != "overlay" or getattr(self, "overlay_item", None) is None:
                QMessageBox.information(self, "Secondary Capture", "Önce iki görüntüyü Overlay modunda açın.")
                return
            output, _ = QFileDialog.getSaveFileName(self, "Overlay DICOM kaydet", "overlay_secondary_capture.dcm", "DICOM (*.dcm)")
            if not output:
                return
            try:
                from dicom.validation import validate_dicom_file
                for source in paths:
                    validation = validate_dicom_file(source)
                    if not validation.valid:
                        raise ValueError(f"Kaynak DICOM geçersiz: {'; '.join(validation.errors)}")
                self._write_overlay_secondary_capture(paths[0], paths[1], output)
                validation = validate_dicom_file(output)
                if not validation.valid:
                    raise ValueError(f"Üretilen Secondary Capture doğrulanamadı: {'; '.join(validation.errors)}")
                metadata = read_exam_metadata(paths[0])
                self.exam_repository.record_audit_event(metadata["patient_id"], "overlay_secondary_capture_exported", os.path.basename(output))
                QMessageBox.information(self, "Secondary Capture", f"Yeni DICOM oluşturuldu:\n{output}")
            except Exception as exc:
                QMessageBox.warning(self, "Secondary Capture", f"DICOM oluşturulamadı:\n{exc}")

        def _write_overlay_secondary_capture(self, reference_path, comparison_path, output_path):
            import numpy as np
            import pydicom
            from pydicom.dataset import Dataset, FileDataset, FileMetaDataset
            from pydicom.uid import ExplicitVRLittleEndian, SecondaryCaptureImageStorage, generate_uid
            from PySide6.QtCore import QRectF
            from PySide6.QtGui import QImage, QPainter

            source = pydicom.dcmread(reference_path, stop_before_pixels=True)
            comparison_source = pydicom.dcmread(comparison_path, stop_before_pixels=True)
            rect = self.scene_left.itemsBoundingRect()
            if rect.isEmpty():
                raise ValueError("Overlay görüntüsü hazır değil.")
            image = QImage(1200, 1200, QImage.Format.Format_RGB888)
            image.fill(Qt.GlobalColor.black)
            painter = QPainter(image)
            self.scene_left.render(painter, QRectF(0, 0, 1200, 1200), rect)
            painter.end()
            raw = bytes(image.bits())
            pixels = np.frombuffer(raw, dtype=np.uint8).reshape((image.height(), image.width(), 3))

            meta = FileMetaDataset()
            meta.MediaStorageSOPClassUID = SecondaryCaptureImageStorage
            meta.MediaStorageSOPInstanceUID = generate_uid()
            meta.TransferSyntaxUID = ExplicitVRLittleEndian
            meta.ImplementationClassUID = generate_uid()
            dataset = FileDataset(str(output_path), {}, file_meta=meta, preamble=b"\0" * 128)
            for field in ("PatientName", "PatientID", "PatientBirthDate", "PatientSex", "StudyInstanceUID", "StudyDate", "StudyTime", "AccessionNumber", "StudyDescription"):
                if hasattr(source, field):
                    setattr(dataset, field, getattr(source, field))
            dataset.SOPClassUID = SecondaryCaptureImageStorage
            dataset.SOPInstanceUID = meta.MediaStorageSOPInstanceUID
            dataset.Modality = "OT"
            dataset.ConversionType = "WSD"
            dataset.ImageType = ["DERIVED", "SECONDARY"]
            dataset.SeriesInstanceUID = generate_uid()
            dataset.SeriesNumber = 999
            dataset.InstanceNumber = 1
            dataset.SeriesDescription = "Scoliosis Follow-Up Overlay Secondary Capture"
            dataset.DerivationDescription = "Overlay of two source DICOM images; generated in application."
            now = datetime.now()
            dataset.ContentDate = now.strftime("%Y%m%d")
            dataset.ContentTime = now.strftime("%H%M%S")
            dataset.Rows, dataset.Columns = pixels.shape[:2]
            dataset.SamplesPerPixel = 3
            dataset.PhotometricInterpretation = "RGB"
            dataset.PlanarConfiguration = 0
            dataset.BitsAllocated = dataset.BitsStored = dataset.HighBit = 8
            dataset.PixelRepresentation = 0
            dataset.PixelData = pixels.tobytes()
            dataset.SourceImageSequence = []
            for item in (source, comparison_source):
                reference = Dataset()
                reference.ReferencedSOPClassUID = getattr(item, "SOPClassUID", "")
                reference.ReferencedSOPInstanceUID = getattr(item, "SOPInstanceUID", "")
                dataset.SourceImageSequence.append(reference)
            dataset.save_as(str(output_path), enforce_file_format=True)

        def show_comparison_sessions(self):
            patient = self._current_patient()
            if not patient:
                QMessageBox.information(self, "Overlay oturumları", "Önce bir DICOM/görüntü seçin.")
                return
            dialog = ComparisonSessionDialog(self.exam_repository, patient["patient_id"], self)
            dialog.session_selected.connect(self._restore_comparison_session)
            dialog.exec()

        def show_cobb_history(self):
            patient = self._current_patient()
            if not patient:
                QMessageBox.information(self, "Cobb ölçüm geçmişi", "Önce bir DICOM/görüntü seçin.")
                return
            CobbHistoryDialog(
                self.exam_repository, patient["patient_id"], self.current_user_name, self.current_user_role, self
            ).exec()

        def show_cobb_trend(self):
            patient = self._current_patient()
            if not patient:
                QMessageBox.information(self, "Cobb trend grafiği", "Önce bir DICOM/görüntü seçin.")
                return
            CobbTrendDialog(self.exam_repository, patient["patient_id"], self).exec()

        def show_longitudinal_center(self):
            patient = self._current_patient()
            patient_id = patient["patient_id"] if patient else ""
            dialog = LongitudinalCenterDialog(
                self.exam_repository,
                patient_id,
                activate_viewer_path=self._activate_viewer_path_for_tracking,
                parent=self,
            )
            self._longitudinal_center_dialog = dialog
            dialog.show()
            dialog.raise_()
            dialog.activateWindow()

        def show_longitudinal_panel(self):
            """İlerleme panelini ana uygulamaya aç ve viewer köprülerini bağla."""
            patient = self._current_patient()
            patient_id = patient["patient_id"] if patient else ""
            dialog = LongitudinalPanelDialog(
                self.exam_repository,
                patient_id=patient_id,
                parent=self,
            )
            dialog.exam_open_requested.connect(self._open_exam_from_longitudinal_panel)
            dialog.overlay_requested.connect(self._open_pair_from_longitudinal_panel)
            dialog.measurement_requested.connect(self._show_longitudinal_measurement)
            dialog.csv_export_requested.connect(self._export_longitudinal_csv)
            dialog.pdf_export_requested.connect(self._export_longitudinal_pdf)
            dialog.error_occurred.connect(
                lambda message: self.statusBar().showMessage(str(message), 5000)
            )
            self._longitudinal_panel_dialog = dialog
            dialog.show()
            dialog.raise_()
            dialog.activateWindow()

        def _open_exam_from_longitudinal_panel(self, item):
            """Paneldeki tek satırı mevcut takipten açma akışına gönder."""
            row = self._longitudinal_item_to_exam_row(item)
            self._open_exam_from_summary(row)

        def _open_pair_from_longitudinal_panel(self, items):
            """Panelde seçilen iki satırı mevcut Overlay köprüsüne gönder."""
            rows = [self._longitudinal_item_to_exam_row(item) for item in list(items or [])]
            if len(rows) != 2:
                return
            self._open_summary_pair_in_overlay(rows)

        @staticmethod
        def _longitudinal_item_to_exam_row(item):
            return {
                "id": getattr(item, "exam_id", None),
                "patient_id": getattr(item, "patient_id", ""),
                "patient_name": "",
                "exam_date": getattr(item, "exam_date", ""),
                "body_part": getattr(item, "body_part", ""),
                "modality": getattr(item, "modality", ""),
                "study_description": getattr(item, "study_description", ""),
                "dicom_path": getattr(item, "dicom_path", ""),
                "notes": getattr(item, "notes", ""),
            }

        def _show_longitudinal_measurement(self, detail):
            """Grafik veya tablodan gelen ölçüm bağlamını kullanıcıya göster."""
            measurement_id = getattr(detail, "measurement_id", "")
            value = getattr(detail, "value", "")
            try:
                value_text = f"{float(value):.2f}°"
            except (TypeError, ValueError):
                value_text = str(value)
            self.statusBar().showMessage(
                f"Longitudinal ölçüm seçildi: #{measurement_id} · {value_text}",
                5000,
            )

        def _export_longitudinal_csv(self, snapshot):
            """Panel filtresine göre zaman çizelgesini CSV olarak dışa aktar."""
            if not self._require_role({"Yönetici", "Hekim"}, "Takip verisini CSV olarak dışa aktarma"):
                return
            if snapshot is None:
                return
            patient_id = str(getattr(snapshot, "patient_id", "") or "")
            if not patient_id:
                return
            suggested = f"ilerleme_takip_{patient_id}.csv"
            path, _ = QFileDialog.getSaveFileName(
                self, "İlerleme ve takip CSV'sini kaydet", suggested, "CSV (*.csv)"
            )
            if not path:
                return
            if not path.lower().endswith(".csv"):
                path += ".csv"
            try:
                from modular_app.timeline.longitudinal_service import LongitudinalService

                rows = LongitudinalService(self.exam_repository).build_csv_rows(snapshot)
                fieldnames = list(rows[0].keys()) if rows else ["patient_id"]
                with open(path, "w", newline="", encoding="utf-8-sig") as handle:
                    writer = csv.DictWriter(handle, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(rows)
                self.exam_repository.record_audit_event(
                    patient_id,
                    "longitudinal_panel_csv_exported",
                    os.path.basename(path),
                    actor=self.current_user_name,
                    actor_role=self.current_user_role,
                )
                QMessageBox.information(self, "CSV dışa aktarımı", f"Panel verisi kaydedildi:\n{path}")
            except Exception as exc:
                QMessageBox.warning(self, "CSV dışa aktarımı", f"Panel verisi kaydedilemedi:\n{exc}")

        def _export_longitudinal_pdf(self, snapshot):
            """Panelde seçili hastanın takip raporunu PDF olarak üret."""
            if not self._require_role({"Yönetici", "Hekim"}, "Takip raporunu PDF olarak dışa aktarma"):
                return
            if snapshot is None:
                return
            patient_id = str(getattr(snapshot, "patient_id", "") or "")
            patient_name = str(getattr(snapshot, "patient_name", "") or "")
            if not patient_id:
                return
            suggested = f"ilerleme_takip_{patient_id}.pdf"
            path, _ = QFileDialog.getSaveFileName(
                self, "İlerleme ve takip PDF'sini kaydet", suggested, "PDF (*.pdf)"
            )
            if not path:
                return
            clinical_note, accepted = QInputDialog.getMultiLineText(
                self, "Rapor notu", "Klinik not (isteğe bağlı):"
            )
            if not accepted:
                return
            overlay_snapshot = self._capture_overlay_snapshot(path)
            try:
                from modular_app.reporting.follow_up_pdf import generate_follow_up_report

                output = generate_follow_up_report(
                    self.exam_repository,
                    patient_id,
                    patient_name,
                    path,
                    clinical_note=clinical_note,
                    overlay_snapshot=overlay_snapshot,
                    prepared_by=self.current_user_name,
                    prepared_role=self.current_user_role,
                )
                self.exam_repository.record_audit_event(
                    patient_id,
                    "longitudinal_panel_pdf_exported",
                    os.path.basename(str(output)),
                    actor=self.current_user_name,
                    actor_role=self.current_user_role,
                )
                QMessageBox.information(self, "PDF raporu", f"Panel raporu kaydedildi:\n{output}")
            except Exception as exc:
                QMessageBox.warning(self, "PDF raporu", f"Panel raporu oluşturulamadı:\n{exc}")
            finally:
                if overlay_snapshot:
                    try:
                        os.remove(overlay_snapshot)
                    except OSError:
                        pass

        def show_audit_history(self):
            patient = self._current_patient()
            if not patient:
                QMessageBox.information(self, "İşlem geçmişi", "Önce bir DICOM/görüntü seçin.")
                return
            AuditHistoryDialog(self.exam_repository, patient["patient_id"], self).exec()

        def show_patient_manager(self):
            dialog = PatientManagerDialog(self.exam_repository, self)
            dialog.patient_selected.connect(self._open_patient_from_manager)
            dialog.exec()

        def show_follow_up_schedule(self):
            dialog = FollowUpScheduleDialog(self.exam_repository, self)
            dialog.patient_selected.connect(self._open_patient_from_manager)
            dialog.exec()

        def show_pacs(self):
            dialog = PacsDialog(self, allow_send=self.current_user_role in {"Yönetici", "Hekim"})
            dialog.files_retrieved.connect(self._import_pacs_files)
            dialog.dicom_sent.connect(self._record_pacs_send)
            dialog.exec()

        def _import_pacs_files(self, paths):
            imported = []
            for path in paths:
                if path and os.path.isfile(path) and self._add_path_to_study_list(path) is not None:
                    imported.append(path)
            self._register_paths(imported)
            if imported:
                for path in imported:
                    try:
                        metadata = read_exam_metadata(path)
                        self.exam_repository.record_audit_event(
                            metadata["patient_id"], "pacs_dicom_retrieved", os.path.basename(path),
                            actor=self.current_user_name, actor_role=self.current_user_role,
                        )
                    except Exception:
                        continue
                self.statusBar().showMessage(f"PACS'ten {len(imported)} DICOM uygulamaya eklendi.")

        def _record_pacs_send(self, path):
            try:
                metadata = read_exam_metadata(path)
                self.exam_repository.record_audit_event(
                    metadata["patient_id"], "pacs_dicom_sent", os.path.basename(path),
                    actor=self.current_user_name, actor_role=self.current_user_role,
                )
            except Exception:
                pass

        def _open_patient_from_manager(self, patient):
            exams = self.exam_repository.list_patient_exams(patient["patient_id"])
            if not exams:
                return
            self._open_exam_from_summary(exams[0])

        def show_quality_checks(self):
            patient = self._current_patient()
            if not patient:
                QMessageBox.information(self, "Veri kalite kontrolü", "Önce bir DICOM/görüntü seçin.")
                return
            QualityCheckDialog(self.exam_repository, patient["patient_id"], self).exec()

        def _selected_or_requested_dicom_paths(self, title: str) -> list[str]:
            """Use the shared study selection first, then permit explicit files.

            This keeps Viewer, Spine Stitcher and Follow-up on the same patient
            selection model while still allowing a preflight check before import.
            """
            paths = self._selected_paths_for_history()
            if not paths:
                viewer_path = str(getattr(self, "viewer_current_path", "") or "")
                if viewer_path and os.path.isfile(viewer_path):
                    paths = [viewer_path]
            if paths:
                return list(dict.fromkeys(str(path) for path in paths))
            selected, _ = QFileDialog.getOpenFileNames(
                self,
                title,
                "",
                "DICOM dosyaları (*.dcm *.dicom *.ima);;Tüm dosyalar (*)",
            )
            return [path for path in selected if os.path.isfile(path)]

        def run_dicom_quality_check(self):
            paths = self._selected_or_requested_dicom_paths("Teknik kalite denetimi için DICOM dosyalarını seçin")
            if not paths:
                return
            cursor_set = False
            try:
                from modular_app.services.dicom_quality import (
                    export_dicom_quality_csv,
                    inspect_dicom_paths,
                    quality_summary,
                )
                QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
                cursor_set = True
                results = inspect_dicom_paths(paths)
            except Exception as exc:
                QMessageBox.warning(self, "Teknik kalite denetimi", f"DICOM denetimi tamamlanamadı:\n{exc}")
                return
            finally:
                if cursor_set:
                    QApplication.restoreOverrideCursor()
            valid, invalid, warned = quality_summary(results)
            sample_issues = []
            for result in results:
                details = list(result.errors) + list(result.warnings)
                if details:
                    sample_issues.append(f"{result.source.name}: {'; '.join(details)}")
            message = (
                f"{len(results)} dosya denetlendi.\n\n"
                f"Geçerli: {valid}\nGeçersiz: {invalid}\nUyarılı: {warned}"
            )
            codec_rows = [
                f"{result.source.name}: {result.transfer_syntax or 'Bilinmiyor'} — {result.compression_status or 'Bilinmiyor'}"
                for result in results
            ]
            if codec_rows:
                message += "\n\nAktarım türleri:\n" + "\n".join(codec_rows[:5])
                if len(codec_rows) > 5:
                    message += "\n…"
            if sample_issues:
                message += "\n\nİlk bulgular:\n" + "\n".join(sample_issues[:3])
            save_report = QMessageBox.question(
                self,
                "Teknik kalite denetimi",
                message + "\n\nHasta etiketi içermeyen ayrıntılı CSV raporu kaydedilsin mi?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if save_report == QMessageBox.StandardButton.Yes:
                suggested = f"dicom_teknik_kalite_{datetime.now():%Y%m%d_%H%M%S}.csv"
                destination, _ = QFileDialog.getSaveFileName(self, "Teknik kalite raporunu kaydet", suggested, "CSV (*.csv)")
                if destination:
                    if not destination.lower().endswith(".csv"):
                        destination += ".csv"
                    try:
                        report = export_dicom_quality_csv(results, destination)
                        message += f"\n\nCSV raporu kaydedildi:\n{report}"
                    except Exception as exc:
                        QMessageBox.warning(self, "Teknik kalite denetimi", f"CSV raporu kaydedilemedi:\n{exc}")
                        return
            for path in paths:
                try:
                    metadata = read_exam_metadata(path)
                    self.exam_repository.record_audit_event(
                        metadata["patient_id"], "dicom_technical_quality_checked", os.path.basename(path),
                        actor=self.current_user_name, actor_role=self.current_user_role,
                    )
                except Exception:
                    continue
            QMessageBox.information(self, "Teknik kalite denetimi", message)

        def export_anonymized_dicoms(self):
            if not self._require_role({"Yönetici", "Hekim"}, "Anonim DICOM araştırma kopyası oluşturma"):
                return
            paths = self._selected_or_requested_dicom_paths("Anonimleştirilecek DICOM dosyalarını seçin")
            if not paths:
                return
            destination = QFileDialog.getExistingDirectory(
                self,
                "Anonim DICOM kopyaları için boş bir klasör seçin",
            )
            if not destination:
                return
            confirmation = QMessageBox.question(
                self,
                "Anonim araştırma kopyası",
                "Seçilen dosyaların yeni kopyaları oluşturulacak; orijinal DICOM dosyaları değiştirilmeyecek.\n\n"
                "Önemli: Piksel içine yazılmış isim veya kurum bilgileri otomatik olarak tespit edilmez. "
                "Bu çıktıyı klinik/PACS kullanımı için değil, yalnızca ayrıca gözden geçirilmiş araştırma paylaşımı için kullanın.\n\n"
                "Devam edilsin mi?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if confirmation != QMessageBox.StandardButton.Yes:
                return
            cursor_set = False
            try:
                from anonymization import AnonymizationError, anonymize_dicom_files
                from modular_app.services.dicom_quality import inspect_dicom_paths
                preflight = inspect_dicom_paths(paths)
                invalid = [item for item in preflight if not item.valid]
                if invalid:
                    names = ", ".join(item.source.name for item in invalid[:3])
                    raise AnonymizationError(f"Geçersiz DICOM dosyaları nedeniyle işlem başlatılmadı: {names}")
                QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
                cursor_set = True
                exported = anonymize_dicom_files(paths, destination)
            except Exception as exc:
                QMessageBox.warning(self, "Anonim araştırma kopyası", f"Anonim kopya oluşturulamadı:\n{exc}")
                return
            finally:
                if cursor_set:
                    QApplication.restoreOverrideCursor()
            for item in exported:
                try:
                    metadata = read_exam_metadata(str(item.source))
                    self.exam_repository.record_audit_event(
                        metadata["patient_id"], "dicom_anonymized_research_export", item.output.name,
                        actor=self.current_user_name, actor_role=self.current_user_role,
                    )
                except Exception:
                    continue
            QMessageBox.information(
                self,
                "Anonim araştırma kopyası",
                f"{len(exported)} anonim DICOM kopyası oluşturuldu:\n{destination}\n\n"
                "Orijinal dosyalar değiştirilmedi. Olası piksel içi yazıları paylaşmadan önce görsel olarak kontrol edin.",
            )

        def backup_database(self):
            if not self._require_role({"Yönetici"}, "Şifreli veritabanı yedeği oluşturma"):
                return
            suggested = f"scoliosis_yedek_{datetime.now():%Y%m%d_%H%M%S}.sfbak"
            path, _ = QFileDialog.getSaveFileName(self, "Şifreli veritabanı yedeğini kaydet", suggested, "Scoliosis şifreli yedek (*.sfbak)")
            if not path:
                return
            password, accepted = QInputDialog.getText(self, "Yedek parolası", "En az 8 karakterlik yedek parolası:", QLineEdit.EchoMode.Password)
            if not accepted:
                return
            confirm, accepted = QInputDialog.getText(self, "Yedek parolası", "Parolayı tekrar girin:", QLineEdit.EchoMode.Password)
            if not accepted or password != confirm:
                QMessageBox.warning(self, "Şifreli yedek", "Parolalar eşleşmiyor.")
                return
            try:
                output = export_encrypted_backup(DB_PATH, path, password)
                self.exam_repository.set_setting("backup/last_success_at", datetime.now().astimezone().isoformat())
                self.statusBar().showMessage("Şifreli veritabanı yedeği oluşturuldu.")
                QMessageBox.information(self, "Şifreli yedek", f"Yedek kaydedildi:\n{output}\n\nParolayı kaybederseniz bu yedek geri getirilemez.")
            except BackupError as exc:
                QMessageBox.warning(self, "Şifreli yedek", str(exc))
            except Exception as exc:
                QMessageBox.warning(self, "Şifreli yedek", f"Yedek oluşturulamadı:\n{exc}")

        def restore_database(self):
            if not self._require_role({"Yönetici"}, "Şifreli veritabanı geri yükleme"):
                return
            path, _ = QFileDialog.getOpenFileName(self, "Şifreli veritabanı yedeğini seç", "", "Scoliosis şifreli yedek (*.sfbak)")
            if not path:
                return
            answer = QMessageBox.question(
                self, "Veritabanını geri yükle",
                "Mevcut yerel takip kayıtları seçilen şifreli yedekle değiştirilecek. DICOM dosyalarına dokunulmayacak.\n\nDevam edilsin mi?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
            password, accepted = QInputDialog.getText(self, "Yedek parolası", "Yedek parolası:", QLineEdit.EchoMode.Password)
            if not accepted:
                return
            try:
                restore_encrypted_backup(path, DB_PATH, password)
                self.exam_repository = ExamRepository(DB_PATH)
                self.statusBar().showMessage("Veritabanı geri yüklendi. Açık pencereleri yeniden açın.")
            except BackupError as exc:
                QMessageBox.warning(self, "Geri yükleme", str(exc))
            except Exception as exc:
                QMessageBox.warning(self, "Geri yükleme", f"Geri yükleme tamamlanamadı:\n{exc}")

        def toggle_blink_mode(self):
            if getattr(self, "current_mode", "") != "overlay" or getattr(self, "overlay_item", None) is None:
                QMessageBox.information(self, "Blink modu", "Önce iki görüntüyü Overlay modunda açın.")
                return
            self.blink_enabled = not self.blink_enabled
            self._blink_visible = True
            if self.blink_enabled:
                self._blink_timer.start()
                self.statusBar().showMessage("Blink modu açık.")
            else:
                self._blink_timer.stop()
                self.overlay_item.setVisible(True)
                self.statusBar().showMessage("Blink modu kapalı.")

        def _blink_tick(self):
            if not self.blink_enabled or getattr(self, "overlay_item", None) is None:
                self._blink_timer.stop()
                return
            self._blink_visible = not self._blink_visible
            self.overlay_item.setVisible(self._blink_visible)

        def toggle_overlay_lock(self):
            self.overlay_locked = not self.overlay_locked
            self.statusBar().showMessage("Overlay hizalaması kilitlendi." if self.overlay_locked else "Overlay hizalaması açıldı.")

        def toggle_sync_views(self):
            self.sync_views_enabled = not self.sync_views_enabled
            if self.sync_views_enabled:
                self._sync_timer.start()
                self.statusBar().showMessage("Yan yana görünüm senkronu açık.")
            else:
                self._sync_timer.stop()
                self.statusBar().showMessage("Yan yana görünüm senkronu kapalı.")

        def _sync_side_by_side_views(self):
            if not self.sync_views_enabled or getattr(self, "current_mode", "") != "side_by_side":
                return
            if not getattr(self, "view_right", None) or not self.view_right.isVisible():
                return
            self.view_right.setTransform(self.view_left.transform())
            self.view_right.centerOn(self.view_left.mapToScene(self.view_left.viewport().rect().center()))

        def _refresh_auto_align_button(self):
            return workspace_actions._refresh_auto_align_button(self)

        def _apply_overlay_transform(self):
            return workspace_actions._apply_overlay_transform(self)

        def auto_align_overlay(self):
            return workspace_actions.auto_align_overlay(self)

        def move_overlay(self, dx, dy):
            if not self.overlay_locked:
                super().move_overlay(dx, dy)

        def on_overlay_x_changed(self, value):
            if not self.overlay_locked:
                super().on_overlay_x_changed(value)

        def on_overlay_y_changed(self, value):
            if not self.overlay_locked:
                super().on_overlay_y_changed(value)

        def on_overlay_zoom_changed(self, value):
            if not self.overlay_locked:
                super().on_overlay_zoom_changed(value)

        def on_overlay_rotation_changed(self, value):
            if not self.overlay_locked:
                workspace_actions.on_overlay_rotation_changed(self, value)

        def update_viewers(self):
            super().update_viewers()
            # Checkpoint sahneleri yeniden kurduktan sonra kalıcı yerel omur
            # etiketlerini tekrar çiz. Etiketler kaynak DICOM'a yazılmaz.
            QTimer.singleShot(0, self._render_vertebra_labels)

        def eventFilter(self, watched, event):
            if watched in self._drop_viewports:
                if event.type() == QEvent.Type.DragEnter:
                    if event.mimeData().hasUrls() and any(url.isLocalFile() for url in event.mimeData().urls()):
                        event.acceptProposedAction()
                        return True
                elif event.type() == QEvent.Type.Drop:
                    self._handle_dropped_urls(event.mimeData().urls(), event)
                    return True
            if watched in self._vertebra_label_viewports and event.type() in {QEvent.Type.Wheel, QEvent.Type.Resize}:
                self._schedule_vertebra_label_refresh()
            return super().eventFilter(watched, event)

        def _schedule_vertebra_label_refresh(self):
            if self._vertebra_label_refresh_pending:
                return
            self._vertebra_label_refresh_pending = True

            def refresh():
                self._vertebra_label_refresh_pending = False
                self._render_vertebra_labels()

            QTimer.singleShot(0, refresh)

        def toggle_vertebra_label_mode(self):
            if not self._selected_paths_for_history():
                QMessageBox.information(self, "Omur etiketleme", "Önce bir görüntü seçin.")
                return
            self.vertebra_label_mode_active = not self.vertebra_label_mode_active
            for view in (getattr(self, "view_left", None), getattr(self, "view_right", None)):
                if view is not None:
                    view.refresh_cursor()
            self.statusBar().showMessage(
                "Omur etiketleme modu açık: görüntüde konuma tıklayın." if self.vertebra_label_mode_active
                else "Omur etiketleme modu kapalı."
            )

        def handle_vertebra_label_click(self, side, pos):
            paths = self._selected_paths_for_history()
            image_index = 0 if side == "left" else 1
            if len(paths) <= image_index:
                return
            path = paths[image_index]
            try:
                metadata = read_exam_metadata(path)
            except Exception:
                QMessageBox.warning(self, "Omur etiketleme", "Seçili DICOM bilgileri okunamadı.")
                return
            level, accepted = QInputDialog.getItem(self, "Omur etiketi", "Omur seviyesi:", VERTEBRA_LEVELS, 7, False)
            if not accepted:
                return
            note, accepted = QInputDialog.getText(self, "Omur etiketi", "Kısa not (isteğe bağlı):")
            if not accepted:
                return
            label_id = self.exam_repository.add_vertebra_label(
                patient_id=metadata["patient_id"], dicom_path=path, vertebra=level,
                x=pos.x(), y=pos.y(), note=note, created_by=self.current_user_name,
            )
            self.exam_repository.record_audit_event(metadata["patient_id"], "vertebra_label_added", f"{level}; kayıt #{label_id}")
            self._render_vertebra_labels()
            self.statusBar().showMessage(f"{level} etiketi kaydedildi.")

        def _render_vertebra_labels(self):
            if not hasattr(self, "exam_repository"):
                return
            paths = self._selected_paths_for_history()
            if not paths:
                return
            mapping = [("left", getattr(self, "scene_left", None), getattr(self, "view_left", None), 0)]
            if getattr(self, "current_mode", "") == "side_by_side":
                mapping.append(("right", getattr(self, "scene_right", None), getattr(self, "view_right", None), 1))
            for _side, scene, _view, _index in mapping:
                if scene is not None:
                    for item in list(scene.items()):
                        if item.data(0) == "vertebra_label":
                            scene.removeItem(item)
            for _side, scene, view, index in mapping:
                if scene is None or len(paths) <= index:
                    continue
                try:
                    metadata = read_exam_metadata(paths[index])
                    labels = self.exam_repository.list_vertebra_labels(metadata["patient_id"], paths[index])
                except Exception:
                    continue
                view_scale = abs(float(view.transform().m11())) if view is not None else 1.0
                # Uzak görünümde görüntüyü kaplamaz; yakın görünümde okunur
                # kalır. ItemIgnoresTransformations yazıyı bulanıklaştırmadan
                # sabit tutarken bu aralık, zoom'a nazikçe uyum sağlar.
                font_size = max(8, min(14, int(round(10 + 2 * math.log2(max(view_scale, 0.025) / 0.20)))))
                marker_radius = max(5, min(8, int(round(font_size * 0.55))))
                for label in labels:
                    # Sabit sahne birimleriyle çizilen eski işaretler, büyük
                    # DICOM'larda nokta kadar küçük kalıyordu. Etiketleri
                    # görüntü yakınlaştırmasından bağımsız ekran boyutunda
                    # tutarak hem geniş görüntüde hem yakın planda okunur yap.
                    x, y = float(label["x"]), float(label["y"])
                    marker = scene.addEllipse(x - marker_radius, y - marker_radius, marker_radius * 2, marker_radius * 2)
                    marker.setPen(QPen(Qt.GlobalColor.yellow, 2))
                    marker.setBrush(Qt.BrushStyle.NoBrush)
                    marker.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True)
                    marker.setZValue(100)
                    marker.setToolTip(str(label.get("note", "")))
                    marker.setData(0, "vertebra_label")
                    text = scene.addText(str(label["vertebra"]))
                    text.setFont(QFont("Segoe UI", font_size, QFont.Weight.Bold))
                    text.setDefaultTextColor(Qt.GlobalColor.yellow)
                    text.setPos(x + marker_radius + 3, y - marker_radius - 4)
                    text.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True)
                    text.setZValue(101)
                    text.setToolTip(str(label.get("note", "")))
                    text.setData(0, "vertebra_label")

        def show_vertebra_labels(self):
            paths = self._selected_paths_for_history()
            if not paths:
                QMessageBox.information(self, "Omur etiketleri", "Önce bir görüntü seçin.")
                return
            try:
                metadata = read_exam_metadata(paths[0])
            except Exception:
                return
            dialog = VertebraLabelsDialog(self.exam_repository, metadata["patient_id"], paths[0], self)
            dialog.exec()
            self._render_vertebra_labels()

        def show_follow_up_summary(self):
            patient = self._current_patient()
            if not patient:
                QMessageBox.information(self, "Hasta takip özeti", "Önce bir DICOM/görüntü seçin.")
                return
            dialog = FollowUpSummaryDialog(
                self.exam_repository,
                patient["patient_id"],
                patient.get("patient_name", ""),
                self,
            )
            dialog.exam_selected.connect(self._open_exam_from_summary)
            dialog.exams_selected_for_overlay.connect(self._open_summary_pair_in_overlay)
            dialog.exec()

        def _open_exam_from_summary(self, row):
            path = row.get("dicom_path", "")
            if not path or not os.path.exists(path):
                QMessageBox.warning(self, "Tetkik bulunamadı", f"Dosya mevcut değil:\n{path}")
                return
            widget = getattr(self, "study_list_widget", None)
            if widget is None:
                return
            item = self._add_path_to_study_list(path)
            if item is None:
                return
            widget.clearSelection()
            item.setSelected(True)
            widget.setCurrentItem(item)
            self.set_side_by_side_mode()
            self.exam_repository.record_audit_event(str(row.get("patient_id", "UNKNOWN")), "exam_opened_from_summary", os.path.basename(path))
            self.statusBar().showMessage("Tetkik takip özetinden açıldı.")

        def _open_summary_pair_in_overlay(self, rows):
            if len(rows) != 2:
                return
            reference_path, comparison_path = (rows[0].get("dicom_path", ""), rows[1].get("dicom_path", ""))
            if not all((reference_path, comparison_path)) or not all(os.path.exists(path) for path in (reference_path, comparison_path)):
                QMessageBox.warning(self, "Overlay", "Seçili tetkik dosyalarından biri bulunamadı.")
                return
            if os.path.abspath(reference_path) == os.path.abspath(comparison_path):
                return
            widget = getattr(self, "study_list_widget", None)
            if widget is None:
                return
            reference_item = self._add_path_to_study_list(reference_path)
            comparison_item = self._add_path_to_study_list(comparison_path)
            self._put_comparison_pair_first(widget, reference_item, comparison_item)
            widget.clearSelection()
            reference_item.setSelected(True)
            comparison_item.setSelected(True)
            widget.setCurrentItem(reference_item)
            self.set_overlay_mode()
            self.exam_repository.record_audit_event(str(rows[0].get("patient_id", "UNKNOWN")), "overlay_opened_from_summary", os.path.basename(comparison_path))
            self.statusBar().showMessage("Seçili iki tetkik Overlay/Mukayese moduna gönderildi.")

        def export_follow_up_pdf(self):
            if not self._require_role({"Yönetici", "Hekim"}, "Takip raporunu PDF olarak dışa aktarma"):
                return
            patient = self._current_patient()
            if not patient:
                QMessageBox.information(self, "PDF raporu", "Önce bir DICOM/görüntü seçin.")
                return
            suggested = f"takip_raporu_{patient['patient_id']}.pdf"
            path, _ = QFileDialog.getSaveFileName(self, "Takip raporunu kaydet", suggested, "PDF (*.pdf)")
            if not path:
                return
            clinical_note, accepted = QInputDialog.getMultiLineText(
                self, "Rapor notu", "Klinik not (isteğe bağlı):"
            )
            if not accepted:
                return
            snapshot = self._capture_overlay_snapshot(path)
            try:
                # Lazy import: reportlab eksikse ana uygulamanın açılmasını engellemez.
                from modular_app.reporting.follow_up_pdf import generate_follow_up_report
                output = generate_follow_up_report(
                    self.exam_repository,
                    patient["patient_id"],
                    patient.get("patient_name", ""),
                    path,
                    clinical_note=clinical_note,
                    overlay_snapshot=snapshot,
                    prepared_by=self.current_user_name,
                    prepared_role=self.current_user_role,
                )
                self.exam_repository.record_audit_event(patient["patient_id"], "follow_up_pdf_exported", os.path.basename(str(output)))
                QMessageBox.information(self, "PDF raporu", f"Takip raporu kaydedildi:\n{output}")
            except Exception as exc:
                QMessageBox.warning(self, "PDF raporu", f"Rapor oluşturulamadı:\n{exc}")
            finally:
                if snapshot:
                    try:
                        os.remove(snapshot)
                    except OSError:
                        pass

        def export_follow_up_csv(self):
            if not self._require_role({"Yönetici", "Hekim"}, "Takip verisini CSV olarak dışa aktarma"):
                return
            patient = self._current_patient()
            if not patient:
                QMessageBox.information(self, "CSV dışa aktarımı", "Önce bir DICOM/görüntü seçin.")
                return
            suggested = f"takip_verisi_{patient['patient_id']}.csv"
            path, _ = QFileDialog.getSaveFileName(self, "Takip verisini CSV olarak kaydet", suggested, "CSV (*.csv)")
            if not path:
                return
            if not path.lower().endswith(".csv"):
                path += ".csv"
            try:
                from modular_app.reporting.follow_up_csv import export_follow_up_csv
                output, exam_count, measurement_count = export_follow_up_csv(
                    self.exam_repository,
                    patient["patient_id"],
                    patient.get("patient_name", ""),
                    path,
                )
                self.exam_repository.record_audit_event(
                    patient["patient_id"], "follow_up_csv_exported", os.path.basename(str(output)),
                    actor=self.current_user_name, actor_role=self.current_user_role,
                )
                QMessageBox.information(
                    self,
                    "CSV dışa aktarımı",
                    f"Takip verisi kaydedildi:\n{output}\n\nTetkik: {exam_count}\nCobb ölçümü: {measurement_count}\n\n"
                    "CSV dosyası hasta kimliği içerir; yalnızca yetkili kişilerle paylaşın.",
                )
            except Exception as exc:
                QMessageBox.warning(self, "CSV dışa aktarımı", f"Takip verisi kaydedilemedi:\n{exc}")

        def _capture_overlay_snapshot(self, report_path):
            """Capture only the active viewer scene for an optional report illustration."""
            if getattr(self, "current_mode", "") != "overlay" or getattr(self, "overlay_item", None) is None:
                return None
            try:
                from PySide6.QtCore import QRectF
                from PySide6.QtGui import QImage, QPainter
                rect = self.scene_left.itemsBoundingRect()
                if rect.isEmpty():
                    return None
                image = QImage(1200, 1200, QImage.Format.Format_ARGB32)
                image.fill(Qt.GlobalColor.black)
                painter = QPainter(image)
                self.scene_left.render(painter, QRectF(0, 0, 1200, 1200), rect)
                painter.end()
                snapshot = str(Path(report_path).with_suffix(".overlay_preview.png"))
                return snapshot if image.save(snapshot, "PNG") else None
            except Exception:
                return None

        def handle_cobb_click(self, side, pos):
            """Delegate drawing to the checkpoint, then record a completed measurement."""
            points = list(getattr(self, "cobb_points", []))
            target_side = getattr(self, "cobb_target_side", None)
            should_record = (
                getattr(self, "cobb_mode_active", False)
                and (target_side is None or target_side == side)
                and len(points) == 3
            )
            angle = None
            evidence_points = []
            if should_record:
                v1 = (points[1].x() - points[0].x(), points[1].y() - points[0].y())
                v2 = (pos.x() - points[2].x(), pos.y() - points[2].y())
                magnitude = (v1[0] ** 2 + v1[1] ** 2) ** 0.5 * (v2[0] ** 2 + v2[1] ** 2) ** 0.5
                if magnitude > 0:
                    import math
                    cosine = max(-1.0, min(1.0, (v1[0] * v2[0] + v1[1] * v2[1]) / magnitude))
                    angle = math.degrees(math.acos(cosine))
                    evidence_points = [
                        {"x": float(point.x()), "y": float(point.y())}
                        for point in [*points, pos]
                    ]

            super().handle_cobb_click(side, pos)
            if angle is None:
                return
            paths = self._selected_paths_for_history()
            image_index = 0 if side == "left" else 1
            if len(paths) <= image_index:
                return
            try:
                metadata = read_exam_metadata(paths[image_index])
                measurement_id = self.exam_repository.add_cobb_measurement(
                    patient_id=metadata["patient_id"],
                    dicom_path=paths[image_index],
                    exam_date=metadata.get("exam_date", "UNKNOWN"),
                    side=side,
                    angle_degrees=angle,
                    source_sop_instance_uid=metadata.get("sop_instance_uid", ""),
                    points=evidence_points,
                    created_by=self.current_user_name,
                )
                self.exam_repository.record_audit_event(
                    metadata["patient_id"],
                    "cobb_measurement_saved",
                    f"Kayıt #{measurement_id}; {angle:.2f} derece; 4 noktalı manuel kanıt kaydedildi",
                    actor=self.current_user_name,
                    actor_role=self.current_user_role,
                )
                self.statusBar().showMessage(f"Cobb açısı kaydedildi: {angle:.2f}° (Kayıt #{measurement_id}).")
            except Exception:
                # The checkpoint has already displayed the measurement; a history error must not affect it.
                pass

        def handle_viewer_cobb_click(self, pos):
            """Keep a Viewer Cobb measurement in the same local follow-up history.

            The checkpoint remains responsible for interaction and drawing. This
            bridge only stores the four point evidence after the fourth click,
            using a distinct source label so Viewer and comparison measurements
            are never confused in the history.
            """
            training_capture = bool(getattr(self, "ai_training_capture_active", False))
            points = list(getattr(self, "viewer_cobb_points", []))
            should_record = bool(getattr(self, "viewer_cobb_mode_active", False)) and len(points) == 3
            angle = None
            evidence_points = []
            if should_record:
                first, second, third = points
                v1 = (second.x() - first.x(), second.y() - first.y())
                v2 = (pos.x() - third.x(), pos.y() - third.y())
                magnitude = (v1[0] ** 2 + v1[1] ** 2) ** 0.5 * (v2[0] ** 2 + v2[1] ** 2) ** 0.5
                if magnitude > 0:
                    cosine = max(-1.0, min(1.0, (v1[0] * v2[0] + v1[1] * v2[1]) / magnitude))
                    evidence_points = [{"x": float(point.x()), "y": float(point.y())} for point in [*points, pos]]
                    angle = math.degrees(math.acos(cosine))
                    if training_capture:
                        angle = calculate_cobb_angle(
                            tuple((point["x"], point["y"]) for point in evidence_points)
                        )

            super().handle_viewer_cobb_click(pos)
            if should_record and training_capture:
                self.ai_training_capture_active = False
            if angle is None:
                return
            source_path = str(getattr(self, "viewer_current_path", "") or "")
            if not source_path or not os.path.isfile(source_path):
                return
            try:
                metadata = read_exam_metadata(source_path)
                measurement_id = self.exam_repository.add_cobb_measurement(
                    patient_id=metadata["patient_id"],
                    dicom_path=source_path,
                    exam_date=metadata.get("exam_date", "UNKNOWN"),
                    side="viewer",
                    angle_degrees=angle,
                    source_sop_instance_uid=metadata.get("sop_instance_uid", ""),
                    points=evidence_points,
                    measurement_method=TRAINING_METHOD if training_capture else "viewer_manual_4_point",
                    created_by=self.current_user_name,
                )
                event_type = "ai_training_label_created" if training_capture else "viewer_cobb_measurement_saved"
                details = (
                    f"Kayıt #{measurement_id}; {angle:.2f} derece; doğrulama bekleyen AI eğitim etiketi"
                    if training_capture
                    else f"Kayıt #{measurement_id}; {angle:.2f} derece; 4 noktalı Viewer kanıtı kaydedildi"
                )
                self.exam_repository.record_audit_event(
                    metadata["patient_id"],
                    event_type,
                    details,
                    actor=self.current_user_name,
                    actor_role=self.current_user_role,
                )
                if training_capture:
                    self.statusBar().showMessage(
                        f"AI eğitim etiketi oluşturuldu: {angle:.2f}° (Kayıt #{measurement_id}). "
                        "AI Eğitim Verisi ekranından doğrulayıp kilitleyin."
                    )
                else:
                    self.statusBar().showMessage(f"Cobb açısı takip geçmişine kaydedildi: {angle:.2f}° (Kayıt #{measurement_id}).")
            except Exception:
                # Görüntüleyici ölçümünün çizilmesini kayıt katmanındaki bir
                # hata nedeniyle bozma; kullanıcı ekrandaki sonucu görür.
                pass

        def _restore_comparison_session(self, session):
            reference_path = session.get("reference_path", "")
            comparison_path = session.get("comparison_path", "")
            missing = [path for path in (reference_path, comparison_path) if not path or not os.path.exists(path)]
            if missing:
                QMessageBox.warning(self, "Overlay oturumu", "Kayıtlı DICOM dosyası bulunamadı:\n" + "\n".join(missing))
                return
            try:
                reference_meta = read_exam_metadata(reference_path)
                comparison_meta = read_exam_metadata(comparison_path)
            except Exception:
                QMessageBox.warning(self, "Overlay oturumu", "Kayıtlı DICOM dosyaları okunamadı.")
                return
            if reference_meta["patient_id"] != comparison_meta["patient_id"]:
                QMessageBox.warning(self, "Overlay oturumu", "Kayıtlı oturumdaki hasta kimlikleri artık uyuşmuyor.")
                return

            widget = getattr(self, "study_list_widget", None)
            if widget is None:
                return
            reference_item = self._add_path_to_study_list(reference_path)
            comparison_item = self._add_path_to_study_list(comparison_path)
            self._put_comparison_pair_first(widget, reference_item, comparison_item)
            widget.clearSelection()
            reference_item.setSelected(True)
            comparison_item.setSelected(True)
            widget.setCurrentItem(reference_item)

            self.overlay_offset_x = float(session.get("overlay_offset_x", 0.0))
            self.overlay_offset_y = float(session.get("overlay_offset_y", 0.0))
            self.overlay_scale = float(session.get("overlay_scale", 1.0))
            self.overlay_rotation = float(session.get("overlay_rotation", 0.0) or 0.0)
            self.overlay_opacity = float(session.get("overlay_opacity", 0.5))
            if session.get("reference_window_center") is not None and session.get("reference_window_width") is not None:
                self.window_settings[os.path.abspath(reference_path)] = (
                    float(session["reference_window_center"]), float(session["reference_window_width"])
                )
            if session.get("comparison_window_center") is not None and session.get("comparison_window_width") is not None:
                self.window_settings[os.path.abspath(comparison_path)] = (
                    float(session["comparison_window_center"]), float(session["comparison_window_width"])
                )
            # Pixmap anahtarı W/L değerlerini içerir; bu nedenle önceki
            # oturumun görüntülerini silmeye gerek yoktur. Aynı oturum tekrar
            # açıldığında önbellekten anında gösterilebilir.
            self._sync_overlay_sliders()
            opacity_slider = getattr(self, "overlay_opacity_slider", None)
            if opacity_slider is not None:
                opacity_slider.blockSignals(True)
                opacity_slider.setValue(round(max(0.0, min(1.0, self.overlay_opacity)) * 100))
                opacity_slider.blockSignals(False)
            self.set_overlay_mode()
            self.exam_repository.record_audit_event(reference_meta["patient_id"], "overlay_session_restored", f"Kayıt #{session.get('id', '')}")
            self.statusBar().showMessage("Kayıtlı Overlay oturumu geri açıldı.")

        def show_exam_history(self):
            patient = self._current_patient()
            if not patient:
                QMessageBox.information(self, "Tetkik Geçmişi", "Önce en az bir DICOM/görüntü yükleyin.")
                return

            self._register_paths(list(self.loaded_files.values()))
            dialog = ExamTimelineDialog(
                self.exam_repository,
                patient["patient_id"],
                patient.get("patient_name", ""),
                self,
            )
            # Geçmişten seçilen kayıt, mevcut seçili görüntüyle karşılaştırılır.
            # Checkpoint'teki görüntüleme/overlay kodu değiştirilmez.
            dialog.exam_selected.connect(self._send_history_exam_to_overlay)
            self._history_dialog = dialog
            dialog.exec()

        def _selected_reference_path(self):
            """Return the current image selected before the history dialog opens."""
            paths = self._selected_paths_for_history()
            if paths:
                return paths[0]
            return next(iter(self.loaded_files.values()), "")

        def _add_path_to_study_list(self, path):
            """Dosyayı ortak Viewer/Takip modeline tek kez ekler."""
            if not path or not os.path.isfile(path):
                return None
            item, added = self._ensure_tracking_path(path)
            if added:
                self._add_viewer_paths([path])
            return item

        @staticmethod
        def _put_comparison_pair_first(widget, reference_item, history_item):
            """Guarantee the order required by the checkpoint's Overlay method."""
            for item in (reference_item, history_item):
                row = widget.row(item)
                if row >= 0:
                    widget.takeItem(row)
            widget.insertItem(0, reference_item)
            widget.insertItem(1, history_item)

        def _send_history_exam_to_overlay(self, row):
            """Select current + historical DICOM, then hand off to existing Overlay."""
            path = row.get("dicom_path", "")
            if not path or not os.path.exists(path):
                QMessageBox.warning(self, "Görüntü bulunamadı", f"Dosya mevcut değil:\n{path}")
                return

            widget = getattr(self, "study_list_widget", None)
            if widget is None:
                return

            reference_path = self._selected_reference_path()
            if not reference_path or not os.path.exists(reference_path):
                QMessageBox.warning(self, "Referans görüntü yok", "Mukayese için önce ana ekrandan bir görüntü seçin.")
                return
            if os.path.abspath(reference_path) == os.path.abspath(path):
                QMessageBox.information(self, "Aynı görüntü", "Mukayese için geçmişten farklı bir tetkik seçin.")
                return

            # Geçmiş listesi hasta bazlıdır; yine de dışarıdan değiştirilmiş
            # kayıtların yanlış hastayla overlay yapılmasını engelle.
            try:
                reference_meta = read_exam_metadata(reference_path)
                history_meta = read_exam_metadata(path)
                reference_id = reference_meta.get("patient_id", "UNKNOWN")
                history_id = history_meta.get("patient_id", "UNKNOWN")
                if reference_id != "UNKNOWN" and history_id != "UNKNOWN" and reference_id != history_id:
                    answer = QMessageBox.question(
                        self,
                        "Demo karşılaştırma onayı",
                        "Seçilen iki DICOM farklı hastalara ait.\n\n"
                        "Bu işlem yalnızca test/demonstrasyon amaçlıdır; klinik değerlendirme için kullanmayın.\n\n"
                        "Yine de Overlay/Mukayeseye göndermek istiyor musunuz?",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                        QMessageBox.StandardButton.No,
                    )
                    if answer != QMessageBox.StandardButton.Yes:
                        return
            except Exception:
                QMessageBox.warning(self, "DICOM okunamadı", "Geçmiş tetkik doğrulanamadığı için mukayeseye gönderilmedi.")
                return

            reference_item = self._add_path_to_study_list(reference_path)
            history_item = self._add_path_to_study_list(path)
            if reference_item is None or history_item is None:
                return

            self._put_comparison_pair_first(widget, reference_item, history_item)
            widget.clearSelection()
            # Sıra önemlidir: checkpoint ilk seçileni referans, ikincisini overlay yapar.
            reference_item.setSelected(True)
            history_item.setSelected(True)
            widget.setCurrentItem(reference_item)
            self.set_overlay_mode()
            self.exam_repository.record_audit_event(reference_meta["patient_id"], "overlay_comparison_opened", os.path.basename(path))
            self.statusBar().showMessage("Geçmiş tetkik mevcut görüntüyle Overlay/Mukayese moduna gönderildi.")

    return ModularApp


def _startup_dicom_path(argv) -> Path | None:
    """Return a requested local DICOM path only for explicit startup smoke/use flows."""
    values = list(argv or ())
    try:
        index = values.index("--open-dicom")
    except ValueError:
        return None
    if index + 1 >= len(values):
        return None
    candidate = Path(str(values[index + 1])).expanduser().resolve()
    return candidate if candidate.is_file() else None


def _open_startup_dicom(window, path: Path) -> bool:
    """Open a local file in the Viewer without modifying the source DICOM."""
    try:
        window._add_viewer_paths([str(path)])
        window.render_viewer_file(str(path), fit=True)
        if getattr(window, "tabs", None) is not None and getattr(window, "viewer_tab", None) is not None:
            window.tabs.setCurrentWidget(window.viewer_tab)
        window.statusBar().showMessage(f"Başlangıçta yerel DICOM açıldı: {path.name}", 12000)
        return True
    except Exception as exc:
        window.statusBar().showMessage(f"Başlangıç DICOM açılamadı: {path.name} — {exc}", 15000)
        return False


def main(checkpoint_class=None):
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    icon_path = application_icon_path()
    if icon_path.is_file():
        app.setWindowIcon(QIcon(str(icon_path)))

    splash = create_startup_splash(app, icon_path)

    integrity = verify_distribution_integrity()
    if not integrity.allowed:
        if splash is not None:
            splash.close()
        QMessageBox.critical(
            None,
            "Uygulama bütünlüğü doğrulanamadı",
            integrity.message + "\n\nUygulamayı resmi kurulum paketiyle yeniden yükleyin.",
        )
        return 3

    configure_logging(DB_PATH.parent)

    # Repository açılmadan önce yalnızca-okunur SQLite denetimi yapılır.
    # Bozuk bir dosyada şema yükseltmesi veya yeni yazım gerçekleştirilmez.
    preflight_health = check_local_database_health(DB_PATH)
    if not preflight_health.ok:
        if splash is not None:
            splash.close()
        QMessageBox.critical(
            None,
            "Yerel veritabanı doğrulanamadı",
            preflight_health.message + "\n\nUygulama açılmadı. Doğrulanmış şifreli yedekten geri yükleyin.",
        )
        return 4

    if splash is not None:
        splash.showMessage("Bileşenler hazırlanıyor…", Qt.AlignBottom | Qt.AlignHCenter, Qt.darkBlue)
        app.processEvents()

    # main.py doğrudan çalıştırıldığında sınıf zaten yüklenmiştir; yeniden
    # import etmeyerek açılışı hızlandırırız. run_modular.py tek başına
    # çalıştırıldığında ise eski uyumlu checkpoint yükleme yolu korunur.
    if checkpoint_class is None:
        checkpoint = load_checkpoint()
        checkpoint_class = checkpoint.ScoliosisFollowUpApp
    AppClass = install_modules(checkpoint_class)
    window = AppClass()
    if icon_path.is_file():
        window.setWindowIcon(QIcon(str(icon_path)))

    post_startup_health = check_local_database_health(
        DB_PATH,
        required_tables=("exams", "cobb_measurements", "app_settings", "patient_profiles"),
    )
    if not post_startup_health.ok:
        if splash is not None:
            splash.close()
        QMessageBox.critical(None, "Yerel veritabanı doğrulanamadı", post_startup_health.message)
        return 4

    # Lisans denetimi her açılışta zorunludur. Etkin lisans doğrulanamazsa
    # çevrimdışı tolerans 6 saattir; ilk lisanssız kullanım 14 gün sürer.
    license_gate = evaluate_license_gate(window.exam_repository)
    if not license_gate.allowed:
        if splash is not None:
            splash.hide()
        dialog = LicenseDialog(window.exam_repository, window, startup_message=license_gate.message)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        # Aktivasyon veya 'Doğrula ve Başlat' sonrasında süre/etkinlik
        # mutlaka yeniden değerlendirilir; arada ağ kesildiyse uygulama
        # yalnızca tanımlı çevrimdışı sınır içinde açılabilir.
        license_gate = evaluate_license_gate(window.exam_repository)
        if not license_gate.allowed:
            QMessageBox.warning(window, "Lisans", license_gate.message)
            return
        if splash is not None:
            splash.show()

    if license_gate.mode != "licensed":
        window.statusBar().showMessage(license_gate.message, 15000)
    schedule_runtime_license_check(app, window, license_gate)
    QTimer.singleShot(1800, window.run_startup_safety_checks)

    # Hazır olduktan sonra sabit 1,5 saniye bekletme; ana pencereyi hemen aç.
    window.show()
    if splash is not None:
        splash.finish(window)
    startup_dicom = _startup_dicom_path(sys.argv)
    if startup_dicom is not None:
        QTimer.singleShot(0, lambda: _open_startup_dicom(window, startup_dicom))
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

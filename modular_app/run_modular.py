from __future__ import annotations

import importlib.util
import os
import sys
from datetime import datetime
from pathlib import Path

# The launcher lives in modular_app while optional PACS and validation modules
# remain at the project root. Keep both locations importable in development.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    # Keep modular_app first so the integration's database/timeline modules win.
    # The project root remains available for optional dicom and pacs packages.
    sys.path.append(str(PROJECT_ROOT))

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QApplication, QDialog, QFileDialog, QInputDialog, QLineEdit, QMessageBox, QSplashScreen
from PySide6.QtGui import QPen, QPixmap

from modular_app.database.exam_repository import ExamRepository
from modular_app.timeline.exam_timeline import ExamTimelineDialog
from modular_app.timeline.comparison_sessions import ComparisonSessionDialog
from modular_app.timeline.cobb_history import CobbHistoryDialog
from modular_app.timeline.follow_up_summary import FollowUpSummaryDialog
from modular_app.timeline.cobb_trend import CobbTrendDialog
from modular_app.timeline.audit_history import AuditHistoryDialog
from modular_app.timeline.patient_manager import PatientManagerDialog
from modular_app.timeline.quality_check import QualityCheckDialog
from modular_app.timeline.patient_card import PatientCardDialog
from modular_app.timeline.follow_up_alerts import FollowUpAlertsDialog
from modular_app.timeline.user_manager import UserManagerDialog
from modular_app.timeline.vertebra_labels import VERTEBRA_LEVELS, VertebraLabelsDialog
from modular_app.ui.pacs_dialog import PacsDialog
from modular_app.ui.license_dialog import LicenseDialog
from modular_app.services.system_services import APP_VERSION, BackupError, check_for_update, configure_logging, export_diagnostic_bundle, export_encrypted_backup, restore_encrypted_backup
from modular_app.services.license_policy import evaluate_license_gate
from modular_app.security.integrity import verify_distribution_integrity

BASE = Path(__file__).resolve().parent
MODULAR_CHECKPOINT = BASE / "Scoliosis_FollowUp_OVERLAY_ALIGN_v9_PRESET_FIX_WW4000_WL2000.py"
# Bazı kopyalamalarda yalnızca modül klasörleri taşınmış olabilir. Bu durumda
# ana checkpoint güvenli geri dönüş noktasıdır; başlatıcı kapanmak yerine onu
# kullanarak modüler özellikleri uygulamaya bağlamaya devam eder.
CHECKPOINT = MODULAR_CHECKPOINT if MODULAR_CHECKPOINT.is_file() else PROJECT_ROOT / "main.py"


def application_data_dir() -> Path:
    """Kullanıcı verilerini EXE paketinden ayrı, yazılabilir yerde tutar."""
    if getattr(sys, "frozen", False):
        local_data = os.environ.get("LOCALAPPDATA")
        root = Path(local_data) if local_data else Path.home() / "AppData" / "Local"
        return root / "ScoliosisFollowUp"
    return BASE / "data"


DATA_DIR = application_data_dir()
DB_PATH = DATA_DIR / "scoliosis.db"


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
        "dicom_path": path,
    }


def install_modules(AppClass):
    repo = ExamRepository(DB_PATH)

    class ModularApp(AppClass):
        def __init__(self):
            super().__init__()
            self.exam_repository = repo
            self._history_dialog = None
            self.overlay_locked = False
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
            self.vertebra_label_mode_active = False

            # Checkpoint'in artık kullanılmayan üst menülerini kaldır; ana araç çubuğu korunur.
            menubar = self.menuBar()
            for action in list(menubar.actions()):
                menu = action.menu()
                if menu is not None and action.text() in {"File", "View", "Tools", "Help"}:
                    menubar.removeAction(action)

            # Günlük kullanımda yalnızca takip, görünüm ve yardım menüleri gösterilir.
            patient_menu = menubar.addMenu("Hasta Takibi")
            overlay_menu = menubar.addMenu("Görünüm")
            help_menu = menubar.addMenu("Help")

            patient_card_action = patient_menu.addAction("Hasta Kartı")
            patient_card_action.triggered.connect(self.show_patient_card)
            history_action = patient_menu.addAction("Tetkik Geçmişi")
            history_action.triggered.connect(self.show_exam_history)
            follow_up_action = patient_menu.addAction("Hasta Takip Özeti")
            follow_up_action.triggered.connect(self.show_follow_up_summary)
            cobb_history_action = patient_menu.addAction("Cobb Ölçüm Geçmişi")
            cobb_history_action.triggered.connect(self.show_cobb_history)
            cobb_trend_action = patient_menu.addAction("Cobb Trend Grafiği")
            cobb_trend_action.triggered.connect(self.show_cobb_trend)
            patient_list_action = patient_menu.addAction("Hasta Listesi ve Arama")
            patient_list_action.triggered.connect(self.show_patient_manager)
            alerts_action = patient_menu.addAction("Takip Uyarıları")
            alerts_action.triggered.connect(self.show_follow_up_alerts)
            pacs_action = patient_menu.addAction("PACS Sorgula / Al / Gönder")
            pacs_action.triggered.connect(self.show_pacs)
            patient_menu.addSeparator()

            report_action = patient_menu.addAction("Takip Raporunu PDF Olarak Dışa Aktar")
            report_action.triggered.connect(self.export_follow_up_pdf)
            audit_action = patient_menu.addAction("İşlem Geçmişi")
            audit_action.triggered.connect(self.show_audit_history)
            quality_action = patient_menu.addAction("Veri Kalite Kontrolü")
            quality_action.triggered.connect(self.show_quality_checks)
            users_action = patient_menu.addAction("Yerel Kullanıcı ve Roller")
            users_action.triggered.connect(self.show_user_manager)
            patient_menu.addSeparator()
            backup_action = patient_menu.addAction("Şifreli Veritabanı Yedeği Oluştur")
            backup_action.triggered.connect(self.backup_database)
            restore_action = patient_menu.addAction("Şifreli Veritabanı Yedeğini Geri Yükle")
            restore_action.triggered.connect(self.restore_database)

            save_overlay_action = overlay_menu.addAction("Overlay Oturumunu Kaydet")
            save_overlay_action.triggered.connect(self.save_overlay_session)
            open_overlay_action = overlay_menu.addAction("Kayıtlı Overlay Oturumları")
            open_overlay_action.triggered.connect(self.show_comparison_sessions)
            score_action = overlay_menu.addAction("Teknik Uyum Skorunu Hesapla")
            score_action.triggered.connect(self.show_alignment_score)
            export_dicom_action = overlay_menu.addAction("Overlay'i Secondary Capture DICOM Olarak Dışa Aktar")
            export_dicom_action.triggered.connect(self.export_overlay_secondary_capture)
            blink_action = overlay_menu.addAction("Blink Modu Aç/Kapat")
            blink_action.triggered.connect(self.toggle_blink_mode)
            lock_action = overlay_menu.addAction("Hizalamayı Kilitle/Aç")
            lock_action.triggered.connect(self.toggle_overlay_lock)
            sync_action = overlay_menu.addAction("Yan Yana Senkron Görünüm Aç/Kapat")
            sync_action.triggered.connect(self.toggle_sync_views)
            overlay_menu.addSeparator()
            label_mode_action = overlay_menu.addAction("Omur Etiketleme Modu Aç/Kapat")
            label_mode_action.triggered.connect(self.toggle_vertebra_label_mode)
            labels_action = overlay_menu.addAction("Omur Etiketlerini Yönet")
            labels_action.triggered.connect(self.show_vertebra_labels)

            help_menu.addAction("Lisans Durumunu Kontrol Et", self.check_license_status)
            help_menu.addAction("Lisans Yönetimi", self.show_license_manager)
            help_menu.addAction("Güncellemeleri Denetle", self.check_for_updates)
            help_menu.addAction("Tanı Paketini Dışa Aktar", self.export_diagnostic_bundle)
            help_menu.addAction("Hata Günlüğü Konumu", self.show_log_location)
            help_menu.addAction("Hakkında", self.show_about)

            self._sync_loaded_exams_to_database()

        def check_license_status(self):
            """Lisans durumunu denetler ve 6 saatlik çevrimdışı kuralı uygular."""
            result = evaluate_license_gate(self.exam_repository)
            expiry = result.expires_at or "Tanımlı değil"
            message = f"{result.message}\n\nLisans son kullanım tarihi: {expiry}"
            if result.allowed:
                QMessageBox.information(self, "Lisans kontrolü", message)
            else:
                QMessageBox.warning(self, "Lisans kontrolü", message)

        def show_license_manager(self):
            LicenseDialog(self.exam_repository, self).exec()

        def check_for_updates(self):
            current_url = self.exam_repository.get_setting("updates/feed_url", "")
            url, accepted = QInputDialog.getText(
                self,
                "Güncelleme denetimi",
                "Sürüm JSON adresi (isteğe bağlı):",
                text=current_url,
            )
            if not accepted:
                return
            self.exam_repository.set_setting("updates/feed_url", url.strip())
            available, message = check_for_update(url, APP_VERSION)
            QMessageBox.information(self, "Güncelleme denetimi", message if not available else message + "\n\nİndirme işlemi kullanıcı tarafından başlatılmalıdır.")

        def show_log_location(self):
            log_path = Path(DB_PATH).parent / "logs" / "application.log"
            QMessageBox.information(self, "Hata günlüğü", f"Uygulama hata günlüğü:\n{log_path}\n\nKişisel hasta verilerini paylaşmadan önce günlüğü kontrol edin.")

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
                    f"Tanı paketi oluşturuldu:\n{bundle}\n\nDICOM, veritabanı ve hasta görüntüleri pakete eklenmez.",
                )
            except Exception as exc:
                QMessageBox.warning(self, "Tanı paketi", f"Tanı paketi oluşturulamadı:\n{exc}")

        def _require_role(self, roles: set[str], action_name: str) -> bool:
            if self.current_user_role in roles:
                return True
            QMessageBox.warning(self, "Yetki gerekli", f"{action_name} için {', '.join(sorted(roles))} rolü gerekir.\nAktif rol: {self.current_user_role}")
            return False

        def show_user_manager(self):
            dialog = UserManagerDialog(self.exam_repository, self.current_user_name, self)
            dialog.active_user_selected.connect(self._set_active_user)
            dialog.exec()

        def _set_active_user(self, user):
            self.current_user_name = str(user.get("display_name", "Yerel Yönetici"))
            self.current_user_role = str(user.get("role", "Teknisyen"))
            self.exam_repository.set_setting("active_user_name", self.current_user_name)
            self.exam_repository.set_setting("active_user_role", self.current_user_role)
            self.statusBar().showMessage(f"Aktif yerel kullanıcı: {self.current_user_name} ({self.current_user_role})")

        def show_patient_card(self):
            patient = self._current_patient()
            if not patient:
                QMessageBox.information(self, "Hasta kartı", "Önce bir DICOM/görüntü seçin.")
                return
            PatientCardDialog(
                self.exam_repository, patient["patient_id"], patient.get("patient_name", ""), self.current_user_name, self
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
                QMessageBox.warning(self, "DICOM kalite uyarısı", "\n".join(warnings[:5]) + ("\n…" if len(warnings) > 5 else ""))

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
                overlay_rotation=0.0,
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
            dataset.is_little_endian = True
            dataset.is_implicit_VR = False
            dataset.save_as(str(output_path), write_like_original=False)

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

        def show_pacs(self):
            dialog = PacsDialog(self)
            dialog.files_retrieved.connect(self._import_pacs_files)
            dialog.exec()

        def _import_pacs_files(self, paths):
            imported = []
            for path in paths:
                if path and os.path.isfile(path) and self._add_path_to_study_list(path) is not None:
                    imported.append(path)
            self._register_paths(imported)
            if imported:
                self.statusBar().showMessage(f"PACS'ten {len(imported)} DICOM uygulamaya eklendi.")

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

        def backup_database(self):
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
                self.statusBar().showMessage("Şifreli veritabanı yedeği oluşturuldu.")
                QMessageBox.information(self, "Şifreli yedek", f"Yedek kaydedildi:\n{output}\n\nParolayı kaybederseniz bu yedek geri getirilemez.")
            except BackupError as exc:
                QMessageBox.warning(self, "Şifreli yedek", str(exc))
            except Exception as exc:
                QMessageBox.warning(self, "Şifreli yedek", f"Yedek oluşturulamadı:\n{exc}")

        def restore_database(self):
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

        def update_viewers(self):
            super().update_viewers()
            # Checkpoint sahneleri yeniden kurduktan sonra kalıcı yerel omur
            # etiketlerini tekrar çiz. Etiketler kaynak DICOM'a yazılmaz.
            QTimer.singleShot(0, self._render_vertebra_labels)

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
            mapping = [("left", getattr(self, "scene_left", None), 0)]
            if getattr(self, "current_mode", "") == "side_by_side":
                mapping.append(("right", getattr(self, "scene_right", None), 1))
            for _side, scene, _index in mapping:
                if scene is not None:
                    for item in list(scene.items()):
                        if item.data(0) == "vertebra_label":
                            scene.removeItem(item)
            for _side, scene, index in mapping:
                if scene is None or len(paths) <= index:
                    continue
                try:
                    metadata = read_exam_metadata(paths[index])
                    labels = self.exam_repository.list_vertebra_labels(metadata["patient_id"], paths[index])
                except Exception:
                    continue
                for label in labels:
                    marker = scene.addEllipse(float(label["x"]) - 4, float(label["y"]) - 4, 8, 8)
                    marker.setPen(QPen(Qt.GlobalColor.yellow, 2))
                    marker.setData(0, "vertebra_label")
                    text = scene.addText(str(label["vertebra"]))
                    text.setDefaultTextColor(Qt.GlobalColor.yellow)
                    text.setPos(float(label["x"]) + 6, float(label["y"]) - 12)
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
            if should_record:
                v1 = (points[1].x() - points[0].x(), points[1].y() - points[0].y())
                v2 = (pos.x() - points[2].x(), pos.y() - points[2].y())
                magnitude = (v1[0] ** 2 + v1[1] ** 2) ** 0.5 * (v2[0] ** 2 + v2[1] ** 2) ** 0.5
                if magnitude > 0:
                    import math
                    cosine = max(-1.0, min(1.0, (v1[0] * v2[0] + v1[1] * v2[1]) / magnitude))
                    angle = math.degrees(math.acos(cosine))

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
                )
                self.exam_repository.record_audit_event(metadata["patient_id"], "cobb_measurement_saved", f"Kayıt #{measurement_id}; {angle:.2f} derece")
                self.statusBar().showMessage(f"Cobb açısı kaydedildi: {angle:.2f}° (Kayıt #{measurement_id}).")
            except Exception:
                # The checkpoint has already displayed the measurement; a history error must not affect it.
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


def main(checkpoint_class=None):
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    integrity = verify_distribution_integrity()
    if not integrity.allowed:
        QMessageBox.critical(
            None,
            "Uygulama bütünlüğü doğrulanamadı",
            integrity.message + "\n\nUygulamayı resmi kurulum paketiyle yeniden yükleyin.",
        )
        return 3

    configure_logging(DB_PATH.parent)

    # main.py'deki açılış banner'ını modüler başlatıcıda da koru. Önce splash
    # gösterilir; checkpoint ve modüller yüklenirken kullanıcı boş pencere
    # yerine uygulamanın açıldığını görür.
    splash = None
    logo_path = PROJECT_ROOT / "logo.png"
    if logo_path.is_file():
        pixmap = QPixmap(str(logo_path))
        if not pixmap.isNull():
            splash = QSplashScreen(pixmap, Qt.WindowStaysOnTopHint)
            splash.showMessage(
                "Scoliosis Follow-Up Yükleniyor…",
                Qt.AlignBottom | Qt.AlignHCenter,
                Qt.white,
            )
            splash.show()
            app.processEvents()

    # main.py doğrudan çalıştırıldığında sınıf zaten yüklenmiştir; yeniden
    # import etmeyerek açılışı hızlandırırız. run_modular.py tek başına
    # çalıştırıldığında ise eski uyumlu checkpoint yükleme yolu korunur.
    if checkpoint_class is None:
        checkpoint = load_checkpoint()
        checkpoint_class = checkpoint.ScoliosisFollowUpApp
    AppClass = install_modules(checkpoint_class)
    window = AppClass()

    # Lisans denetimi her açılışta zorunludur. Geçerli bir çevrimiçi
    # doğrulama yoksa uygulama yalnızca 6 saatlik yerel süre içinde açılır.
    license_gate = evaluate_license_gate(window.exam_repository)
    if not license_gate.allowed:
        if splash is not None:
            splash.hide()
        dialog = LicenseDialog(window.exam_repository, window, startup_message=license_gate.message)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        # Aktivasyon veya 'Doğrula ve Başlat' sonrasında süre/etkinlik
        # mutlaka yeniden değerlendirilir; arada ağ kesildiyse uygulama
        # yalnızca tanımlı altı saatlik sınır içinde açılabilir.
        license_gate = evaluate_license_gate(window.exam_repository)
        if not license_gate.allowed:
            QMessageBox.warning(window, "Lisans", license_gate.message)
            return
        if splash is not None:
            splash.show()

    if license_gate.mode != "licensed":
        window.statusBar().showMessage(license_gate.message, 15000)
    schedule_runtime_license_check(app, window, license_gate)

    if splash is not None:
        QTimer.singleShot(1500, lambda: (splash.finish(window), window.show()))
    else:
        window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

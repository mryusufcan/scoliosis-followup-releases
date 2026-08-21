from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QComboBox, QDialog, QDialogButtonBox, QLabel, QMessageBox, QPushButton, QVBoxLayout


class AILandmarkAssistantDialog(QDialog):
    """Explicit opt-in dialog for an unpersisted experimental 68-landmark overlay."""

    draft_requested = Signal(object)
    cobb_draft_requested = Signal(object)

    def __init__(self, model, dicom_path: str, parent=None):
        super().__init__(parent)
        self.model = model
        self.dicom_path = str(dicom_path or "")
        self.suggestion = None
        self.landmarks_shown = False
        self.setWindowTitle("Deneysel AI 68-Landmark Taslağı")
        self.setMinimumWidth(590)
        root = QVBoxLayout(self)
        title = QLabel("<b>DENEYSEL — 17 vertebra / 68 landmark taslağı</b>")
        title.setStyleSheet("font-size: 15px;")
        root.addWidget(title)
        warning = QLabel(
            "Bu araç görüntüyü internet veya sunucuya göndermeden yerel teknik taslak üretir. "
            "Tanı koymaz ve hiçbir ölçümü otomatik kaydetmez. AI Cobb önerisi yalnızca görüntü üzerinde "
            "manuel doğrulama için gösterilir."
        )
        warning.setWordWrap(True)
        warning.setStyleSheet("color: #f1c40f; padding: 9px; background: #3b3420; border-radius: 4px;")
        root.addWidget(warning)
        self.status_label = QLabel()
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("color: #f5f7fa; padding: 10px; background: #242424; border: 1px solid #444;")
        root.addWidget(self.status_label)
        view_label = QLabel("DICOM yön bilgisi eksikse görüntü yönünü doğrulayın:")
        root.addWidget(view_label)
        self.view_combo = QComboBox()
        self.view_combo.setObjectName("ai_landmark_view_confirmation")
        self.view_combo.addItem("DICOM metadata bilgisini kullan", "")
        self.view_combo.addItem("AP — kullanıcı doğrulaması", "AP")
        self.view_combo.addItem("PA — kullanıcı doğrulaması", "PA")
        self.view_combo.setToolTip("Yalnızca DICOM ViewPosition alanı boşsa AP veya PA seçin; kaynak dosya değiştirilmez.")
        root.addWidget(self.view_combo)
        self.analyze_button = QPushButton("Yerel Analizi Başlat")
        self.analyze_button.setObjectName("run_ai_landmark_draft_button")
        self.analyze_button.clicked.connect(self._run)
        root.addWidget(self.analyze_button)
        self.show_button = QPushButton("Taslağı Görüntüye Aktar (Kaydetmez)")
        self.show_button.setObjectName("show_ai_landmark_draft_button")
        self.show_button.setEnabled(False)
        self.show_button.clicked.connect(self._show)
        root.addWidget(self.show_button)
        self.cobb_button = QPushButton("Deneysel Cobb Taslağını Öner (Kaydetmez)")
        self.cobb_button.setObjectName("propose_ai_landmark_cobb_button")
        self.cobb_button.setEnabled(False)
        self.cobb_button.clicked.connect(self._propose_cobb)
        root.addWidget(self.cobb_button)
        close_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close_box.rejected.connect(self.reject)
        root.addWidget(close_box)
        self._refresh()

    def _refresh(self):
        status = self.model.inspect()
        path_text = self.dicom_path if self.dicom_path else "Tek kareli bir DICOM seçilmemiş."
        self.status_label.setText(f"<b>Durum:</b> {status.code}<br><b>Açıklama:</b> {status.message}<br><b>Görüntü:</b> {path_text}")
        self.analyze_button.setEnabled(bool(status.ready and self.dicom_path))
        if not status.ready:
            self.analyze_button.setToolTip("Yerel analiz kapalı: " + status.message)
        elif not self.dicom_path:
            self.analyze_button.setToolTip("Yerel analiz kapalı: Aktif tek kareli DICOM görüntüsü seçin.")
        else:
            self.analyze_button.setToolTip("Yerel analiz hazır: DICOM bilgisayar dışına gönderilmez.")

    def _run(self):
        try:
            suggestion = self.model.analyze_dicom(
                self.dicom_path,
                confirmed_view=str(self.view_combo.currentData() or ""),
            )
        except Exception as exc:
            QMessageBox.warning(self, "Deneysel landmark taslağı", str(exc))
            return
        if not suggestion.usable:
            QMessageBox.warning(
                self,
                "Görüntü AI landmark analizi için uygun değil",
                suggestion.warning or "Landmark taslağı kalite kapısından geçmedi.",
            )
            return
        self.suggestion = suggestion
        self.landmarks_shown = False
        self.cobb_button.setEnabled(False)
        self.show_button.setEnabled(True)
        self.status_label.setText(
            f"<b>Teknik taslak hazır:</b> 68 landmark, 17 vertebra adayı.<br>"
            f"<b>Güven aralığı:</b> {min(suggestion.confidences):.1%}–{max(suggestion.confidences):.1%}<br>"
            f"<b>Yön doğrulaması:</b> {suggestion.confirmed_view or ('DICOM metadata' if suggestion.safety_status == 'eligible' else 'Eksik — taslak kaydedilemez')}<br>"
            + (f"<b>Uyarı:</b> {suggestion.warning}<br>" if suggestion.warning else "")
            + "Ölçüm kaydedilmez; yalnızca görüntü üzerinde incelenebilir."
        )

    def _show(self):
        if self.suggestion is not None:
            self.draft_requested.emit(self.suggestion)
            self.landmarks_shown = True
            self.cobb_button.setEnabled(bool(self.suggestion.cobb_eligible))
            if self.suggestion.warning:
                self.cobb_button.setToolTip("Düşük güvenli deneysel taslak; yalnızca görsel kontrol içindir ve kaydedilemez.")
            self.status_label.setText(self.status_label.text() + "<br><b>Overlay:</b> Landmark taslağı görüntüye aktarıldı; kayıt oluşturulmadı.")

    def _propose_cobb(self):
        if self.suggestion is None or not self.landmarks_shown:
            return
        try:
            draft = self.model.propose_cobb_draft(self.suggestion)
        except Exception as exc:
            QMessageBox.warning(self, "Deneysel Cobb taslağı", str(exc))
            return
        self.cobb_draft_requested.emit(draft)
        self.status_label.setText(
            self.status_label.text()
            + f"<br><b>Deneysel Cobb önerisi:</b> {draft.angle_degrees:.2f}°; "
            + "yalnızca görüntü üzerinde gösterildi, kaydedilmedi."
        )

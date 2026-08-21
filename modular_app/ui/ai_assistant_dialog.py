from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal, Slot, Qt
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from ai.model_runtime import AIModelError, CobbSuggestion, LocalCobbModel


class _AIAnalysisWorker(QObject):
    completed = Signal(object)
    failed = Signal(str)

    def __init__(self, model, dicom_path: str):
        super().__init__()
        self.model = model
        self.dicom_path = dicom_path

    @Slot()
    def run(self):
        try:
            self.completed.emit(self.model.analyze_dicom(self.dicom_path))
        except Exception as exc:
            self.failed.emit(str(exc))


class AICobbAssistantDialog(QDialog):
    """Local model status and opt-in Cobb draft workflow."""

    draft_requested = Signal(object)

    def __init__(self, model: LocalCobbModel, dicom_path: str = "", parent=None):
        super().__init__(parent)
        self.model = model
        self.dicom_path = str(dicom_path or "")
        self.suggestion: CobbSuggestion | None = None
        self._analysis_thread: QThread | None = None
        self._analysis_worker: _AIAnalysisWorker | None = None
        display_name = str(getattr(model, "display_name", "Yerel Yapay Zekâ Cobb Asistanı"))
        self.setWindowTitle(display_name + " — Deneysel")
        self.setMinimumWidth(560)

        root = QVBoxLayout(self)
        title = QLabel(f"<b>{display_name}</b>")
        title.setStyleSheet("font-size: 15px;")
        root.addWidget(title)

        warning = QLabel(str(getattr(model, "warning_text", (
            "Bu özellik tanı koymaz. Sonuç yalnızca doğrulanmamış taslaktır; "
            "klinik kullanım öncesinde uzman tarafından manuel olarak doğrulanmalıdır."
        ))))
        warning.setWordWrap(True)
        warning.setStyleSheet("color: #f1c40f; padding: 8px; background: #3b3420; border-radius: 4px;")
        root.addWidget(warning)

        self.file_label = QLabel()
        self.file_label.setWordWrap(True)
        root.addWidget(self.file_label)

        self.status_label = QLabel()
        self.status_label.setWordWrap(True)
        self.status_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        root.addWidget(self.status_label)

        self.result_label = QLabel("Henüz analiz yapılmadı.")
        self.result_label.setWordWrap(True)
        self.result_label.setStyleSheet("padding: 10px; background: #242424; border: 1px solid #444;")
        root.addWidget(self.result_label)

        action_row = QHBoxLayout()
        self.analyze_button = QPushButton("Yerel Analizi Çalıştır")
        self.analyze_button.clicked.connect(self.run_analysis)
        action_row.addWidget(self.analyze_button)
        self.apply_button = QPushButton("Taslağı Görüntüye Aktar")
        self.apply_button.setEnabled(False)
        self.apply_button.clicked.connect(self.emit_draft)
        action_row.addWidget(self.apply_button)
        root.addLayout(action_row)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)
        self.refresh_status()

    def refresh_status(self):
        status = self.model.inspect()
        self.file_label.setText(
            f"<b>Aktif görüntü:</b> {Path(self.dicom_path).name}"
            if self.dicom_path
            else "<b>Aktif görüntü:</b> Seçilmedi"
        )
        details = [f"<b>Model durumu:</b> {status.message}"]
        if status.model_version:
            details.append(f"<b>Model sürümü:</b> {status.model_version}")
        if status.sha256:
            details.append(f"<b>Model özeti:</b> {status.sha256[:16]}…")
        if status.package is not None and status.package.is_v2:
            details.append(f"<b>Kaynak depo:</b> {status.package.source_repository}")
            details.append(f"<b>Kod / ağırlık lisansı:</b> {status.package.source_license} / {status.package.weights_license}")
        elif getattr(self.model, "source_repository", ""):
            details.append(f"<b>Kaynak depo:</b> {self.model.source_repository}")
            details.append(f"<b>Kod lisansı:</b> {getattr(self.model, 'source_license', 'Belirtilmedi')}")
        details.append("<b>Çalışma biçimi:</b> Tamamen yerel / çevrimdışı")
        self.status_label.setText("<br>".join(details))
        self.analyze_button.setEnabled(bool(status.ready and self.dicom_path))

    def run_analysis(self):
        if not self.dicom_path:
            QMessageBox.information(self, "AI Cobb", "Önce bir DICOM görüntüsü açın.")
            return
        if self._analysis_thread is not None:
            return
        self.suggestion = None
        self.analyze_button.setEnabled(False)
        self.analyze_button.setText("Analiz sürüyor…")
        self.apply_button.setEnabled(False)
        self.result_label.setText(
            "<b>Yerel AI analizi sürüyor.</b><br>Pencereyi kullanmaya devam edebilirsiniz; "
            "ilk çalıştırma 30–90 saniye sürebilir."
        )
        thread = QThread(self)
        worker = _AIAnalysisWorker(self.model, self.dicom_path)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.completed.connect(self._analysis_completed)
        worker.failed.connect(self._analysis_failed)
        worker.completed.connect(thread.quit)
        worker.failed.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._analysis_thread_finished)
        self._analysis_thread = thread
        self._analysis_worker = worker
        thread.start()

    @Slot(object)
    def _analysis_completed(self, suggestion):
        self.suggestion = suggestion
        confidence_text = f"{suggestion.confidence:.1%}"
        result = (
            f"<b>AI taslak Cobb açısı:</b> {suggestion.angle_degrees:.2f}°<br>"
            f"<b>Ortalama model güveni:</b> {confidence_text}<br>"
            f"<b>Teknik güvenlik durumu:</b> {suggestion.safety_status}<br>"
            f"<b>Durum:</b> {'Taslak aktarılabilir; uzman görsel doğrulaması zorunludur.' if suggestion.usable else suggestion.warning}"
        )
        self.result_label.setText(result)
        self.apply_button.setEnabled(bool(suggestion.usable))

    @Slot(str)
    def _analysis_failed(self, message: str):
        self.suggestion = None
        self.apply_button.setEnabled(False)
        self.result_label.setText("Analiz tamamlanamadı. Yerel model dosyasını ve çalışma bileşenlerini kontrol edin.")
        QMessageBox.warning(self, "AI analizi tamamlanamadı", message)

    @Slot()
    def _analysis_thread_finished(self):
        self._analysis_thread = None
        self._analysis_worker = None
        self.analyze_button.setText("Yerel Analizi Çalıştır")
        self.analyze_button.setEnabled(bool(self.dicom_path and self.model.inspect().ready))

    def reject(self):
        if self._analysis_thread is not None:
            QMessageBox.information(self, "AI analizi sürüyor", "Analiz tamamlanana kadar bu pencereyi açık bırakın.")
            return
        super().reject()

    def closeEvent(self, event):
        if self._analysis_thread is not None:
            event.ignore()
            QMessageBox.information(self, "AI analizi sürüyor", "Analiz tamamlanana kadar bu pencereyi açık bırakın.")
            return
        super().closeEvent(event)

    def emit_draft(self):
        if self.suggestion is None or not self.suggestion.usable:
            return
        self.draft_requested.emit(self.suggestion)
        self.accept()

from pathlib import Path
from typing import Any, Callable

from PySide6.QtCore import QSettings, QThreadPool, Signal
from PySide6.QtWidgets import (
    QDialog, QFileDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QMessageBox,
    QPushButton, QSpinBox, QTableWidget, QTableWidgetItem, QVBoxLayout,
)

from modular_app.ui.background_task import FunctionTask
from pacs.client import PacsConfig, PacsError, query_studies, retrieve_study, send_dicom, test_connection


class PacsDialog(QDialog):
    """Explicit, user-configured PACS query/retrieve/send window."""

    files_retrieved = Signal(list)
    dicom_sent = Signal(str)

    def __init__(self, parent=None, *, allow_send: bool = True):
        super().__init__(parent)
        self.rows: list[dict[str, str]] = []
        self.settings = QSettings("ScoliosisFollowUp", "ScoliosisFollowUp")
        self._thread_pool = QThreadPool(self)
        self._thread_pool.setMaxThreadCount(1)
        self._active_task: FunctionTask | None = None
        self._busy = False
        self._allow_send = bool(allow_send)

        self.setWindowTitle("PACS Bağlantısı")
        self.resize(920, 560)
        self.setStyleSheet("background:#242424;color:#ecf0f1;")
        root = QVBoxLayout(self)
        note = QLabel("Ayarlar yalnızca bu Windows kullanıcısının profilinde saklanır.")
        note.setStyleSheet("color:#95a5a6;")
        root.addWidget(note)
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color:#36C5D8;")
        root.addWidget(self.status_label)
        form = QFormLayout()
        self.host = QLineEdit(self.settings.value("pacs/host", ""))
        self.port = QSpinBox()
        self.port.setRange(1, 65535)
        self.port.setValue(int(self.settings.value("pacs/port", 104)))
        self.called = QLineEdit(self.settings.value("pacs/called_ae", ""))
        self.calling = QLineEdit(self.settings.value("pacs/calling_ae", "SCOLIOSIS_APP"))
        self.patient_id = QLineEdit()
        self.patient_id.setPlaceholderText("Hasta ID (isteğe bağlı)")
        self.patient_name = QLineEdit()
        self.patient_name.setPlaceholderText("Hasta adı (isteğe bağlı)")
        self.study_date = QLineEdit()
        self.study_date.setPlaceholderText("YYYYMMDD veya tarih aralığı (isteğe bağlı)")
        for label, widget in (
            ("PACS IP / sunucu", self.host),
            ("Port", self.port),
            ("Called AE Title", self.called),
            ("Calling AE Title", self.calling),
            ("Hasta ID", self.patient_id),
            ("Hasta adı", self.patient_name),
            ("Tetkik tarihi", self.study_date),
        ):
            form.addRow(label, widget)
        root.addLayout(form)

        connection_button = QPushButton("Bağlantıyı Test Et")
        connection_button.clicked.connect(self.test_connection)
        query_button = QPushButton("Tetkikleri Sorgula")
        query_button.clicked.connect(self.query)
        top_buttons = QHBoxLayout()
        top_buttons.addWidget(connection_button)
        top_buttons.addWidget(query_button)
        top_buttons.addStretch()
        root.addLayout(top_buttons)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Hasta ID", "Hasta adı", "Tarih", "Açıklama", "Modalite", "Study UID"])
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        root.addWidget(self.table, 1)

        retrieve_button = QPushButton("Seçili Tetkiki Al (C-GET)")
        retrieve_button.clicked.connect(self.retrieve)
        send_button = QPushButton("DICOM Gönder (C-STORE)")
        send_button.clicked.connect(self.send)
        send_button.setEnabled(bool(allow_send))
        if not allow_send:
            send_button.setToolTip("DICOM gönderimi için Hekim veya Yönetici rolü gerekir.")
        buttons = QHBoxLayout()
        buttons.addStretch()
        buttons.addWidget(retrieve_button)
        buttons.addWidget(send_button)
        root.addLayout(buttons)

        self._action_buttons = [connection_button, query_button, retrieve_button, send_button]
        self._input_widgets = [self.host, self.port, self.called, self.calling, self.patient_id, self.patient_name, self.study_date]

    def config(self) -> PacsConfig:
        host = self.host.text().strip()
        called = self.called.text().strip()
        calling = self.calling.text().strip()
        if not host or not called or not calling:
            raise PacsError("PACS IP/sunucu, Called AE Title ve Calling AE Title zorunludur.")
        self.settings.setValue("pacs/host", host)
        self.settings.setValue("pacs/port", self.port.value())
        self.settings.setValue("pacs/called_ae", called)
        self.settings.setValue("pacs/calling_ae", calling)
        return PacsConfig(
            host=host,
            port=self.port.value(),
            called_ae_title=called,
            calling_ae_title=calling,
        )

    def _set_busy(self, busy: bool, message: str = "") -> None:
        self._busy = bool(busy)
        for widget in self._action_buttons:
            widget.setEnabled(not self._busy)
        # Send remains disabled for roles that are not allowed to transmit.
        if self._action_buttons:
            self._action_buttons[-1].setEnabled(not self._busy and self._allow_send)
        for widget in self._input_widgets:
            widget.setEnabled(not self._busy)
        self.status_label.setText(message)

    def _run_async(self, function: Callable[[], Any], on_success: Callable[[Any], None], title: str) -> None:
        if self._busy:
            self.status_label.setText("Önce devam eden PACS işleminin tamamlanmasını bekleyin.")
            return
        self._set_busy(True, f"{title} arka planda çalışıyor…")
        task = FunctionTask(function)
        self._active_task = task

        def finish(value: Any) -> None:
            self._active_task = None
            self._set_busy(False, "")
            on_success(value)

        def fail(error: object) -> None:
            self._active_task = None
            self._set_busy(False, "")
            if isinstance(error, PacsError):
                message = str(error)
            else:
                message = str(error) or error.__class__.__name__
            QMessageBox.warning(self, "PACS işlemi", f"{title} tamamlanamadı:\n{message}")

        task.signals.finished.connect(finish)
        task.signals.failed.connect(fail)
        self._thread_pool.start(task)

    def test_connection(self):
        try:
            config = self.config()
        except PacsError as exc:
            QMessageBox.warning(self, "PACS bağlantısı", str(exc))
            return
        self._run_async(
            lambda: test_connection(config),
            lambda _result: self._show_success("PACS bağlantısı", "DICOM bağlantısı ve AE Title doğrulandı."),
            "Bağlantı testi",
        )

    def query(self):
        try:
            config = self.config()
        except PacsError as exc:
            QMessageBox.warning(self, "PACS sorgusu", str(exc))
            return
        patient_id = self.patient_id.text().strip()
        patient_name = self.patient_name.text().strip()
        study_date = self.study_date.text().strip()
        self._run_async(
            lambda: query_studies(config, patient_id, patient_name, study_date),
            self._apply_query_result,
            "PACS sorgusu",
        )

    def _apply_query_result(self, rows: Any) -> None:
        self.rows = list(rows or [])
        self.table.setRowCount(len(self.rows))
        fields = ("PatientID", "PatientName", "StudyDate", "StudyDescription", "ModalitiesInStudy", "StudyInstanceUID")
        for row_index, row in enumerate(self.rows):
            for column, field in enumerate(fields):
                self.table.setItem(row_index, column, QTableWidgetItem(str(row.get(field, ""))))
        self._show_success("PACS", f"{len(self.rows)} tetkik bulundu.")

    def retrieve(self):
        index = self.table.currentRow()
        if not 0 <= index < len(self.rows):
            QMessageBox.information(self, "PACS", "Önce bir tetkik seçin.")
            return
        destination = QFileDialog.getExistingDirectory(self, "Alınan DICOM klasörü")
        if not destination:
            return
        try:
            config = self.config()
        except PacsError as exc:
            QMessageBox.warning(self, "PACS alma", str(exc))
            return
        study_uid = self.rows[index].get("StudyInstanceUID", "")
        self._run_async(
            lambda: retrieve_study(config, study_uid, destination),
            self._apply_retrieve_result,
            "PACS tetkik alma",
        )

    def _apply_retrieve_result(self, files: Any) -> None:
        paths = [str(path) for path in (files or [])]
        self.files_retrieved.emit(paths)
        self._show_success("PACS", f"{len(paths)} DICOM alındı.")

    def send(self):
        path, _ = QFileDialog.getOpenFileName(self, "Gönderilecek DICOM", "", "DICOM (*.dcm);;Tüm dosyalar (*.*)")
        if not path:
            return
        try:
            config = self.config()
        except PacsError as exc:
            QMessageBox.warning(self, "PACS gönderme", str(exc))
            return
        self._run_async(
            lambda: send_dicom(config, path),
            lambda _result, sent_path=path: self._apply_send_result(sent_path),
            "PACS DICOM gönderme",
        )

    def _apply_send_result(self, path: str) -> None:
        self.dicom_sent.emit(path)
        self._show_success("PACS", "DICOM başarıyla gönderildi.")

    def _show_success(self, title: str, message: str) -> None:
        self.status_label.setText(message)
        QMessageBox.information(self, title, message)

    def closeEvent(self, event) -> None:
        if self._busy:
            QMessageBox.information(self, "PACS işlemi sürüyor", "PACS işlemi tamamlanana kadar bu pencere kapatılamaz.")
            event.ignore()
            return
        self._thread_pool.clear()
        event.accept()

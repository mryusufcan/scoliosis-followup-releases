from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings, Signal
from PySide6.QtWidgets import (
    QDialog, QFileDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QMessageBox,
    QPushButton, QSpinBox, QTableWidget, QTableWidgetItem, QVBoxLayout,
)

from pacs.client import PacsConfig, PacsError, query_studies, retrieve_study, send_dicom, test_connection


class PacsDialog(QDialog):
    """Explicit, user-configured PACS query/retrieve/send window."""
    files_retrieved = Signal(list)
    dicom_sent = Signal(str)

    def __init__(self, parent=None, *, allow_send: bool = True):
        super().__init__(parent)
        self.rows: list[dict[str, str]] = []
        self.settings = QSettings("ScoliosisFollowUp", "ScoliosisFollowUp")
        self.setWindowTitle("PACS Bağlantısı")
        self.resize(920, 560)
        self.setStyleSheet("background:#242424;color:#ecf0f1;")
        root = QVBoxLayout(self)
        note = QLabel("Ayarlar yalnızca bu Windows kullanıcısının profilinde saklanır.")
        note.setStyleSheet("color:#95a5a6;")
        root.addWidget(note)
        form = QFormLayout()
        self.host = QLineEdit(self.settings.value("pacs/host", ""))
        self.port = QSpinBox(); self.port.setRange(1, 65535); self.port.setValue(int(self.settings.value("pacs/port", 104)))
        self.called = QLineEdit(self.settings.value("pacs/called_ae", ""))
        self.calling = QLineEdit(self.settings.value("pacs/calling_ae", "SCOLIOSIS_APP"))
        self.patient_id = QLineEdit(); self.patient_id.setPlaceholderText("Hasta ID (isteğe bağlı)")
        self.patient_name = QLineEdit(); self.patient_name.setPlaceholderText("Hasta adı (isteğe bağlı)")
        self.study_date = QLineEdit(); self.study_date.setPlaceholderText("YYYYMMDD veya tarih aralığı (isteğe bağlı)")
        for label, widget in (("PACS IP / sunucu", self.host), ("Port", self.port), ("Called AE Title", self.called), ("Calling AE Title", self.calling), ("Hasta ID", self.patient_id), ("Hasta adı", self.patient_name), ("Tetkik tarihi", self.study_date)):
            form.addRow(label, widget)
        root.addLayout(form)
        query_button = QPushButton("Tetkikleri Sorgula")
        query_button.clicked.connect(self.query)
        connection_button = QPushButton("Bağlantıyı Test Et")
        connection_button.clicked.connect(self.test_connection)
        top_buttons = QHBoxLayout(); top_buttons.addWidget(connection_button); top_buttons.addWidget(query_button); top_buttons.addStretch()
        root.addLayout(top_buttons)
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Hasta ID", "Hasta adı", "Tarih", "Açıklama", "Modalite", "Study UID"])
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        root.addWidget(self.table, 1)
        buttons = QHBoxLayout()
        retrieve_button = QPushButton("Seçili Tetkiki Al (C-GET)")
        retrieve_button.clicked.connect(self.retrieve)
        send_button = QPushButton("DICOM Gönder (C-STORE)")
        send_button.clicked.connect(self.send)
        send_button.setEnabled(bool(allow_send))
        if not allow_send:
            send_button.setToolTip("DICOM gönderimi için Hekim veya Yönetici rolü gerekir.")
        buttons.addStretch(); buttons.addWidget(retrieve_button); buttons.addWidget(send_button)
        root.addLayout(buttons)

    def config(self) -> PacsConfig:
        host, called, calling = self.host.text().strip(), self.called.text().strip(), self.calling.text().strip()
        if not host or not called or not calling:
            raise PacsError("PACS IP/sunucu, Called AE Title ve Calling AE Title zorunludur.")
        self.settings.setValue("pacs/host", host); self.settings.setValue("pacs/port", self.port.value())
        self.settings.setValue("pacs/called_ae", called); self.settings.setValue("pacs/calling_ae", calling)
        return PacsConfig(host=host, port=self.port.value(), called_ae_title=called, calling_ae_title=calling)

    def test_connection(self):
        try:
            test_connection(self.config())
            QMessageBox.information(self, "PACS bağlantısı", "DICOM bağlantısı ve AE Title doğrulandı.")
        except PacsError as exc:
            QMessageBox.warning(self, "PACS bağlantısı", str(exc))
        except Exception as exc:
            QMessageBox.warning(self, "PACS bağlantısı", f"Bağlantı denetlenemedi:\n{exc}")

    def query(self):
        try:
            self.rows = query_studies(self.config(), self.patient_id.text().strip(), self.patient_name.text().strip(), self.study_date.text().strip())
            self.table.setRowCount(0)
            for index, row in enumerate(self.rows):
                self.table.insertRow(index)
                for column, field in enumerate(("PatientID", "PatientName", "StudyDate", "StudyDescription", "ModalitiesInStudy", "StudyInstanceUID")):
                    self.table.setItem(index, column, QTableWidgetItem(row.get(field, "")))
            QMessageBox.information(self, "PACS", f"{len(self.rows)} tetkik bulundu.")
        except PacsError as exc:
            QMessageBox.warning(self, "PACS sorgusu", str(exc))
        except Exception as exc:
            QMessageBox.warning(self, "PACS sorgusu", f"Sorgu tamamlanamadı:\n{exc}")

    def retrieve(self):
        index = self.table.currentRow()
        if not 0 <= index < len(self.rows):
            QMessageBox.information(self, "PACS", "Önce bir tetkik seçin.")
            return
        destination = QFileDialog.getExistingDirectory(self, "Alınan DICOM klasörü")
        if not destination:
            return
        try:
            files = retrieve_study(self.config(), self.rows[index]["StudyInstanceUID"], destination)
            self.files_retrieved.emit([str(path) for path in files])
            QMessageBox.information(self, "PACS", f"{len(files)} DICOM alındı.")
        except PacsError as exc:
            QMessageBox.warning(self, "PACS alma", str(exc))
        except Exception as exc:
            QMessageBox.warning(self, "PACS alma", f"Tetkik alınamadı:\n{exc}")

    def send(self):
        path, _ = QFileDialog.getOpenFileName(self, "Gönderilecek DICOM", "", "DICOM (*.dcm);;Tüm dosyalar (*.*)")
        if not path:
            return
        try:
            send_dicom(self.config(), path)
            self.dicom_sent.emit(path)
            QMessageBox.information(self, "PACS", "DICOM başarıyla gönderildi.")
        except PacsError as exc:
            QMessageBox.warning(self, "PACS gönderme", str(exc))
        except Exception as exc:
            QMessageBox.warning(self, "PACS gönderme", f"DICOM gönderilemedi:\n{exc}")

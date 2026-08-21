from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

import pydicom
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from modular_app.database.exam_repository import ExamRepository


def _format_timestamp(value: object) -> str:
    raw = str(value or "").strip()
    if not raw:
        return "—"
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(raw[:19], fmt).strftime("%d.%m.%Y %H:%M")
        except ValueError:
            pass
    return raw


def _format_study_date(value: object) -> str:
    raw = str(value or "").strip()
    if len(raw) == 8 and raw.isdigit():
        try:
            return datetime.strptime(raw, "%Y%m%d").strftime("%d.%m.%Y")
        except ValueError:
            pass
    return raw or "—"


class ImageNotesDialog(QDialog):
    """Hasta ve görüntü bazlı kalıcı yerel not yönetimi v2.

    Kaynak DICOM hiçbir zaman değiştirilmez. Notlar yerel veritabanında tutulur.
    """

    def __init__(
        self,
        repository: ExamRepository,
        patient_id: str,
        dicom_path: str,
        actor: str = "",
        actor_role: str = "",
        parent=None,
    ):
        super().__init__(parent)
        self.repository = repository
        self.patient_id = str(patient_id)
        self.dicom_path = str(Path(dicom_path).resolve())
        self.actor = str(actor)
        self.actor_role = str(actor_role)
        self.editable = self.actor_role in {"Yönetici", "Hekim"}
        self.rows: list[dict] = []
        self._editing_note_id: int | None = None

        self.setWindowTitle("Hasta / Görüntü Notları v2")
        self.resize(980, 610)
        self.setMinimumSize(820, 520)
        self.setStyleSheet(
            "QDialog { background:#242424; color:#ecf0f1; }"
            "QFrame { background:#2b2b2b; border:1px solid #3d3d3d; border-radius:7px; }"
            "QPushButton { background:#34495e; color:white; border:none; border-radius:5px; padding:7px 12px; }"
            "QPushButton:hover { background:#3f5870; }"
            "QPushButton:disabled { color:#777; background:#303030; }"
            "QPlainTextEdit, QTableWidget { background:#1e1e1e; color:#ecf0f1; border:1px solid #404040; }"
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(8)

        # Başlık
        header = QHBoxLayout()
        title = QLabel("<b>Hasta / Görüntü Notları</b>")
        title.setStyleSheet("font-size:15px;")
        header.addWidget(title)
        header.addStretch()

        self.patient_label = QLabel(f"Hasta ID: {self.patient_id}")
        self.patient_label.setStyleSheet("color:#95a5a6;")
        header.addWidget(self.patient_label)
        root.addLayout(header)

        # Aktif tetkik kartı
        exam_frame = QFrame()
        exam_layout = QVBoxLayout(exam_frame)
        exam_layout.setContentsMargins(10, 7, 10, 7)
        exam_layout.setSpacing(2)
        exam_layout.addWidget(QLabel("<b>Aktif görüntü / tetkik</b>"))

        self.exam_info = QLabel(self._exam_description(self.dicom_path))
        self.exam_info.setWordWrap(True)
        self.exam_info.setStyleSheet("color:#bdc3c7; border:none;")
        exam_layout.addWidget(self.exam_info)
        root.addWidget(exam_frame)

        if not self.editable:
            permission = QLabel("Not ekleme, düzenleme ve silme için Hekim veya Yönetici rolü gerekir.")
            permission.setStyleSheet("color:#e67e22;")
            root.addWidget(permission)

        self.show_all_patient = QCheckBox("Bu hastanın tüm görüntülerindeki notları göster")
        self.show_all_patient.toggled.connect(self._load)
        root.addWidget(self.show_all_patient)

        splitter = QSplitter(Qt.Orientation.Vertical)

        # Not listesi
        list_widget = QWidget()
        list_layout = QVBoxLayout(list_widget)
        list_layout.setContentsMargins(0, 0, 0, 0)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Tarih", "Tetkik / Dosya", "Ekleyen", "Not", "ID"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.setColumnWidth(0, 125)
        self.table.setColumnWidth(1, 235)
        self.table.setColumnWidth(2, 120)
        self.table.setColumnWidth(4, 55)
        self.table.horizontalHeader().setSectionResizeMode(3, self.table.horizontalHeader().ResizeMode.Stretch)
        self.table.itemSelectionChanged.connect(self._selection_changed)
        self.table.itemDoubleClicked.connect(lambda _item: self._begin_edit())
        list_layout.addWidget(self.table)
        splitter.addWidget(list_widget)

        # Editör
        editor_widget = QWidget()
        editor_layout = QVBoxLayout(editor_widget)
        editor_layout.setContentsMargins(0, 4, 0, 0)

        self.mode_label = QLabel("Yeni not")
        self.mode_label.setStyleSheet("font-weight:bold; color:#3498db;")
        editor_layout.addWidget(self.mode_label)

        self.editor = QPlainTextEdit()
        self.editor.setPlaceholderText(
            "Bu görüntüyle ilgili takip notunu yazın. Kaynak DICOM değiştirilmeyecektir."
        )
        self.editor.setMaximumBlockCount(200)
        self.editor.setEnabled(self.editable)
        self.editor.textChanged.connect(self._update_counter)
        editor_layout.addWidget(self.editor)

        bottom = QHBoxLayout()
        self.counter = QLabel("0 / 4000")
        self.counter.setStyleSheet("color:#7f8c8d;")
        bottom.addWidget(self.counter)
        bottom.addStretch()

        self.btn_cancel_edit = QPushButton("Düzenlemeyi İptal")
        self.btn_cancel_edit.setVisible(False)
        self.btn_cancel_edit.clicked.connect(self._cancel_edit)
        bottom.addWidget(self.btn_cancel_edit)

        self.btn_edit = QPushButton("Seçili Notu Düzenle")
        self.btn_edit.setEnabled(False)
        self.btn_edit.clicked.connect(self._begin_edit)
        bottom.addWidget(self.btn_edit)

        self.btn_delete = QPushButton("Seçili Notu Sil")
        self.btn_delete.setEnabled(False)
        self.btn_delete.clicked.connect(self._delete_note)
        bottom.addWidget(self.btn_delete)

        self.btn_save = QPushButton("Notu Ekle")
        self.btn_save.setEnabled(self.editable)
        self.btn_save.setStyleSheet(
            "QPushButton { background:#27ae60; color:white; font-weight:bold; border-radius:5px; padding:7px 14px; }"
            "QPushButton:hover { background:#2fbd6b; }"
            "QPushButton:disabled { background:#303030; color:#777; }"
        )
        self.btn_save.clicked.connect(self._save_note)
        bottom.addWidget(self.btn_save)

        editor_layout.addLayout(bottom)
        splitter.addWidget(editor_widget)
        splitter.setSizes([340, 190])
        root.addWidget(splitter, 1)

        footer = QHBoxLayout()
        self.status_label = QLabel("Kaynak DICOM dosyası değiştirilmez; notlar yalnızca yerel veritabanında tutulur.")
        self.status_label.setStyleSheet("color:#7f8c8d; font-size:10px;")
        footer.addWidget(self.status_label)
        footer.addStretch()

        close = QPushButton("Kapat")
        close.clicked.connect(self.accept)
        footer.addWidget(close)
        root.addLayout(footer)

        self._load()
        self._update_counter()

    def _exam_description(self, path: str) -> str:
        filename = os.path.basename(path)
        try:
            ds = pydicom.dcmread(path, stop_before_pixels=True)
            study_date = _format_study_date(getattr(ds, "StudyDate", ""))
            study = str(getattr(ds, "StudyDescription", "") or "").strip()
            series = str(getattr(ds, "SeriesDescription", "") or "").strip()
            modality = str(getattr(ds, "Modality", "") or "").strip()
            description = study or series or "Açıklama yok"
            return f"{study_date}  |  {modality or '—'}  |  {description}  |  {filename}"
        except Exception:
            return filename

    def _load(self) -> None:
        if self.show_all_patient.isChecked():
            self.rows = self.repository.list_image_notes(self.patient_id)
        else:
            self.rows = self.repository.list_image_notes(self.patient_id, self.dicom_path)

        self.table.setRowCount(0)
        for note in self.rows:
            row = self.table.rowCount()
            self.table.insertRow(row)

            note_path = str(note.get("dicom_path", "") or "")
            values = (
                _format_timestamp(note.get("created_at", "")),
                self._exam_description(note_path),
                note.get("created_by", "") or "—",
                note.get("note", ""),
                note.get("id", ""),
            )

            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setData(Qt.ItemDataRole.UserRole, note.get("id"))
                if column == 3:
                    item.setToolTip(str(value))
                if column == 1:
                    item.setToolTip(note_path)
                self.table.setItem(row, column, item)

        self.table.clearSelection()
        self._selection_changed()
        scope = "hasta genelinde" if self.show_all_patient.isChecked() else "aktif görüntüde"
        self.status_label.setText(f"{scope} {len(self.rows)} not bulundu. Kaynak DICOM değiştirilmez.")

    def _selected_note(self) -> dict | None:
        row = self.table.currentRow()
        if 0 <= row < len(self.rows):
            return self.rows[row]
        return None

    def _selection_changed(self) -> None:
        selected = self._selected_note() is not None
        self.btn_edit.setEnabled(self.editable and selected and self._editing_note_id is None)
        self.btn_delete.setEnabled(self.editable and selected and self._editing_note_id is None)

    def _update_counter(self) -> None:
        count = len(self.editor.toPlainText())
        self.counter.setText(f"{count} / 4000")
        self.counter.setStyleSheet("color:#e74c3c;" if count > 4000 else "color:#7f8c8d;")

    def _begin_edit(self) -> None:
        if not self.editable:
            return
        note = self._selected_note()
        if note is None:
            return

        self._editing_note_id = int(note["id"])
        self.editor.setPlainText(str(note.get("note", "")))
        self.mode_label.setText(f"Not #{self._editing_note_id} düzenleniyor")
        self.mode_label.setStyleSheet("font-weight:bold; color:#f39c12;")
        self.btn_save.setText("Değişiklikleri Kaydet")
        self.btn_cancel_edit.setVisible(True)
        self.btn_edit.setEnabled(False)
        self.btn_delete.setEnabled(False)
        self.editor.setFocus()

    def _cancel_edit(self) -> None:
        self._editing_note_id = None
        self.editor.clear()
        self.mode_label.setText("Yeni not")
        self.mode_label.setStyleSheet("font-weight:bold; color:#3498db;")
        self.btn_save.setText("Notu Ekle")
        self.btn_cancel_edit.setVisible(False)
        self._selection_changed()

    def _save_note(self) -> None:
        if not self.editable:
            return

        text = self.editor.toPlainText()
        try:
            if self._editing_note_id is None:
                note_id = self.repository.add_image_note(
                    patient_id=self.patient_id,
                    dicom_path=self.dicom_path,
                    note=text,
                    created_by=self.actor,
                )
                self.repository.record_audit_event(
                    self.patient_id,
                    "image_note_added",
                    f"Görüntü notu #{note_id}; {os.path.basename(self.dicom_path)}",
                    actor=self.actor,
                    actor_role=self.actor_role,
                )
                message = f"Not #{note_id} eklendi."
            else:
                note_id = int(self._editing_note_id)
                self.repository.update_image_note(note_id, text)
                self.repository.record_audit_event(
                    self.patient_id,
                    "image_note_updated",
                    f"Görüntü notu #{note_id} düzenlendi",
                    actor=self.actor,
                    actor_role=self.actor_role,
                )
                message = f"Not #{note_id} güncellendi."
        except ValueError as exc:
            QMessageBox.warning(self, "Görüntü notu", str(exc))
            return

        self._editing_note_id = None
        self.editor.clear()
        self.mode_label.setText("Yeni not")
        self.mode_label.setStyleSheet("font-weight:bold; color:#3498db;")
        self.btn_save.setText("Notu Ekle")
        self.btn_cancel_edit.setVisible(False)
        self._load()
        self.status_label.setText(message + " Kaynak DICOM değiştirilmedi.")

    def _delete_note(self) -> None:
        if not self.editable:
            return
        note = self._selected_note()
        if note is None:
            return

        answer = QMessageBox.question(
            self,
            "Görüntü notunu sil",
            f"Not #{note['id']} silinecek. Kaynak DICOM değişmeyecek.\n\nDevam edilsin mi?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        self.repository.delete_image_note(int(note["id"]))
        self.repository.record_audit_event(
            self.patient_id,
            "image_note_deleted",
            f"Görüntü notu #{note['id']} silindi",
            actor=self.actor,
            actor_role=self.actor_role,
        )
        self._cancel_edit()
        self._load()

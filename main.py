import sys
import os
import math
import datetime
import json
import pydicom
import numpy as np

try:
    import cv2
except ImportError:
    cv2 = None
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QPushButton, QTabWidget, QFileDialog, QGraphicsView, 
    QGraphicsScene, QGraphicsPixmapItem, QGraphicsItem, QSplitter, QAbstractItemView, QListWidget, QListWidgetItem, QTreeWidget, QTreeWidgetItem, QSlider, QStatusBar,
    QDialog, QCheckBox, QGridLayout, QMessageBox, QScrollArea, QSizePolicy, QMenu, QInputDialog
)
from PySide6.QtCore import Qt, QPointF, QSize, QTimer, QRectF
from PySide6.QtGui import (
    QFont, QPixmap, QImage, QPainter, QPen, QIcon, 
    QWheelEvent, QMouseEvent, QAction, QShortcut, QKeySequence, QTransform,
    QPdfWriter, QPageSize
)


def process_dicom_array(ds, brightness_val=0, window_center=None, window_width=None):
    """DICOM -> 8-bit görüntü. W/L verilirse gerçek Window/Level dönüşümü uygulanır."""
    if not hasattr(ds, 'pixel_array'):
        return None

    arr = ds.pixel_array.astype(np.float32)
    slope = float(getattr(ds, 'RescaleSlope', 1.0))
    intercept = float(getattr(ds, 'RescaleIntercept', 0.0))
    arr = arr * slope + intercept

    photo = str(getattr(ds, 'PhotometricInterpretation', 'MONOCHROME2')).upper()
    if photo == 'MONOCHROME1':
        arr = np.max(arr) - arr

    wc = window_center if window_center is not None else getattr(ds, 'WindowCenter', None)
    ww = window_width if window_width is not None else getattr(ds, 'WindowWidth', None)
    if isinstance(wc, (list, pydicom.multival.MultiValue)):
        wc = wc[0] if wc else None
    if isinstance(ww, (list, pydicom.multival.MultiValue)):
        ww = ww[0] if ww else None

    try:
        if wc is not None and ww is not None:
            wc, ww = float(wc), max(1.0, float(ww))
            ymin, ymax = wc - ww / 2.0, wc + ww / 2.0
            arr = ((arr - ymin) / max(1.0, ymax - ymin)) * 255.0
        else:
            mn, mx = float(np.min(arr)), float(np.max(arr))
            if mx > mn:
                arr = (arr - mn) / (mx - mn) * 255.0
            else:
                arr = np.zeros_like(arr)
    except (ValueError, TypeError):
        mn, mx = float(np.min(arr)), float(np.max(arr))
        if mx > mn:
            arr = (arr - mn) / (mx - mn) * 255.0
        else:
            arr = np.zeros_like(arr)

    arr += brightness_val * 5.0
    return np.clip(arr, 0, 255).astype(np.uint8)


class DicomPreviewDialog(QDialog):
    def __init__(self, part_name, initial_dir="", parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"{part_name.capitalize()} - DICOM Seç (Önizlemeli)")
        self.resize(950, 650)
        self.setStyleSheet("background-color: #2b2b2b; color: #ecf0f1;")
        
        self.selected_file_path = None
        self.folder_path = initial_dir
        self.dicom_files = []
        
        layout = QVBoxLayout(self)
        
        top_layout = QHBoxLayout()
        self.btn_select_folder = QPushButton("Klasör Seç...")
        self.btn_select_folder.setStyleSheet("background-color: #2980b9; color: white; padding: 6px 12px; font-weight: bold;")
        self.btn_select_folder.clicked.connect(self.browse_folder)
        
        self.lbl_folder_path = QLabel(initial_dir if initial_dir else "Klasör seçilmedi")
        self.lbl_folder_path.setStyleSheet("color: #bdc3c7; background-color: #1e1e1e; padding: 6px; border: 1px solid #444;")
        
        top_layout.addWidget(self.btn_select_folder)
        top_layout.addWidget(self.lbl_folder_path, stretch=1)
        layout.addLayout(top_layout)
        
        splitter = QSplitter(Qt.Horizontal)
        
        self.file_list_widget = QListWidget()
        self.file_list_widget.setStyleSheet("background-color: #1e1e1e; color: #ecf0f1; border: 1px solid #444;")
        self.file_list_widget.itemSelectionChanged.connect(self.on_file_selected)
        splitter.addWidget(self.file_list_widget)
        
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        
        self.preview_scene = QGraphicsScene()
        self.preview_view = QGraphicsView(self.preview_scene)
        self.preview_view.setStyleSheet("background-color: #111; border: 1px solid #444;")
        right_layout.addWidget(self.preview_view, stretch=3)
        
        self.info_label = QLabel("DICOM Etiket Bilgileri Bekleniyor...")
        self.info_label.setStyleSheet("background-color: #1e1e1e; color: #2ecc71; padding: 8px; font-family: Consolas; font-size: 11px; border: 1px solid #444;")
        self.info_label.setWordWrap(True)
        right_layout.addWidget(self.info_label, stretch=2)
        
        splitter.addWidget(right_widget)
        splitter.setSizes([280, 670])
        layout.addWidget(splitter)
        
        bottom_layout = QHBoxLayout()
        bottom_layout.addStretch()
        
        self.btn_cancel = QPushButton("İptal")
        self.btn_cancel.setStyleSheet("background-color: #c0392b; color: white; padding: 6px 16px;")
        self.btn_cancel.clicked.connect(self.reject)
        
        self.btn_select = QPushButton("Bu Dosyayı Seç")
        self.btn_select.setStyleSheet("background-color: #27ae60; color: white; padding: 6px 16px; font-weight: bold;")
        self.btn_select.clicked.connect(self.accept_file)
        self.btn_select.setEnabled(False)
        
        bottom_layout.addWidget(self.btn_cancel)
        bottom_layout.addWidget(self.btn_select)
        layout.addLayout(bottom_layout)
        
        if initial_dir and os.path.exists(initial_dir):
            self.load_dicom_files_from_dir(initial_dir)

    def browse_folder(self):
        dir_path = QFileDialog.getExistingDirectory(self, "DICOM Klasörü Seç", self.folder_path)
        if dir_path:
            self.folder_path = dir_path
            self.lbl_folder_path.setText(dir_path)
            self.load_dicom_files_from_dir(dir_path)

    def load_dicom_files_from_dir(self, dir_path):
        self.file_list_widget.clear()
        self.dicom_files = []
        for root, _, files in os.walk(dir_path):
            for file in files:
                full_path = os.path.join(root, file)
                self.dicom_files.append(full_path)
                self.file_list_widget.addItem(file)

    def on_file_selected(self):
        items = self.file_list_widget.selectedItems()
        if not items:
            return
        index = self.file_list_widget.row(items[0])
        if 0 <= index < len(self.dicom_files):
            file_path = self.dicom_files[index]
            self.selected_file_path = file_path
            self.btn_select.setEnabled(True)
            self.show_file_preview(file_path)

    def show_file_preview(self, file_path):
        self.preview_scene.clear()
        try:
            ds = pydicom.dcmread(file_path)
            patient_name = str(getattr(ds, 'PatientName', 'Bilinmiyor'))
            patient_id = str(getattr(ds, 'PatientID', '-'))
            study_desc = str(getattr(ds, 'StudyDescription', '-'))
            series_desc = str(getattr(ds, 'SeriesDescription', '-'))
            body_part = str(getattr(ds, 'BodyPartExamined', '-'))
            modality = str(getattr(ds, 'Modality', '-'))
            study_date = str(getattr(ds, 'StudyDate', '-'))
            series_num = str(getattr(ds, 'SeriesNumber', '-'))
            instance_num = str(getattr(ds, 'InstanceNumber', '-'))
            
            arr = process_dicom_array(ds)
            if arr is not None:
                h, w = arr.shape
                q_img = QImage(arr.data, w, h, w, QImage.Format_Grayscale8)
                pix = QPixmap.fromImage(q_img)
                self.preview_scene.addPixmap(pix)
                self.preview_view.fitInView(self.preview_scene.itemsBoundingRect(), Qt.KeepAspectRatio)
                
                info_text = (
                    f"Hasta Adı: {patient_name}\n"
                    f"Hasta ID: {patient_id}\n"
                    f"Etüt Açıklaması: {study_desc}\n"
                    f"Seri Açıklaması: {series_desc}\n"
                    f"Vücut Bölgesi: {body_part}\n"
                    f"Modalite: {modality}\n"
                    f"Etüt Tarihi: {study_date}\n"
                    f"Seri / Instance No: {series_num} / {instance_num}\n"
                    f"Boyut: {w} x {h} px"
                )
                self.info_label.setText(info_text)
        except Exception as e:
            self.info_label.setText(f"Önizleme yüklenemedi / Standart görsel:\n{str(e)}")
            pix = QPixmap(file_path)
            if not pix.isNull():
                self.preview_scene.addPixmap(pix)
                self.preview_view.fitInView(self.preview_scene.itemsBoundingRect(), Qt.KeepAspectRatio)

    def accept_file(self):
        if self.selected_file_path:
            self.accept()


class MultiPartDicomPreviewDialog(QDialog):
    """Tek pencerede Servikal/Dorsal/Lomber DICOM seçimi."""
    def __init__(self, initial_dir="", initial_files=None, initial_target="servical", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Omurga Parçaları - DICOM Seç (Önizlemeli)")
        self.resize(1100, 720)
        self.setStyleSheet("background-color: #2b2b2b; color: #ecf0f1;")
        self.folder_path = initial_dir or ""
        self.dicom_files = []
        self.selected_file_path = None
        self.selected_files = dict(initial_files or {})
        self.active_target = initial_target if initial_target in self.selected_files else "servical"
        self.target_buttons = {}
        self.assignment_labels = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)

        title = QLabel("<b>Omurga Parçalarını Tek Pencerede Seç</b>")
        title.setStyleSheet("font-size: 14px; color: #ecf0f1;")
        root.addWidget(title)

        target_row = QHBoxLayout()
        target_row.addWidget(QLabel("Hedef parça:"))
        for key, text in [("servical", "Servikal"), ("dorsal", "Dorsal"), ("lumbar", "Lomber")]:
            btn = QPushButton(text)
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked=False, k=key: self.set_active_target(k))
            self.target_buttons[key] = btn
            target_row.addWidget(btn)
            status = QLabel("Yüklenmedi")
            status.setStyleSheet("color: #95a5a6; padding-left: 4px;")
            self.assignment_labels[key] = status
            target_row.addWidget(status)
        target_row.addStretch()
        root.addLayout(target_row)

        folder_row = QHBoxLayout()
        btn_folder = QPushButton("Klasör Seç...")
        btn_folder.setStyleSheet("background-color: #2980b9; color: white; padding: 6px 12px; font-weight: bold;")
        btn_folder.clicked.connect(self.browse_folder)
        self.lbl_folder_path = QLabel(self.folder_path if self.folder_path else "Klasör seçilmedi")
        self.lbl_folder_path.setStyleSheet("color: #bdc3c7; background-color: #1e1e1e; padding: 6px; border: 1px solid #444;")
        folder_row.addWidget(btn_folder)
        folder_row.addWidget(self.lbl_folder_path, 1)
        root.addLayout(folder_row)

        splitter = QSplitter(Qt.Horizontal)
        self.file_list_widget = QListWidget()
        self.file_list_widget.setStyleSheet("background-color: #1e1e1e; color: #ecf0f1; border: 1px solid #444;")
        self.file_list_widget.itemSelectionChanged.connect(self.on_file_selected)
        splitter.addWidget(self.file_list_widget)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        self.preview_scene = QGraphicsScene()
        self.preview_view = QGraphicsView(self.preview_scene)
        self.preview_view.setStyleSheet("background-color: #111; border: 1px solid #444;")
        right_layout.addWidget(self.preview_view, 1)
        self.info_label = QLabel("DICOM Etiket Bilgileri Bekleniyor...")
        self.info_label.setWordWrap(True)
        self.info_label.setStyleSheet("background-color: #1e1e1e; color: #2ecc71; padding: 8px; font-family: Consolas; font-size: 11px; border: 1px solid #444;")
        right_layout.addWidget(self.info_label)
        splitter.addWidget(right)
        splitter.setSizes([320, 700])
        root.addWidget(splitter, 1)

        action_row = QHBoxLayout()
        self.btn_assign = QPushButton("Seçili dosyayı Servikal'e Ata")
        self.btn_assign.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold; padding: 8px 14px;")
        self.btn_assign.clicked.connect(self.assign_selected)
        self.btn_assign.setEnabled(False)
        action_row.addWidget(self.btn_assign)
        action_row.addStretch()
        self.btn_cancel = QPushButton("İptal")
        self.btn_cancel.setStyleSheet("background-color: #c0392b; color: white; padding: 8px 14px;")
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_ok = QPushButton("Seçimleri Tamamla")
        self.btn_ok.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold; padding: 8px 14px;")
        self.btn_ok.clicked.connect(self.accept_all)
        action_row.addWidget(self.btn_cancel)
        action_row.addWidget(self.btn_ok)
        root.addLayout(action_row)

        self.refresh_target_ui()
        if self.folder_path and os.path.isdir(self.folder_path):
            self.load_dicom_files_from_dir(self.folder_path)

    def set_active_target(self, key):
        # Hedef değiştirildiğinde mevcut seçili dosyayı otomatik atama:
        # dosya seç -> hedefe tıkla -> hedef atanır. Böylece üç parçayı tek
        # pencerede art arda seçmek mümkün olur. İlk hedef seçimi dosya yoksa
        # yalnızca hedefi değiştirir.
        previous_target = getattr(self, "active_target", None)
        self.active_target = key
        for k, btn in self.target_buttons.items():
            btn.setChecked(k == key)

        if self.selected_file_path and previous_target is not None and previous_target != key:
            self.selected_files[key] = self.selected_file_path
            self.refresh_target_ui()

        self.btn_assign.setText(f"Seçili dosyayı {self.target_buttons[key].text()}'e Ata")

    def refresh_target_ui(self):
        self.set_active_target(self.active_target)
        for key, label in self.assignment_labels.items():
            path = self.selected_files.get(key)
            label.setText(os.path.basename(path) if path else "Yüklenmedi")
            label.setStyleSheet("color: #2ecc71; padding-left: 4px;" if path else "color: #95a5a6; padding-left: 4px;")

    def browse_folder(self):
        path = QFileDialog.getExistingDirectory(self, "DICOM Klasörü Seç", self.folder_path)
        if path:
            self.folder_path = path
            self.lbl_folder_path.setText(path)
            self.load_dicom_files_from_dir(path)

    def load_dicom_files_from_dir(self, dir_path):
        self.file_list_widget.clear()
        self.dicom_files = []
        for root, _, files in os.walk(dir_path):
            for file in files:
                full = os.path.join(root, file)
                self.dicom_files.append(full)
                self.file_list_widget.addItem(file)

    def on_file_selected(self):
        items = self.file_list_widget.selectedItems()
        if not items:
            return
        idx = self.file_list_widget.row(items[0])
        if 0 <= idx < len(self.dicom_files):
            self.selected_file_path = self.dicom_files[idx]
            self.btn_assign.setEnabled(True)
            self.show_file_preview(self.selected_file_path)

    def show_file_preview(self, file_path):
        self.preview_scene.clear()
        try:
            ds = pydicom.dcmread(file_path)
            arr = process_dicom_array(ds)
            if arr is not None:
                h, w = arr.shape
                qimg = QImage(arr.data, w, h, w, QImage.Format_Grayscale8).copy()
                self.preview_scene.addPixmap(QPixmap.fromImage(qimg))
                self.preview_view.fitInView(self.preview_scene.itemsBoundingRect(), Qt.KeepAspectRatio)
            def tag(name, default='-'):
                return str(getattr(ds, name, default))
            self.info_label.setText(
                f"Hasta: {tag('PatientName', 'Bilinmiyor')}\n"
                f"Hasta ID: {tag('PatientID')}\n"
                f"Etüt: {tag('StudyDescription')}\n"
                f"Seri: {tag('SeriesDescription')}\n"
                f"Vücut: {tag('BodyPartExamined')}\n"
                f"Tarih: {tag('StudyDate')}\n"
                f"Modalite: {tag('Modality')}\n"
                f"Instance: {tag('InstanceNumber')}"
            )
        except Exception as e:
            self.info_label.setText(f"Önizleme yüklenemedi:\n{e}")

    def assign_selected(self):
        if not self.selected_file_path:
            return
        self.selected_files[self.active_target] = self.selected_file_path
        self.refresh_target_ui()
        self.status_message = f"{self.target_buttons[self.active_target].text()} seçildi."

    def accept_all(self):
        if not any(self.selected_files.values()):
            QMessageBox.information(self, "Omurga Parçaları", "En az bir DICOM parçası seçin.")
            return
        self.accept()



class StudySelectionDialog(QDialog):
    """DICOM/görüntü seçimi için önizlemeli ortak pencere."""
    def __init__(self, initial_files=None, parent=None, title=None, selection_hint=None, ok_label=None):
        super().__init__(parent)
        self.dialog_title = title or "Skolyoz Grafikleri / DICOM Seç"
        self.selection_hint = selection_hint or "Overlay için iki farklı zaman görüntüsünü seçin."
        self.setWindowTitle(self.dialog_title)
        self.resize(1050, 700)
        self.setStyleSheet("background-color:#2b2b2b; color:#ecf0f1;")
        self.files = []

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)

        top = QHBoxLayout()
        self.btn_add = QPushButton("Dosya Ekle...")
        self.btn_add.setStyleSheet("background-color:#2980b9; color:white; padding:7px 14px; font-weight:bold;")
        self.btn_add.clicked.connect(self.add_files)
        self.btn_folder = QPushButton("Klasör Tara...")
        self.btn_folder.setStyleSheet("background-color:#34495e; color:white; padding:7px 14px;")
        self.btn_folder.clicked.connect(self.add_folder)
        self.lbl_count = QLabel("0 görüntü seçildi")
        self.lbl_count.setStyleSheet("color:#bdc3c7; padding-left:8px;")
        top.addWidget(self.btn_add)
        top.addWidget(self.btn_folder)
        top.addWidget(self.lbl_count)
        top.addStretch()
        root.addLayout(top)

        splitter = QSplitter(Qt.Horizontal)
        self.file_list = QListWidget()
        self.file_list.setSelectionMode(QListWidget.MultiSelection)
        self.file_list.setIconSize(QSize(58, 58))
        self.file_list.setStyleSheet("background-color:#1e1e1e; color:#ecf0f1; border:1px solid #444;")
        self.file_list.itemSelectionChanged.connect(self.on_selection_changed)
        splitter.addWidget(self.file_list)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0,0,0,0)
        self.preview_scene = QGraphicsScene()
        self.preview_view = QGraphicsView(self.preview_scene)
        self.preview_view.setStyleSheet("background-color:#111; border:1px solid #444;")
        right_layout.addWidget(self.preview_view, 1)
        self.info_label = QLabel("Bir görüntü seçin; önizleme ve DICOM bilgileri burada görünecek.")
        self.info_label.setWordWrap(True)
        self.info_label.setStyleSheet("background-color:#1e1e1e; color:#2ecc71; padding:9px; font-family:Consolas; font-size:11px; border:1px solid #444;")
        right_layout.addWidget(self.info_label)
        splitter.addWidget(right)
        splitter.setSizes([360, 680])
        root.addWidget(splitter, 1)

        bottom = QHBoxLayout()
        self.lbl_hint = QLabel(self.selection_hint)
        self.lbl_hint.setStyleSheet("color:#95a5a6; font-size:11px;")
        bottom.addWidget(self.lbl_hint)
        bottom.addStretch()
        btn_cancel = QPushButton("İptal")
        btn_cancel.setStyleSheet("background-color:#c0392b; color:white; padding:7px 16px;")
        btn_cancel.clicked.connect(self.reject)
        self.btn_ok = QPushButton(ok_label or "Seçimleri Yükle")
        self.btn_ok.setStyleSheet("background-color:#27ae60; color:white; padding:7px 16px; font-weight:bold;")
        self.btn_ok.clicked.connect(self.accept_selection)
        self.btn_ok.setEnabled(False)
        bottom.addWidget(btn_cancel)
        bottom.addWidget(self.btn_ok)
        root.addLayout(bottom)

        for f in initial_files or []:
            self.add_path(f)
        self._refresh_count()

    def add_path(self, path):
        path = os.path.abspath(path)
        if path in self.files or not os.path.isfile(path):
            return
        self.files.append(path)
        try:
            ds = pydicom.dcmread(path, stop_before_pixels=True)
            date = str(getattr(ds, 'StudyDate', '') or '')
            desc = str(getattr(ds, 'StudyDescription', '') or getattr(ds, 'SeriesDescription', '') or '')
            modality = str(getattr(ds, 'Modality', '') or '')
            text = os.path.basename(path)
            if date or modality or desc:
                text += f"  |  {date}  {modality}  {desc}".strip()
            icon = QIcon()
            try:
                pix = self._preview_pixmap(path, ds)
                if not pix.isNull():
                    icon = QIcon(pix)
            except Exception:
                pass
            item = QListWidgetItem(icon, text)
            item.setData(Qt.UserRole, path)
            self.file_list.addItem(item)
        except Exception:
            item = QListWidgetItem(os.path.basename(path))
            item.setData(Qt.UserRole, path)
            self.file_list.addItem(item)

    def _preview_pixmap(self, path, ds=None):
        ds = ds or pydicom.dcmread(path)
        if not hasattr(ds, 'PixelData'):
            ds = pydicom.dcmread(path)
        arr = process_dicom_array(ds)
        if arr is None:
            return QPixmap(path)
        arr = np.asarray(arr)
        if arr.ndim == 3:
            samples = int(getattr(ds, 'SamplesPerPixel', 1) or 1)
            arr = arr[..., 0] if samples > 1 and arr.shape[-1] in (3, 4) else arr[0]
        if arr.ndim != 2:
            return QPixmap(path)
        arr = np.ascontiguousarray(arr)
        h, w = arr.shape
        qimg = QImage(arr.data, w, h, w, QImage.Format_Grayscale8).copy()
        pix = QPixmap.fromImage(qimg)
        if pix.width() > 500 or pix.height() > 500:
            pix = pix.scaled(500, 500, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        return pix

    def add_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, self.dialog_title, "",
            "Tüm Dosyalar (*.*);;DICOM / Görüntü (*.dcm *.dicom *.jpg *.jpeg *.png *.bmp)"
        )
        for f in files:
            self.add_path(f)
        self._refresh_count()

    def add_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "DICOM Klasörü Seç", "")
        if not folder:
            return
        found = []
        for root, _, names in os.walk(folder):
            for name in names:
                full = os.path.join(root, name)
                if os.path.isfile(full):
                    found.append(full)
        # DICOM dışı dosyaları da tamamen engellemiyoruz; get_image_pixmap gibi
        # standart görüntüler için de önizleme desteği devam eder.
        for f in found:
            self.add_path(f)
        self._refresh_count()

    def on_selection_changed(self):
        items = self.file_list.selectedItems()
        self._refresh_count()
        if not items:
            self.preview_scene.clear()
            return
        path = items[-1].data(Qt.UserRole)
        self.show_preview(path)

    def show_preview(self, path):
        self.preview_scene.clear()
        try:
            ds = pydicom.dcmread(path)
            pix = self._preview_pixmap(path, ds)
            if not pix.isNull():
                item = self.preview_scene.addPixmap(pix)
                self.preview_scene.setSceneRect(item.boundingRect())
                self.preview_view.fitInView(item, Qt.KeepAspectRatio)

            def tag(name, default='-'):
                value = getattr(ds, name, default)
                if isinstance(value, (list, pydicom.multival.MultiValue)):
                    value = '\\'.join(str(x) for x in value)
                return str(value) if value not in (None, '') else default

            self.info_label.setText(
                f"Hasta Adı: {tag('PatientName', 'Bilinmiyor')}\\n"
                f"Hasta ID: {tag('PatientID')}\\n"
                f"Doğum Tarihi: {tag('PatientBirthDate')}\\n"
                f"Cinsiyet: {tag('PatientSex')}\\n"
                f"Etüt: {tag('StudyDescription')}\\n"
                f"Seri: {tag('SeriesDescription')}\\n"
                f"Vücut Bölgesi: {tag('BodyPartExamined')}\\n"
                f"Modalite: {tag('Modality')}\\n"
                f"Etüt Tarihi: {tag('StudyDate')}\\n"
                f"Seri / Instance: {tag('SeriesNumber')} / {tag('InstanceNumber')}"
            )
        except Exception as e:
            pix = QPixmap(path)
            if not pix.isNull():
                item = self.preview_scene.addPixmap(pix)
                self.preview_scene.setSceneRect(item.boundingRect())
                self.preview_view.fitInView(item, Qt.KeepAspectRatio)
            self.info_label.setText(f"Önizleme / DICOM bilgisi okunamadı:\\n{e}")

    def _refresh_count(self):
        n = len(self.file_list.selectedItems())
        total = self.file_list.count()
        self.lbl_count.setText(f"{n} görüntü seçildi / {total} görüntü")
        self.btn_ok.setEnabled(n >= 1)
        if n > 2 and "Overlay" in self.selection_hint:
            self.lbl_hint.setText("Overlay ilk iki seçili görüntüyü kullanır; isterseniz daha fazla görüntüyü kütüphaneye yükleyebilirsiniz.")
        else:
            self.lbl_hint.setText(self.selection_hint)

    def accept_selection(self):
        selected = [i.data(Qt.UserRole) for i in self.file_list.selectedItems()]
        if not selected:
            return
        self.selected_paths = selected
        self.accept()


class InteractiveGraphicsView(QGraphicsView):
    def __init__(self, scene, view_side, parent=None):
        super().__init__(scene, parent)
        self.view_side = view_side
        self.setRenderHint(QPainter.Antialiasing)
        self.setRenderHint(QPainter.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.NoDrag)
        self.setStyleSheet("background-color: #111111; border: 1px solid #444;")
        self.zoom_factor = 1.15
        self.parent_app = None
        self._panning = False
        self._pan_last_pos = None
        self._windowing = False
        self._windowing_last_pos = None
        self._overlay_dragging = False
        self._overlay_last_scene_pos = None
        self.setCursor(Qt.ArrowCursor)

    def refresh_cursor(self):
        marking = False
        if self.parent_app is not None:
            if self.view_side == 'stitch' and getattr(self.parent_app, 'manual_mode_active', False):
                marking = True
            if (self.view_side == 'viewer'
                    and (getattr(self.parent_app, 'viewer_cobb_mode_active', False)
                         or getattr(self.parent_app, 'viewer_length_mode_active', False)
                         or getattr(self.parent_app, 'viewer_markup_mode', None))):
                marking = True
            if self.view_side != 'viewer' and getattr(self.parent_app, 'cobb_mode_active', False):
                marking = True
            if getattr(self.parent_app, 'vertebra_label_mode_active', False):
                marking = True
        self.setCursor(Qt.CrossCursor if marking else Qt.ArrowCursor)

    def wheelEvent(self, event: QWheelEvent):
        if self.parent_app is not None and self.view_side == 'viewer':
            factor = self.zoom_factor if event.angleDelta().y() > 0 else (1 / self.zoom_factor)
            self.parent_app.adjust_viewer_zoom(factor)
            event.accept()
            return
        if (self.parent_app is not None and self.view_side == 'left'
                and getattr(self.parent_app, 'current_mode', '') == 'overlay'
                and getattr(self.parent_app, 'overlay_item', None) is not None):
            step = 1.05 if event.angleDelta().y() > 0 else (1.0 / 1.05)
            current = getattr(self.parent_app, 'overlay_scale', 1.0)
            new_value = max(0.5, min(1.6, current * step))
            slider = getattr(self.parent_app, 'overlay_zoom_slider', None)
            if slider is not None:
                slider.setValue(int(round(new_value * 100)))
            else:
                self.parent_app.overlay_scale = new_value
                self.parent_app.on_overlay_zoom_changed(int(round(new_value * 100)))
            event.accept()
            return
        if event.angleDelta().y() > 0:
            self.scale(self.zoom_factor, self.zoom_factor)
        else:
            self.scale(1 / self.zoom_factor, 1 / self.zoom_factor)

    def mousePressEvent(self, event: QMouseEvent):
        # Bağımsız görüntüleyicide sol tık, etkin ölçüm/işaretleme aracına ayrılır.
        if (event.button() == Qt.LeftButton and self.parent_app is not None
                and self.view_side == 'viewer'
                and getattr(self.parent_app, 'viewer_markup_mode', None)):
            self.parent_app.handle_viewer_markup_click(self.mapToScene(event.position().toPoint()))
            event.accept()
            return
        if (event.button() == Qt.LeftButton and self.parent_app is not None
                and self.view_side == 'viewer'
                and getattr(self.parent_app, 'viewer_cobb_mode_active', False)):
            self.parent_app.handle_viewer_cobb_click(self.mapToScene(event.position().toPoint()))
            event.accept()
            return
        if (event.button() == Qt.LeftButton and self.parent_app is not None
                and self.view_side == 'viewer'
                and getattr(self.parent_app, 'viewer_length_mode_active', False)):
            self.parent_app.handle_viewer_length_click(self.mapToScene(event.position().toPoint()))
            event.accept()
            return

        # Orta fare: W/L
        if event.button() == Qt.MiddleButton:
            self._windowing = True
            self._windowing_last_pos = event.position().toPoint()
            self.setCursor(Qt.SizeAllCursor)
            event.accept()
            return

        # Omur etiketi modu açıkken tıklama önce etikete ayrılır.
        if (event.button() == Qt.LeftButton and self.parent_app is not None
                and getattr(self.parent_app, 'vertebra_label_mode_active', False)
                and self.view_side in {'left', 'right'}):
            self.parent_app.handle_vertebra_label_click(self.view_side, self.mapToScene(event.position().toPoint()))
            event.accept()
            return

        # Overlay modunda sol fare: üstteki görüntüyü doğrudan sürükle.
        # Cobb ölçümü açıksa tıklama ölçüme ayrılır.
        if (event.button() == Qt.LeftButton and self.parent_app is not None
                and self.view_side == 'left'
                and getattr(self.parent_app, 'current_mode', '') == 'overlay'
                and not getattr(self.parent_app, 'cobb_mode_active', False)
                and getattr(self.parent_app, 'overlay_item', None) is not None):
            self._overlay_dragging = True
            self._overlay_last_scene_pos = self.mapToScene(event.position().toPoint())
            self.setCursor(Qt.SizeAllCursor)
            event.accept()
            return

        if event.button() == Qt.RightButton:
            self._panning = True
            self._pan_last_pos = event.position().toPoint()
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()
            return

        if (self.parent_app and self.view_side == 'stitch'
                and getattr(self.parent_app, 'manual_mode_active', False)
                and event.button() == Qt.LeftButton):
            scene_pos = self.mapToScene(event.position().toPoint())
            self.parent_app.handle_manual_point_click(scene_pos)
            event.accept()
        elif (self.parent_app and self.view_side != 'viewer'
              and self.parent_app.cobb_mode_active and event.button() == Qt.LeftButton):
            scene_pos = self.mapToScene(event.position().toPoint())
            self.parent_app.handle_cobb_click(self.view_side, scene_pos)
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._overlay_dragging and self._overlay_last_scene_pos is not None:
            current = self.mapToScene(event.position().toPoint())
            delta = current - self._overlay_last_scene_pos
            self._overlay_last_scene_pos = current
            if self.parent_app is not None:
                self.parent_app.move_overlay(delta.x(), delta.y())
            event.accept()
            return

        if self._windowing and self._windowing_last_pos is not None:
            current_pos = event.position().toPoint()
            delta = current_pos - self._windowing_last_pos
            self._windowing_last_pos = current_pos
            if self.parent_app is not None:
                if self.view_side == 'viewer':
                    self.parent_app.adjust_viewer_window_level(delta.x(), delta.y())
                else:
                    self.parent_app.adjust_window_level(self.view_side, delta.x(), delta.y())
            event.accept()
            return

        if self._panning and self._pan_last_pos is not None:
            current_pos = event.position().toPoint()
            delta = current_pos - self._pan_last_pos
            self._pan_last_pos = current_pos
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton and self._overlay_dragging:
            self._overlay_dragging = False
            self._overlay_last_scene_pos = None
            self.refresh_cursor()
            event.accept()
            return
        if event.button() == Qt.MiddleButton and self._windowing:
            self._windowing = False
            self._windowing_last_pos = None
            self.refresh_cursor()
            event.accept()
            return
        if event.button() == Qt.RightButton and self._panning:
            self._panning = False
            self._pan_last_pos = None
            self.refresh_cursor()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def contextMenuEvent(self, event):
        event.ignore()


class ScoliosisFollowUpApp(QMainWindow):
    OVERLAP_PX = 80

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Scoliosis Follow-Up")
        self.setGeometry(100, 100, 1400, 900)
        self.setStyleSheet("background-color: #1e1e1e; color: #ecf0f1;")
        
        self.loaded_files = {} 
        self.current_mode = "side_by_side"
        # Skolyoz Takip Overlay / W-L kontrolleri
        self.overlay_item = None
        self.overlay_offset_x = 0.0
        self.overlay_offset_y = 0.0
        self.overlay_opacity = 0.50
        self.overlay_scale = 1.0
        self._overlay_initial_scale = 1.0
        self.window_settings = {}
        self._default_window_cache = {}
        self.cobb_mode_active = False
        self.cobb_points = [] 
        self.cobb_target_side = None 
        self.final_result_qimage = None
        self.final_brightness = 0
        self.final_contrast = 0
        
        self.stitch_files = {'servical': None, 'dorsal': None, 'lumbar': None}
        self.stitch_scenes = {}
        self.stitch_load_buttons = {}
        self.stitch_remove_buttons = {}
        self.last_stitch_folder = ''
        self.is_stitched_completed = False
        
        self.stitch_offset_x = 0.0
        self.stitch_offset_y = 0.0
        # Parça bazlı manuel kaydırma: Servikal her zaman sabittir.
        self.stitch_part_offsets = {"servical": [0.0, 0.0], "dorsal": [0.0, 0.0], "lumbar": [0.0, 0.0]}
        self.active_stitch_part = "dorsal"
        self.current_step_val = 1.0
        self.manual_mode_active = False
        # Manuel hizalama noktaları: her parçada en fazla 2 karşılık gelen nokta.
        # 2 nokta -> öteleme + küçük rijit rotasyon hesabı yapılır.
        self.manual_points = {}
        # (üst, alt) -> (dx, dy, angle_deg)
        self.manual_junction_offsets = {}
        self.manual_stage_index = 0
        self._pick_pixmaps = []
        self._pick_positions = []
        self._manual_point_marker_by_part = {}
        self._last_pixmaps = []
        self._last_positions = []
        self._last_overlap = self.OVERLAP_PX
        self._manual_point_markers = []

        # Performans önbellekleri: DICOM'u ve otomatik hizalamayı her tuş
        # basışında baştan hesaplamamak için kullanılır.
        self._stitch_pixmap_cache = {}
        self._stitch_array_cache = {}
        self._auto_align_cache = {}
        self._stitch_mask_cache = {}
        self._stitch_gray_cache = {}
        self._stitch_gray_flag_cache = {}
        self._stitch_result_item = None
        self._viewer_pixmap_cache = {}

        # Bağımsız görüntüleyicinin ayarları takip/overlay ayarlarından ayrıdır.
        self.viewer_current_path = None
        self.viewer_window_settings = {}
        self.viewer_brightness_value = 0
        self.viewer_cobb_mode_active = False
        self.viewer_cobb_points = []
        self.viewer_cobb_items = []
        self.viewer_length_mode_active = False
        self.viewer_length_start = None
        self.viewer_length_items = []
        self.viewer_measurement_records = []
        self.viewer_annotation_items = []
        self.viewer_annotations_visible = True
        self.viewer_markup_mode = None
        self.viewer_markup_start = None
        self.viewer_markup_items = []
        self.viewer_markup_records = []
        self.viewer_pixmap_item = None
        self._viewer_only_pixmap_cache = {}
        self._viewer_dataset_cache = {}
        self._viewer_dicom_flags = {}
        self._viewer_metadata_cache = {}
        self._viewer_frame_counts = {}
        self._viewer_fit_scale = 0.0
        self.viewer_frame_index = 0
        self.viewer_frame_count = 1
        self.viewer_rotation = 0
        self.viewer_flip_horizontal = False
        self.viewer_flip_vertical = False
        self.viewer_inverted = False
        self.viewer_cine_timer = QTimer(self)
        self.viewer_cine_timer.setInterval(120)
        self.viewer_cine_timer.timeout.connect(self.advance_viewer_frame)

        # Hızlı parça hareketlerinde her tuş vuruşunda tam birleştirme
        # render'ı çalıştırmak yerine kısa bir debounce kullanılır.
        # Böylece ok tuşuna basılı tutulduğunda son konum için tek render yapılır.
        self._stitch_render_timer = QTimer(self)
        self._stitch_render_timer.setSingleShot(True)
        self._stitch_render_timer.setInterval(16)
        self._stitch_render_timer.timeout.connect(self._render_interactive_preview)
        self._stitch_full_render_timer = QTimer(self)
        self._stitch_full_render_timer.setSingleShot(True)
        self._stitch_full_render_timer.setInterval(140)
        self._stitch_full_render_timer.timeout.connect(self._render_full_after_move)
        self._stitch_interactive = False
        self._stitch_preview_scale = 0.55
        
        menubar = self.menuBar()
        menubar.setStyleSheet("background-color: #2c3e50; color: #ecf0f1;")
        file_menu = menubar.addMenu("File")
        file_menu.addAction("Aç...", self.load_dicoms)
        file_menu.addAction("Çıkış", self.close)
        
        view_menu = menubar.addMenu("View")
        view_menu.addAction("Yan Yana", self.set_side_by_side_mode)
        view_menu.addAction("Overlay", self.set_overlay_mode)
        
        tools_menu = menubar.addMenu("Tools")
        tools_menu.addAction("Cobb Açısı Ölç", self.toggle_cobb_measurement)
        
        help_menu = menubar.addMenu("Help")
        help_menu.addAction("Hakkında", lambda: QMessageBox.information(self, "Hakkında", "Scoliosis Follow-Up v1.2"))
        
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane { border: none; }
            QTabBar::tab { 
                background: #2c3e50; 
                color: #ecf0f1;
                padding: 10px 20px; 
                font-weight: bold; 
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            QTabBar::tab:selected { 
                background: #34495e; 
                color: #3498db;
            }
        """)
        self.main_layout.addWidget(self.tabs)
        
        # Uygulama akışı: hızlı görüntüleme, omurga birleştirme, skolyoz takibi.
        # Sekmeler birbirinden bağımsız kurulur; böylece takip ve birleştirme
        # iş akışlarının mevcut davranışı değişmez.
        self.init_viewer_tab()
        self.init_stitcher_tab()
        self.init_workspace_tab()
        self.tabs.setCurrentWidget(self.viewer_tab)
        
        self.setStatusBar(QStatusBar(self))
        self.statusBar().showMessage("Hazır.")

    def init_viewer_tab(self):
        """Bağımsız DICOM görüntüleme, W/L ve Cobb ölçüm çalışma alanı."""
        self.viewer_tab = QWidget()
        viewer_layout = QVBoxLayout(self.viewer_tab)
        viewer_layout.setContentsMargins(8, 6, 8, 6)
        viewer_layout.setSpacing(5)

        controls_box = QWidget()
        controls_layout = QVBoxLayout(controls_box)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_layout.setSpacing(4)

        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(0, 0, 0, 0)
        toolbar.setSpacing(5)

        btn_open = QPushButton("📁 Görüntü / DICOM Aç")
        btn_open.setStyleSheet(
            "padding: 6px 12px; font-weight: bold; "
            "background-color: #27ae60; color: white;"
        )
        btn_open.clicked.connect(self.open_viewer_files)
        toolbar.addWidget(btn_open)

        toolbar.addWidget(QLabel("Zoom:"))
        btn_zoom_out = QPushButton("−")
        btn_zoom_out.setFixedWidth(28)
        btn_zoom_out.setToolTip("Uzaklaştır")
        btn_zoom_out.clicked.connect(lambda: self.adjust_viewer_zoom(1 / 1.15))
        toolbar.addWidget(btn_zoom_out)

        btn_fit = QPushButton("Görüntüyü Sığdır")
        btn_fit.setStyleSheet("padding: 6px 12px; background-color: #34495e; color: white;")
        btn_fit.clicked.connect(self.fit_viewer_image)
        toolbar.addWidget(btn_fit)

        btn_zoom_in = QPushButton("+")
        btn_zoom_in.setFixedWidth(28)
        btn_zoom_in.setToolTip("Yakınlaştır")
        btn_zoom_in.clicked.connect(lambda: self.adjust_viewer_zoom(1.15))
        toolbar.addWidget(btn_zoom_in)

        self.viewer_zoom_label = QLabel("Sığdır")
        self.viewer_zoom_label.setStyleSheet("color:#95a5a6; font-size:11px; min-width:70px;")
        toolbar.addWidget(self.viewer_zoom_label)

        self.btn_viewer_cobb = QPushButton("📐 Cobb Açısı Ölç")
        self.btn_viewer_cobb.setStyleSheet("padding: 6px 12px; background-color: #34495e; color: white;")
        self.btn_viewer_cobb.clicked.connect(self.toggle_viewer_cobb_measurement)
        toolbar.addWidget(self.btn_viewer_cobb)

        self.btn_viewer_length = QPushButton("↔ Mesafe Ölç")
        self.btn_viewer_length.setStyleSheet("padding: 6px 12px; background-color: #34495e; color: white;")
        self.btn_viewer_length.clicked.connect(self.toggle_viewer_length_measurement)
        toolbar.addWidget(self.btn_viewer_length)

        btn_clear_measurement = QPushButton("Ölçümü Temizle")
        btn_clear_measurement.setStyleSheet("padding: 6px 10px; background-color: #34495e; color: white;")
        btn_clear_measurement.clicked.connect(self.clear_viewer_measurements)
        toolbar.addWidget(btn_clear_measurement)

        self.btn_viewer_annotations = QPushButton("Anotasyonlar")
        self.btn_viewer_annotations.setCheckable(True)
        self.btn_viewer_annotations.setChecked(True)
        self.btn_viewer_annotations.setStyleSheet("padding: 6px 10px; background-color: #34495e; color: white;")
        self.btn_viewer_annotations.toggled.connect(self.set_viewer_annotations_visible)
        toolbar.addWidget(self.btn_viewer_annotations)

        btn_clear = QPushButton("Listeyi Temizle")
        btn_clear.setStyleSheet("padding: 6px 12px; background-color: #34495e; color: white;")
        btn_clear.clicked.connect(self.clear_viewer_files)
        toolbar.addWidget(btn_clear)
        toolbar.addStretch(1)

        self.viewer_info_label = QLabel("DICOM veya görüntü dosyası açın.")
        self.viewer_info_label.setStyleSheet("color:#95a5a6; font-size:11px; padding:2px 4px;")
        toolbar.addWidget(self.viewer_info_label)
        controls_layout.addLayout(toolbar)

        windowing_toolbar = QHBoxLayout()
        windowing_toolbar.setContentsMargins(0, 0, 0, 0)
        windowing_toolbar.setSpacing(4)
        windowing_toolbar.addWidget(QLabel("Pencere:"))
        for label, preset in [("Yumuşak", "soft"), ("Orijinal", "original"), ("Sert", "bone")]:
            button = QPushButton(label)
            button.setFixedHeight(23)
            button.setStyleSheet("background-color:#34495e; color:white; padding:1px 10px; font-size:10px;")
            button.clicked.connect(lambda checked=False, p=preset: self.apply_viewer_window_preset(p))
            windowing_toolbar.addWidget(button)

        self.viewer_window_label = QLabel("W/L: —")
        self.viewer_window_label.setStyleSheet("color:#bdc3c7; font-size:10px; padding:2px 6px;")
        windowing_toolbar.addWidget(self.viewer_window_label)
        windowing_toolbar.addSpacing(8)
        windowing_toolbar.addWidget(QLabel("Parlaklık:"))
        self.viewer_brightness_slider = QSlider(Qt.Horizontal)
        self.viewer_brightness_slider.setRange(-100, 100)
        self.viewer_brightness_slider.setValue(0)
        self.viewer_brightness_slider.setFixedWidth(100)
        self.viewer_brightness_slider.valueChanged.connect(self.on_viewer_brightness_changed)
        windowing_toolbar.addWidget(self.viewer_brightness_slider)
        self.viewer_brightness_label = QLabel("0")
        self.viewer_brightness_label.setStyleSheet("color:#95a5a6; font-size:10px; min-width:24px;")
        windowing_toolbar.addWidget(self.viewer_brightness_label)

        self.viewer_frame_controls = QWidget()
        frame_layout = QHBoxLayout(self.viewer_frame_controls)
        frame_layout.setContentsMargins(5, 0, 0, 0)
        frame_layout.setSpacing(3)
        frame_layout.addWidget(QLabel("Kare:"))
        self.viewer_frame_slider = QSlider(Qt.Horizontal)
        self.viewer_frame_slider.setRange(0, 0)
        self.viewer_frame_slider.setFixedWidth(90)
        self.viewer_frame_slider.valueChanged.connect(self.set_viewer_frame)
        frame_layout.addWidget(self.viewer_frame_slider)
        self.viewer_frame_label = QLabel("1/1")
        self.viewer_frame_label.setStyleSheet("color:#95a5a6; font-size:10px; min-width:34px;")
        frame_layout.addWidget(self.viewer_frame_label)
        self.btn_viewer_cine = QPushButton("▶")
        self.btn_viewer_cine.setFixedWidth(28)
        self.btn_viewer_cine.setToolTip("Çok kareli DICOM'u oynat/durdur")
        self.btn_viewer_cine.clicked.connect(self.toggle_viewer_cine)
        frame_layout.addWidget(self.btn_viewer_cine)
        self.viewer_frame_controls.setVisible(False)
        windowing_toolbar.addWidget(self.viewer_frame_controls)

        btn_dicom_info = QPushButton("DICOM Bilgileri")
        btn_dicom_info.setStyleSheet("background-color:#34495e; color:white; padding:2px 9px; font-size:10px;")
        btn_dicom_info.clicked.connect(self.show_viewer_dicom_info)
        windowing_toolbar.addWidget(btn_dicom_info)

        tools_menu = QMenu(self)
        tools_menu.addAction("90° Sola Döndür", lambda: self.rotate_viewer(-90))
        tools_menu.addAction("90° Sağa Döndür", lambda: self.rotate_viewer(90))
        tools_menu.addSeparator()
        tools_menu.addAction("Yatay Çevir", self.flip_viewer_horizontal)
        tools_menu.addAction("Dikey Çevir", self.flip_viewer_vertical)
        tools_menu.addSeparator()
        self.viewer_invert_action = tools_menu.addAction("Negatif Görünüm")
        self.viewer_invert_action.setCheckable(True)
        self.viewer_invert_action.toggled.connect(self.set_viewer_inverted)
        tools_menu.addSeparator()
        tools_menu.addAction("Görünümü Sıfırla", self.reset_viewer_transform)
        tools_button = QPushButton("Görüntü Araçları ▾")
        tools_button.setStyleSheet("background-color:#34495e; color:white; padding:2px 9px; font-size:10px;")
        tools_button.setMenu(tools_menu)
        windowing_toolbar.addWidget(tools_button)

        markup_menu = QMenu(self)
        markup_menu.addAction("Metin Ekle", lambda: self.activate_viewer_markup("text"))
        markup_menu.addAction("Ok Çiz", lambda: self.activate_viewer_markup("arrow"))
        markup_menu.addSeparator()
        markup_menu.addAction("Bu Görüntüdeki İşaretleri Temizle", self.clear_viewer_markups)
        markup_button = QPushButton("İşaretleme ▾")
        markup_button.setStyleSheet("background-color:#34495e; color:white; padding:2px 9px; font-size:10px;")
        markup_button.setMenu(markup_menu)
        windowing_toolbar.addWidget(markup_button)

        session_menu = QMenu(self)
        session_menu.addAction("Oturumu Kaydet", self.save_viewer_session)
        session_menu.addAction("Oturumu Aç", self.load_viewer_session)
        session_menu.addAction("Ölçüm / İşaretleme Listesi", self.show_viewer_markup_summary)
        session_button = QPushButton("Oturum ▾")
        session_button.setStyleSheet("background-color:#34495e; color:white; padding:2px 9px; font-size:10px;")
        session_button.setMenu(session_menu)
        windowing_toolbar.addWidget(session_button)

        export_menu = QMenu(self)
        export_menu.addAction("PNG Olarak Kaydet", lambda: self.export_viewer_snapshot("png"))
        export_menu.addAction("PDF Olarak Kaydet", lambda: self.export_viewer_snapshot("pdf"))
        export_button = QPushButton("Dışa Aktar ▾")
        export_button.setStyleSheet("background-color:#2980b9; color:white; padding:2px 9px; font-size:10px;")
        export_button.setMenu(export_menu)
        windowing_toolbar.addWidget(export_button)
        windowing_toolbar.addStretch(1)
        instructions = QLabel("Tekerlek: zoom  |  Orta fare: W/L  |  Sağ fare: kaydır")
        instructions.setStyleSheet("color:#7f8c8d; font-size:10px;")
        windowing_toolbar.addWidget(instructions)
        controls_layout.addLayout(windowing_toolbar)
        viewer_layout.addWidget(controls_box)

        viewer_splitter = QSplitter(Qt.Horizontal)
        viewer_splitter.setChildrenCollapsible(False)

        viewer_list_panel = QWidget()
        viewer_list_layout = QVBoxLayout(viewer_list_panel)
        viewer_list_layout.setContentsMargins(0, 0, 4, 0)
        viewer_list_layout.setSpacing(3)
        viewer_list_layout.addWidget(QLabel("<b>Açılan Görüntüler</b>"))

        self.viewer_file_tree = QTreeWidget()
        self.viewer_file_tree.setHeaderHidden(True)
        self.viewer_file_tree.setIconSize(QSize(52, 52))
        self.viewer_file_tree.setStyleSheet("background-color: #2b2b2b; color: #ecf0f1;")
        self.viewer_file_tree.itemSelectionChanged.connect(self.show_selected_viewer_file)
        viewer_list_layout.addWidget(self.viewer_file_tree, 1)
        viewer_splitter.addWidget(viewer_list_panel)

        self.viewer_scene = QGraphicsScene()
        self.viewer_view = InteractiveGraphicsView(self.viewer_scene, 'viewer')
        self.viewer_view.parent_app = self
        viewer_splitter.addWidget(self.viewer_view)
        viewer_splitter.setStretchFactor(0, 0)
        viewer_splitter.setStretchFactor(1, 1)
        viewer_splitter.setSizes([230, 1170])
        viewer_layout.addWidget(viewer_splitter, 1)

        self.tabs.addTab(self.viewer_tab, "Görüntüleyici")

        # Bu kısayollar yalnızca görüntüleyici sekmesi ve çocuklarında etkindir.
        viewer_shortcuts = [
            ("F", self.fit_viewer_image),
            ("M", self.toggle_viewer_cobb_measurement),
            ("L", self.toggle_viewer_length_measurement),
            ("A", lambda: self.activate_viewer_markup("arrow")),
            ("R", self.reset_viewer_transform),
            ("+", lambda: self.adjust_viewer_zoom(1.15)),
            ("-", lambda: self.adjust_viewer_zoom(1 / 1.15)),
            ("Space", self.toggle_viewer_cine),
        ]
        self.viewer_shortcuts = []
        for sequence, callback in viewer_shortcuts:
            shortcut = QShortcut(QKeySequence(sequence), self.viewer_tab)
            shortcut.setContext(Qt.WidgetWithChildrenShortcut)
            shortcut.activated.connect(callback)
            self.viewer_shortcuts.append(shortcut)

    def open_viewer_files(self):
        """Önizlemeli ortak seçim penceresinden Viewer'a dosya ekler."""
        initial_paths = [
            item.data(0, Qt.UserRole)
            for item in self._viewer_file_items()
            if item.data(0, Qt.UserRole)
        ]
        dialog = StudySelectionDialog(
            initial_files=initial_paths,
            parent=self,
            title="Görüntüleyici - Görüntü / DICOM Seç",
            selection_hint="Görüntüleyiciye eklenecek dosyaları seçin; önizleme ve DICOM bilgileri sağda gösterilir.",
            ok_label="Görüntüleyiciye Ekle",
        )
        if dialog.exec() != QDialog.Accepted:
            return
        paths = list(getattr(dialog, 'selected_paths', []))
        if not paths:
            return

        added, first_added_item = self._add_viewer_paths(paths)
        if first_added_item is not None:
            self.viewer_file_tree.setCurrentItem(first_added_item)
        if added:
            self.statusBar().showMessage(f"Görüntüleyiciye {added} dosya eklendi.")
        else:
            self.statusBar().showMessage("Seçilen dosyalardan görüntülenebilir bir görüntü bulunamadı veya zaten listede.")

    def _add_viewer_paths(self, paths):
        """Viewer listesine dosya ekler; oturum açma ve seçim penceresi ortak kullanır."""
        known_paths = {
            os.path.abspath(item.data(0, Qt.UserRole))
            for item in self._viewer_file_items()
            if item.data(0, Qt.UserRole)
        }
        added = 0
        first_added_item = None
        new_tracking_paths = []
        for path in paths:
            absolute_path = os.path.abspath(path)
            if absolute_path in known_paths:
                continue
            pixmap = self.get_viewer_file_pixmap(absolute_path)
            if pixmap.isNull():
                continue
            metadata = self._viewer_metadata(absolute_path)
            list_label = os.path.basename(absolute_path)
            if metadata is not None:
                series_label = metadata["description"] or metadata["body_part"]
                if series_label:
                    list_label += f"\n{series_label[:36]}"
            item = QTreeWidgetItem([list_label])
            item.setIcon(0, QIcon(pixmap))
            item.setToolTip(0, absolute_path)
            item.setData(0, Qt.UserRole, absolute_path)
            parent = self._viewer_tree_group(metadata)
            parent.addChild(item)
            _, added_to_tracking = self._ensure_tracking_path(absolute_path)
            if added_to_tracking:
                new_tracking_paths.append(absolute_path)
            if first_added_item is None:
                first_added_item = item
            known_paths.add(absolute_path)
            added += 1
        register_paths = getattr(self, "_register_paths", None)
        if new_tracking_paths and callable(register_paths):
            dicom_paths = [path for path in new_tracking_paths if self._viewer_is_dicom(path)]
            if dicom_paths:
                register_paths(dicom_paths)
        return added, first_added_item

    def _viewer_file_items(self):
        """Ağaçtaki gerçek dosya satırlarını, grup satırları olmadan döndürür."""
        items = []

        def collect(parent):
            for index in range(parent.childCount()):
                child = parent.child(index)
                if child.data(0, Qt.UserRole):
                    items.append(child)
                else:
                    collect(child)

        for index in range(self.viewer_file_tree.topLevelItemCount()):
            top_level = self.viewer_file_tree.topLevelItem(index)
            if top_level.data(0, Qt.UserRole):
                items.append(top_level)
            else:
                collect(top_level)
        return items

    def _viewer_tree_find_or_add(self, parent, title):
        """Aynı başlıktaki hasta/tetkik/seri gruplarını yeniden kullanır."""
        count = self.viewer_file_tree.topLevelItemCount() if parent is None else parent.childCount()
        get_item = self.viewer_file_tree.topLevelItem if parent is None else parent.child
        for index in range(count):
            candidate = get_item(index)
            if candidate.text(0) == title and not candidate.data(0, Qt.UserRole):
                return candidate

        group = QTreeWidgetItem([title])
        group.setFlags(group.flags() & ~Qt.ItemFlag.ItemIsSelectable)
        if parent is None:
            self.viewer_file_tree.addTopLevelItem(group)
        else:
            parent.addChild(group)
        group.setExpanded(True)
        return group

    def _viewer_tree_group(self, metadata):
        """Dosyayı Hasta → Tetkik → Seri hiyerarşisinde yerleştirir."""
        if metadata is None:
            patient_title, study_title, series_title = "Diğer dosyalar", "DICOM dışı", "Görüntüler"
        else:
            patient_title = f"{metadata['patient_name']} | ID: {metadata['patient_id']}"
            study_parts = [metadata['study_date'], metadata['description']]
            study_title = " | ".join(part for part in study_parts if part) or "Tetkik"
            series_parts = [metadata['modality'], metadata['body_part'], metadata['laterality']]
            series_title = " | ".join(part for part in series_parts if part) or "Seri"

        patient_group = self._viewer_tree_find_or_add(None, patient_title)
        study_group = self._viewer_tree_find_or_add(patient_group, study_title)
        return self._viewer_tree_find_or_add(study_group, series_title)

    def get_viewer_file_pixmap(self, file_path):
        """DICOM'u görüntüleyiciye özgü W/L ile 8-bit önizlemeye dönüştürür."""
        absolute_path = os.path.abspath(file_path)
        brightness = int(getattr(self, 'viewer_brightness_value', 0))
        default_wc, default_ww = self._default_window(absolute_path)
        wc, ww = self.viewer_window_settings.get(absolute_path, (default_wc, default_ww))
        frame_index = self.viewer_frame_index if absolute_path == self.viewer_current_path else 0
        cache_key = (
            absolute_path, brightness, round(float(wc), 3), round(float(ww), 3), frame_index,
            self.viewer_rotation, self.viewer_flip_horizontal, self.viewer_flip_vertical, self.viewer_inverted,
        )
        cached = self._viewer_only_pixmap_cache.get(cache_key)
        if cached is not None and not cached.isNull():
            return cached
        try:
            ds = self._viewer_dataset_cache.get(absolute_path)
            if ds is None:
                ds = pydicom.dcmread(absolute_path)
                # W/L sürüklenirken dosyayı her pikselde yeniden okumamak için
                # küçük bir çalışma seti bellekte tutulur.
                if len(self._viewer_dataset_cache) >= 8:
                    self._viewer_dataset_cache.pop(next(iter(self._viewer_dataset_cache)))
                self._viewer_dataset_cache[absolute_path] = ds
            arr = process_dicom_array(ds, brightness, wc, ww)
            if arr is not None:
                arr = np.asarray(arr)
                if arr.ndim == 3:
                    # Çok kareli DICOM'da seçili kare, RGB görüntüde gri kanal kullanılır.
                    samples = int(getattr(ds, 'SamplesPerPixel', 1) or 1)
                    if samples > 1 and arr.shape[-1] in (3, 4):
                        arr = arr[..., 0]
                    else:
                        arr = arr[min(max(0, frame_index), arr.shape[0] - 1)]
                if arr.ndim == 2:
                    if self.viewer_inverted:
                        arr = 255 - arr
                    rotations = (self.viewer_rotation // 90) % 4
                    if rotations:
                        # viewer_rotation saat yönündedir; numpy'nin yönü tersidir.
                        arr = np.rot90(arr, -rotations)
                    if self.viewer_flip_horizontal:
                        arr = np.fliplr(arr)
                    if self.viewer_flip_vertical:
                        arr = np.flipud(arr)
                    arr = np.ascontiguousarray(arr)
                    height, width = arr.shape
                    pixmap = QPixmap.fromImage(
                        QImage(arr.data, width, height, width, QImage.Format_Grayscale8).copy()
                    )
                    self._viewer_only_pixmap_cache[cache_key] = pixmap
                    return pixmap
        except Exception:
            pass
        pixmap = QPixmap(absolute_path)
        if not pixmap.isNull():
            if self.viewer_inverted:
                image = pixmap.toImage().convertToFormat(QImage.Format_ARGB32)
                image.invertPixels()
                pixmap = QPixmap.fromImage(image)
            if self.viewer_rotation:
                pixmap = pixmap.transformed(QTransform().rotate(self.viewer_rotation), Qt.SmoothTransformation)
            if self.viewer_flip_horizontal:
                pixmap = pixmap.transformed(QTransform().scale(-1, 1), Qt.SmoothTransformation)
            if self.viewer_flip_vertical:
                pixmap = pixmap.transformed(QTransform().scale(1, -1), Qt.SmoothTransformation)
            self._viewer_only_pixmap_cache[cache_key] = pixmap
        return pixmap

    def show_selected_viewer_file(self):
        selected = [item for item in self.viewer_file_tree.selectedItems() if item.data(0, Qt.UserRole)]
        if not selected:
            return
        path = selected[0].data(0, Qt.UserRole)
        self._activate_viewer_path_for_tracking(path)
        self.render_viewer_file(path, fit=True)

    def render_viewer_file(self, path, fit=False):
        """Seçili dosyayı tekrar yükler; W/L değişiminde ölçümler korunur."""
        if not path:
            return
        absolute_path = os.path.abspath(path)
        is_new_file = absolute_path != self.viewer_current_path
        if is_new_file:
            self.stop_viewer_cine()
            self.viewer_frame_count = self._viewer_frame_count_for_path(absolute_path)
            self.viewer_frame_index = 0
        pixmap = self.get_viewer_file_pixmap(path)
        if pixmap.isNull():
            self.viewer_info_label.setText("Görüntü açılamadı.")
            return

        if is_new_file or self.viewer_pixmap_item is None:
            self.viewer_scene.clear()
            self.viewer_cobb_points.clear()
            self.viewer_cobb_items.clear()
            self.viewer_length_start = None
            self.viewer_length_items.clear()
            self.viewer_annotation_items.clear()
            self.viewer_markup_items.clear()
            self.viewer_pixmap_item = self.viewer_scene.addPixmap(pixmap)
            self.viewer_current_path = os.path.abspath(path)
            if self.viewer_cobb_mode_active:
                self.viewer_cobb_mode_active = False
                self._refresh_viewer_cobb_button()
            if self.viewer_length_mode_active:
                self.viewer_length_mode_active = False
                self._refresh_viewer_length_button()
            self.viewer_view.refresh_cursor()
        else:
            self.viewer_pixmap_item.setPixmap(pixmap)

        self._add_viewer_annotations(path, pixmap)
        if is_new_file:
            self._render_viewer_saved_items(path)
        self._update_viewer_window_label()
        self._refresh_viewer_frame_controls()
        self.viewer_info_label.setText(f"{os.path.basename(path)}  |  {pixmap.width()} × {pixmap.height()} px")
        if fit:
            self.fit_viewer_image()
        else:
            self._update_viewer_zoom_label()

    def _viewer_is_dicom(self, file_path):
        path = os.path.abspath(file_path)
        if path in self._viewer_dicom_flags:
            return self._viewer_dicom_flags[path]
        try:
            ds = pydicom.dcmread(path, stop_before_pixels=True)
            is_dicom = hasattr(ds, 'SOPClassUID') or hasattr(ds, 'Rows')
        except Exception:
            is_dicom = False
        self._viewer_dicom_flags[path] = is_dicom
        return is_dicom

    def _viewer_frame_count_for_path(self, file_path):
        path = os.path.abspath(file_path)
        if path in self._viewer_frame_counts:
            return self._viewer_frame_counts[path]
        count = 1
        if self._viewer_is_dicom(path):
            try:
                ds = pydicom.dcmread(path, stop_before_pixels=True)
                count = max(1, int(getattr(ds, 'NumberOfFrames', 1) or 1))
            except Exception:
                pass
        self._viewer_frame_counts[path] = count
        return count

    def _refresh_viewer_frame_controls(self):
        is_multiframe = self.viewer_frame_count > 1
        self.viewer_frame_controls.setVisible(is_multiframe)
        self.viewer_frame_slider.blockSignals(True)
        self.viewer_frame_slider.setRange(0, max(0, self.viewer_frame_count - 1))
        self.viewer_frame_slider.setValue(min(self.viewer_frame_index, self.viewer_frame_count - 1))
        self.viewer_frame_slider.blockSignals(False)
        self.viewer_frame_label.setText(f"{self.viewer_frame_index + 1}/{self.viewer_frame_count}")
        self.btn_viewer_cine.setText("■" if self.viewer_cine_timer.isActive() else "▶")

    def set_viewer_frame(self, frame_index):
        if not self.viewer_current_path or self.viewer_frame_count <= 1:
            return
        index = max(0, min(int(frame_index), self.viewer_frame_count - 1))
        if index == self.viewer_frame_index:
            return
        self.viewer_frame_index = index
        self.clear_viewer_measurements(notify=False)
        self.render_viewer_file(self.viewer_current_path, fit=False)
        self.statusBar().showMessage(f"Çok kareli DICOM: {index + 1}/{self.viewer_frame_count}.")

    def advance_viewer_frame(self):
        if not self.viewer_current_path or self.viewer_frame_count <= 1:
            self.stop_viewer_cine()
            return
        self.set_viewer_frame((self.viewer_frame_index + 1) % self.viewer_frame_count)

    def toggle_viewer_cine(self):
        if self.viewer_frame_count <= 1:
            self.statusBar().showMessage("Bu görüntü tek karelidir.")
            return
        if self.viewer_cine_timer.isActive():
            self.stop_viewer_cine()
            self.statusBar().showMessage("Cine oynatma durduruldu.")
        else:
            self.viewer_cine_timer.start()
            self._refresh_viewer_frame_controls()
            self.statusBar().showMessage("Cine oynatma başladı.")

    def stop_viewer_cine(self):
        if self.viewer_cine_timer.isActive():
            self.viewer_cine_timer.stop()
        if hasattr(self, 'btn_viewer_cine'):
            self.btn_viewer_cine.setText("▶")

    def rotate_viewer(self, degrees):
        if self.viewer_pixmap_item is None:
            self.statusBar().showMessage("Döndürmek için önce bir görüntü açın.")
            return
        self.viewer_rotation = (self.viewer_rotation + int(degrees)) % 360
        self._refresh_viewer_after_transform("Görüntü döndürüldü.")

    def flip_viewer_horizontal(self):
        if self.viewer_pixmap_item is None:
            self.statusBar().showMessage("Çevirmek için önce bir görüntü açın.")
            return
        self.viewer_flip_horizontal = not self.viewer_flip_horizontal
        self._refresh_viewer_after_transform("Görüntü yatay çevrildi.")

    def flip_viewer_vertical(self):
        if self.viewer_pixmap_item is None:
            self.statusBar().showMessage("Çevirmek için önce bir görüntü açın.")
            return
        self.viewer_flip_vertical = not self.viewer_flip_vertical
        self._refresh_viewer_after_transform("Görüntü dikey çevrildi.")

    def set_viewer_inverted(self, enabled):
        self.viewer_inverted = bool(enabled)
        if self.viewer_pixmap_item is not None:
            self._refresh_viewer_after_transform("Negatif görünüm güncellendi.")

    def reset_viewer_transform(self):
        if self.viewer_pixmap_item is None:
            return
        self.viewer_rotation = 0
        self.viewer_flip_horizontal = False
        self.viewer_flip_vertical = False
        self.viewer_inverted = False
        self.viewer_invert_action.blockSignals(True)
        self.viewer_invert_action.setChecked(False)
        self.viewer_invert_action.blockSignals(False)
        self._refresh_viewer_after_transform("Görüntü araçları sıfırlandı.")

    def _refresh_viewer_after_transform(self, message):
        # İşaretlerin yeni piksel geometrisinde yanıltıcı olmaması için temizlenir.
        self.clear_viewer_measurements(notify=False)
        self.clear_viewer_markups()
        self._viewer_only_pixmap_cache.clear()
        self.render_viewer_file(self.viewer_current_path, fit=True)
        self.statusBar().showMessage(message)

    def _viewer_pixel_spacing(self):
        if not self.viewer_current_path or not self._viewer_is_dicom(self.viewer_current_path):
            return None
        try:
            ds = self._viewer_dataset_cache.get(self.viewer_current_path)
            if ds is None:
                ds = pydicom.dcmread(self.viewer_current_path, stop_before_pixels=True)
            spacing = getattr(ds, 'PixelSpacing', None)
            if spacing is None or len(spacing) < 2:
                return None
            return float(spacing[0]), float(spacing[1])  # satır, sütun mm
        except Exception:
            return None

    def show_viewer_dicom_info(self):
        if not self.viewer_current_path:
            self.statusBar().showMessage("Bilgi için önce bir dosya açın.")
            return
        metadata = self._viewer_metadata(self.viewer_current_path)
        if metadata is None:
            QMessageBox.information(self, "Görüntü bilgileri", f"Dosya: {os.path.basename(self.viewer_current_path)}\n\nBu dosya DICOM olarak okunamadı.")
            return
        spacing = self._viewer_pixel_spacing()
        spacing_text = "—" if spacing is None else f"{spacing[0]:.4g} × {spacing[1]:.4g} mm/piksel"
        default_wc, default_ww = self._default_window(self.viewer_current_path)
        wc, ww = self.viewer_window_settings.get(self.viewer_current_path, (default_wc, default_ww))
        text = "\n".join([
            f"Hasta: {metadata['patient_name']}",
            f"Hasta ID: {metadata['patient_id']}",
            f"Tetkik tarihi: {metadata['study_date']}",
            f"Modalite: {metadata['modality']}",
            f"Bölge / seri: {metadata['body_part'] or metadata['description'] or '—'}",
            f"Kare: {self.viewer_frame_index + 1}/{self.viewer_frame_count}",
            f"Pixel Spacing: {spacing_text}",
            f"Aktif W/L: WW {ww:.0f} | WL {wc:.0f}",
            f"Dosya: {self.viewer_current_path}",
        ])
        QMessageBox.information(self, "DICOM Bilgileri", text)

    def _viewer_metadata(self, file_path):
        path = os.path.abspath(file_path)
        if path in self._viewer_metadata_cache:
            return self._viewer_metadata_cache[path]
        if not self._viewer_is_dicom(path):
            self._viewer_metadata_cache[path] = None
            return None
        try:
            ds = pydicom.dcmread(path, stop_before_pixels=True)

            def value(name, default="—"):
                item = getattr(ds, name, None)
                text = str(item).strip() if item not in (None, "") else ""
                return text or default

            data = {
                "patient_name": value("PatientName"),
                "patient_id": value("PatientID"),
                "study_date": value("StudyDate"),
                "modality": value("Modality"),
                "body_part": value("BodyPartExamined", ""),
                "description": value("StudyDescription", value("SeriesDescription", "")),
                "laterality": value("ImageLaterality", value("Laterality", "")),
            }
        except Exception:
            data = None
        self._viewer_metadata_cache[path] = data
        return data

    def _clear_viewer_annotations(self):
        for item in self.viewer_annotation_items:
            self.viewer_scene.removeItem(item)
        self.viewer_annotation_items.clear()

    def _add_viewer_annotations(self, file_path, pixmap):
        self._clear_viewer_annotations()
        if not self.viewer_annotations_visible:
            return
        metadata = self._viewer_metadata(file_path)
        if metadata is None:
            lines = [
                f"Dosya: {os.path.basename(file_path)}",
                f"Görüntü: {pixmap.width()} × {pixmap.height()} px",
            ]
        else:
            default_wc, default_ww = self._default_window(file_path)
            wc, ww = self.viewer_window_settings.get(os.path.abspath(file_path), (default_wc, default_ww))
            body_part = metadata["body_part"] or metadata["description"] or "—"
            lines = [
                f"Hasta: {metadata['patient_name']}   ID: {metadata['patient_id']}",
                f"Tarih: {metadata['study_date']}   {metadata['modality']}   Bölge: {body_part}",
                f"WW: {ww:.0f}   WL: {wc:.0f}   {pixmap.width()} × {pixmap.height()} px",
            ]
            if self.viewer_frame_count > 1:
                lines.append(f"Kare: {self.viewer_frame_index + 1}/{self.viewer_frame_count}")
            if metadata["laterality"]:
                lines.append(f"Taraf: {metadata['laterality']}")

        annotation = self.viewer_scene.addText("\n".join(lines), QFont("Segoe UI", 9))
        annotation.setDefaultTextColor(Qt.white)
        annotation.setPos(36, 36)
        annotation.setZValue(50)
        annotation.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True)
        self.viewer_annotation_items.append(annotation)

    def set_viewer_annotations_visible(self, visible):
        self.viewer_annotations_visible = bool(visible)
        if self.viewer_current_path:
            self.render_viewer_file(self.viewer_current_path, fit=False)

    @staticmethod
    def _viewer_point_data(point):
        return [round(float(point.x()), 3), round(float(point.y()), 3)]

    @staticmethod
    def _viewer_point_from_data(data):
        return QPointF(float(data[0]), float(data[1]))

    def activate_viewer_markup(self, mode):
        if self.viewer_pixmap_item is None:
            self.statusBar().showMessage("İşaretlemek için önce bir görüntü açın.")
            return
        self.viewer_markup_mode = mode
        self.viewer_markup_start = None
        self.viewer_cobb_mode_active = False
        self.viewer_length_mode_active = False
        self._refresh_viewer_cobb_button()
        self._refresh_viewer_length_button()
        self.viewer_view.refresh_cursor()
        message = "Görüntü üzerinde metnin konumunu seçin." if mode == "text" else "Ok için başlangıç noktasını seçin."
        self.statusBar().showMessage(message)

    def handle_viewer_markup_click(self, pos):
        if not self.viewer_markup_mode or not self.viewer_current_path:
            return
        if self.viewer_markup_mode == "text":
            text, accepted = QInputDialog.getText(self, "Metin işaretlemesi", "Metin:")
            if accepted and text.strip():
                record = {"type": "text", "path": self.viewer_current_path, "position": self._viewer_point_data(pos), "text": text.strip()}
                self.viewer_markup_records.append(record)
                self._draw_viewer_markup(record)
            self.viewer_markup_mode = None
            self.viewer_view.refresh_cursor()
            return
        if self.viewer_markup_start is None:
            self.viewer_markup_start = pos
            self.statusBar().showMessage("Ok için bitiş noktasını seçin.")
            return
        record = {
            "type": "arrow", "path": self.viewer_current_path,
            "start": self._viewer_point_data(self.viewer_markup_start), "end": self._viewer_point_data(pos),
        }
        self.viewer_markup_records.append(record)
        self._draw_viewer_markup(record)
        self.viewer_markup_start = None
        self.viewer_markup_mode = None
        self.viewer_view.refresh_cursor()
        self.statusBar().showMessage("Ok işaretlemesi eklendi.")

    def _draw_viewer_markup(self, record):
        if record.get("type") == "text":
            point = self._viewer_point_from_data(record["position"])
            item = self.viewer_scene.addText(str(record.get("text", "")), QFont("Segoe UI", 11, QFont.Bold))
            item.setDefaultTextColor(Qt.magenta)
            item.setPos(point)
            item.setZValue(80)
            item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True)
            self.viewer_markup_items.append(item)
            return
        start, end = self._viewer_point_from_data(record["start"]), self._viewer_point_from_data(record["end"])
        pen = QPen(Qt.magenta, 3)
        line = self.viewer_scene.addLine(start.x(), start.y(), end.x(), end.y(), pen)
        line.setZValue(80)
        self.viewer_markup_items.append(line)
        angle = math.atan2(end.y() - start.y(), end.x() - start.x())
        arrow_size = 14
        for direction in (math.pi * 0.82, -math.pi * 0.82):
            point = QPointF(end.x() + arrow_size * math.cos(angle + direction), end.y() + arrow_size * math.sin(angle + direction))
            head = self.viewer_scene.addLine(end.x(), end.y(), point.x(), point.y(), pen)
            head.setZValue(80)
            self.viewer_markup_items.append(head)

    def _render_viewer_saved_items(self, path):
        path = os.path.abspath(path)
        for record in self.viewer_markup_records:
            if os.path.abspath(str(record.get("path", ""))) == path:
                self._draw_viewer_markup(record)
        for record in self.viewer_measurement_records:
            if os.path.abspath(str(record.get("path", ""))) == path:
                self._draw_viewer_measurement(record)

    def clear_viewer_markups(self):
        for item in self.viewer_markup_items:
            self.viewer_scene.removeItem(item)
        self.viewer_markup_items.clear()
        if self.viewer_current_path:
            self.viewer_markup_records = [
                row for row in self.viewer_markup_records
                if os.path.abspath(str(row.get("path", ""))) != self.viewer_current_path
            ]
        self.viewer_markup_mode = None
        self.viewer_markup_start = None
        self.viewer_view.refresh_cursor()
        self.statusBar().showMessage("Bu görüntüdeki işaretlemeler temizlendi.")

    def _draw_viewer_measurement(self, record):
        measurement_type = record.get("type")
        if measurement_type == "cobb":
            points = [self._viewer_point_from_data(point) for point in record.get("points", [])]
            if len(points) != 4:
                return
            for point in points:
                marker = self.viewer_scene.addEllipse(point.x() - 4, point.y() - 4, 8, 8, QPen(Qt.red, 4))
                marker.setZValue(70); self.viewer_cobb_items.append(marker)
            first = self.viewer_scene.addLine(points[0].x(), points[0].y(), points[1].x(), points[1].y(), QPen(Qt.red, 4))
            second = self.viewer_scene.addLine(points[2].x(), points[2].y(), points[3].x(), points[3].y(), QPen(Qt.cyan, 3))
            first.setZValue(70); second.setZValue(70); self.viewer_cobb_items.extend([first, second])
            label = self.viewer_scene.addText(str(record.get("label", "Cobb")), QFont("Segoe UI", 12, QFont.Bold))
            label.setDefaultTextColor(Qt.yellow); label.setPos(points[2]); label.setZValue(75)
            label.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True); self.viewer_cobb_items.append(label)
        elif measurement_type == "length":
            start, end = self._viewer_point_from_data(record["start"]), self._viewer_point_from_data(record["end"])
            for point in (start, end):
                marker = self.viewer_scene.addEllipse(point.x() - 4, point.y() - 4, 8, 8, QPen(Qt.green, 4))
                marker.setZValue(70); self.viewer_length_items.append(marker)
            line = self.viewer_scene.addLine(start.x(), start.y(), end.x(), end.y(), QPen(Qt.green, 3))
            line.setZValue(70); self.viewer_length_items.append(line)
            label = self.viewer_scene.addText(str(record.get("label", "")), QFont("Segoe UI", 11, QFont.Bold))
            label.setDefaultTextColor(Qt.green); label.setPos(end); label.setZValue(75)
            label.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True); self.viewer_length_items.append(label)

    def apply_viewer_window_preset(self, preset):
        if not self.viewer_current_path:
            self.statusBar().showMessage("Pencere ayarı için önce bir DICOM açın.")
            return
        if not self._viewer_is_dicom(self.viewer_current_path):
            self.statusBar().showMessage("Pencere ayarı yalnızca DICOM görüntülerinde kullanılabilir.")
            return
        if preset == "original":
            self.viewer_window_settings.pop(self.viewer_current_path, None)
        else:
            presets = {"soft": (300.0, 1200.0), "bone": (2000.0, 4000.0)}
            self.viewer_window_settings[self.viewer_current_path] = presets[preset]
        self._viewer_only_pixmap_cache.clear()
        self.render_viewer_file(self.viewer_current_path, fit=False)
        self.statusBar().showMessage("Görüntüleyici W/L ayarı güncellendi.")

    def on_viewer_brightness_changed(self, value):
        self.viewer_brightness_value = int(value)
        self.viewer_brightness_label.setText(str(int(value)))
        if self.viewer_current_path:
            self._viewer_only_pixmap_cache.clear()
            self.render_viewer_file(self.viewer_current_path, fit=False)

    def adjust_viewer_window_level(self, dx, dy):
        if not self.viewer_current_path or not self._viewer_is_dicom(self.viewer_current_path):
            return
        default_wc, default_ww = self._default_window(self.viewer_current_path)
        wc, ww = self.viewer_window_settings.get(self.viewer_current_path, (default_wc, default_ww))
        ww = float(np.clip(ww * (1.0 + dx * 0.01), 8.0, 20000.0))
        wc = float(wc - dy * max(1.0, ww) * 0.005)
        self.viewer_window_settings[self.viewer_current_path] = (wc, ww)
        self._viewer_only_pixmap_cache.clear()
        self.render_viewer_file(self.viewer_current_path, fit=False)

    def _update_viewer_window_label(self):
        if not self.viewer_current_path:
            self.viewer_window_label.setText("W/L: —")
            return
        if not self._viewer_is_dicom(self.viewer_current_path):
            self.viewer_window_label.setText("W/L: normal görüntü")
            return
        default_wc, default_ww = self._default_window(self.viewer_current_path)
        wc, ww = self.viewer_window_settings.get(self.viewer_current_path, (default_wc, default_ww))
        self.viewer_window_label.setText(f"W/L: WW {ww:.0f} | WL {wc:.0f}")

    def adjust_viewer_zoom(self, factor):
        if self.viewer_pixmap_item is None:
            return
        current_scale = abs(self.viewer_view.transform().m11())
        fit_scale = self._viewer_fit_scale or current_scale or 1.0
        target_scale = current_scale * float(factor)
        if target_scale < fit_scale * 0.35 or target_scale > fit_scale * 12.0:
            return
        self.viewer_view.scale(float(factor), float(factor))
        self._update_viewer_zoom_label()

    def _update_viewer_zoom_label(self):
        if self.viewer_pixmap_item is None:
            self.viewer_zoom_label.setText("Sığdır")
            return
        current_scale = abs(self.viewer_view.transform().m11())
        fit_scale = self._viewer_fit_scale or current_scale or 1.0
        percent = (current_scale / fit_scale) * 100.0
        self.viewer_zoom_label.setText("Sığdır" if abs(percent - 100.0) < 0.5 else f"%{percent:.0f}")

    def fit_viewer_image(self):
        rect = self.viewer_pixmap_item.sceneBoundingRect() if self.viewer_pixmap_item is not None else self.viewer_scene.itemsBoundingRect()
        if not rect.isNull():
            self.viewer_view.fitInView(rect, Qt.KeepAspectRatio)
            self._viewer_fit_scale = abs(self.viewer_view.transform().m11())
            self._update_viewer_zoom_label()

    def _refresh_viewer_cobb_button(self):
        if self.viewer_cobb_mode_active:
            self.btn_viewer_cobb.setText("📐 Cobb Ölçümü Aktif")
            self.btn_viewer_cobb.setStyleSheet("padding: 6px 12px; background-color: #2980b9; color: white;")
        else:
            self.btn_viewer_cobb.setText("📐 Cobb Açısı Ölç")
            self.btn_viewer_cobb.setStyleSheet("padding: 6px 12px; background-color: #34495e; color: white;")

    def toggle_viewer_cobb_measurement(self):
        if self.viewer_pixmap_item is None:
            self.statusBar().showMessage("Cobb ölçümü için önce bir görüntü açın.")
            return
        self.viewer_cobb_mode_active = not self.viewer_cobb_mode_active
        if self.viewer_cobb_mode_active:
            self.viewer_length_mode_active = False
            self.viewer_length_start = None
            self._refresh_viewer_length_button()
        self.viewer_cobb_points.clear()
        self._refresh_viewer_cobb_button()
        self.viewer_view.refresh_cursor()
        if self.viewer_cobb_mode_active:
            self.statusBar().showMessage("Cobb Ölçümü: üst vertebra için iki, alt vertebra için iki nokta seçin.")
        else:
            self.statusBar().showMessage("Cobb ölçüm modu kapatıldı.")

    def handle_viewer_cobb_click(self, pos: QPointF):
        if not self.viewer_cobb_mode_active:
            return
        self.viewer_cobb_points.append(pos)
        point = self.viewer_scene.addEllipse(pos.x() - 4, pos.y() - 4, 8, 8, QPen(Qt.red, 4))
        point.setZValue(70)
        self.viewer_cobb_items.append(point)

        n = len(self.viewer_cobb_points)
        if n == 2:
            first, second = self.viewer_cobb_points
            line = self.viewer_scene.addLine(first.x(), first.y(), second.x(), second.y(), QPen(Qt.red, 4))
            line.setZValue(70)
            self.viewer_cobb_items.append(line)
            self.statusBar().showMessage("Cobb Ölçümü: alt vertebra için iki nokta daha seçin.")
            return
        if n != 4:
            return

        third, fourth = self.viewer_cobb_points[2:]
        second_line = self.viewer_scene.addLine(third.x(), third.y(), fourth.x(), fourth.y(), QPen(Qt.cyan, 3))
        second_line.setZValue(70)
        self.viewer_cobb_items.append(second_line)
        first, second = self.viewer_cobb_points[:2]
        v1 = (second.x() - first.x(), second.y() - first.y())
        v2 = (fourth.x() - third.x(), fourth.y() - third.y())
        length1, length2 = math.hypot(*v1), math.hypot(*v2)
        if length1 > 0 and length2 > 0:
            cosine = max(-1.0, min(1.0, (v1[0] * v2[0] + v1[1] * v2[1]) / (length1 * length2)))
            angle = math.degrees(math.acos(cosine))
            label = self.viewer_scene.addText(f"Cobb: {angle:.2f}°", QFont("Segoe UI", 12, QFont.Bold))
            label.setDefaultTextColor(Qt.yellow)
            label.setPos(third)
            label.setZValue(75)
            label.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True)
            self.viewer_cobb_items.append(label)
            self.statusBar().showMessage(f"📐 Hesaplanan Cobb Açısı: {angle:.2f}°")
            self.viewer_measurement_records.append({
                "type": "cobb", "path": self.viewer_current_path,
                "points": [self._viewer_point_data(point) for point in self.viewer_cobb_points],
                "label": f"Cobb: {angle:.2f}°",
            })
        self.viewer_cobb_points.clear()
        self.viewer_cobb_mode_active = False
        self._refresh_viewer_cobb_button()
        self.viewer_view.refresh_cursor()

    def _refresh_viewer_length_button(self):
        if self.viewer_length_mode_active:
            self.btn_viewer_length.setText("↔ Mesafe Ölçümü Aktif")
            self.btn_viewer_length.setStyleSheet("padding: 6px 12px; background-color: #2980b9; color: white;")
        else:
            self.btn_viewer_length.setText("↔ Mesafe Ölç")
            self.btn_viewer_length.setStyleSheet("padding: 6px 12px; background-color: #34495e; color: white;")

    def toggle_viewer_length_measurement(self):
        if self.viewer_pixmap_item is None:
            self.statusBar().showMessage("Mesafe ölçümü için önce bir görüntü açın.")
            return
        self.viewer_length_mode_active = not self.viewer_length_mode_active
        if self.viewer_length_mode_active:
            self.viewer_cobb_mode_active = False
            self.viewer_cobb_points.clear()
            self._refresh_viewer_cobb_button()
        self.viewer_length_start = None
        self._refresh_viewer_length_button()
        self.viewer_view.refresh_cursor()
        if self.viewer_length_mode_active:
            self.statusBar().showMessage("Mesafe Ölçümü: başlangıç ve bitiş noktasını seçin.")
        else:
            self.statusBar().showMessage("Mesafe ölçüm modu kapatıldı.")

    def handle_viewer_length_click(self, pos: QPointF):
        if not self.viewer_length_mode_active:
            return
        if self.viewer_length_start is None:
            self.viewer_length_start = pos
            marker = self.viewer_scene.addEllipse(pos.x() - 4, pos.y() - 4, 8, 8, QPen(Qt.green, 4))
            marker.setZValue(70)
            self.viewer_length_items.append(marker)
            self.statusBar().showMessage("Mesafe Ölçümü: bitiş noktasını seçin.")
            return

        start = self.viewer_length_start
        end = pos
        end_marker = self.viewer_scene.addEllipse(end.x() - 4, end.y() - 4, 8, 8, QPen(Qt.green, 4))
        line = self.viewer_scene.addLine(start.x(), start.y(), end.x(), end.y(), QPen(Qt.green, 3))
        end_marker.setZValue(70)
        line.setZValue(70)
        self.viewer_length_items.extend([end_marker, line])

        dx, dy = end.x() - start.x(), end.y() - start.y()
        spacing = self._viewer_pixel_spacing()
        if spacing is None:
            text = f"{math.hypot(dx, dy):.1f} px"
        else:
            row_mm, column_mm = spacing
            if self.viewer_rotation % 180:
                x_mm, y_mm = row_mm, column_mm
            else:
                x_mm, y_mm = column_mm, row_mm
            distance_mm = math.hypot(dx * x_mm, dy * y_mm)
            text = f"{distance_mm / 10:.2f} cm" if distance_mm >= 100 else f"{distance_mm:.1f} mm"

        label = self.viewer_scene.addText(text, QFont("Segoe UI", 11, QFont.Bold))
        label.setDefaultTextColor(Qt.green)
        label.setPos(end)
        label.setZValue(75)
        label.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True)
        self.viewer_length_items.append(label)
        self.viewer_length_start = None
        self.viewer_length_mode_active = False
        self._refresh_viewer_length_button()
        self.viewer_view.refresh_cursor()
        self.viewer_measurement_records.append({
            "type": "length", "path": self.viewer_current_path,
            "start": self._viewer_point_data(start), "end": self._viewer_point_data(end), "label": text,
        })
        self.statusBar().showMessage(f"Ölçülen mesafe: {text}")

    def clear_viewer_measurements(self, notify=True):
        for item in self.viewer_cobb_items:
            self.viewer_scene.removeItem(item)
        for item in self.viewer_length_items:
            self.viewer_scene.removeItem(item)
        self.viewer_cobb_items.clear()
        self.viewer_cobb_points.clear()
        self.viewer_length_items.clear()
        self.viewer_length_start = None
        self.viewer_cobb_mode_active = False
        self.viewer_length_mode_active = False
        if self.viewer_current_path:
            self.viewer_measurement_records = [
                row for row in self.viewer_measurement_records
                if os.path.abspath(str(row.get("path", ""))) != self.viewer_current_path
            ]
        self._refresh_viewer_cobb_button()
        self._refresh_viewer_length_button()
        self.viewer_view.refresh_cursor()
        if notify:
            self.statusBar().showMessage("Görüntüleyici ölçümleri temizlendi.")

    def clear_viewer_files(self):
        self.stop_viewer_cine()
        self.viewer_file_tree.clear()
        self.viewer_scene.clear()
        self.viewer_current_path = None
        self.viewer_pixmap_item = None
        self.viewer_cobb_points.clear()
        self.viewer_cobb_items.clear()
        self.viewer_length_start = None
        self.viewer_length_items.clear()
        self.viewer_annotation_items.clear()
        self.viewer_markup_items.clear()
        self.viewer_markup_records.clear()
        self.viewer_measurement_records.clear()
        self.viewer_markup_mode = None
        self.viewer_markup_start = None
        self.viewer_cobb_mode_active = False
        self.viewer_length_mode_active = False
        self._refresh_viewer_cobb_button()
        self._refresh_viewer_length_button()
        self._viewer_fit_scale = 0.0
        self.viewer_frame_index = 0
        self.viewer_frame_count = 1
        self._viewer_only_pixmap_cache.clear()
        self._viewer_dataset_cache.clear()
        self._viewer_frame_counts.clear()
        self._refresh_viewer_frame_controls()
        self._update_viewer_window_label()
        self._update_viewer_zoom_label()
        self.viewer_info_label.setText("DICOM veya görüntü dosyası açın.")
        self.statusBar().showMessage("Görüntüleyici listesi temizlendi.")

    def _viewer_session_paths(self):
        return [
            os.path.abspath(item.data(0, Qt.UserRole))
            for item in self._viewer_file_items()
            if item.data(0, Qt.UserRole)
        ]

    def save_viewer_session(self):
        paths = self._viewer_session_paths()
        if not paths:
            self.statusBar().showMessage("Oturum kaydı için önce en az bir görüntü açın.")
            return
        suggested = "goruntuleyici_oturumu.json"
        output, _ = QFileDialog.getSaveFileName(self, "Görüntüleyici oturumunu kaydet", suggested, "Görüntüleyici oturumu (*.json)")
        if not output:
            return
        if not output.lower().endswith(".json"):
            output += ".json"
        session = {
            "format": "ScoliosisFollowUpViewerSession",
            "version": 1,
            "paths": paths,
            "current_path": self.viewer_current_path,
            "brightness": self.viewer_brightness_value,
            "window_settings": {path: list(value) for path, value in self.viewer_window_settings.items() if path in paths},
            "rotation": self.viewer_rotation,
            "flip_horizontal": self.viewer_flip_horizontal,
            "flip_vertical": self.viewer_flip_vertical,
            "inverted": self.viewer_inverted,
            "annotations_visible": self.viewer_annotations_visible,
            "markups": self.viewer_markup_records,
            "measurements": self.viewer_measurement_records,
            "saved_at": datetime.datetime.now().isoformat(timespec="seconds"),
        }
        try:
            with open(output, "w", encoding="utf-8") as handle:
                json.dump(session, handle, ensure_ascii=False, indent=2)
            self.statusBar().showMessage(f"Görüntüleyici oturumu kaydedildi: {output}")
        except OSError as exc:
            QMessageBox.warning(self, "Oturum kaydı", f"Oturum kaydedilemedi:\n{exc}")

    def load_viewer_session(self):
        source, _ = QFileDialog.getOpenFileName(self, "Görüntüleyici oturumunu aç", "", "Görüntüleyici oturumu (*.json)")
        if not source:
            return
        try:
            with open(source, "r", encoding="utf-8") as handle:
                session = json.load(handle)
            if session.get("format") != "ScoliosisFollowUpViewerSession":
                raise ValueError("Bu dosya desteklenen bir görüntüleyici oturumu değil.")
            paths = [os.path.abspath(str(path)) for path in session.get("paths", []) if os.path.isfile(str(path))]
            if not paths:
                raise ValueError("Oturumdaki görüntü dosyaları bu bilgisayarda bulunamadı.")
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            QMessageBox.warning(self, "Oturum aç", f"Oturum açılamadı:\n{exc}")
            return

        self.clear_viewer_files()
        self.viewer_brightness_value = int(session.get("brightness", 0))
        self.viewer_brightness_slider.blockSignals(True)
        self.viewer_brightness_slider.setValue(self.viewer_brightness_value)
        self.viewer_brightness_slider.blockSignals(False)
        self.viewer_brightness_label.setText(str(self.viewer_brightness_value))
        self.viewer_window_settings = {
            os.path.abspath(path): (float(value[0]), float(value[1]))
            for path, value in dict(session.get("window_settings", {})).items()
            if isinstance(value, (list, tuple)) and len(value) == 2
        }
        self.viewer_rotation = int(session.get("rotation", 0)) % 360
        self.viewer_flip_horizontal = bool(session.get("flip_horizontal", False))
        self.viewer_flip_vertical = bool(session.get("flip_vertical", False))
        self.viewer_inverted = bool(session.get("inverted", False))
        self.viewer_invert_action.blockSignals(True)
        self.viewer_invert_action.setChecked(self.viewer_inverted)
        self.viewer_invert_action.blockSignals(False)
        self.viewer_annotations_visible = bool(session.get("annotations_visible", True))
        self.btn_viewer_annotations.blockSignals(True)
        self.btn_viewer_annotations.setChecked(self.viewer_annotations_visible)
        self.btn_viewer_annotations.blockSignals(False)
        self.viewer_markup_records = [row for row in session.get("markups", []) if isinstance(row, dict)]
        self.viewer_measurement_records = [row for row in session.get("measurements", []) if isinstance(row, dict)]
        self._add_viewer_paths(paths)
        current = os.path.abspath(str(session.get("current_path", paths[0])))
        for item in self._viewer_file_items():
            if os.path.abspath(str(item.data(0, Qt.UserRole))) == current:
                self.viewer_file_tree.setCurrentItem(item)
                break
        else:
            self.viewer_file_tree.setCurrentItem(self._viewer_file_items()[0])
        self.statusBar().showMessage(f"Görüntüleyici oturumu açıldı: {os.path.basename(source)}")

    def show_viewer_markup_summary(self):
        if not self.viewer_current_path:
            self.statusBar().showMessage("Liste için önce bir görüntü açın.")
            return
        current = self.viewer_current_path
        markups = [row for row in self.viewer_markup_records if os.path.abspath(str(row.get("path", ""))) == current]
        measures = [row for row in self.viewer_measurement_records if os.path.abspath(str(row.get("path", ""))) == current]
        lines = [f"Metin/ok işaretlemesi: {len(markups)}", f"Ölçüm: {len(measures)}"]
        for index, row in enumerate(measures, 1):
            lines.append(f"{index}. {'Cobb' if row.get('type') == 'cobb' else 'Mesafe'} — {row.get('label', '—')}")
        QMessageBox.information(self, "Ölçüm / İşaretleme Listesi", "\n".join(lines))

    def _viewer_export_image(self):
        if self.viewer_pixmap_item is None:
            return None
        source = self.viewer_pixmap_item.sceneBoundingRect()
        if source.isEmpty():
            return None
        longest_side = max(source.width(), source.height())
        scale = min(1.0, 4096.0 / longest_side) if longest_side else 1.0
        width = max(1, int(round(source.width() * scale)))
        height = max(1, int(round(source.height() * scale)))
        image = QImage(width, height, QImage.Format_ARGB32)
        image.fill(Qt.black)
        painter = QPainter(image)
        self.viewer_scene.render(painter, QRectF(0, 0, width, height), source)
        painter.end()
        return image

    def export_viewer_snapshot(self, format_name):
        if self.viewer_pixmap_item is None:
            self.statusBar().showMessage("Dışa aktarmak için önce bir görüntü açın.")
            return
        is_pdf = str(format_name).lower() == "pdf"
        extension = "pdf" if is_pdf else "png"
        label = "PDF" if is_pdf else "PNG"
        suggested = f"{os.path.splitext(os.path.basename(self.viewer_current_path))[0]}_viewer.{extension}"
        output_path, _ = QFileDialog.getSaveFileName(self, f"Görüntüleyiciyi {label} olarak kaydet", suggested, f"{label} (*.{extension})")
        if not output_path:
            return
        if not output_path.lower().endswith(f".{extension}"):
            output_path += f".{extension}"
        image = self._viewer_export_image()
        if image is None:
            QMessageBox.warning(self, "Dışa aktar", "Görüntü dışa aktarılamadı.")
            return
        try:
            if is_pdf:
                writer = QPdfWriter(output_path)
                writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
                writer.setResolution(150)
                painter = QPainter(writer)
                page = QRectF(painter.viewport())
                ratio = min(page.width() / image.width(), page.height() / image.height())
                target = QRectF(
                    page.x() + (page.width() - image.width() * ratio) / 2,
                    page.y() + (page.height() - image.height() * ratio) / 2,
                    image.width() * ratio,
                    image.height() * ratio,
                )
                painter.drawImage(target, image)
                painter.end()
            elif not image.save(output_path, "PNG"):
                raise RuntimeError("PNG dosyası yazılamadı.")
            self.statusBar().showMessage(f"Görüntüleyici {label} olarak kaydedildi: {output_path}")
        except Exception as exc:
            QMessageBox.warning(self, "Dışa aktar", f"{label} oluşturulamadı:\n{exc}")

    def init_workspace_tab(self):
        """Skolyoz Takip çalışma alanı.

        Amaç: mevcut arayüzdeki kontrolleri koruyup üstteki gereksiz dikey
        boşluğu kaldırmak ve görüntü alanını mümkün olduğunca büyütmek.
        """
        self.workspace_tab = QWidget()
        workspace_layout = QVBoxLayout(self.workspace_tab)
        workspace_layout.setContentsMargins(8, 6, 8, 6)
        workspace_layout.setSpacing(5)

        # ------------------------------------------------------------
        # KOMPAKT ÜST KONTROL ALANI
        # ------------------------------------------------------------
        controls_box = QWidget()
        controls_box.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        controls_box.setFixedHeight(66)
        controls_layout = QVBoxLayout(controls_box)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_layout.setSpacing(4)

        toolbar_layout = QHBoxLayout()
        toolbar_layout.setContentsMargins(0, 0, 0, 0)
        toolbar_layout.setSpacing(5)

        self.btn_load_dicom = QPushButton("📁 Grafikleri / DICOM Yükle")
        self.btn_load_dicom.setStyleSheet("padding: 6px 12px; font-weight: bold; background-color: #27ae60; color: white;")
        self.btn_load_dicom.clicked.connect(self.load_dicoms)

        self.btn_side_by_side = QPushButton("▤ Yan Yana Mukayese")
        self.btn_side_by_side.setStyleSheet("padding: 6px 12px; background-color: #2980b9; color: white;")
        self.btn_side_by_side.clicked.connect(self.set_side_by_side_mode)

        self.btn_overlay = QPushButton("🔲 Üst Üste (Overlay) Çakıştır")
        self.btn_overlay.setStyleSheet("padding: 6px 12px; background-color: #34495e; color: white;")
        self.btn_overlay.clicked.connect(self.set_overlay_mode)

        self.btn_measure_cobb = QPushButton("📐 Cobb Açısı Ölç")
        self.btn_measure_cobb.setStyleSheet("padding: 6px 12px; background-color: #34495e; color: white;")
        self.btn_measure_cobb.clicked.connect(self.toggle_cobb_measurement)

        toolbar_layout.addWidget(self.btn_load_dicom)
        toolbar_layout.addWidget(self.btn_side_by_side)
        toolbar_layout.addWidget(self.btn_overlay)
        toolbar_layout.addWidget(self.btn_measure_cobb)
        toolbar_layout.addStretch(1)

        toolbar_layout.addWidget(QLabel("Parlaklık:"))
        self.brightness_slider = QSlider(Qt.Horizontal)
        self.brightness_slider.setRange(-100, 100)
        self.brightness_slider.setValue(0)
        self.brightness_slider.setFixedWidth(100)
        self.brightness_slider.valueChanged.connect(self.update_viewers)
        toolbar_layout.addWidget(self.brightness_slider)

        self.lbl_overlay_offset = QLabel("ΔX 0 | ΔY 0 | Z 1.00x")
        self.lbl_overlay_offset.setStyleSheet("color:#95a5a6; font-size:10px; padding:2px 4px;")
        toolbar_layout.addWidget(self.lbl_overlay_offset)

        toolbar_layout.addWidget(QLabel("Saydamlık:"))
        self.overlay_opacity_slider = QSlider(Qt.Horizontal)
        self.overlay_opacity_slider.setRange(10, 90)
        self.overlay_opacity_slider.setValue(50)
        self.overlay_opacity_slider.setFixedWidth(75)
        self.overlay_opacity_slider.setToolTip("Overlay saydamlığı")
        self.overlay_opacity_slider.valueChanged.connect(self.on_overlay_opacity_changed)
        toolbar_layout.addWidget(self.overlay_opacity_slider)

        controls_layout.addLayout(toolbar_layout)

        # İkinci satır: W/L preset + hassas Overlay kontrolleri.
        bottom_controls = QHBoxLayout()
        bottom_controls.setContentsMargins(0, 0, 0, 0)
        bottom_controls.setSpacing(4)

        bottom_controls.addWidget(QLabel("Pencere:"))
        for label, key in [("Yumuşak", "soft"), ("Orijinal", "original"), ("Sert", "bone")]:
            b = QPushButton(label)
            b.setFixedHeight(24)
            b.setStyleSheet("background-color:#34495e; color:white; padding:1px 10px; font-size:10px;")
            b.clicked.connect(lambda checked=False, k=key: self.apply_window_preset(k))
            bottom_controls.addWidget(b)

        self.lbl_windowing = QLabel("W/L: DICOM varsayılanı")
        self.lbl_windowing.setStyleSheet("color:#bdc3c7; padding:2px 6px; font-size:10px;")
        bottom_controls.addWidget(self.lbl_windowing)
        bottom_controls.addSpacing(8)

        bottom_controls.addWidget(QLabel("Zoom:"))
        self.overlay_zoom_slider = QSlider(Qt.Horizontal)
        self.overlay_zoom_slider.setRange(50, 160)
        self.overlay_zoom_slider.setValue(100)
        self.overlay_zoom_slider.setFixedWidth(90)
        self.overlay_zoom_slider.setToolTip("Overlay ölçeği / zoom")
        self.overlay_zoom_slider.valueChanged.connect(self.on_overlay_zoom_changed)
        bottom_controls.addWidget(self.overlay_zoom_slider)

        bottom_controls.addWidget(QLabel("X:"))
        self.overlay_x_slider = QSlider(Qt.Horizontal)
        self.overlay_x_slider.setRange(-3000, 3000)
        self.overlay_x_slider.setValue(0)
        self.overlay_x_slider.setFixedWidth(90)
        self.overlay_x_slider.setToolTip("Overlay yatay kaydırma")
        self.overlay_x_slider.valueChanged.connect(self.on_overlay_x_changed)
        bottom_controls.addWidget(self.overlay_x_slider)

        bottom_controls.addWidget(QLabel("Y:"))
        self.overlay_y_slider = QSlider(Qt.Horizontal)
        self.overlay_y_slider.setRange(-3000, 3000)
        self.overlay_y_slider.setValue(0)
        self.overlay_y_slider.setFixedWidth(90)
        self.overlay_y_slider.setToolTip("Overlay dikey kaydırma")
        self.overlay_y_slider.valueChanged.connect(self.on_overlay_y_changed)
        bottom_controls.addWidget(self.overlay_y_slider)

        self.btn_overlay_reset = QPushButton("Overlay Sıfırla")
        self.btn_overlay_reset.setFixedHeight(24)
        self.btn_overlay_reset.clicked.connect(self.reset_overlay_adjustment)
        bottom_controls.addWidget(self.btn_overlay_reset)
        bottom_controls.addStretch(1)

        controls_layout.addLayout(bottom_controls)
        workspace_layout.addWidget(controls_box)

        # ------------------------------------------------------------
        # ANA ÇALIŞMA ALANI — görüntü her zaman öncelikli
        # ------------------------------------------------------------
        main_splitter = QSplitter(Qt.Horizontal)
        main_splitter.setChildrenCollapsible(False)
        main_splitter.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        left_panel = QWidget()
        left_panel.setMinimumWidth(180)
        left_panel.setMaximumWidth(280)
        left_panel.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 4, 0)
        left_layout.setSpacing(3)

        left_header = QLabel("<b>Hastalar / Tetkikler / Seriler</b>")
        left_header.setStyleSheet("padding:2px 2px; color:#ecf0f1;")
        left_layout.addWidget(left_header)

        # Mevcut takip/overlay algoritması düz listeyi veri modeli olarak
        # kullanır. Görünür tarafta ise aynı dosyalar Viewer ile birebir aynı
        # Hasta → Tetkik → Seri ağacı içinde gösterilir.
        self.study_list_widget = QListWidget()
        self.study_list_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.study_list_widget.setIconSize(QSize(44, 44))
        self.study_list_widget.setSelectionMode(QListWidget.MultiSelection)
        self._study_tree_syncing = False
        self.study_list_widget.itemSelectionChanged.connect(self._on_study_model_selection_changed)

        self.study_tree_widget = QTreeWidget()
        self.study_tree_widget.setHeaderHidden(True)
        self.study_tree_widget.setIconSize(QSize(44, 44))
        self.study_tree_widget.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
        self.study_tree_widget.setStyleSheet("background-color: #2b2b2b; color: #ecf0f1;")
        self.study_tree_widget.itemSelectionChanged.connect(self._on_study_tree_selection_changed)
        left_layout.addWidget(self.study_tree_widget, 1)

        main_splitter.addWidget(left_panel)

        self.viewer_container = QWidget()
        self.viewer_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.viewer_layout = QHBoxLayout(self.viewer_container)
        self.viewer_layout.setContentsMargins(0, 0, 0, 0)
        self.viewer_layout.setSpacing(3)

        self.scene_left = QGraphicsScene()
        self.view_left = InteractiveGraphicsView(self.scene_left, 'left')
        self.view_left.parent_app = self
        self.view_left.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.scene_right = QGraphicsScene()
        self.view_right = InteractiveGraphicsView(self.scene_right, 'right')
        self.view_right.parent_app = self
        self.view_right.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.viewer_layout.addWidget(self.view_left, 1)
        self.viewer_layout.addWidget(self.view_right, 1)
        main_splitter.addWidget(self.viewer_container)

        # Liste sabit dar; kalan alan tamamen görüntüye.
        main_splitter.setStretchFactor(0, 0)
        main_splitter.setStretchFactor(1, 1)
        main_splitter.setSizes([215, 1180])

        workspace_layout.addWidget(main_splitter, 1)
        workspace_layout.setStretch(0, 0)
        workspace_layout.setStretch(1, 1)

        self.tabs.addTab(self.workspace_tab, "Skolyoz Takip")

    def _study_tree_file_items(self):
        """Takip ağacındaki yalnızca gerçek dosya satırlarını döndürür."""
        items = []

        def collect(parent):
            for index in range(parent.childCount()):
                child = parent.child(index)
                if child.data(0, Qt.UserRole):
                    items.append(child)
                else:
                    collect(child)

        for index in range(self.study_tree_widget.topLevelItemCount()):
            top_level = self.study_tree_widget.topLevelItem(index)
            if top_level.data(0, Qt.UserRole):
                items.append(top_level)
            else:
                collect(top_level)
        return items

    def _study_tree_find_or_add(self, parent, title):
        count = self.study_tree_widget.topLevelItemCount() if parent is None else parent.childCount()
        get_item = self.study_tree_widget.topLevelItem if parent is None else parent.child
        for index in range(count):
            candidate = get_item(index)
            if candidate.text(0) == title and not candidate.data(0, Qt.UserRole):
                return candidate

        group = QTreeWidgetItem([title])
        group.setFlags(group.flags() & ~Qt.ItemFlag.ItemIsSelectable)
        if parent is None:
            self.study_tree_widget.addTopLevelItem(group)
        else:
            parent.addChild(group)
        group.setExpanded(True)
        return group

    def _study_tree_group(self, metadata):
        """Viewer ile aynı Hasta → Tetkik → Seri gruplamasını üretir."""
        if metadata is None:
            patient_title, study_title, series_title = "Diğer dosyalar", "DICOM dışı", "Görüntüler"
        else:
            patient_title = f"{metadata['patient_name']} | ID: {metadata['patient_id']}"
            study_title = " | ".join(part for part in (metadata['study_date'], metadata['description']) if part) or "Tetkik"
            series_title = " | ".join(
                part for part in (metadata['modality'], metadata['body_part'], metadata['laterality']) if part
            ) or "Seri"
        patient_group = self._study_tree_find_or_add(None, patient_title)
        study_group = self._study_tree_find_or_add(patient_group, study_title)
        return self._study_tree_find_or_add(study_group, series_title)

    def _add_path_to_study_tree(self, path, model_item=None):
        """Gizli takip veri modelindeki dosyayı görünür hasta ağacına ekler."""
        absolute_path = os.path.abspath(path)
        for item in self._study_tree_file_items():
            item_path = str(item.data(0, Qt.UserRole) or "")
            if item_path and os.path.abspath(item_path) == absolute_path:
                return item

        pixmap = self.get_image_pixmap(absolute_path)
        metadata = self._viewer_metadata(absolute_path)
        label = os.path.basename(absolute_path)
        if metadata is not None:
            series_label = metadata["description"] or metadata["body_part"]
            if series_label:
                label += f"\n{series_label[:36]}"
        item = QTreeWidgetItem([label])
        item.setIcon(0, QIcon(pixmap) if not pixmap.isNull() else QIcon())
        item.setData(0, Qt.UserRole, absolute_path)
        item.setToolTip(0, absolute_path)
        self._study_tree_group(metadata).addChild(item)
        return item

    def _ensure_tracking_path(self, path):
        """Bir dosyayı takip veri modeline ve görünür ağaca tek kez ekler."""
        absolute_path = os.path.abspath(path)
        for index in range(self.study_list_widget.count()):
            item = self.study_list_widget.item(index)
            item_path = str(item.data(Qt.UserRole) or "")
            if item_path and os.path.abspath(item_path) == absolute_path:
                self._add_path_to_study_tree(absolute_path, item)
                return item, False

        key = os.path.basename(absolute_path)
        if key in self.loaded_files and os.path.abspath(self.loaded_files[key]) != absolute_path:
            key = f"{os.path.basename(absolute_path)}  |  {os.path.dirname(absolute_path)}"
        self.loaded_files[key] = absolute_path

        pixmap = self.get_image_pixmap(absolute_path)
        item = QListWidgetItem(QIcon(pixmap) if not pixmap.isNull() else QIcon(), key)
        item.setData(Qt.UserRole, absolute_path)
        self.study_list_widget.addItem(item)
        self._add_path_to_study_tree(absolute_path, item)
        return item, True

    def _sync_study_tree_selection_from_model(self):
        selected_paths = {
            os.path.abspath(str(item.data(Qt.UserRole)))
            for item in self.study_list_widget.selectedItems()
            if item.data(Qt.UserRole)
        }
        self._study_tree_syncing = True
        try:
            self.study_tree_widget.clearSelection()
            for item in self._study_tree_file_items():
                path = str(item.data(0, Qt.UserRole) or "")
                if path and os.path.abspath(path) in selected_paths:
                    item.setSelected(True)
        finally:
            self._study_tree_syncing = False

    def _on_study_model_selection_changed(self):
        if self._study_tree_syncing:
            return
        self._sync_study_tree_selection_from_model()
        self.update_viewers()

    def _on_study_tree_selection_changed(self):
        if self._study_tree_syncing:
            return
        selected_paths = {
            os.path.abspath(str(item.data(0, Qt.UserRole)))
            for item in self.study_tree_widget.selectedItems()
            if item.data(0, Qt.UserRole)
        }
        self._study_tree_syncing = True
        try:
            self.study_list_widget.clearSelection()
            for index in range(self.study_list_widget.count()):
                item = self.study_list_widget.item(index)
                path = str(item.data(Qt.UserRole) or "")
                if path and os.path.abspath(path) in selected_paths:
                    item.setSelected(True)
        finally:
            self._study_tree_syncing = False
        self.update_viewers()

    def _activate_viewer_path_for_tracking(self, path):
        """Viewer seçimini takip modülünün aktif hasta/tetkik seçimine taşır."""
        if not path or not os.path.isfile(path):
            return
        item, added = self._ensure_tracking_path(path)
        self._study_tree_syncing = True
        try:
            self.study_list_widget.clearSelection()
            item.setSelected(True)
            self.study_list_widget.setCurrentItem(item)
        finally:
            self._study_tree_syncing = False
        self._sync_study_tree_selection_from_model()
        self.update_viewers()

        # Modüler çalıştırıcı etkinse Viewer'dan açılan DICOM da veritabanındaki
        # hasta/tetkik geçmişine eklenir. Ana checkpoint tek başına çalışırken
        # bu kanca yoktur ve güvenle atlanır.
        register_paths = getattr(self, "_register_paths", None)
        if added and callable(register_paths) and self._viewer_is_dicom(path):
            register_paths([path])

    def init_stitcher_tab(self):
        self.stitcher_tab = QWidget()
        stitcher_layout = QHBoxLayout(self.stitcher_tab)
        stitcher_layout.setContentsMargins(10, 10, 10, 10)
        
        left_pane = QVBoxLayout()
        header_box = QHBoxLayout()
        
        title_box_widget = QWidget()
        title_box_layout = QVBoxLayout(title_box_widget)
        title_box_layout.setContentsMargins(0, 0, 0, 0)
        
        title_lbl = QLabel("<b>DICOM Omurga Birleştirme</b>")
        title_lbl.setStyleSheet("color: #ecf0f1; font-size: 14px;")
        sub_desc = QLabel("Servikal • Dorsal • Lomber | Otomatik hizalama ve manuel düzeltme")
        sub_desc.setStyleSheet("color: #95a5a6; font-size: 11px;")
        
        title_box_layout.addWidget(title_lbl)
        title_box_layout.addWidget(sub_desc)
        header_box.addWidget(title_box_widget)
        header_box.addStretch()
        
        self.lbl_status_badge = QLabel("Aşama hazırdır — kontrol edin")
        self.lbl_status_badge.setStyleSheet("background-color: #2c3e50; color: #3498db; padding: 5px 10px; border-radius: 4px; font-weight: bold; font-size: 11px;")
        header_box.addWidget(self.lbl_status_badge)
        left_pane.addLayout(header_box)
        
        self.stitch_scene = QGraphicsScene()
        self.stitch_view = InteractiveGraphicsView(self.stitch_scene, 'stitch')
        self.stitch_view.parent_app = self
        left_pane.addWidget(self.stitch_view)
        
        stitcher_layout.addLayout(left_pane, stretch=3)
        
        right_panel = QWidget()
        right_panel.setStyleSheet("background-color: #2b2b2b; border-radius: 6px;")
        right_panel.setMaximumWidth(340)
        self.right_panel_layout = QVBoxLayout(right_panel)
        self.right_panel_layout.setContentsMargins(10, 10, 10, 10)

        # Parçalar, iş akışının ilk adımı olduğu için sağ panelin en üstünde
        # yer alır: önce Servikal/Dorsal/Lomber seçilir, sonra hizalama
        # kontrolleri kullanılır.
        parts_loader_box = QVBoxLayout()
        parts_loader_box.addWidget(QLabel("<b>Omurga Parçaları</b>"))

        for p_key, p_name in [('servical', 'Servikal Yükle'), ('dorsal', 'Dorsal Yükle'), ('lumbar', 'Lomber Yükle')]:
            row_box = QHBoxLayout()
            btn_load = QPushButton(p_name)
            btn_load.setStyleSheet("background-color: #34495e; color: white; padding: 4px;")
            btn_load.clicked.connect(lambda checked=False, k=p_key: self.open_preview_dialog(k))
            self.stitch_load_buttons[p_key] = btn_load
            if self.stitch_files.get(p_key):
                btn_load.setText(f"{p_name.replace(' Yükle', '')} ✓")

            btn_rem = QPushButton("Kaldır")
            btn_rem.setStyleSheet("background-color: #c0392b; color: white; padding: 4px;")
            btn_rem.clicked.connect(lambda checked=False, k=p_key: self.remove_stitch_part(k))
            btn_rem.setVisible(False)
            self.stitch_remove_buttons[p_key] = btn_rem

            row_box.addWidget(btn_load)
            row_box.addWidget(btn_rem)
            parts_loader_box.addLayout(row_box)

        self.right_panel_layout.addLayout(parts_loader_box)
        
        self.stitch_top_preview_view = QGraphicsView()
        self.stitch_top_preview_scene = QGraphicsScene()
        self.stitch_top_preview_view.setScene(self.stitch_top_preview_scene)
        self.stitch_top_preview_view.setFixedHeight(70)
        self.stitch_top_preview_view.setStyleSheet("background-color: #111; border: 1px dashed #555;")
        self.right_panel_layout.addWidget(self.stitch_top_preview_view)
        
        self.right_panel_layout.addWidget(QLabel("<b>Manuel Nokta Modu</b>"))
        mode_btns_layout = QHBoxLayout()
        self.btn_mode_off = QPushButton("Kapalı")
        self.btn_mode_off.setStyleSheet("background-color: #2980b9; color: white; padding: 5px;")
        self.btn_mode_off.clicked.connect(self.toggle_manual_point_mode)
        self.btn_clear_pts = QPushButton("Noktaları Temizle")
        self.btn_clear_pts.setStyleSheet("background-color: #34495e; color: white; padding: 5px;")
        self.btn_clear_pts.clicked.connect(self.clear_manual_points)
        mode_btns_layout.addWidget(self.btn_mode_off)
        mode_btns_layout.addWidget(self.btn_clear_pts)
        self.right_panel_layout.addLayout(mode_btns_layout)
        
        self.lbl_manual_mode_info = QLabel("<font color='#95a5a6' size='2'>Otomatik hizalama kullanılacak.</font>")
        self.lbl_manual_mode_info.setWordWrap(True)
        self.right_panel_layout.addWidget(self.lbl_manual_mode_info)

        self.btn_manual_next_stage = QPushButton("Aşama tamamla → sonraki parçaya geç")
        self.btn_manual_next_stage.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold; padding: 7px;")
        self.btn_manual_next_stage.setVisible(False)
        self.btn_manual_next_stage.setEnabled(False)
        self.btn_manual_next_stage.setMinimumHeight(36)
        self.btn_manual_next_stage.clicked.connect(self.advance_manual_stage)
        self.right_panel_layout.addWidget(self.btn_manual_next_stage)
        
        self.chk_histogram = QCheckBox("Pozlama Eşitleme (Histogram Matching)")
        self.chk_histogram.setStyleSheet("color: #ecf0f1; margin-top: 5px;")
        self.chk_histogram.stateChanged.connect(self.update_stitched_spine)
        self.right_panel_layout.addWidget(self.chk_histogram)
        lbl_hist_note = QLabel("<font color='#7f8c8d' size='2'>(Sadece görseldir; hizalama hesabını etkilemez)</font>")
        lbl_hist_note.setWordWrap(True)
        self.right_panel_layout.addWidget(lbl_hist_note)
        
        self.chk_auto_align = QCheckBox("Otomatik Hizalama (kenar korelasyonu)")
        self.chk_auto_align.setStyleSheet("color: #ecf0f1; margin-top: 3px;")
        self.chk_auto_align.setChecked(True)
        self.chk_auto_align.stateChanged.connect(self.update_stitched_spine)
        self.right_panel_layout.addWidget(self.chk_auto_align)
        lbl_auto_note = QLabel("<font color='#7f8c8d' size='2'>Çakışma bandını kenarlarına göre otomatik hizalar.</font>")
        lbl_auto_note.setWordWrap(True)
        self.right_panel_layout.addWidget(lbl_auto_note)
        
        self.btn_stitch_action = QPushButton("Hizala / Birleştir")
        self.btn_stitch_action.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold; padding: 10px; border-radius: 4px; margin-top: 5px;")
        self.btn_stitch_action.clicked.connect(self.trigger_stitch_action)
        self.right_panel_layout.addWidget(self.btn_stitch_action)
        
        self.controls_container = QWidget()
        self.controls_layout = QVBoxLayout(self.controls_container)
        self.controls_layout.setContentsMargins(0, 0, 0, 0)
        
        self.controls_layout.addWidget(QLabel("<b>Önizleme / Hizalama Kontrolleri</b>"))
        
        self.lbl_stitch_stage_info = QLabel("Aşama: Otomatik Hizalama (CLAHE + Sobel + NCC)")
        self.lbl_stitch_stage_info.setStyleSheet("color: #bdc3c7; font-size: 11px;")
        self.controls_layout.addWidget(self.lbl_stitch_stage_info)
        
        zoom_box = QHBoxLayout()
        zoom_box.addWidget(QLabel("Yakınlaştırma:"))
        self.lbl_zoom_val = QLabel("1.00x")
        zoom_box.addWidget(self.lbl_zoom_val)
        zoom_box.addStretch()
        self.controls_layout.addLayout(zoom_box)
        
        self.stitch_slider = QSlider(Qt.Horizontal)
        self.stitch_slider.setRange(10, 300)
        self.stitch_slider.setValue(100)
        self.stitch_slider.valueChanged.connect(self.on_stitch_zoom_changed)
        self.controls_layout.addWidget(self.stitch_slider)
        
        self.lbl_confidence = QLabel("Güven skoru: 0.00")
        self.lbl_confidence.setStyleSheet("color: #2ecc71; font-weight: bold; font-size: 11px;")
        self.controls_layout.addWidget(self.lbl_confidence)
        
        self.lbl_manual_offset = QLabel(f"Manuel düzeltme: sağ/sol {self.stitch_offset_x:+.2f} px, yukarı/aşağı {self.stitch_offset_y:+.2f} px")
        self.lbl_manual_offset.setStyleSheet("color: #95a5a6; font-size: 10px;")
        self.controls_layout.addWidget(self.lbl_manual_offset)
        
        self.chk_checkerboard = QCheckBox("Dama tahtası (dikiş kontrolü)")
        self.chk_checkerboard.setStyleSheet("color: #ecf0f1; font-size: 11px;")
        self.chk_checkerboard.stateChanged.connect(self.update_stitched_spine)
        self.controls_layout.addWidget(self.chk_checkerboard)
        
        self.controls_layout.addWidget(QLabel("<b>Hassas Kaydırma</b>"))
        self.step_input = QLabel("1.0")
        self.step_input.setStyleSheet("background-color: #1e1e1e; padding: 5px; border: 1px solid #444;")
        self.controls_layout.addWidget(self.step_input)
        
        step_btns_layout = QHBoxLayout()
        for val_str in ["0.5", "1", "3", "5", "10"]:
            b = QPushButton(val_str)
            b.setStyleSheet("background-color: #34495e; color: white; padding: 4px;")
            b.clicked.connect(lambda checked=False, s=val_str: self.set_shift_step(s))
            step_btns_layout.addWidget(b)
        self.controls_layout.addLayout(step_btns_layout)
        
        # Hareket ettirilecek parçayı seç. Servikal bilinçli olarak sabittir.
        self.lbl_move_part = QLabel("<b>Hareket Ettirilecek Parça</b>")
        self.controls_layout.addWidget(self.lbl_move_part)
        move_part_layout = QHBoxLayout()
        self.btn_move_servical = QPushButton("Servikal · Sabit")
        self.btn_move_dorsal = QPushButton("Dorsal")
        self.btn_move_lumbar = QPushButton("Lomber")
        self.btn_move_servical.setEnabled(False)
        self.btn_move_dorsal.clicked.connect(lambda: self.select_stitch_part("dorsal"))
        self.btn_move_lumbar.clicked.connect(lambda: self.select_stitch_part("lumbar"))
        for b in [self.btn_move_servical, self.btn_move_dorsal, self.btn_move_lumbar]:
            b.setStyleSheet("background-color: #34495e; color: white; padding: 5px; border-radius: 3px;")
            move_part_layout.addWidget(b)
        self.controls_layout.addLayout(move_part_layout)
        
        grid_dir = QGridLayout()
        btn_up = QPushButton("↑")
        btn_left = QPushButton("←")
        btn_zero = QPushButton("Sıfırla")
        btn_right = QPushButton("→")
        btn_down = QPushButton("↓")
        self.btn_move_up = btn_up
        self.btn_move_left = btn_left
        self.btn_move_zero = btn_zero
        self.btn_move_right = btn_right
        self.btn_move_down = btn_down
        
        btn_up.clicked.connect(lambda: self.adjust_stitch_offset(0, -self.current_step_val))
        btn_down.clicked.connect(lambda: self.adjust_stitch_offset(0, self.current_step_val))
        btn_left.clicked.connect(lambda: self.adjust_stitch_offset(-self.current_step_val, 0))
        btn_right.clicked.connect(lambda: self.adjust_stitch_offset(self.current_step_val, 0))
        btn_zero.clicked.connect(lambda: self.reset_stitch_offset())
        
        for b in [btn_up, btn_left, btn_zero, btn_right, btn_down]:
            b.setStyleSheet("background-color: #34495e; color: white; padding: 4px;")
        
        grid_dir.addWidget(btn_up, 0, 1)
        grid_dir.addWidget(btn_left, 1, 0)
        grid_dir.addWidget(btn_zero, 1, 1)
        grid_dir.addWidget(btn_right, 1, 2)
        grid_dir.addWidget(btn_down, 2, 1)
        self.controls_layout.addLayout(grid_dir)
        self._refresh_stitch_part_buttons()
        
        self.btn_confirm_finish = QPushButton("Onayla ve Bitir")
        self.btn_confirm_finish.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold; padding: 10px; border-radius: 4px; margin-top: 5px;")
        self.btn_confirm_finish.clicked.connect(self.on_confirm_finish_clicked)
        self.controls_layout.addWidget(self.btn_confirm_finish)
        
        self.controls_container.setVisible(False)

        # Uzun kontrol grubunu scroll alanına alıyoruz. Böylece özellikle
        # Ölçüm bölümündeki çok satırlı checkbox ve butonlar dar panelde
        # birbirinin üzerine binmez.
        self.controls_scroll = QScrollArea()
        self.controls_scroll.setWidgetResizable(True)
        self.controls_scroll.setFrameShape(QScrollArea.NoFrame)
        self.controls_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.controls_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.controls_scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            "QScrollBar:vertical { width: 10px; background: #202020; }"
        )
        self.controls_scroll.setWidget(self.controls_container)
        self.controls_scroll.setVisible(False)
        self.right_panel_layout.addWidget(self.controls_scroll, 1)
        
        self.right_panel_layout.addStretch()
        stitcher_layout.addWidget(right_panel, stretch=1)
        self.tabs.addTab(self.stitcher_tab, "DICOM Omurga Birleştirme")

        # Global Kısayollar
        self.shortcut_up = QShortcut(QKeySequence(Qt.Key_Up), self.stitcher_tab)
        self.shortcut_up.activated.connect(lambda: self.handle_shortcut_move(0, -self.current_step_val))
        
        self.shortcut_down = QShortcut(QKeySequence(Qt.Key_Down), self.stitcher_tab)
        self.shortcut_down.activated.connect(lambda: self.handle_shortcut_move(0, self.current_step_val))
        
        self.shortcut_left = QShortcut(QKeySequence(Qt.Key_Left), self.stitcher_tab)
        self.shortcut_left.activated.connect(lambda: self.handle_shortcut_move(-self.current_step_val, 0))
        
        self.shortcut_right = QShortcut(QKeySequence(Qt.Key_Right), self.stitcher_tab)
        self.shortcut_right.activated.connect(lambda: self.handle_shortcut_move(self.current_step_val, 0))

    def handle_shortcut_move(self, dx, dy):
        if self.tabs.currentIndex() == 1 and self.is_stitched_completed:
            self.adjust_stitch_offset(dx, dy)

    def _render_interactive_preview(self):
        # Hareket sırasında düşük çözünürlüklü önizleme; son konumda tam kalite render.
        if not self.is_stitched_completed:
            return
        self._stitch_interactive = True
        self.update_stitched_spine()

    def _render_full_after_move(self):
        self._stitch_interactive = False
        self.update_stitched_spine()

    # =========================================================================
    # DİNANMİK ÇAKIŞMA VE BİRLEŞTİRME METODLARI (BURAYA EKLENİYOR)
    # =========================================================================

    def _auto_estimate_offset(self, arr_top, arr_bottom, min_ratio=0.12, max_ratio=0.32, max_dx=50):
        """
        Hızlandırılmış otomatik hizalama.

        Önceki sürüm tüm görüntüye tile-normalize + Sobel uyguluyor ve ardından
        çok sayıda tam boy FFT yapıyordu. Bu, özellikle büyük DICOM'larda
        gereksiz yere CPU'yu dolduruyordu. Burada yalnızca gerçek birleşim
        bölgesini kullanıyor ve korelasyon hesabını küçültülmüş görüntü üzerinde
        yapıyoruz. Sonuç yine aynı dx/dy mantığıyla döner.
        """
        try:
            h_top, w_top = arr_top.shape[:2]
            h_bot, w_bot = arr_bottom.shape[:2]
            band_w = min(w_top, w_bot)

            min_overlap = int(h_top * min_ratio)
            max_overlap = int(h_top * max_ratio)
            if h_top < 10 or h_bot < 10 or max_overlap <= min_overlap:
                return 0.0, float(max(1, int(h_top * 0.20))), 0.0, arr_bottom

            # Sadece birleşim civarında ihtiyaç duyulan 120 px'lik bant.
            window_h = min(120, h_top, h_bot)
            max_feature_w = 640
            scale = min(1.0, max_feature_w / float(max(1, band_w)))
            feat_w = max(64, int(round(band_w * scale)))
            feat_h = max(32, int(round(window_h * scale)))

            def make_feature(region):
                gray = self._to_gray(region).astype(np.float32)
                if cv2 is not None:
                    gray = cv2.resize(gray, (feat_w, feat_h), interpolation=cv2.INTER_AREA)
                    gray = cv2.GaussianBlur(gray, (3, 3), 0)
                    gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
                    gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
                    feat = cv2.magnitude(gx, gy)
                else:
                    gray = self._resize_gray_fast(gray, feat_w, feat_h)
                    feat = self._sobel_magnitude(gray)
                feat -= feat.mean()
                std = feat.std()
                if std > 1e-6:
                    feat /= std
                return feat.astype(np.float32)

            top_region = arr_top[max(0, h_top - window_h):h_top, :band_w]
            top_feat = make_feature(top_region)

            # Aynı üst görüntü için FFT tekrar tekrar hesaplanmasın.
            win = np.hanning(feat_h)[:, None] * np.hanning(feat_w)[None, :]
            top_win = top_feat * win
            top_fft = np.fft.fft2(top_win)

            best_score = -1.0
            best_dy = int(h_top * 0.20)
            best_dx = 0

            # 5 px aralığını koruyoruz; fakat küçük feature alanı sayesinde
            # hesap çok daha ucuz.
            for trial_overlap in range(min_overlap, max_overlap + 1, 5):
                if trial_overlap < window_h or trial_overlap > h_bot:
                    continue

                y2 = trial_overlap
                y1 = y2 - window_h
                bot_region = arr_bottom[y1:y2, :band_w]
                if bot_region.shape[0] != window_h:
                    continue

                bot_feat = make_feature(bot_region)
                bot_win = bot_feat * win
                bot_fft = np.fft.fft2(bot_win)
                r_fft = top_fft * np.conj(bot_fft)
                r_fft /= (np.abs(r_fft) + 1e-8)
                corr = np.fft.fftshift(np.fft.ifft2(r_fft).real)
                peak_idx = np.unravel_index(np.argmax(corr), corr.shape)
                peak_val = float(corr[peak_idx])
                mean_abs = float(np.mean(np.abs(corr))) + 1e-8
                score = float(np.clip(peak_val / (mean_abs * 50.0), 0.0, 1.0))

                dy_feat = peak_idx[0] - feat_h // 2
                dx_feat = peak_idx[1] - feat_w // 2
                dy = int(round(dy_feat / scale))
                dx = int(round(dx_feat / scale))
                calc_dy = trial_overlap + dy

                if score > best_score and min_overlap <= calc_dy <= max_overlap:
                    best_score = score
                    best_dy = calc_dy
                    best_dx = dx

            best_dx = float(np.clip(best_dx, -max_dx, max_dx))
            best_dy = float(np.clip(best_dy, min_overlap, max_overlap))
            return best_dx, best_dy, best_score, arr_bottom

        except Exception as e:
            print(f"Dinamik çakışma hizalaması başarısız: {e}")
            fallback_dy = float(int(arr_top.shape[0] * 0.20))
            return 0.0, fallback_dy, 0.0, arr_bottom

    @staticmethod
    def _resize_gray_fast(gray, width, height):
        """OpenCV yoksa otomatik hizalama için ucuz numpy yeniden boyutlandırma."""
        h, w = gray.shape[:2]
        if w == width and h == height:
            return gray.astype(np.float32, copy=False)
        ys = np.linspace(0, h - 1, height).astype(np.int32)
        xs = np.linspace(0, w - 1, width).astype(np.int32)
        return gray[np.ix_(ys, xs)].astype(np.float32, copy=False)

    def update_stitched_spine(self):
        if getattr(self, "manual_mode_active", False):
            self.render_manual_pick_view()
            return

        # Normal renderde aynı QGraphicsPixmapItem'ı yeniden kullan.
        # Manuel görünüm sahneyi temizlediğinde referans zaten None yapılır.
        active_parts = [
            p for p in ["servical", "dorsal", "lumbar"]
            if self.stitch_files.get(p) is not None
        ]

        if not active_parts:
            self.stitch_scene.clear()
            self._stitch_result_item = None
            return

        pixmaps = []
        arrays = []
        valid_parts = []
        for part in active_parts:
            path = self.stitch_files[part]
            # Aynı DICOM'u her manuel kaydırmada tekrar decode etme.
            pix = self._stitch_pixmap_cache.get(path)
            if pix is None or pix.isNull():
                pix = self.get_image_pixmap(path)
                if pix.isNull():
                    self.statusBar().showMessage(f"{part.capitalize()} görüntüsü okunamadı; birleştirme durduruldu.")
                    return
                self._stitch_pixmap_cache[path] = pix

            arr = self._stitch_array_cache.get(path)
            if arr is None:
                arr = self._qimage_to_numpy(pix.toImage())
                self._stitch_array_cache[path] = arr

            # Pahalı RGB eşitliği kontrolünü her ok tuşunda yapma.
            # İlk yüklemede bir kez belirle ve gri kanalın float32 halini cache'le.
            if path not in self._stitch_gray_flag_cache:
                is_gray = bool(
                    arr.ndim == 3 and arr.shape[2] >= 4 and
                    np.array_equal(arr[..., 0], arr[..., 1]) and
                    np.array_equal(arr[..., 1], arr[..., 2])
                )
                self._stitch_gray_flag_cache[path] = is_gray
                if is_gray:
                    self._stitch_gray_cache[path] = arr[..., 0].astype(np.float32, copy=True)

            pixmaps.append(pix)
            arrays.append(arr)
            valid_parts.append(part)

        if not pixmaps:
            return

        # ---------------------------------------------------------
        # OTOMATİK HİZALAMA
        # ---------------------------------------------------------
        auto_align_on = (
            not getattr(self, "manual_mode_active", False)
            and (
                not hasattr(self, "chk_auto_align")
                or self.chk_auto_align.isChecked()
            )
        )

        junction_offsets = []
        rotated_any = False

        if len(arrays) > 1:
            for i in range(1, len(arrays)):
                upper = active_parts[i - 1]
                lower = active_parts[i]

                # -----------------------------------------------------
                # ÖNCELİK: MANUEL HİZALAMA
                # Manuel olarak sabitlenmiş bir eklem varsa, otomatik
                # hizalama ASLA bu eklemi yeniden hesaplamaz. Bu sayede
                # otomatik kutusu açık olsa bile manuel sonuç korunur.
                # -----------------------------------------------------
                manual = self.manual_junction_offsets.get((upper, lower))
                if manual is not None:
                    if len(manual) >= 3:
                        dx_m, target_y, angle_deg = manual
                    else:
                        # Eski sürüm kayıtları için geriye dönük uyumluluk.
                        dx_m, dy_m = manual
                        target_y = arrays[i - 1].shape[0] - self.OVERLAP_PX + float(dy_m)
                        angle_deg = 0.0

                    h_prev = arrays[i - 1].shape[0]
                    h_curr = arrays[i].shape[0]

                    # target_y, hareketli parçanın gerçek üst Y konumudur.
                    # Mevcut stitch modeli overlap = h_prev - lower_y
                    # kullandığı için burada doğru dönüşüm yapılır.
                    dy = float(h_prev - float(target_y))
                    dy = float(np.clip(
                        dy,
                        1.0,
                        float(max(1, min(h_prev - 1, h_curr - 1)))
                    ))

                    dx = float(dx_m)
                    score = 1.0

                    # Manuel iki noktanın verdiği küçük rijit rotasyonu yalnızca
                    # burada uygula; otomatik hizalama ile üst üste bindirme yapma.
                    if abs(float(angle_deg)) > 1e-4:
                        arrays[i] = self._rotate_array(
                            arrays[i], float(angle_deg), fill=0
                        )
                        rotated_any = True

                    junction_offsets.append((dx, dy, score))
                    continue

                # -----------------------------------------------------
                # MANUEL KAYIT YOKSA: OTOMATİK veya GÜVENLİ FALLBACK
                # -----------------------------------------------------
                if auto_align_on:
                    pair_key = (
                        self.stitch_files[upper],
                        self.stitch_files[lower],
                        arrays[i - 1].shape[:2],
                        arrays[i].shape[:2],
                    )
                    cached = self._auto_align_cache.get(pair_key)
                    if cached is None:
                        cached = self._auto_estimate_offset(
                            arrays[i - 1], arrays[i]
                        )[:3]
                        self._auto_align_cache[pair_key] = cached
                    dx, dy, score = cached
                else:
                    dx = 0.0
                    dy = float(max(1, int(arrays[i - 1].shape[0] * 0.20)))
                    score = 0.0

                junction_offsets.append((dx, dy, score))

        # ---------------------------------------------------------
        # GÜVEN SKORU
        # ---------------------------------------------------------
        if hasattr(self, "lbl_confidence"):
            if junction_offsets:
                avg_score = (
                    sum(s for _, _, s in junction_offsets)
                    / len(junction_offsets)
                )
                self.lbl_confidence.setText(
                    f"Güven skoru: {avg_score:.2f}"
                )
            elif len(arrays) > 1:
                self.lbl_confidence.setText(
                    "Güven skoru: — (manuel/kapalı)"
                )

        # ---------------------------------------------------------
        # ETKİLEŞİMLİ ÖNİZLEME
        # Hareket sırasında yalnızca ekranda görülecek daha küçük bir raster
        # üretilir. Offset/hizalama değerleri fiziksel pikselden preview
        # pikseline ölçeklenir; tam kalite render boşta kaldığında geri gelir.
        # ---------------------------------------------------------
        render_scale = float(getattr(self, "_stitch_preview_scale", 1.0)) if getattr(self, "_stitch_interactive", False) else 1.0
        if render_scale < 0.999:
            scaled_arrays = []
            scaled_pixmaps = []
            for arr, pix in zip(arrays, pixmaps):
                nh = max(1, int(round(arr.shape[0] * render_scale)))
                nw = max(1, int(round(arr.shape[1] * render_scale)))
                if nh == arr.shape[0] and nw == arr.shape[1]:
                    a2 = arr
                else:
                    ys = np.linspace(0, arr.shape[0] - 1, nh).astype(np.int32)
                    xs = np.linspace(0, arr.shape[1] - 1, nw).astype(np.int32)
                    a2 = arr[np.ix_(ys, xs)]
                scaled_arrays.append(a2)
                # Yalnızca boyut bilgisi için küçük bir pixmap yeterli.
                scaled_pixmaps.append(QPixmap(nw, nh))
            arrays = scaled_arrays
            pixmaps = scaled_pixmaps
            junction_offsets = [
                (dx * render_scale, dy * render_scale, score)
                for dx, dy, score in junction_offsets
            ]

        # ---------------------------------------------------------
        # GÖRÜNTÜ KONUMU
        #
        # Overlap artık KESİLMİYOR.
        # İki görüntü gerçekten üst üste bindiriliyor.
        # ---------------------------------------------------------
        positions = [(0.0, 0.0)]

        curr_x = 0.0
        curr_y = 0.0

        for i in range(1, len(pixmaps)):
            h_prev = pixmaps[i - 1].height()

            if (i - 1) < len(junction_offsets):
                dx_auto, dy_auto, _ = junction_offsets[i - 1]

                if dy_auto <= 0:
                    dy_auto = h_prev * 0.20

                dy_auto = float(
                    np.clip(
                        dy_auto,
                        1,
                        max(1, h_prev - 1)
                    )
                )

                curr_x += dx_auto
                curr_y += h_prev - dy_auto

            else:
                curr_y += h_prev * 0.80

            part_key = active_parts[i]
            part_dx, part_dy = self.stitch_part_offsets.get(part_key, [0.0, 0.0])
            # Preview rasterında manuel offsetleri aynı ölçeğe indir.
            part_dx *= render_scale
            part_dy *= render_scale
            # Servikal her zaman (0,0) kabul edilir; Dorsal/Lomber bağımsız hareket eder.
            positions.append(
                (
                    curr_x + float(part_dx),
                    curr_y + float(part_dy)
                )
            )

        min_x = min(p[0] for p in positions)
        min_y = min(p[1] for p in positions)

        shifted_positions = [
            (
                p[0] - min_x,
                p[1] - min_y
            )
            for p in positions
        ]

        max_w = max(
            p[0] + pix.width()
            for p, pix in zip(shifted_positions, pixmaps)
        )

        max_h = max(
            p[1] + pix.height()
            for p, pix in zip(shifted_positions, pixmaps)
        )

        max_w = int(np.ceil(max_w))
        max_h = int(np.ceil(max_h))

        if max_w <= 0 or max_h <= 0:
            return

        # ---------------------------------------------------------
        # HIZLI GRİ BLEND
        # Röntgen çıktıları gri ve opak olduğu için RGB+alpha üzerinde
        # çalışmak gereksiz CPU/RAM tüketir. Ok tuşlarıyla her harekette
        # tekrar kullanılan feather maskeleri de önbellekten alınır.
        # ---------------------------------------------------------
        # Kaynak DICOM'lar normalde opak gri ARGB32'dir. Alpha kanalını her
        # ok tuşunda taramak yerine yalnızca manuel rotasyon yapıldığında
        # güvenli yolu kullanıyoruz (rotasyonda kenarlara şeffaf dolgu gelir).
        gray_fast = (not rotated_any) and all(
            self._stitch_gray_flag_cache.get(self.stitch_files[part], False)
            for part in valid_parts
        )

        if gray_fast:
            canvas_gray = np.zeros((max_h, max_w), dtype=np.float32)
            canvas_alpha = np.zeros((max_h, max_w), dtype=np.float32)

            for i, arr in enumerate(arrays):
                img_h, img_w = arr.shape[:2]
                x = int(round(shifted_positions[i][0]))
                y = int(round(shifted_positions[i][1]))

                top_overlap = 0
                if i > 0 and (i - 1) < len(junction_offsets):
                    top_overlap = int(np.clip(junction_offsets[i - 1][1], 1, max(1, img_h - 1)))

                bottom_overlap = 0
                if i < len(junction_offsets):
                    bottom_overlap = int(np.clip(junction_offsets[i][1], 1, max(1, img_h - 1)))

                mask = self._get_stitch_mask(img_h, img_w, top_overlap, bottom_overlap)

                dst_x1 = max(0, x)
                dst_y1 = max(0, y)
                dst_x2 = min(max_w, x + img_w)
                dst_y2 = min(max_h, y + img_h)
                if dst_x1 >= dst_x2 or dst_y1 >= dst_y2:
                    continue

                src_x1 = dst_x1 - x
                src_y1 = dst_y1 - y
                src_x2 = src_x1 + (dst_x2 - dst_x1)
                src_y2 = src_y1 + (dst_y2 - dst_y1)

                gray_cache = self._stitch_gray_cache.get(self.stitch_files[valid_parts[i]])
                if gray_cache is not None and gray_cache.shape[:2] == arr.shape[:2]:
                    src_gray = gray_cache[src_y1:src_y2, src_x1:src_x2]
                else:
                    src_gray = arr[src_y1:src_y2, src_x1:src_x2, 0].astype(np.float32)
                local_mask = mask[src_y1:src_y2, src_x1:src_x2]
                dst_gray = canvas_gray[dst_y1:dst_y2, dst_x1:dst_x2]
                dst_alpha = canvas_alpha[dst_y1:dst_y2, dst_x1:dst_x2]

                # Source-over compositing, yalnızca tek kanal üzerinde.
                out_alpha = local_mask + dst_alpha * (1.0 - local_mask)
                valid = out_alpha > 1e-6
                numerator = src_gray * local_mask + dst_gray * dst_alpha * (1.0 - local_mask)
                dst_gray[valid] = numerator[valid] / out_alpha[valid]
                dst_gray[~valid] = 0.0
                dst_alpha[:] = out_alpha

            result_gray = np.clip(canvas_gray, 0, 255).astype(np.uint8)
            if hasattr(self, "chk_checkerboard") and self.chk_checkerboard.isChecked() and len(junction_offsets) > 0:
                result_bgra = self._gray_to_bgra(result_gray, canvas_alpha * 255.0)
                for i in range(1, len(shifted_positions)):
                    overlap = int(max(0, min(
                        float(junction_offsets[i - 1][1]),
                        pixmaps[i - 1].height(),
                        pixmaps[i].height()
                    )))
                    if overlap > 1:
                        y_start = int(round(shifted_positions[i][1]))
                        result_bgra = self._apply_checker_bw(
                            result_bgra, y_start, y_start + overlap, cell=22, intensity=0.32
                        )
                result_arr = result_bgra
            else:
                result_arr = self._gray_to_bgra(result_gray, canvas_alpha * 255.0)
        else:
            # Renkli/şeffaf kaynaklar için mevcut güvenli yol.
            canvas = np.zeros((max_h, max_w, 4), dtype=np.float32)
            for i, arr in enumerate(arrays):
                img_h, img_w = arr.shape[:2]
                x = int(round(shifted_positions[i][0]))
                y = int(round(shifted_positions[i][1]))

                top_overlap = 0
                if i > 0 and (i - 1) < len(junction_offsets):
                    top_overlap = int(np.clip(junction_offsets[i - 1][1], 1, max(1, img_h - 1)))
                bottom_overlap = 0
                if i < len(junction_offsets):
                    bottom_overlap = int(np.clip(junction_offsets[i][1], 1, max(1, img_h - 1)))
                mask = self._get_stitch_mask(img_h, img_w, top_overlap, bottom_overlap)

                dst_x1, dst_y1 = max(0, x), max(0, y)
                dst_x2, dst_y2 = min(max_w, x + img_w), min(max_h, y + img_h)
                if dst_x1 >= dst_x2 or dst_y1 >= dst_y2:
                    continue
                src_x1, src_y1 = dst_x1 - x, dst_y1 - y
                src_x2, src_y2 = src_x1 + (dst_x2 - dst_x1), src_y1 + (dst_y2 - dst_y1)
                src = arr[src_y1:src_y2, src_x1:src_x2].astype(np.float32)
                dst = canvas[dst_y1:dst_y2, dst_x1:dst_x2]
                local_mask = mask[src_y1:src_y2, src_x1:src_x2]
                src_alpha = local_mask[..., None] * (src[..., 3:4] / 255.0)
                dst_alpha = dst[..., 3:4] / 255.0
                out_alpha = src_alpha + dst_alpha * (1.0 - src_alpha)
                numerator = src[..., :3] * src_alpha + dst[..., :3] * dst_alpha * (1.0 - src_alpha)
                out_rgb = np.zeros_like(numerator)
                valid = out_alpha[..., 0] > 1e-6
                out_rgb[valid] = numerator[valid] / out_alpha[valid]
                out = np.zeros_like(dst)
                out[..., :3] = out_rgb
                out[..., 3:4] = out_alpha * 255.0
                canvas[dst_y1:dst_y2, dst_x1:dst_x2] = out

            if hasattr(self, "chk_checkerboard") and self.chk_checkerboard.isChecked() and len(junction_offsets) > 0:
                temp = np.clip(canvas, 0, 255).astype(np.uint8)
                for i in range(1, len(shifted_positions)):
                    overlap = int(max(0, min(float(junction_offsets[i - 1][1]), pixmaps[i - 1].height(), pixmaps[i].height())))
                    if overlap > 1:
                        y_start = int(round(shifted_positions[i][1]))
                        temp = self._apply_checker_bw(temp, y_start, y_start + overlap, cell=22, intensity=0.32)
                result_arr = temp
            else:
                result_arr = np.clip(canvas, 0, 255).astype(np.uint8)

        # ---------------------------------------------------------
        # QIMAGE
        # ---------------------------------------------------------
        # result_arr yukarıdaki gri/renkli dallarda zaten hazırlanıyor.
        # Burada tekrar `canvas` üzerinden ezmemek gerekiyor; gri dalda
        # `canvas` hiç oluşturulmadığı için UnboundLocalError oluşuyordu.
        result_img = self._numpy_to_qimage(result_arr)

        self.final_result_qimage = result_img.copy()

        result_pixmap = QPixmap.fromImage(result_img)
        if self._stitch_result_item is None:
            self.stitch_scene.clear()
            self._stitch_result_item = self.stitch_scene.addPixmap(result_pixmap)
        else:
            self._stitch_result_item.setPixmap(result_pixmap)
        self.statusBar().showMessage(
            " + ".join(p.capitalize() for p in valid_parts) + " görüntüleri yumuşak feather blending ile birleştirildi."
        )

    def _manual_pairs(self):
        active = [p for p in ['servical', 'dorsal', 'lumbar'] if self.stitch_files.get(p) is not None]
        return list(zip(active[:-1], active[1:]))

    def toggle_manual_point_mode(self):
        pairs = self._manual_pairs()
        if not pairs:
            QMessageBox.information(self, "Manuel Hizalama", "Önce en az iki omurga parçası yükleyin.")
            return

        self.manual_mode_active = not self.manual_mode_active
        self.stitch_view.refresh_cursor()

        if self.manual_mode_active:
            # İlk hizalama her zaman servikal → dorsal olur.
            self.manual_stage_index = 0
            self.manual_points = {}
            self._manual_point_marker_by_part = {}
            self.btn_mode_off.setText("Açık")
            self.btn_mode_off.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold; padding: 5px;")
            self.btn_manual_next_stage.setVisible(True)
            self.btn_manual_next_stage.setEnabled(False)
            self.btn_manual_next_stage.setText("Önce 2+2 nokta seçin")
            self.render_manual_pick_view()
            pair = self._manual_pairs()[self.manual_stage_index]
            self.lbl_manual_mode_info.setText(
                f"<font color='#f39c12' size='2'><b>Manuel Aşama {self.manual_stage_index + 1}/{len(pairs)}</b> — "
                f"{pair[0].capitalize()} sabit, {pair[1].capitalize()} hareketli. "
                f"Her görüntüde 2 karşılık gelen noktayı aynı sırayla seçin.</font>"
            )
            self.statusBar().showMessage(f"Manuel hizalama: {pair[0].capitalize()} sabit, {pair[1].capitalize()} hizalanıyor.")
        else:
            self.btn_mode_off.setText("Kapalı")
            self.btn_mode_off.setStyleSheet("background-color: #2980b9; color: white; padding: 5px;")
            self.btn_manual_next_stage.setVisible(False)
            self.btn_manual_next_stage.setEnabled(False)
            self.lbl_manual_mode_info.setText("<font color='#95a5a6' size='2'>Otomatik hizalama kullanılacak.</font>")
            self.clear_manual_points()
            if self.is_stitched_completed:
                self.update_stitched_spine()
            self.statusBar().showMessage("Manuel Nokta Modu kapalı.")

    def render_manual_pick_view(self):
        pairs = self._manual_pairs()
        self.stitch_scene.clear()
        self._stitch_result_item = None
        self._manual_point_markers = []

        if not pairs or self.manual_stage_index >= len(pairs):
            self._pick_pixmaps = []
            self._pick_positions = []
            return

        upper, lower = pairs[self.manual_stage_index]
        paths = [self.stitch_files[upper], self.stitch_files[lower]]
        pixmaps = []
        for path in paths:
            pix = self._stitch_pixmap_cache.get(path)
            if pix is None or pix.isNull():
                pix = self.get_image_pixmap(path)
                if not pix.isNull():
                    self._stitch_pixmap_cache[path] = pix
            if not pix.isNull():
                pixmaps.append(pix)

        if len(pixmaps) != 2:
            self.statusBar().showMessage("Manuel hizalama için iki görüntünün de okunması gerekiyor.")
            self._pick_pixmaps = []
            self._pick_positions = []
            return

        gap = 40
        pos0 = (0, 0)
        pos1 = (pixmaps[0].width() + gap, 0)
        self._pick_pixmaps = pixmaps
        self._pick_positions = [pos0, pos1]
        self._manual_pair_parts = (upper, lower)
        self.manual_points = {}
        self._manual_point_marker_by_part = {}

        self.stitch_scene.addPixmap(pixmaps[0])
        item1 = self.stitch_scene.addPixmap(pixmaps[1])
        item1.setPos(pos1[0], pos1[1])

        divider_x = pixmaps[0].width() + gap / 2
        max_h = max(pixmaps[0].height(), pixmaps[1].height())
        self.stitch_scene.addLine(divider_x, 0, divider_x, max_h, QPen(Qt.darkGray, 2))

        lbl0 = self.stitch_scene.addText(f"{upper.capitalize()} (SABİT) — 2 nokta seç")
        lbl0.setDefaultTextColor(Qt.green)
        lbl0.setPos(10, 10)
        lbl1 = self.stitch_scene.addText(f"{lower.capitalize()} — aynı 2 noktayı seç")
        lbl1.setDefaultTextColor(Qt.red)
        lbl1.setPos(pos1[0] + 10, 10)

        QTimer.singleShot(0, lambda: self.stitch_view.fitInView(
            self.stitch_scene.itemsBoundingRect(), Qt.KeepAspectRatio
        ))

    def clear_manual_points(self):
        self.manual_points = {}
        self._manual_point_marker_by_part = {}
        self._manual_point_markers = []
        if self.manual_mode_active:
            self.render_manual_pick_view()
        else:
            self.statusBar().showMessage("Manuel noktalar temizlendi.")

    def handle_manual_point_click(self, scene_pos):
        """
        Manuel hizalama:
        - Önce SABİT görüntüde 2 nokta
        - Sonra HAREKET EDECEK görüntüde aynı 2 noktayı aynı sırayla
        - İki noktanın doğrultusundan rotasyon, ilk noktadan öteleme hesaplanır.
        """
        if not self.manual_mode_active or not getattr(self, '_pick_pixmaps', None) or len(self._pick_pixmaps) != 2:
            return

        x, y = scene_pos.x(), scene_pos.y()
        pos0, pos1 = self._pick_positions

        if pos0[0] <= x < pos0[0] + self._pick_pixmaps[0].width() and 0 <= y < self._pick_pixmaps[0].height():
            part_idx = 0
            local = (float(x - pos0[0]), float(y - pos0[1]))
            marker_color = Qt.green
        elif pos1[0] <= x < pos1[0] + self._pick_pixmaps[1].width() and 0 <= y < self._pick_pixmaps[1].height():
            part_idx = 1
            local = (float(x - pos1[0]), float(y - pos1[1]))
            marker_color = Qt.red
        else:
            return

        # Sıralı giriş: sabit görüntüde 2 nokta, ardından hareketli görüntüde 2 nokta.
        pts0 = self.manual_points.setdefault(0, [])
        pts1 = self.manual_points.setdefault(1, [])

        target_list = pts0 if part_idx == 0 else pts1

        if len(target_list) >= 2:
            self.statusBar().showMessage(
                "Bu görüntüde zaten 2 nokta var. Önce 'Noktaları Temizle' ile yeniden işaretleyin."
            )
            return

        target_list.append(local)

        # Aynı görüntüde ikinci nokta seçildiğinde marker'ı yeniden çiziyoruz.
        r = 6
        ellipse = self.stitch_scene.addEllipse(
            x - r, y - r, r * 2, r * 2, QPen(marker_color, 3)
        )
        text_item = self.stitch_scene.addText(str(len(target_list)))
        text_item.setDefaultTextColor(marker_color)
        text_item.setPos(x + 7, y - 10)
        self._manual_point_markers.extend([ellipse, text_item])

        if part_idx == 0 and len(pts0) == 1:
            self.statusBar().showMessage(
                "Servikal/Dorsal/Lomber sabit görüntüde 1. nokta seçildi. Aynı görüntüde 2. noktayı seçin."
            )
            return

        if part_idx == 0 and len(pts0) == 2:
            self.statusBar().showMessage(
                "Sabit görüntünün 2 noktası tamam. Şimdi hareketli görüntüde aynı iki anatomik noktayı aynı sırayla seçin."
            )
            return

        if part_idx == 1 and len(pts1) == 1:
            self.statusBar().showMessage(
                "Hareketli görüntüde 1. nokta seçildi. Aynı anatomik noktanın karşılığını 2. noktada seçin."
            )
            return

        if len(pts0) < 2 or len(pts1) < 2:
            return

        # ---------------------------------------------------------
        # 2 NOKTADAN RİJİT TRANSFORM
        # ---------------------------------------------------------
        p0 = np.asarray(pts0[0], dtype=np.float64)
        p1 = np.asarray(pts0[1], dtype=np.float64)
        q0 = np.asarray(pts1[0], dtype=np.float64)
        q1 = np.asarray(pts1[1], dtype=np.float64)

        v_src = q1 - q0
        v_dst = p1 - p0

        src_len = float(np.linalg.norm(v_src))
        dst_len = float(np.linalg.norm(v_dst))

        if src_len < 3.0 or dst_len < 3.0:
            self.statusBar().showMessage(
                "İki nokta birbirine çok yakın. Lütfen daha belirgin iki anatomik nokta seçin."
            )
            return

        angle_src = math.atan2(v_src[1], v_src[0])
        angle_dst = math.atan2(v_dst[1], v_dst[0])
        angle_deg = math.degrees(angle_dst - angle_src)

        # Aynı radyografide küçük pozisyon farkları için rotasyonu güvenli aralıkta tut.
        angle_deg = float(np.clip(angle_deg, -12.0, 12.0))

        # Alt görüntü kendi merkezinde döndürüldüğünde q0'ın yeni koordinatı:
        # _rotate_array ile aynı merkez-pivot matematiği.
        h, w = self._pick_pixmaps[1].height(), self._pick_pixmaps[1].width()
        cx, cy = w / 2.0, h / 2.0
        a = math.radians(angle_deg)
        ca, sa = math.cos(a), math.sin(a)

        q0r_x = ca * (q0[0] - cx) - sa * (q0[1] - cy) + cx
        q0r_y = sa * (q0[0] - cx) + ca * (q0[1] - cy) + cy

        # Nihai yerleşimde alt görüntünün ilk noktası üst görüntünün ilk noktasına gelsin.
        target_x = float(p0[0] - q0r_x)
        target_y = float(p0[1] - q0r_y)

        upper, lower = self._manual_pair_parts
        top_h = self._pick_pixmaps[0].height()
        overlap = float(self.OVERLAP_PX)

        # Manuel kayıtta dy_adjust yerine gerçek hedef Y konumunu saklıyoruz.
        # Böylece final stitch sırasında manuel sonuç otomatik hizalama tarafından
        # bozulmaz ve overlap hesabı ters işaretlenmez.
        dy_adjust = target_y - (top_h - overlap)
        dx_adjust = target_x

        self.manual_junction_offsets[(upper, lower)] = (
            float(dx_adjust),
            float(target_y),
            float(angle_deg)
        )

        self.is_stitched_completed = True
        self.lbl_manual_offset.setText(
            f"Manuel {upper.capitalize()}→{lower.capitalize()}: "
            f"Δx {dx_adjust:+.1f}px, Δy {dy_adjust:+.1f}px, açı {angle_deg:+.2f}°"
        )

        # 2+2 nokta tamamlandı. Hesap hazır; kullanıcı açıkça sabitleme düğmesine basmadan
        # sonraki aşamaya geçme.
        pairs = self._manual_pairs()
        is_last_stage = (self.manual_stage_index + 1 >= len(pairs))
        self.btn_manual_next_stage.setVisible(True)
        self.btn_manual_next_stage.setEnabled(True)
        self.btn_manual_next_stage.setText(
            "Lomber'i Sabitle ve Birleştirmeyi Tamamla" if is_last_stage
            else f"{upper.capitalize()}–{lower.capitalize()} sabitle → sonraki parçaya geç"
        )
        self.lbl_manual_mode_info.setText(
            f"<font color='#2ecc71' size='2'><b>Aşama {self.manual_stage_index + 1}/{len(pairs)} hazır.</b> "
            f"{upper.capitalize()} sabit, {lower.capitalize()} için 2+2 nokta tamamlandı. "
            f"Sabitleme düğmesine basın.</font>"
        )
        self.statusBar().showMessage(
            f"{upper.capitalize()} → {lower.capitalize()} hazır. Sabitlemek için düğmeye basın."
        )

    def advance_manual_stage(self):
        if not self.manual_mode_active:
            return
        pairs=self._manual_pairs()
        if not pairs or self.manual_stage_index >= len(pairs):
            return
        if len(self.manual_points.get(0,[])) < 2 or len(self.manual_points.get(1,[])) < 2:
            QMessageBox.information(self,"Manuel Hizalama","Önce SABİT görüntüde 2 ve HAREKETLİ görüntüde 2 karşılık gelen nokta seçin.")
            return
        if self.manual_stage_index + 1 < len(pairs):
            upper, lower = pairs[self.manual_stage_index]
            self.manual_stage_index += 1
            self.manual_points={}
            self._manual_point_marker_by_part={}
            self._manual_point_markers=[]
            self.btn_manual_next_stage.setEnabled(False)
            self.btn_manual_next_stage.setText("Önce 2+2 nokta seçin")
            self.render_manual_pick_view()
            nu,nl=pairs[self.manual_stage_index]
            self.lbl_manual_mode_info.setText(
                f"<font color='#f39c12' size='2'><b>Manuel Aşama {self.manual_stage_index+1}/{len(pairs)}</b> — "
                f"{nu.capitalize()} SABİT, {nl.capitalize()} hareketli. Her görüntüde 2 karşılık gelen nokta seçin.</font>"
            )
            self.statusBar().showMessage(f"{upper.capitalize()}–{lower.capitalize()} sabitlendi. Şimdi {nu.capitalize()} sabit; {nl.capitalize()} hizalanacak.")
            return
        self.manual_mode_active=False
        self.btn_manual_next_stage.setVisible(False)
        self.btn_manual_next_stage.setEnabled(False)
        self.btn_mode_off.setText("Kapalı")
        self.btn_mode_off.setStyleSheet("background-color: #2980b9; color: white; padding: 5px;")
        self.stitch_view.refresh_cursor()
        self.lbl_manual_mode_info.setText("<font color='#2ecc71' size='2'><b>Manuel hizalama tamamlandı.</b> Servikal sabit, Dorsal ve Lomber ayrı ayrı sabitlendi.</font>")
        self.is_stitched_completed=True
        self.update_stitched_spine()
        self.statusBar().showMessage("Manuel hizalama tamamlandı: Servikal sabit, Dorsal ve Lomber sabitlendi.")

    def set_shift_step(self, val_str):
        try:
            self.current_step_val = float(val_str)
            self.step_input.setText(val_str)
        except ValueError:
            pass

    def _refresh_stitch_part_buttons(self):
        """Hareket seçimlerini mevcut yüklemelere göre güncelle."""
        has_dorsal = self.stitch_files.get("dorsal") is not None
        has_lumbar = self.stitch_files.get("lumbar") is not None
        self.btn_move_dorsal.setEnabled(has_dorsal)
        self.btn_move_lumbar.setEnabled(has_lumbar)
        if self.active_stitch_part == "dorsal" and not has_dorsal:
            self.active_stitch_part = "lumbar" if has_lumbar else "dorsal"
        if self.active_stitch_part == "lumbar" and not has_lumbar:
            self.active_stitch_part = "dorsal" if has_dorsal else "lumbar"
        active = self.active_stitch_part
        for key, btn in [("dorsal", self.btn_move_dorsal), ("lumbar", self.btn_move_lumbar)]:
            if btn.isEnabled() and key == active:
                btn.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold; padding: 5px; border-radius: 3px;")
            else:
                btn.setStyleSheet("background-color: #34495e; color: white; padding: 5px; border-radius: 3px;")
        self.btn_move_servical.setStyleSheet("background-color: #1f4f6e; color: #b9d7ea; padding: 5px; border-radius: 3px;")
        self._update_move_offset_label()

    def select_stitch_part(self, part_key):
        if part_key == "servical":
            return
        if self.stitch_files.get(part_key) is None:
            return
        self.active_stitch_part = part_key
        self._refresh_stitch_part_buttons()
        self.statusBar().showMessage(f"{part_key.capitalize()} seçildi. Ok tuşları artık bu parçayı hareket ettirir.")

    def _update_move_offset_label(self):
        dx, dy = self.stitch_part_offsets.get(self.active_stitch_part, [0.0, 0.0])
        self.lbl_manual_offset.setText(
            f"{self.active_stitch_part.capitalize()} kaydırma: sağ/sol {dx:+.2f} px, yukarı/aşağı {dy:+.2f} px"
        )

    def adjust_stitch_offset(self, dx, dy):
        part = self.active_stitch_part
        if part == "servical" or self.stitch_files.get(part) is None:
            return
        self.stitch_part_offsets.setdefault(part, [0.0, 0.0])
        self.stitch_part_offsets[part][0] += float(dx)
        self.stitch_part_offsets[part][1] += float(dy)
        self.stitch_offset_x = self.stitch_part_offsets[part][0]
        self.stitch_offset_y = self.stitch_part_offsets[part][1]
        self._update_move_offset_label()
        # Hareket sırasında hızlı preview, kullanıcı durduğunda tam kalite render.
        self._stitch_interactive = True
        if hasattr(self, "_stitch_render_timer"):
            self._stitch_render_timer.start()
        else:
            self.update_stitched_spine()
        if hasattr(self, "_stitch_full_render_timer"):
            self._stitch_full_render_timer.start()

    def reset_stitch_offset(self):
        part = self.active_stitch_part
        if part == "servical":
            return
        self.stitch_part_offsets[part] = [0.0, 0.0]
        self.stitch_offset_x = 0.0
        self.stitch_offset_y = 0.0
        self._update_move_offset_label()
        if hasattr(self, "_stitch_render_timer"):
            self._stitch_render_timer.stop()
        if hasattr(self, "_stitch_full_render_timer"):
            self._stitch_full_render_timer.stop()
        self._stitch_interactive = False
        self.update_stitched_spine()

    def on_stitch_zoom_changed(self, value):
        factor = value / 100.0
        self.lbl_zoom_val.setText(f"{factor:.2f}x")
        self.stitch_view.resetTransform()
        self.stitch_view.scale(factor, factor)

    def open_preview_dialog(self, part_name):
        """Tek DICOM penceresi: Servikal/Dorsal/Lomber aynı oturumda atanır."""
        initial_dir = self.last_stitch_folder or ""
        for path in self.stitch_files.values():
            if path:
                initial_dir = os.path.dirname(path)
                break

        # ÖNEMLİ: Kopya gönderiyoruz; dialog içindeki atamalar kabul edilene
        # kadar ana uygulamanın çalışan verisini değiştirmiyoruz.
        initial_files = dict(self.stitch_files)
        dialog = MultiPartDicomPreviewDialog(
            initial_dir=initial_dir,
            initial_files=initial_files,
            initial_target=part_name,
            parent=self
        )

        if dialog.exec() != QDialog.Accepted:
            return

        changed = False
        new_files = dict(self.stitch_files)
        for key in ("servical", "dorsal", "lumbar"):
            new_path = dialog.selected_files.get(key)
            if new_path == self.stitch_files.get(key):
                continue
            if new_path:
                pix = self.get_image_pixmap(new_path)
                if pix.isNull():
                    QMessageBox.warning(
                        self, "Görüntü yüklenemedi",
                        f"{key.capitalize()} parçası okunamadı:\n{new_path}"
                    )
                    continue
            old_path = self.stitch_files.get(key)
            new_files[key] = new_path
            if old_path and old_path != new_path:
                self._stitch_pixmap_cache.pop(old_path, None)
                self._stitch_array_cache.pop(old_path, None)
            changed = True

        # ÜÇÜNÜ BİRDEN ana uygulamaya uygula. Böylece dialogdan çıkınca sadece
        # son seçilen parça kalması mümkün değil.
        self.stitch_files = new_files

        if dialog.folder_path:
            self.last_stitch_folder = dialog.folder_path

        # Alt paneldeki butonları gerçek duruma göre güncelle.
        names = {
            "servical": "Servikal",
            "dorsal": "Dorsal",
            "lumbar": "Lomber",
        }
        for key, label in names.items():
            loaded = bool(self.stitch_files.get(key))
            btn = self.stitch_load_buttons.get(key)
            rem = self.stitch_remove_buttons.get(key)
            if btn is not None:
                btn.setText(f"{label} ✓" if loaded else f"{label} Yükle")
            if rem is not None:
                rem.setVisible(loaded)

        self._refresh_stitch_part_buttons()

        if changed:
            self.manual_stage_index = 0
            self.manual_points = {}
            self.manual_junction_offsets = {}
            self.is_stitched_completed = False
            # Yeni/yenilenen parça için önceki manuel kaydırmayı sıfırla.
            for key in ("servical", "dorsal", "lumbar"):
                if not self.stitch_files.get(key):
                    self.stitch_part_offsets[key] = [0.0, 0.0]
            self._refresh_stitch_part_buttons()
            self.update_stitched_spine()

            loaded_names = [names[k] for k in ("servical", "dorsal", "lumbar") if self.stitch_files.get(k)]
            self.statusBar().showMessage(
                "Yüklü parçalar: " + (" + ".join(loaded_names) if loaded_names else "yok")
            )


    def remove_stitch_part(self, part_name):
        old_path = self.stitch_files.get(part_name)
        self.stitch_files[part_name] = None
        if old_path:
            self._stitch_pixmap_cache.pop(old_path, None)
            self._stitch_array_cache.pop(old_path, None)
            self._stitch_gray_cache.pop(old_path, None)
            self._stitch_gray_flag_cache.pop(old_path, None)
            self._auto_align_cache = {k: v for k, v in self._auto_align_cache.items() if old_path not in k}
        if part_name in self.stitch_scenes:
            self.stitch_scenes[part_name].clear()

        # Parça silinince ona bağlı manuel eklem kayıtlarını da temizle.
        self.manual_junction_offsets = {
            k: v for k, v in self.manual_junction_offsets.items()
            if part_name not in k
        }
        self.manual_stage_index = 0

        btn_rem = self.stitch_remove_buttons.get(part_name)
        if btn_rem is not None:
            btn_rem.setVisible(False)

        self.update_stitched_spine()

    def trigger_stitch_action(self):
        self.update_stitched_spine()
        self.is_stitched_completed = True
        self.lbl_status_badge.setText("Sonuç hazır")
        self.lbl_status_badge.setStyleSheet("background-color: #27ae60; color: white; padding: 5px 10px; border-radius: 4px; font-weight: bold; font-size: 11px;")
        self.controls_container.setVisible(True)
        if hasattr(self, "controls_scroll"):
            self.controls_scroll.setVisible(True)

    def _clear_layout_recursive(self, layout):
        """Nested layoutlar dahil bütün eski kontrol widgetlarını temizler."""
        while layout.count():
            item = layout.takeAt(0)
            child_layout = item.layout()
            child_widget = item.widget()
            if child_layout is not None:
                self._clear_layout_recursive(child_layout)
                child_layout.deleteLater()
            elif child_widget is not None:
                child_widget.hide()
                child_widget.setParent(None)
                child_widget.deleteLater()

    def on_confirm_finish_clicked(self):
        # Sadece takeAt() kullanmak nested QHBox/QVBox layoutlarını bırakıyor,
        # bu yüzden final kontrolleri eski widgetların üzerine biniyordu.
        self._clear_layout_recursive(self.controls_layout)
        self.controls_layout.setContentsMargins(0, 0, 0, 0)
        self.controls_layout.setSpacing(6)

        self.controls_layout.addWidget(QLabel("<b>Önizleme / Hizalama Kontrolleri</b>"))
        lbl_sonuc = QLabel("Sonuç Görüntüsü")
        lbl_sonuc.setStyleSheet("color: #bdc3c7; font-weight: bold; font-size: 11px;")
        self.controls_layout.addWidget(lbl_sonuc)
        
        zoom_box = QHBoxLayout()
        zoom_box.addWidget(QLabel("Yakınlaştırma:"))
        self.lbl_zoom_val = QLabel("1.00x")
        zoom_box.addWidget(self.lbl_zoom_val)
        zoom_box.addStretch()
        self.controls_layout.addLayout(zoom_box)
        
        self.stitch_slider = QSlider(Qt.Horizontal)
        self.stitch_slider.setRange(10, 300)
        self.stitch_slider.setValue(100)
        self.stitch_slider.valueChanged.connect(self.on_stitch_zoom_changed)
        self.controls_layout.addWidget(self.stitch_slider)
        
        img_adjust_box = QVBoxLayout()
        img_adjust_box.addWidget(QLabel("<b>Görüntü Ayarı (sadece görsel)</b>"))
        
        b_box = QHBoxLayout()
        b_box.addWidget(QLabel("Parlaklık:"))
        self.sl_brightness = QSlider(Qt.Horizontal)
        self.sl_brightness.setRange(-100, 100)
        self.sl_brightness.setValue(self.final_brightness)
        self.sl_brightness.valueChanged.connect(self._on_final_brightness_changed)
        b_box.addWidget(self.sl_brightness)
        img_adjust_box.addLayout(b_box)
        
        c_box = QHBoxLayout()
        c_box.addWidget(QLabel("Kontrast:"))
        self.sl_contrast = QSlider(Qt.Horizontal)
        self.sl_contrast.setRange(-100, 100)
        self.sl_contrast.setValue(self.final_contrast)
        self.sl_contrast.valueChanged.connect(self._on_final_contrast_changed)
        c_box.addWidget(self.sl_contrast)
        img_adjust_box.addLayout(c_box)
        
        btn_reset_img = QPushButton("Görüntü Ayarını Sıfırla")
        btn_reset_img.setStyleSheet("background-color: #34495e; color: white; padding: 6px;")
        btn_reset_img.clicked.connect(self._reset_final_image_adjustment)
        img_adjust_box.addWidget(btn_reset_img)
        self.controls_layout.addLayout(img_adjust_box)
        
        measure_box = QVBoxLayout()
        measure_box.addWidget(QLabel("<b>Ölçüm</b>"))
        self.chk_cobb_mode = QCheckBox("Ölçüm Modu (Cobb Açısı)\nGörüntüde 4 nokta tıklayın")
        self.chk_cobb_mode.setStyleSheet("color: #ecf0f1; font-size: 11px;")
        self.chk_cobb_mode.setChecked(self.cobb_mode_active)
        self.chk_cobb_mode.toggled.connect(self._on_cobb_checkbox_toggled)
        measure_box.addWidget(self.chk_cobb_mode)
            
        btn_clear_meas = QPushButton("Ölçümü Temizle")
        btn_clear_meas.setStyleSheet("background-color: #34495e; color: white; padding: 6px;")
        btn_clear_meas.clicked.connect(self.clear_cobb_measurement)
        measure_box.addWidget(btn_clear_meas)
        
        lbl_warning = QLabel("Not: Kesin klinik değerlendirme için uzman hekim görüşü esastır.")
        lbl_warning.setWordWrap(True)
        lbl_warning.setStyleSheet("color: #e74c3c; font-size: 10px; margin-top: 4px;")
        measure_box.addWidget(lbl_warning)
        self.controls_layout.addLayout(measure_box)
        
        btn_save_files = QPushButton("Kaydet (PNG + DICOM)")
        btn_save_files.setStyleSheet("background-color: #2980b9; color: white; font-weight: bold; padding: 10px; border-radius: 4px; margin-top: 10px;")
        btn_save_files.clicked.connect(self.save_final_result)
        self.controls_layout.addWidget(btn_save_files)

        # Final kontrol grubunun yeni yüksekliğini QScrollArea'ya bildir.
        self.controls_container.adjustSize()
        self.controls_container.updateGeometry()
        if hasattr(self, "controls_scroll"):
            self.controls_scroll.updateGeometry()
            self.controls_scroll.verticalScrollBar().setValue(0)

        self.statusBar().showMessage("Omurga birleştirme onaylandı.")

    def _on_final_brightness_changed(self, val):
        self.final_brightness = val
        self._apply_final_image_adjustment()

    def _on_final_contrast_changed(self, val):
        self.final_contrast = val
        self._apply_final_image_adjustment()

    def _reset_final_image_adjustment(self):
        self.final_brightness = 0
        self.final_contrast = 0
        if hasattr(self, 'sl_brightness'):
            self.sl_brightness.blockSignals(True)
            self.sl_brightness.setValue(0)
            self.sl_brightness.blockSignals(False)
        if hasattr(self, 'sl_contrast'):
            self.sl_contrast.blockSignals(True)
            self.sl_contrast.setValue(0)
            self.sl_contrast.blockSignals(False)
        self._apply_final_image_adjustment()

    def _apply_final_image_adjustment(self):
        if self.final_result_qimage is None:
            return
        arr = self._qimage_to_numpy(self.final_result_qimage).astype(np.float32)
        factor = 1.0 + (self.final_contrast / 100.0)
        rgb = arr[..., :3]
        rgb = (rgb - 127.5) * factor + 127.5 + self.final_brightness
        arr[..., :3] = np.clip(rgb, 0, 255)
        qimg = self._numpy_to_qimage(arr.astype(np.uint8))
        self.stitch_scene.clear()
        self.stitch_scene.addPixmap(QPixmap.fromImage(qimg))

    def _on_cobb_checkbox_toggled(self, checked):
        if checked != self.cobb_mode_active:
            self.toggle_cobb_measurement()

    def save_final_result(self):
        if self.final_result_qimage is None:
            QMessageBox.warning(self, "Kaydet", "Kaydedilecek bir sonuç bulunamadı.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Sonucu Kaydet", "birlesik_omurga.png", "PNG Dosyası (*.png)")
        if not path:
            return
        if not path.lower().endswith(".png"):
            path += ".png"

        arr = self._qimage_to_numpy(self.final_result_qimage).astype(np.float32)
        factor = 1.0 + (self.final_contrast / 100.0)
        rgb = arr[..., :3]
        rgb = (rgb - 127.5) * factor + 127.5 + self.final_brightness
        arr[..., :3] = np.clip(rgb, 0, 255)
        out_arr = arr.astype(np.uint8)
        qimg = self._numpy_to_qimage(out_arr)
        ok_png = qimg.save(path, "PNG")

        dicom_path = path[:-4] + ".dcm"
        ok_dicom = False
        try:
            gray = (0.114 * out_arr[..., 0] + 0.587 * out_arr[..., 1] + 0.299 * out_arr[..., 2]).astype(np.uint8)
            ok_dicom = self._save_as_dicom(gray, dicom_path)
        except Exception as e:
            print(f"DICOM kaydetme hatası: {e}")

        if ok_png and ok_dicom:
            self.statusBar().showMessage(f"Kaydedildi: {path} ve {dicom_path}")
        elif ok_png:
            self.statusBar().showMessage(f"PNG kaydedildi ({path}); DICOM kaydı başarısız oldu.")
        else:
            self.statusBar().showMessage("Kaydetme başarısız oldu.")

    def _save_as_dicom(self, gray_arr, path):
        from pydicom.dataset import FileDataset, FileMetaDataset
        from pydicom.uid import generate_uid, SecondaryCaptureImageStorage, ExplicitVRLittleEndian

        ref_ds = None
        for p in self.stitch_files.values():
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
        ds.PixelData = np.ascontiguousarray(gray_arr).tobytes()

        ds.is_little_endian = True
        ds.is_implicit_VR = False
        ds.save_as(path, write_like_original=False)
        return True

    @staticmethod
    def _qimage_to_numpy(img):
        img = img.convertToFormat(QImage.Format_ARGB32)
        w, h = img.width(), img.height()
        bpl = img.bytesPerLine()
        buf = bytes(img.constBits())
        arr = np.frombuffer(buf, dtype=np.uint8, count=bpl * h).reshape((h, bpl))
        return arr[:, :w * 4].reshape((h, w, 4)).copy()

    @staticmethod
    def _numpy_to_qimage(arr):
        h, w = arr.shape[0], arr.shape[1]
        arr = np.ascontiguousarray(arr)
        return QImage(arr.data, w, h, w * 4, QImage.Format_ARGB32).copy()

    @staticmethod
    def _match_histogram_linear(arr_src, arr_ref, y_src_slice, y_ref_slice):
        src_region = arr_src[y_src_slice][..., :3].astype(np.float32)
        ref_region = arr_ref[y_ref_slice][..., :3].astype(np.float32)
        if src_region.size == 0 or ref_region.size == 0:
            return arr_src
        src_mean, src_std = src_region.mean(), src_region.std() + 1e-6
        ref_mean, ref_std = ref_region.mean(), ref_region.std() + 1e-6
        rgb = arr_src[..., :3].astype(np.float32)
        rgb = (rgb - src_mean) * (ref_std / src_std) + ref_mean
        arr_src[..., :3] = np.clip(rgb, 0, 255).astype(np.uint8)
        return arr_src

    @staticmethod
    def _to_gray(arr_bgra):
        b = arr_bgra[..., 0].astype(np.float32)
        g = arr_bgra[..., 1].astype(np.float32)
        r = arr_bgra[..., 2].astype(np.float32)
        return 0.114 * b + 0.587 * g + 0.299 * r

    @staticmethod
    def _tile_normalize(gray, tile=24):
        h, w = gray.shape
        pad_h = (-h) % tile
        pad_w = (-w) % tile
        padded = np.pad(gray, ((0, pad_h), (0, pad_w)), mode='reflect').astype(np.float32)
        ph, pw = padded.shape
        blocks = padded.reshape(ph // tile, tile, pw // tile, tile)
        means = blocks.mean(axis=(1, 3), keepdims=True)
        stds = blocks.std(axis=(1, 3), keepdims=True) + 1e-4
        normed = (blocks - means) / stds
        return normed.reshape(ph, pw)[:h, :w]

    @staticmethod
    def _sobel_magnitude(gray):
        gray = gray.astype(np.float32)
        padded = np.pad(gray, 1, mode='reflect')
        kx = np.array([[-1, 0, 1], [-2, 0, 2], [-1, 0, 1]], dtype=np.float32)
        ky = kx.T
        gx = np.zeros_like(gray)
        gy = np.zeros_like(gray)
        for i in range(3):
            for j in range(3):
                window = padded[i:i + gray.shape[0], j:j + gray.shape[1]]
                gx += kx[i, j] * window
                gy += ky[i, j] * window
        return np.hypot(gx, gy)

    @staticmethod
    def _phase_correlate(img_a, img_b):
        h, w = img_a.shape
        win = np.hanning(h)[:, None] * np.hanning(w)[None, :]
        a = (img_a - img_a.mean()) * win
        b = (img_b - img_b.mean()) * win
        fa = np.fft.fft2(a)
        fb = np.fft.fft2(b)
        r_fft = fa * np.conj(fb)
        r_fft /= (np.abs(r_fft) + 1e-8)
        r = np.fft.fftshift(np.fft.ifft2(r_fft).real)
        peak_idx = np.unravel_index(np.argmax(r), r.shape)
        peak_val = r[peak_idx]
        dy = peak_idx[0] - h // 2
        dx = peak_idx[1] - w // 2
        score = float(np.clip(peak_val / (np.mean(np.abs(r)) * 50 + 1e-8), 0.0, 1.0))
        return dx, dy, score

    @staticmethod
    def _rotate_array(arr, angle_deg, fill=0):
        if abs(angle_deg) < 1e-6:
            return arr.copy()
        h, w = arr.shape[0], arr.shape[1]
        angle = np.radians(angle_deg)
        cos_a, sin_a = np.cos(angle), np.sin(angle)
        cy, cx = h / 2.0, w / 2.0
        yy, xx = np.indices((h, w))
        x_rel = xx - cx
        y_rel = yy - cy
        src_x = cos_a * x_rel + sin_a * y_rel + cx
        src_y = -sin_a * x_rel + cos_a * y_rel + cy
        src_xi = np.clip(np.round(src_x).astype(np.int32), 0, w - 1)
        src_yi = np.clip(np.round(src_y).astype(np.int32), 0, h - 1)
        valid = (np.round(src_x) >= 0) & (np.round(src_x) < w) & (np.round(src_y) >= 0) & (np.round(src_y) < h)
        out = arr[src_yi, src_xi]
        mask = valid if out.ndim == 2 else valid[..., None]
        out = np.where(mask, out, fill)
        return out.astype(arr.dtype)

   
    @staticmethod
    def _gray_to_bgra(gray, alpha=None):
        """8-bit gri görüntüyü QImage için BGRA'ya hızlı çevirir."""
        gray = np.ascontiguousarray(gray, dtype=np.uint8)
        h, w = gray.shape
        out = np.empty((h, w, 4), dtype=np.uint8)
        out[..., 0] = gray
        out[..., 1] = gray
        out[..., 2] = gray
        if alpha is None:
            out[..., 3] = 255
        else:
            out[..., 3] = np.clip(alpha, 0, 255).astype(np.uint8)
        return out

    def _get_stitch_mask(self, img_h, img_w, top_overlap, bottom_overlap):
        """Feather maskesini önbellekten al; ok tuşlarında tekrar üretme."""
        key = (int(img_h), int(img_w), int(top_overlap), int(bottom_overlap))
        cached = self._stitch_mask_cache.get(key)
        if cached is not None:
            return cached

        mask = np.ones((img_h, img_w), dtype=np.float32)
        if top_overlap > 1:
            n = min(int(top_overlap), img_h)
            if n > 1:
                ramp = np.linspace(0.0, 1.0, n, dtype=np.float32)
                ramp = ramp * ramp * (3.0 - 2.0 * ramp)
                mask[:n, :] *= ramp[:, None]
        if bottom_overlap > 1:
            n = min(int(bottom_overlap), img_h)
            if n > 1:
                ramp = np.linspace(1.0, 0.0, n, dtype=np.float32)
                ramp = ramp * ramp * (3.0 - 2.0 * ramp)
                mask[img_h - n:img_h, :] *= ramp[:, None]

        self._stitch_mask_cache[key] = mask
        return mask

    @staticmethod
    def _apply_checker_bw(arr, y_start, y_end, cell=20, intensity=0.32):
        """Sadece mevcut görüntü piksellerine dama efekti uygular.
        Alfa kanalına dokunmaz; böylece dama açıldığında tüm canvasın siyaha
        düşmesi engellenir.
        """
        if arr is None or arr.ndim != 3 or arr.shape[2] < 4:
            return arr

        y_start = max(0, int(y_start))
        y_end = min(arr.shape[0], int(y_end))
        if y_end <= y_start:
            return arr

        w = arr.shape[1]
        band_h = y_end - y_start
        yy, xx = np.indices((band_h, w))
        checker = ((xx // max(4, int(cell))) + (yy // max(4, int(cell)))) % 2 == 0

        region = arr[y_start:y_end, :, :3].astype(np.float32)
        alpha = arr[y_start:y_end, :, 3:4].astype(np.float32)

        # Şeffaf piksellere işlem yapma.
        visible = alpha > 1.0
        bright = region * (1.0 - intensity) + 255.0 * intensity
        dark = region * (1.0 - intensity)
        mixed = np.where(checker[..., None], bright, dark)

        region_new = np.where(visible, mixed, region)
        arr[y_start:y_end, :, :3] = np.clip(region_new, 0, 255).astype(np.uint8)

        # Alfa kanalını aynen koru.
        return arr

    def load_dicoms(self):
        # Ana pencerenin görünümünü değiştirmeden, seçim sırasında önizleme +
        # hasta/etüt bilgisi sağlayan seçim penceresi kullanılır.
        initial = list(self.loaded_files.values())
        dialog = StudySelectionDialog(initial_files=initial, parent=self)
        if dialog.exec() != QDialog.Accepted:
            return

        selected = list(getattr(dialog, 'selected_paths', []))
        if not selected:
            return

        added = 0
        for file_name in selected:
            _, added_to_tracking = self._ensure_tracking_path(file_name)
            if added_to_tracking:
                # Takipten açılan dosya da Viewer ağacına eklenir; iki modül
                # aynı hasta/tetkik/seri listesini gösterir.
                self._add_viewer_paths([file_name])
                added += 1

        if added:
            # Yeni eklenenleri birlikte seç; Overlay'de ilk iki tanesi karşılaştırılır.
            self.study_list_widget.clearSelection()
            count = self.study_list_widget.count()
            for i in range(count - 1, max(-1, count - added - 1), -1):
                self.study_list_widget.item(i).setSelected(True)
            self.statusBar().showMessage(f"{added} görüntü yüklendi. Overlay için iki görüntüyü seçip 'Üst Üste'ye basın.")
        elif self.study_list_widget.count() > 0:
            self.study_list_widget.setCurrentRow(0)

    def _default_window(self, file_path):
        key = os.path.abspath(file_path)
        if key in self._default_window_cache:
            return self._default_window_cache[key]
        try:
            ds = pydicom.dcmread(file_path, stop_before_pixels=True)
            wc = getattr(ds, 'WindowCenter', None)
            ww = getattr(ds, 'WindowWidth', None)
            if isinstance(wc, (list, pydicom.multival.MultiValue)):
                wc = wc[0] if wc else None
            if isinstance(ww, (list, pydicom.multival.MultiValue)):
                ww = ww[0] if ww else None
            wc = float(wc) if wc is not None else 1000.0
            ww = max(1.0, float(ww)) if ww is not None else 2000.0
        except Exception:
            wc, ww = 1000.0, 2000.0
        self._default_window_cache[key] = (wc, ww)
        return wc, ww

    def get_image_pixmap(self, file_path):
        brightness_val = self.brightness_slider.value() if hasattr(self, 'brightness_slider') else 0
        default_wc, default_ww = self._default_window(file_path)
        wc, ww = self.window_settings.get(os.path.abspath(file_path), (default_wc, default_ww))
        cache_key = (os.path.abspath(file_path), int(brightness_val), round(float(wc), 3), round(float(ww), 3))
        cached = self._viewer_pixmap_cache.get(cache_key)
        if cached is not None and not cached.isNull():
            return cached
        try:
            ds = pydicom.dcmread(file_path)
            arr = process_dicom_array(ds, brightness_val, wc, ww)
            if arr is not None:
                height, width = arr.shape
                q_img = QImage(arr.data, width, height, width, QImage.Format_Grayscale8)
                pix = QPixmap.fromImage(q_img.copy())
                self._viewer_pixmap_cache[cache_key] = pix
                return pix
        except Exception:
            pixmap = QPixmap(file_path)
            if not pixmap.isNull():
                return pixmap
        return QPixmap()

    def _selected_window_paths(self):
        paths = []
        for item in self.study_list_widget.selectedItems():
            path = item.data(Qt.UserRole)
            if path and os.path.exists(path):
                paths.append(path)
            elif item.text() in self.loaded_files:
                paths.append(self.loaded_files[item.text()])
        return paths

    def apply_window_preset(self, preset):
        paths = self._selected_window_paths()
        if not paths:
            self.statusBar().showMessage("Pencere ayarı için önce tetkik seçin.")
            return
        presets = {
            "soft": (300.0, 1200.0),
            # Sert: Orijinalden daha koyu ve kontrastlı.
            # (WW=4000, WL=2000) daha koyu ve kemik detayları belirgin.
            "bone": (2000.0, 4000.0),
        }
        if preset == "original":
            for path in paths:
                self.window_settings.pop(os.path.abspath(path), None)
            self._viewer_pixmap_cache.clear()
            wc, ww = self._default_window(paths[0])
            self.lbl_windowing.setText(f"W/L: Orijinal | WW {ww:.0f} | WL {wc:.0f}")
            self.update_viewers()
            self.statusBar().showMessage("W/L preset uygulandı: Orijinal")
            return
        for path in paths:
            self.window_settings[os.path.abspath(path)] = presets[preset]
        self._viewer_pixmap_cache.clear()
        wc, ww = self.window_settings[os.path.abspath(paths[0])]
        self.lbl_windowing.setText(f"W/L: WW {ww:.0f} | WL {wc:.0f} | Orta fare ile ayarla")
        self.update_viewers()
        self.statusBar().showMessage(f"W/L preset uygulandı: {preset}")

    def reset_window_level(self):
        paths = self._selected_window_paths()
        if not paths:
            self.statusBar().showMessage("Pencere ayarını sıfırlamak için önce tetkik seçin.")
            return
        for path in paths:
            self.window_settings.pop(os.path.abspath(path), None)
        self._viewer_pixmap_cache.clear()
        wc, ww = self._default_window(paths[0])
        self.lbl_windowing.setText(f"W/L: WW {ww:.0f} | WL {wc:.0f} | Orta fare ile ayarla")
        self.update_viewers()
        self.statusBar().showMessage("W/L sıfırlandı; DICOM varsayılanına dönüldü.")

    def adjust_window_level(self, side, dx, dy):
        paths = self._selected_window_paths()
        if not paths:
            return
        target_paths = paths[:2] if self.current_mode == 'overlay' else ([paths[1]] if side == 'right' and len(paths) >= 2 else [paths[0]])
        for path in target_paths:
            key = os.path.abspath(path)
            wc, ww = self.window_settings.get(key, self._default_window(path))
            ww = float(np.clip(ww * (1.0 + dx * 0.01), 8.0, 20000.0))
            wc -= dy * max(1.0, ww) * 0.005
            self.window_settings[key] = (float(wc), ww)
        self._viewer_pixmap_cache.clear()
        wc, ww = self.window_settings[os.path.abspath(target_paths[0])]
        self.lbl_windowing.setText(f"W/L: WW {ww:.0f} | WL {wc:.0f} | Orta fare ile ayarla")
        self.update_viewers()

    def update_viewers(self):
        selected_items = self.study_list_widget.selectedItems()
        selected_paths = []
        for item in selected_items:
            path = item.data(Qt.UserRole)
            if path and os.path.exists(path):
                selected_paths.append(path)
            elif item.text() in self.loaded_files:
                selected_paths.append(self.loaded_files[item.text()])

        self.scene_left.clear()
        self.scene_right.clear()
        self.overlay_item = None
        self.cobb_points.clear()

        if self.current_mode == 'side_by_side':
            self.view_right.setVisible(True)
            if len(selected_paths) >= 1:
                pix_left = self.get_image_pixmap(selected_paths[0])
                if not pix_left.isNull():
                    self.scene_left.addPixmap(pix_left)
                    self.view_left.fitInView(self.scene_left.itemsBoundingRect(), Qt.KeepAspectRatio)
            if len(selected_paths) >= 2:
                pix_right = self.get_image_pixmap(selected_paths[1])
                if not pix_right.isNull():
                    self.scene_right.addPixmap(pix_right)
                    self.view_right.fitInView(self.scene_right.itemsBoundingRect(), Qt.KeepAspectRatio)
            return

        if self.current_mode == 'overlay':
            self.view_right.setVisible(False)
            if not selected_paths:
                return
            pix_base = self.get_image_pixmap(selected_paths[0])
            if pix_base.isNull():
                return
            base_item = self.scene_left.addPixmap(pix_base)
            base_item.setZValue(0)

            if len(selected_paths) >= 2:
                pix_overlay = self.get_image_pixmap(selected_paths[1])
                if not pix_overlay.isNull():
                    # Oranı bozma: ikinci görüntünün ilk görüntüye göre başlangıç
                    # ölçeğini genişlik üzerinden hesapla; daha sonra kullanıcı
                    # Zoom/X/Y sliderlarıyla ince ayar yapar.
                    base_w = max(1, pix_base.width())
                    pix_overlay = pix_overlay.scaledToWidth(base_w, Qt.SmoothTransformation)
                    initial_scale = 1.0
                    self._overlay_initial_scale = initial_scale
                    self.overlay_item = self.scene_left.addPixmap(pix_overlay)
                    self.overlay_item.setZValue(1)
                    self.overlay_item.setOpacity(self.overlay_opacity)
                    self.overlay_item.setPos(self.overlay_offset_x, self.overlay_offset_y)
                    self.overlay_item.setScale(self.overlay_scale * initial_scale)
                    self.overlay_item.setToolTip("Sol fare ile sürükleyerek overlay'i hizalayın")

            # Görünümü yalnızca temel görüntüye göre sığdır. Overlay'in kenarları
            # büyüdüğünde view otomatik olarak küçülüp hizalamayı bozmasın.
            self.view_left.fitInView(pix_base.rect(), Qt.KeepAspectRatio)
            self._update_overlay_label()

    def _update_overlay_label(self):
        if hasattr(self, 'lbl_overlay_offset'):
            self.lbl_overlay_offset.setText(
                f"ΔX {self.overlay_offset_x:+.0f} | ΔY {self.overlay_offset_y:+.0f} | Z {self.overlay_scale:.2f}x"
            )

    def move_overlay(self, dx, dy):
        if self.current_mode != 'overlay' or self.overlay_item is None:
            return
        self.overlay_offset_x += float(dx)
        self.overlay_offset_y += float(dy)
        self.overlay_item.setPos(self.overlay_offset_x, self.overlay_offset_y)
        self._sync_overlay_sliders()
        self._update_overlay_label()

    def _sync_overlay_sliders(self):
        for name, value in (
            ('overlay_x_slider', int(round(self.overlay_offset_x))),
            ('overlay_y_slider', int(round(self.overlay_offset_y))),
            ('overlay_zoom_slider', int(round(self.overlay_scale * 100.0))),
        ):
            slider = getattr(self, name, None)
            if slider is not None:
                slider.blockSignals(True)
                slider.setValue(max(slider.minimum(), min(slider.maximum(), value)))
                slider.blockSignals(False)

    def on_overlay_x_changed(self, value):
        self.overlay_offset_x = float(value)
        if self.overlay_item is not None:
            self.overlay_item.setPos(self.overlay_offset_x, self.overlay_offset_y)
        self._update_overlay_label()

    def on_overlay_y_changed(self, value):
        self.overlay_offset_y = float(value)
        if self.overlay_item is not None:
            self.overlay_item.setPos(self.overlay_offset_x, self.overlay_offset_y)
        self._update_overlay_label()

    def on_overlay_zoom_changed(self, value):
        self.overlay_scale = max(0.5, float(value) / 100.0)
        if self.overlay_item is not None:
            # Base genişliğine göre oluşturulan başlangıç ölçeğini korumak için
            # pixmap boyutundan değil mevcut item ölçeğinden ilerliyoruz.
            current = getattr(self, '_overlay_initial_scale', None)
            if current is not None:
                self.overlay_item.setScale(current * self.overlay_scale)
            else:
                self.update_viewers()
        self._update_overlay_label()

    def on_overlay_opacity_changed(self, value):
        self.overlay_opacity = value / 100.0
        if self.overlay_item is not None:
            self.overlay_item.setOpacity(self.overlay_opacity)

    def reset_overlay_adjustment(self):
        self.overlay_offset_x = 0.0
        self.overlay_offset_y = 0.0
        self.overlay_opacity = 0.50
        self.overlay_scale = 1.0
        self._sync_overlay_sliders()
        if hasattr(self, 'overlay_opacity_slider'):
            self.overlay_opacity_slider.blockSignals(True)
            self.overlay_opacity_slider.setValue(50)
            self.overlay_opacity_slider.blockSignals(False)
        self.update_viewers()
        self.statusBar().showMessage("Overlay hizalaması, zoom ve saydamlık sıfırlandı.")

    def set_side_by_side_mode(self):
        self.current_mode = "side_by_side"
        self.btn_side_by_side.setStyleSheet("padding: 8px 15px; background-color: #2980b9; color: white;")
        self.btn_overlay.setStyleSheet("padding: 8px 15px; background-color: #34495e; color: white;")
        self.update_viewers()
        self.statusBar().showMessage("Mod: Yan Yana Mukayese aktif.")

    def set_overlay_mode(self):
        self.current_mode = "overlay"
        self.btn_overlay.setStyleSheet("padding: 8px 15px; background-color: #2980b9; color: white;")
        self.btn_side_by_side.setStyleSheet("padding: 8px 15px; background-color: #34495e; color: white;")
        self.update_viewers()
        self.statusBar().showMessage("Mod: Üst Üste (Overlay) Şeffaf Çakıştırma aktif.")

    def toggle_cobb_measurement(self):
        self.cobb_mode_active = not self.cobb_mode_active
        for v in (getattr(self, 'view_left', None), getattr(self, 'view_right', None), getattr(self, 'stitch_view', None)):
            if v is not None:
                v.refresh_cursor()
        if self.cobb_mode_active:
            self.btn_measure_cobb.setStyleSheet("padding: 8px 15px; background-color: #e67e22; color: white;")
            self.cobb_points.clear()
            self.cobb_target_side = None
            self.statusBar().showMessage("Cobb Ölçümü: Lütfen ölçüm yapmak istediğiniz ekrana tıklayarak başlayın.")
        else:
            self.btn_measure_cobb.setStyleSheet("padding: 8px 15px; background-color: #34495e; color: white;")
            self.statusBar().showMessage("Cobb Açısı Ölçüm Modu kapatıldı.")

    def handle_cobb_click(self, side: str, pos: QPointF):
        if self.cobb_target_side is None:
            self.cobb_target_side = side
        elif self.cobb_target_side != side:
            return 

        self.cobb_points.append(pos)
        if side == 'left':
            target_scene = self.scene_left
        elif side == 'right':
            target_scene = self.scene_right
        else:
            target_scene = self.stitch_scene
        
        pen = QPen(Qt.red, 4)
        target_scene.addEllipse(pos.x() - 4, pos.y() - 4, 8, 8, pen)
        
        n = len(self.cobb_points)
        if n == 2:
            target_scene.addLine(self.cobb_points[0].x(), self.cobb_points[0].y(), 
                                 self.cobb_points[1].x(), self.cobb_points[1].y(), pen)
            self.statusBar().showMessage(f"Cobb Ölçümü ({side.upper()}): Alt omurga için 2 nokta daha belirleyin.")
        elif n == 4:
            pen_blue = QPen(Qt.cyan, 3)
            target_scene.addLine(self.cobb_points[2].x(), self.cobb_points[2].y(), 
                                 self.cobb_points[3].x(), self.cobb_points[3].y(), pen_blue)
            
            v1 = (self.cobb_points[1].x() - self.cobb_points[0].x(), self.cobb_points[1].y() - self.cobb_points[0].y())
            v2 = (self.cobb_points[3].x() - self.cobb_points[2].x(), self.cobb_points[3].y() - self.cobb_points[2].y())
            
            dot = v1[0]*v2[0] + v1[1]*v2[1]
            mod1 = math.hypot(v1[0], v1[1])
            mod2 = math.hypot(v2[0], v2[1])
            
            if mod1 > 0 and mod2 > 0:
                cos_angle = max(-1.0, min(1.0, dot / (mod1 * mod2)))
                angle_deg = math.degrees(math.acos(cos_angle))
                
                self.statusBar().showMessage(f"📐 Hesaplanan Cobb Açısı ({side.upper()}): {angle_deg:.2f}°")
                
                text_item = target_scene.addText(f"Cobb: {angle_deg:.2f}°", QFont("Segoe UI", 14, QFont.Bold))
                text_item.setDefaultTextColor(Qt.yellow)
                text_item.setPos(self.cobb_points[2])
            
            self.cobb_points.clear()
            self.cobb_target_side = None
            self.cobb_mode_active = False
            self.btn_measure_cobb.setStyleSheet("padding: 8px 15px; background-color: #34495e; color: white;")
            if hasattr(self, 'chk_cobb_mode'):
                self.chk_cobb_mode.blockSignals(True)
                self.chk_cobb_mode.setChecked(False)
                self.chk_cobb_mode.blockSignals(False)
            for v in (getattr(self, 'view_left', None), getattr(self, 'view_right', None), getattr(self, 'stitch_view', None)):
                if v is not None:
                    v.refresh_cursor()

    def clear_cobb_measurement(self):
        self.cobb_points.clear()
        self.cobb_target_side = None
        self.cobb_mode_active = False
        self.btn_measure_cobb.setStyleSheet("padding: 8px 15px; background-color: #34495e; color: white;")
        if hasattr(self, 'chk_cobb_mode'):
            self.chk_cobb_mode.blockSignals(True)
            self.chk_cobb_mode.setChecked(False)
            self.chk_cobb_mode.blockSignals(False)
        for scene in (getattr(self, 'scene_left', None), getattr(self, 'scene_right', None), getattr(self, 'stitch_scene', None)):
            if scene is None:
                continue
            for item in list(scene.items()):
                if not isinstance(item, QGraphicsPixmapItem):
                    scene.removeItem(item)
        for v in (getattr(self, 'view_left', None), getattr(self, 'view_right', None), getattr(self, 'stitch_view', None)):
            if v is not None:
                v.refresh_cursor()
        self.statusBar().showMessage("Ölçüm temizlendi.")


if __name__ == "__main__":
    # Ana uygulama giriş noktası budur. Modüler katman (tetkik geçmişi,
    # takip özeti, PACS vb.) checkpoint sınıfını burada tanımlanan uygulama
    # üzerinden genişletir. Böylece kullanıcı yalnızca main.py çalıştırır.
    from modular_app.run_modular import main as start_application

    start_application(ScoliosisFollowUpApp)

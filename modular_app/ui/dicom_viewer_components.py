"""DICOM görüntüleme için ortak UI bileşenleri.

Bu modül:
- DICOM -> 8 bit görüntü dönüşümünü,
- tek parça önizlemeli DICOM seçiciyi,
- ortak StudySelectionDialog'u,
- etkileşimli QGraphicsView sınıfını
barındırır.
"""

import os
import math
import pydicom
import numpy as np

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QGraphicsView, QGraphicsScene, QSplitter,
    QAbstractItemView, QListWidget, QListWidgetItem,
    QTreeWidget, QTreeWidgetItem, QDialog, QCheckBox,
    QGridLayout, QMessageBox, QMenu, QInputDialog,
)
from PySide6.QtCore import (
    Qt, QPointF, QSize, QTimer, QRectF, QObject, QRunnable, QThreadPool, Signal,
)
from PySide6.QtGui import (
    QFont, QPixmap, QImage, QPainter, QPen, QIcon,
    QWheelEvent, QMouseEvent, QShortcut, QKeySequence, QTransform,
)
from modular_app.ui.ui_clarity import configure_action, create_context_banner

_SELECTION_THUMBNAIL_POOL = QThreadPool()
_SELECTION_THUMBNAIL_POOL.setMaxThreadCount(4)
_SELECTION_THUMBNAIL_CACHE = {}
_SELECTION_THUMBNAIL_CACHE_LIMIT = 256
_SELECTION_PREVIEW_CACHE = {}
_SELECTION_PREVIEW_CACHE_LIMIT = 8

def process_dicom_array(
    ds,
    brightness_val=0,
    window_center=None,
    window_width=None,
    source_array=None,
):
    """DICOM -> 8-bit görüntü; source_array verilirse DICOM piksel decode tekrarlanmaz."""
    if source_array is None:
        if not hasattr(ds, 'pixel_array'):
            return None
        source_array = ds.pixel_array

    arr = np.asarray(source_array)
    if arr.ndim == 3:
        samples = int(getattr(ds, 'SamplesPerPixel', 1) or 1)
        if samples > 1 and arr.shape[-1] in (3, 4):
            arr = arr[..., 0]
        else:
            # Multi-frame görüntüde ilk kare preview için kullanılır; ana viewer
            # frame seçimini render katmanında yapar.
            arr = arr[0]
    if arr.ndim != 2:
        return None

    # Görünüm dönüşümü kaynak DICOM array'ini değiştirmemeli. Tek bir writable
    # float32 çalışma buffer'ı oluşturup rescale/window/brightness işlemlerini
    # bunun üzerinde in-place yapmak, aynı frame için ara array sayısını azaltır.
    arr = np.array(arr, dtype=np.float32, copy=True)

    slope = float(getattr(ds, 'RescaleSlope', 1.0))
    intercept = float(getattr(ds, 'RescaleIntercept', 0.0))
    if slope != 1.0:
        np.multiply(arr, slope, out=arr)
    if intercept != 0.0:
        np.add(arr, intercept, out=arr)

    photo = str(getattr(ds, 'PhotometricInterpretation', 'MONOCHROME2')).upper()
    if photo == 'MONOCHROME1':
        np.subtract(float(np.max(arr)), arr, out=arr)

    wc = window_center if window_center is not None else getattr(ds, 'WindowCenter', None)
    ww = window_width if window_width is not None else getattr(ds, 'WindowWidth', None)
    if isinstance(wc, (list, pydicom.multival.MultiValue)):
        wc = wc[0] if wc else None
    if isinstance(ww, (list, pydicom.multival.MultiValue)):
        ww = ww[0] if ww else None

    normalized = False
    if wc is not None and ww is not None:
        try:
            wc = float(wc)
            ww = max(1.0, float(ww))
            np.subtract(arr, wc - ww / 2.0, out=arr)
            np.multiply(arr, 255.0 / ww, out=arr)
            normalized = True
        except (ValueError, TypeError):
            normalized = False
    if not normalized:
        mn, mx = float(np.min(arr)), float(np.max(arr))
        if mx > mn:
            np.subtract(arr, mn, out=arr)
            np.multiply(arr, 255.0 / (mx - mn), out=arr)
        else:
            arr.fill(0.0)

    if brightness_val:
        np.add(arr, float(brightness_val) * 5.0, out=arr)
    np.clip(arr, 0, 255, out=arr)
    return arr.astype(np.uint8, copy=False)

class DicomPreviewDialog(QDialog):
    def __init__(self, part_name, initial_dir="", parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"{part_name.capitalize()} - DICOM Seç (Önizlemeli)")
        self.setObjectName("workflowDialog")
        self.resize(950, 650)

        self.selected_file_path = None
        self.folder_path = initial_dir
        self.dicom_files = []

        layout = QVBoxLayout(self)

        top_layout = QHBoxLayout()
        self.btn_select_folder = QPushButton("Klasör Tara")
        configure_action(self.btn_select_folder, label="DICOM klasörü tara", role="primary", tooltip="Bir klasördeki DICOM ve görüntü dosyalarını listele")

        self.btn_select_folder.clicked.connect(self.browse_folder)

        self.lbl_folder_path = QLabel(initial_dir if initial_dir else "Klasör seçilmedi")
        self.lbl_folder_path.setObjectName("dicomSelectionHint")

        top_layout.addWidget(self.btn_select_folder)
        top_layout.addWidget(self.lbl_folder_path, stretch=1)
        layout.addLayout(top_layout)

        splitter = QSplitter(Qt.Horizontal)

        self.file_list_widget = QListWidget()
        self.file_list_widget.setIconSize(QSize(96, 96))
        self.file_list_widget.setObjectName("dicomSelectionList")

        self.file_list_widget.itemSelectionChanged.connect(self.on_file_selected)
        self.file_list_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.file_list_widget.customContextMenuRequested.connect(self._show_file_context_menu)
        splitter.addWidget(self.file_list_widget)

        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)

        self.preview_scene = QGraphicsScene()
        self.preview_view = QGraphicsView(self.preview_scene)
        self.preview_view.setObjectName("dicomPreviewView")

        right_layout.addWidget(self.preview_view, stretch=3)

        self.info_label = QLabel("DICOM Etiket Bilgileri Bekleniyor...")
        self.info_label.setObjectName("dicomInfoLabel")

        self.info_label.setWordWrap(True)
        right_layout.addWidget(self.info_label, stretch=2)

        splitter.addWidget(right_widget)
        splitter.setSizes([280, 670])
        layout.addWidget(splitter)

        bottom_layout = QHBoxLayout()
        bottom_layout.addStretch()

        self.btn_cancel = QPushButton("İptal")
        configure_action(self.btn_cancel, label="DICOM seçimini iptal et", role="danger", tooltip="Seçim penceresini kapat")

        self.btn_cancel.clicked.connect(self.reject)

        self.btn_select = QPushButton("Bu Dosyayı Seç")
        configure_action(self.btn_select, label="Bu DICOM dosyasını seç", role="primary", tooltip="Seçili DICOM dosyasını ilgili parçaya aktar")

        self.btn_select.clicked.connect(self.accept_file)
        self.btn_select.setEnabled(False)

        bottom_layout.addWidget(self.btn_cancel)
        bottom_layout.addWidget(self.btn_select)
        layout.addLayout(bottom_layout)

        if initial_dir and os.path.exists(initial_dir):
            self.load_dicom_files_from_dir(initial_dir)

    def _preview_pixmap(self, file_path):
        try:
            ds = pydicom.dcmread(file_path)
            arr = process_dicom_array(ds)
            if arr is None:
                return None
            h, w = arr.shape
            qimg = QImage(arr.data, w, h, w, QImage.Format_Grayscale8).copy()
            pix = QPixmap.fromImage(qimg)
            if pix.width() > 96 or pix.height() > 96:
                pix = pix.scaled(96, 96, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            return pix
        except Exception:
            return None

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

                # Klasör taramasında pixel_array decode etmeyin; önizleme
                # yalnızca kullanıcı bir dosyayı seçtiğinde üretilir.
                item = QListWidgetItem(os.path.basename(full_path))
                item.setData(Qt.UserRole, full_path)
                self.file_list_widget.addItem(item)

    def _show_file_context_menu(self, pos):
        item = self.file_list_widget.itemAt(pos)
        if item is None:
            return
        row = self.file_list_widget.row(item)
        menu = QMenu(self)
        action = menu.addAction("Listeden kaldır")
        chosen = menu.exec(self.file_list_widget.viewport().mapToGlobal(pos))
        if chosen != action:
            return
        if 0 <= row < len(self.dicom_files):
            removed_path = self.dicom_files.pop(row)
            self.file_list_widget.takeItem(row)
            if self.selected_file_path == removed_path:
                self.selected_file_path = None
                self.btn_select.setEnabled(False)
                self.preview_scene.clear()
                self.info_label.setText("Bir DICOM seçin.")

    def on_file_selected(self):
        items = self.file_list_widget.selectedItems()
        if not items:
            return
        item = items[0]
        index = self.file_list_widget.row(item)
        file_path = item.data(Qt.UserRole) or (
            self.dicom_files[index] if 0 <= index < len(self.dicom_files) else None
        )
        if file_path:

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


class _SelectionThumbnailSignals(QObject):
    ready = Signal(str, QImage, str)


class _SelectionThumbnailWorker(QRunnable):
    """Decode one small list preview away from the UI thread."""

    def __init__(self, path):
        super().__init__()
        self.path = str(path)
        self.signals = _SelectionThumbnailSignals()

    def run(self):
        image = QImage()
        detail = ""
        try:
            ds = pydicom.dcmread(self.path)
            date = str(getattr(ds, "StudyDate", "") or "")
            desc = str(
                getattr(ds, "StudyDescription", "")
                or getattr(ds, "SeriesDescription", "")
                or ""
            )
            modality = str(getattr(ds, "Modality", "") or "")
            detail = "  ".join(value for value in (date, modality, desc) if value)
            arr = process_dicom_array(ds)
            if arr is not None:
                arr = np.asarray(arr)
                if arr.ndim == 3:
                    samples = int(getattr(ds, "SamplesPerPixel", 1) or 1)
                    arr = arr[..., 0] if samples > 1 and arr.shape[-1] in (3, 4) else arr[0]
                if arr.ndim == 2:
                    arr = np.ascontiguousarray(arr, dtype=np.uint8)
                    height, width = arr.shape
                    image = QImage(
                        arr.data, width, height, width, QImage.Format_Grayscale8
                    ).copy()
        except Exception:
            image = QImage(self.path)
        if not image.isNull():
            image = image.scaled(
                68, 68, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
        self.signals.ready.emit(self.path, image, detail)


class _SelectionPreviewSignals(QObject):
    ready = Signal(str, QImage, str, str)


class _SelectionPreviewWorker(QRunnable):
    """Prepare the large selected-image preview without blocking the dialog."""

    def __init__(self, path):
        super().__init__()
        self.path = str(path)
        self.signals = _SelectionPreviewSignals()

    def run(self):
        image = QImage()
        info = ""
        error = ""
        try:
            ds = pydicom.dcmread(self.path)
            arr = process_dicom_array(ds)
            if arr is not None:
                arr = np.asarray(arr)
                if arr.ndim == 2:
                    arr = np.ascontiguousarray(arr, dtype=np.uint8)
                    height, width = arr.shape
                    image = QImage(
                        arr.data, width, height, width, QImage.Format_Grayscale8
                    ).copy()
                    if width > 900 or height > 900:
                        image = image.scaled(
                            900, 900, Qt.KeepAspectRatio, Qt.FastTransformation
                        )

            def tag(name, default="-"):
                value = getattr(ds, name, default)
                if isinstance(value, (list, pydicom.multival.MultiValue)):
                    value = "\\".join(str(item) for item in value)
                return str(value) if value not in (None, "") else default

            info = (
                f"Hasta Adı: {tag('PatientName', 'Bilinmiyor')}\n"
                f"Hasta ID: {tag('PatientID')}\n"
                f"Doğum Tarihi: {tag('PatientBirthDate')}\n"
                f"Cinsiyet: {tag('PatientSex')}\n"
                f"Etüt: {tag('StudyDescription')}\n"
                f"Seri: {tag('SeriesDescription')}\n"
                f"Vücut Bölgesi: {tag('BodyPartExamined')}\n"
                f"Modalite: {tag('Modality')}\n"
                f"Etüt Tarihi: {tag('StudyDate')}\n"
                f"Seri / Instance: {tag('SeriesNumber')} / {tag('InstanceNumber')}"
            )
        except Exception as exc:
            image = QImage(self.path)
            error = str(exc)
        self.signals.ready.emit(self.path, image, info, error)

class StudySelectionDialog(QDialog):
    """DICOM/görüntü seçimi için önizlemeli ortak pencere."""
    def __init__(self, initial_files=None, parent=None, title=None, selection_hint=None, ok_label=None):
        super().__init__(parent)
        self.dialog_title = title or "Skolyoz Grafikleri / DICOM Seç"
        self.selection_hint = selection_hint or "Overlay için iki farklı zaman görüntüsünü seçin."
        self.setWindowTitle(self.dialog_title)
        self.setObjectName("workflowDialog")
        self.resize(1050, 700)
        self.files = []
        self._thumbnail_items = {}
        self._thumbnail_pool = _SELECTION_THUMBNAIL_POOL
        self._requested_preview_path = ""

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        context_banner, self.context_label = create_context_banner(
            "Görüntü / DICOM Seç",
            self.selection_hint,
            object_name="workflowContextBanner",
        )
        root.addWidget(context_banner)

        top = QHBoxLayout()

        self.btn_add = QPushButton("Dosya Ekle")
        configure_action(self.btn_add, label="DICOM dosyası ekle", role="primary", tooltip="Bir veya birden fazla DICOM/görüntü dosyası seç")

        self.btn_add.clicked.connect(self.add_files)
        self.btn_folder = QPushButton("Klasör Tara")
        configure_action(self.btn_folder, label="DICOM klasörü tara", role="secondary", tooltip="Bir klasördeki DICOM ve görüntü dosyalarını listele")

        self.btn_folder.clicked.connect(self.add_folder)
        self.lbl_count = QLabel("0 görüntü seçildi")
        self.lbl_count.setObjectName("dicomSelectionCount")

        top.addWidget(self.btn_add)
        top.addWidget(self.btn_folder)
        top.addWidget(self.lbl_count)
        top.addStretch()
        root.addLayout(top)

        splitter = QSplitter(Qt.Horizontal)
        self.file_list = QListWidget()
        self.file_list.setSelectionMode(QListWidget.MultiSelection)
        self.file_list.setIconSize(QSize(58, 58))
        self.file_list.setObjectName("dicomSelectionList")

        self.file_list.itemSelectionChanged.connect(self.on_selection_changed)
        self.file_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.file_list.customContextMenuRequested.connect(self._show_file_context_menu)
        splitter.addWidget(self.file_list)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0,0,0,0)
        self.preview_scene = QGraphicsScene()
        self.preview_view = QGraphicsView(self.preview_scene)
        self.preview_view.setObjectName("dicomPreviewView")

        right_layout.addWidget(self.preview_view, 1)
        self.info_label = QLabel("Bir görüntü seçin; önizleme ve DICOM bilgileri burada görünecek.")
        self.info_label.setWordWrap(True)
        self.info_label.setObjectName("dicomInfoLabel")

        right_layout.addWidget(self.info_label)
        splitter.addWidget(right)
        splitter.setSizes([360, 680])
        root.addWidget(splitter, 1)

        bottom = QHBoxLayout()
        self.lbl_hint = QLabel(self.selection_hint)
        self.lbl_hint.setObjectName("dicomSelectionHint")

        bottom.addWidget(self.lbl_hint)
        bottom.addStretch()
        btn_cancel = QPushButton("İptal")
        configure_action(btn_cancel, label="DICOM seçimini iptal et", role="danger", tooltip="Seçim penceresini kapat")

        btn_cancel.clicked.connect(self.reject)
        self.btn_ok = QPushButton(ok_label or "Seçimleri Yükle")
        configure_action(self.btn_ok, label="Seçimleri yükle", role="primary", tooltip="Seçili görüntüleri çalışma alanına aktar")

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
        # Satırı hemen göster. Metadata ve piksel çözme işlemleri arka planda
        # yapılır; büyük klasörlerde pencerenin açılmasını geciktirmez.
        item = QListWidgetItem(os.path.basename(path))
        item.setData(Qt.UserRole, path)
        self.file_list.addItem(item)
        self._thumbnail_items[path] = item
        cached = _SELECTION_THUMBNAIL_CACHE.get(path)
        if cached is not None:
            image, detail = cached
            self._apply_list_thumbnail(path, image, detail)
            return
        worker = _SelectionThumbnailWorker(path)
        worker.signals.ready.connect(self._apply_list_thumbnail)
        self._thumbnail_pool.start(worker)

    def _apply_list_thumbnail(self, path, image, detail=""):
        item = self._thumbnail_items.get(path)
        if item is None:
            return
        if detail:
            item.setText(f"{os.path.basename(path)}  |  {detail}")
        if not image.isNull():
            item.setIcon(QIcon(QPixmap.fromImage(image)))
            item.setSizeHint(QSize(0, 76))
        _SELECTION_THUMBNAIL_CACHE[path] = (image, detail)
        while len(_SELECTION_THUMBNAIL_CACHE) > _SELECTION_THUMBNAIL_CACHE_LIMIT:
            _SELECTION_THUMBNAIL_CACHE.pop(next(iter(_SELECTION_THUMBNAIL_CACHE)))

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
        for f in found:
            self.add_path(f)
        self._refresh_count()

    def _show_file_context_menu(self, pos):
        clicked = self.file_list.itemAt(pos)
        if clicked is None:
            return
        if not clicked.isSelected():
            self.file_list.clearSelection()
            clicked.setSelected(True)
        selected_items = list(self.file_list.selectedItems())
        menu = QMenu(self)
        action = menu.addAction("Listeden kaldır")
        chosen = menu.exec(self.file_list.viewport().mapToGlobal(pos))
        if chosen != action:
            return
        paths_to_remove = {str(item.data(Qt.UserRole) or "") for item in selected_items}
        for row in range(self.file_list.count() - 1, -1, -1):
            item = self.file_list.item(row)
            path = str(item.data(Qt.UserRole) or "")
            if path in paths_to_remove:
                self.file_list.takeItem(row)
        self.files = [path for path in self.files if path not in paths_to_remove]
        for path in paths_to_remove:
            self._thumbnail_items.pop(path, None)
        self.preview_scene.clear()
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
        path = str(path)
        self._requested_preview_path = path
        cached = _SELECTION_PREVIEW_CACHE.get(path)
        if cached is not None:
            self._apply_large_preview(path, *cached)
            return
        self.info_label.setText("Önizleme hazırlanıyor…")
        worker = _SelectionPreviewWorker(path)
        worker.signals.ready.connect(self._apply_large_preview)
        # Seçilen görüntü, sıradaki küçük liste önizlemelerinden önce işlensin.
        self._thumbnail_pool.start(worker, 10)

    def _apply_large_preview(self, path, image, info, error=""):
        _SELECTION_PREVIEW_CACHE[path] = (image, info, error)
        while len(_SELECTION_PREVIEW_CACHE) > _SELECTION_PREVIEW_CACHE_LIMIT:
            _SELECTION_PREVIEW_CACHE.pop(next(iter(_SELECTION_PREVIEW_CACHE)))
        if path != self._requested_preview_path:
            return
        self.preview_scene.clear()
        if not image.isNull():
            pix = QPixmap.fromImage(image)
            item = self.preview_scene.addPixmap(pix)
            self.preview_scene.setSceneRect(item.boundingRect())
            self.preview_view.fitInView(item, Qt.KeepAspectRatio)
        self.info_label.setText(
            info or f"Önizleme / DICOM bilgisi okunamadı:\n{error or 'Bilinmeyen hata'}"
        )

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

        if event.button() == Qt.MiddleButton:
            self._windowing = True
            self._windowing_last_pos = event.position().toPoint()
            self.setCursor(Qt.SizeAllCursor)
            event.accept()
            return

        if (event.button() == Qt.LeftButton and self.parent_app is not None
                and getattr(self.parent_app, 'vertebra_label_mode_active', False)
                and self.view_side in {'left', 'right'}):
            self.parent_app.handle_vertebra_label_click(self.view_side, self.mapToScene(event.position().toPoint()))
            event.accept()
            return

        if (event.button() == Qt.LeftButton and self.parent_app is not None
                and self.view_side == 'left'
                and getattr(self.parent_app, 'current_mode', '') == 'overlay'
                and not getattr(self.parent_app, 'cobb_mode_active', False)
                and getattr(self.parent_app, 'overlay_item', None) is not None):
            self._overlay_dragging = True
            self.parent_app._overlay_drag_history_before = self.parent_app._capture_edit_state()
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
            if self.parent_app is not None:
                before = getattr(self.parent_app, "_overlay_drag_history_before", None)
                if before is not None:
                    self.parent_app._history_commit("Overlay taşıma", before)
                self.parent_app._overlay_drag_history_before = None
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

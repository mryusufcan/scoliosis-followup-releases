"""Görüntüleyici sekmesinin UI kurucusu.

Bu modül yalnızca viewer arayüzünü kurar.
DICOM okuma, render, overlay, W/L, ölçüm ve iş mantığı ana uygulamadaki
mevcut callback'lere bağlanmaya devam eder.
"""

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon, QKeySequence, QShortcut
from modular_app.ui.ui_icons import make_icon
from modular_app.ui.ui_clarity import configure_action, create_context_banner

from PySide6.QtWidgets import (
    QFrame,
    QGraphicsScene,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QSlider,
    QSizePolicy,
    QStyle,
    QSplitter,
    QTreeWidget,
    QVBoxLayout,
    QWidget,
)


def build_viewer_tab(app, view_class):
    _style = app.style()
    def _set_icon(button, name):
        button.setProperty("iconName", name)
        button.setProperty("iconSizePx", 20)
        button.setIcon(make_icon(name, 20))
        button.setIconSize(QSize(20, 20))

    app.viewer_tab = QWidget()
    viewer_layout = QVBoxLayout(app.viewer_tab)
    viewer_layout.setContentsMargins(5, 3, 5, 3)
    viewer_layout.setSpacing(3)

    app.viewer_context_banner, app.viewer_context_label = create_context_banner(
        "Görüntüleyici",
        "Başlamak için Görüntü Aç seçeneğini kullanın. Sonra Sığdır veya bir ölçüm aracı seçin.",
        object_name="workflowContextBanner",
    )
    viewer_layout.addWidget(app.viewer_context_banner)

    # ============================================================
    # UI REFRESH STAGE 1 — compact category/ribbon style viewer bar
    # ============================================================
    controls_box = QWidget()
    controls_box.setObjectName("viewerControlsBox")
    controls_box.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    controls_box.setStyleSheet("""
        QWidget#viewerControlsBox {
            background-color: #151C24;
            border: 1px solid #2A3542;
            border-radius: 8px;
        }
        QWidget#viewerControlsBox QLabel {
            background: transparent;
            border: none;
            color: #c7d0d7;
        }
        QFrame[uiGroup="true"] {
            background-color: #1C2630;
            border: 1px solid #2A3542;
            border-radius: 7px;
        }
        QLabel[uiGroupTitle="true"] {
            background: transparent;
            color: #7F95A5;
            border: none;
            font-size: 10px;
            font-weight: 600;
            padding: 0px 2px;
        }
        QPushButton[uiCompact="true"] {
            background-color: #1E2833;
            color: #F1F5F9;
            border: 1px solid #2A3542;
            border-radius: 3px;
            padding: 3px 7px;
            min-height: 21px;
        }
        QPushButton[uiCompact="true"]:hover {
            background-color: #263846;
            border-color: #36C5D8;
        }
        QPushButton[uiMode="true"] {
            background-color: #1E2833;
            color: #d8e1e7;
            border: 1px solid #2A3542;
            border-radius: 3px;
            padding: 3px 7px;
            min-height: 21px;
        }
        QPushButton[uiMode="true"]:checked {
            background-color: #17424D;
            color: #F1F5F9;
            border: 1px solid #36C5D8;
            font-weight: 600;
        }
        QPushButton[uiMode="true"]:checked:hover {
            background-color: #1C5260;
        }
        QPushButton[uiPrimary="true"] {
            background-color: #1D8478;
            color: #F1F5F9;
            border: 1px solid #36C5D8;
            border-radius: 3px;
            padding: 3px 8px;
            font-weight: 600;
            min-height: 21px;
        }
        QPushButton[uiMeasurement="true"] {
            background-color: #1E2833;
            color: #F1F5F9;
            border: 1px solid #2A3542;
            border-radius: 6px;
            padding: 3px 8px;
            min-height: 21px;
        }
        QPushButton[uiMeasurement="true"]:hover {
            background-color: #263846;
            border-color: #F2B84B;
        }
        QPushButton[uiMeasurement="true"][uiMeasurementActive="true"] {
            background-color: #604B22;
            color: #FFF7E0;
            border: 1px solid #F2B84B;
            font-weight: 700;
        }
        QSlider {
            background: transparent;
            border: none;
        }
        QSlider::groove:horizontal {
            height: 4px;
            background: #2A3542;
            border-radius: 2px;
        }
        QSlider::sub-page:horizontal {
            background: #236A78;
            border-radius: 2px;
        }
        QSlider::handle:horizontal {
            background: #B9C6D2;
            border: 1px solid #36C5D8;
            width: 11px;
            margin: -4px 0;
            border-radius: 5px;
        }
    """)

    controls_layout = QVBoxLayout(controls_box)
    controls_layout.setContentsMargins(4, 3, 4, 3)
    controls_layout.setSpacing(3)

    ribbon = QHBoxLayout()
    ribbon.setContentsMargins(0, 0, 0, 0)
    ribbon.setSpacing(3)

    def _viewer_group(title):
        frame = QFrame()
        frame.setProperty("uiGroup", True)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(4, 2, 4, 3)
        layout.setSpacing(2)
        title_lbl = QLabel(title.upper())
        title_lbl.setProperty("uiGroupTitle", True)
        layout.addWidget(title_lbl)
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(3)
        layout.addLayout(row)
        return frame, row

    def _compact_button(text, tooltip=None, width=None):
        button = QPushButton(text)
        button.setProperty("uiCompact", True)
        if tooltip:
            button.setToolTip(tooltip)
        if width:
            button.setFixedWidth(width)
        return button

    # ----- DOSYA -----
    file_group, file_row = _viewer_group("▣ Dosya")

    btn_open = QPushButton("Görüntü Aç")
    _set_icon(btn_open, "open")
    btn_open.setProperty("uiPrimary", True)
    configure_action(
        btn_open,
        label="Görüntü Aç",
        role="primary",
        tooltip="DICOM veya desteklenen görüntü dosyalarını aç",
        shortcut="Ctrl+O",
    )
    btn_open.clicked.connect(app.open_viewer_files)
    file_row.addWidget(btn_open)

    btn_clear = _compact_button("Listeyi Temizle", "Açılan görüntü listesini temizle")
    _set_icon(btn_clear, "trash")
    configure_action(btn_clear, label="Görüntü listesini temizle", role="quiet", tooltip="Açılan görüntü listesini temizle")
    btn_clear.clicked.connect(app.clear_viewer_files)
    file_row.addWidget(btn_clear)
    ribbon.addWidget(file_group)

    # ----- GÖRÜNÜM -----
    view_group, view_row = _viewer_group("◫ Görünüm")

    btn_zoom_out = _compact_button("−", "Uzaklaştır: görüntüyü bir kademe küçült", 30)
    configure_action(btn_zoom_out, label="Uzaklaştır", role="quiet", tooltip="Görüntüyü bir kademe küçült")
    btn_zoom_out.clicked.connect(lambda: app.adjust_viewer_zoom(1 / 1.15))
    view_row.addWidget(btn_zoom_out)

    btn_fit = _compact_button("Görüntüyü Sığdır", "Görüntüyü çalışma alanına sığdır")
    _set_icon(btn_fit, "fit")
    configure_action(btn_fit, label="Görüntüyü sığdır", role="secondary", tooltip="Görüntüyü çalışma alanına sığdır", shortcut="F")
    btn_fit.clicked.connect(app.fit_viewer_image)
    view_row.addWidget(btn_fit)

    btn_zoom_in = _compact_button("+", "Yakınlaştır: görüntüyü bir kademe büyüt", 30)
    configure_action(btn_zoom_in, label="Yakınlaştır", role="quiet", tooltip="Görüntüyü bir kademe büyüt")
    btn_zoom_in.clicked.connect(lambda: app.adjust_viewer_zoom(1.15))
    view_row.addWidget(btn_zoom_in)

    app.viewer_zoom_label = QLabel("Sığdır")
    app.viewer_zoom_label.setStyleSheet(
        "color:#aebdca; font-size:11px; min-width:46px; padding-left:3px;"
    )
    view_row.addWidget(app.viewer_zoom_label)

    app.btn_viewer_annotations = _compact_button(
        "Notlar", "Görüntü anotasyonlarını göster/gizle (metin, ok ve işaretler)"
    )
    _set_icon(app.btn_viewer_annotations, "notes")
    app.btn_viewer_annotations.setCheckable(True)
    app.btn_viewer_annotations.setProperty("uiMode", True)
    app.btn_viewer_annotations.setChecked(True)
    configure_action(
        app.btn_viewer_annotations,
        label="Görüntü anotasyonlarını göster/gizle",
        role="secondary",
        tooltip="Görüntü anotasyonlarını göster/gizle (metin, ok ve işaretler)",
    )
    app.btn_viewer_annotations.toggled.connect(app.set_viewer_annotations_visible)
    view_row.addWidget(app.btn_viewer_annotations)
    ribbon.addWidget(view_group)

    # ----- ÖLÇÜM -----
    measure_group, measure_row = _viewer_group("∠ Ölçüm")

    app.btn_viewer_cobb = _compact_button("Cobb Ölç", "Cobb açısı ölçümü (M)")
    configure_action(app.btn_viewer_cobb, label="Cobb açısı ölçümü", role="measurement", tooltip="Cobb açısını dört noktayla ölç", shortcut="M")
    app.btn_viewer_cobb.setProperty("uiMeasurement", True)
    _set_icon(app.btn_viewer_cobb, "cobb")
    app.btn_viewer_cobb.clicked.connect(app.toggle_viewer_cobb_measurement)
    measure_row.addWidget(app.btn_viewer_cobb)

    app.btn_viewer_cobb_save = _compact_button(
        "Cobb Kaydet", "Son manuel Cobb ölçümünü takip geçmişine taslak olarak kaydet"
    )
    _set_icon(app.btn_viewer_cobb_save, "save")
    configure_action(
        app.btn_viewer_cobb_save,
        label="Cobb ölçümünü takip geçmişine kaydet",
        role="measurement",
        tooltip="Son manuel Cobb ölçümünü dört nokta kanıtıyla takip geçmişine taslak olarak kaydet",
    )
    app.btn_viewer_cobb_save.setProperty("uiMeasurement", True)
    app.btn_viewer_cobb_save.clicked.connect(app.save_viewer_cobb_measurement)
    app.btn_viewer_cobb_save.setEnabled(False)
    measure_row.addWidget(app.btn_viewer_cobb_save)

    app.btn_viewer_length = _compact_button("Mesafe Ölç", "Mesafe ölçümü (L)")
    configure_action(app.btn_viewer_length, label="Mesafe ölçümü", role="measurement", tooltip="İki nokta arasındaki mesafeyi ölç", shortcut="L")
    app.btn_viewer_length.setProperty("uiMeasurement", True)
    _set_icon(app.btn_viewer_length, "distance")
    app.btn_viewer_length.clicked.connect(app.toggle_viewer_length_measurement)
    measure_row.addWidget(app.btn_viewer_length)

    btn_clear_measurement = _compact_button("Ölçümleri Temizle", "Görüntüdeki ölçümleri temizle")
    _set_icon(btn_clear_measurement, "clear")
    configure_action(btn_clear_measurement, label="Görüntü ölçümlerini temizle", role="quiet", tooltip="Görüntüdeki ölçümleri temizle")
    btn_clear_measurement.clicked.connect(app.clear_viewer_measurements)
    measure_row.addWidget(btn_clear_measurement)
    ribbon.addWidget(measure_group)

    # ----- DÜZENLE -----
    edit_group, edit_row = _viewer_group("↶ Düzenle")

    app.btn_undo = _compact_button("Geri Al", "Son düzenlemeyi geri al (Ctrl+Z)")
    _set_icon(app.btn_undo, "undo")
    app.btn_undo.clicked.connect(app.undo_last_action)
    app.btn_undo.setEnabled(False)
    edit_row.addWidget(app.btn_undo)

    app.btn_redo = _compact_button("Yinele", "Geri alınan düzenlemeyi yeniden uygula (Ctrl+Y)")
    _set_icon(app.btn_redo, "redo")
    app.btn_redo.clicked.connect(app.redo_last_action)
    app.btn_redo.setEnabled(False)
    edit_row.addWidget(app.btn_redo)
    ribbon.addWidget(edit_group)

    ribbon.addStretch(1)

    app.viewer_info_label = QLabel("Önce bir görüntü açın.")
    app.viewer_info_label.setObjectName("viewerInfoLabel")
    app.viewer_info_label.setStyleSheet(
        "color:#8b9aa6; font-size:10px; padding:1px 4px;"
    )
    app.viewer_info_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
    app.viewer_info_label.setMinimumWidth(120)
    app.viewer_info_label.setMaximumWidth(360)
    app.viewer_info_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
    ribbon.addWidget(app.viewer_info_label, 1)

    controls_layout.addLayout(ribbon)

    windowing_frame = QFrame()
    windowing_frame.setObjectName("viewerWindowingFrame")
    windowing_frame.setProperty("uiGroup", True)
    windowing_toolbar = QHBoxLayout(windowing_frame)
    windowing_toolbar.setContentsMargins(4, 2, 4, 2)
    windowing_toolbar.setSpacing(3)

    window_title = QLabel("◐ GÖRÜNTÜ AYARI")
    window_title.setProperty("uiGroupTitle", True)
    windowing_toolbar.addWidget(window_title)
    windowing_toolbar.addSpacing(4)
    windowing_toolbar.addWidget(QLabel("W/L:"))
    for label, preset, tooltip in [
        ("Yumuşak", "soft", "Yumuşak doku için Window/Level presetini uygula"),
        ("Orijinal", "original", "DICOM’un orijinal Window/Level değerlerini geri yükle"),
        ("Sert", "bone", "Kemik yapıları için yüksek kontrastlı preset uygula"),
    ]:
        button = QPushButton(label)
        button.setFixedHeight(21)
        button.setProperty("uiCompact", True)
        button.setToolTip(tooltip)
        button.setAccessibleName(f"Window/Level: {label}")
        button.clicked.connect(lambda checked=False, p=preset: app.apply_viewer_window_preset(p))
        windowing_toolbar.addWidget(button)

    app.viewer_window_label = QLabel("W/L: —")
    app.viewer_window_label.setStyleSheet("color:#bdc3c7; font-size:11px; padding:2px 6px;")
    app.viewer_window_label.setToolTip("Aktif Window/Level değerleri ve uygulanan preset")
    windowing_toolbar.addWidget(app.viewer_window_label)
    windowing_toolbar.addSpacing(8)
    windowing_toolbar.addWidget(QLabel("Parlaklık:"))
    app.viewer_brightness_slider = QSlider(Qt.Horizontal)
    app.viewer_brightness_slider.setRange(-100, 100)
    app.viewer_brightness_slider.setValue(0)
    app.viewer_brightness_slider.setFixedWidth(100)
    app.viewer_brightness_slider.setToolTip("Görüntü parlaklığını artır veya azalt")
    app.viewer_brightness_slider.setAccessibleName("Görüntü parlaklığı")
    app.viewer_brightness_slider.valueChanged.connect(app.on_viewer_brightness_changed)
    windowing_toolbar.addWidget(app.viewer_brightness_slider)
    app.viewer_brightness_label = QLabel("0")
    app.viewer_brightness_label.setStyleSheet("color:#95a5a6; font-size:11px; min-width:24px;")
    windowing_toolbar.addWidget(app.viewer_brightness_label)

    app.viewer_frame_controls = QWidget()
    frame_layout = QHBoxLayout(app.viewer_frame_controls)
    frame_layout.setContentsMargins(5, 0, 0, 0)
    frame_layout.setSpacing(3)
    frame_layout.addWidget(QLabel("Kare:"))
    app.viewer_frame_slider = QSlider(Qt.Horizontal)
    app.viewer_frame_slider.setRange(0, 0)
    app.viewer_frame_slider.setFixedWidth(90)
    app.viewer_frame_slider.setToolTip("Çok kareli DICOM’da gösterilecek kareyi seç")
    app.viewer_frame_slider.setAccessibleName("DICOM kare seçimi")
    app.viewer_frame_slider.valueChanged.connect(app.set_viewer_frame)
    frame_layout.addWidget(app.viewer_frame_slider)
    app.viewer_frame_label = QLabel("1/1")
    app.viewer_frame_label.setStyleSheet("color:#95a5a6; font-size:11px; min-width:34px;")
    frame_layout.addWidget(app.viewer_frame_label)
    app.btn_viewer_cine = QPushButton("▶")
    app.btn_viewer_cine.setFixedWidth(28)
    app.btn_viewer_cine.setToolTip("Çok kareli DICOM oynatmayı başlat/durdur")
    app.btn_viewer_cine.setAccessibleName("Çok kareli DICOM oynat/durdur")
    app.btn_viewer_cine.clicked.connect(app.toggle_viewer_cine)
    frame_layout.addWidget(app.btn_viewer_cine)
    app.viewer_frame_controls.setVisible(False)
    windowing_toolbar.addWidget(app.viewer_frame_controls)

    btn_dicom_info = QPushButton("DICOM Bilgisi")
    _set_icon(btn_dicom_info, "dicom")
    btn_dicom_info.setProperty("uiCompact", True)
    configure_action(
        btn_dicom_info,
        label="DICOM bilgisi",
        role="secondary",
        tooltip="Aktif görüntünün DICOM metadata ve teknik bilgilerini göster",
    )
    btn_dicom_info.clicked.connect(app.show_viewer_dicom_info)
    windowing_toolbar.addWidget(btn_dicom_info)

    tools_menu = QMenu(app)
    tools_menu.addAction("90° Sola Döndür", lambda: app.rotate_viewer(-90))
    tools_menu.addAction("90° Sağa Döndür", lambda: app.rotate_viewer(90))
    tools_menu.addSeparator()
    tools_menu.addAction("Yatay Çevir", app.flip_viewer_horizontal)
    tools_menu.addAction("Dikey Çevir", app.flip_viewer_vertical)
    tools_menu.addSeparator()
    app.viewer_invert_action = tools_menu.addAction("Negatif Görünüm")
    app.viewer_invert_action.setCheckable(True)
    app.viewer_invert_action.toggled.connect(app.set_viewer_inverted)
    tools_menu.addSeparator()
    tools_menu.addAction("Görünümü Sıfırla", app.reset_viewer_transform)
    tools_button = QPushButton("Daha Fazla Araç ▾")
    _set_icon(tools_button, "tools")
    tools_button.setProperty("uiCompact", True)
    configure_action(
        tools_button,
        label="Daha fazla görüntüleme aracı",
        role="secondary",
        tooltip="Döndürme, çevirme, negatif görünüm ve görünüm sıfırlama araçlarını aç",
    )
    tools_button.setMenu(tools_menu)
    windowing_toolbar.addWidget(tools_button)

    markup_menu = QMenu(app)
    markup_menu.addAction("Metin Ekle", lambda: app.activate_viewer_markup("text"))
    markup_menu.addAction("Ok Çiz", lambda: app.activate_viewer_markup("arrow"))
    markup_menu.addSeparator()
    markup_menu.addAction("Bu Görüntüdeki İşaretleri Temizle", app.clear_viewer_markups)
    markup_button = QPushButton("İşaretleme ▾")
    _set_icon(markup_button, "markup")
    markup_button.setProperty("uiCompact", True)
    configure_action(
        markup_button,
        label="İşaretleme araçları",
        role="secondary",
        tooltip="Metin ve ok ekleme veya görüntü işaretlerini temizleme araçlarını aç",
    )
    markup_button.setMenu(markup_menu)
    windowing_toolbar.addWidget(markup_button)

    session_menu = QMenu(app)
    session_menu.addAction("Oturumu Kaydet", app.save_viewer_session)
    session_menu.addAction("Oturumu Aç", app.load_viewer_session)
    session_menu.addAction("Ölçüm / İşaretleme Listesi", app.show_viewer_markup_summary)
    session_button = QPushButton("Oturum ▾")
    _set_icon(session_button, "session")
    session_button.setProperty("uiCompact", True)
    configure_action(
        session_button,
        label="Görüntüleme oturumu",
        role="secondary",
        tooltip="Görüntüleme oturumunu kaydet, aç veya ölçüm listesini görüntüle",
    )
    session_button.setMenu(session_menu)
    windowing_toolbar.addWidget(session_button)

    export_menu = QMenu(app)
    export_menu.addAction("PNG Olarak Kaydet", lambda: app.export_viewer_snapshot("png"))
    export_menu.addAction("PDF Olarak Kaydet", lambda: app.export_viewer_snapshot("pdf"))
    export_button = QPushButton("Dışa Aktar ▾")
    _set_icon(export_button, "export")
    export_button.setProperty("uiPrimary", True)
    configure_action(
        export_button,
        label="Görüntüyü dışa aktar",
        role="primary",
        tooltip="Görüntü görünümünü PNG veya PDF olarak dışa aktar",
    )
    export_button.setMenu(export_menu)
    windowing_toolbar.addWidget(export_button)
    windowing_toolbar.addStretch(1)
    instructions = QLabel("Fare tekerleği: yakınlaştır · Orta tuş: W/L · Sağ tuş: kaydır")
    instructions.setStyleSheet("color:#7f8c8d; font-size:11px;")
    windowing_toolbar.addWidget(instructions)
    controls_layout.addWidget(windowing_frame)
    viewer_layout.addWidget(controls_box)

    viewer_splitter = QSplitter(Qt.Horizontal)
    viewer_splitter.setChildrenCollapsible(False)

    viewer_list_panel = QWidget()
    viewer_list_panel.setObjectName("viewerListPanel")
    viewer_list_layout = QVBoxLayout(viewer_list_panel)
    viewer_list_layout.setContentsMargins(0, 0, 4, 0)
    viewer_list_layout.setSpacing(3)
    viewer_header = QLabel("AÇILAN GÖRÜNTÜLER")
    viewer_header.setStyleSheet("color:#9aa9b4; font-size:11px; font-weight:600; padding:2px 1px;")
    viewer_list_layout.addWidget(viewer_header)

    app.viewer_file_tree = QTreeWidget()
    app.viewer_file_tree.setObjectName("viewerFileTree")
    app.viewer_file_tree.setHeaderHidden(True)
    app.viewer_file_tree.setIconSize(QSize(52, 52))
    # Grup ve dosya öğeleri farklı SizeHint değerleri kullanır: hasta/tetkik/
    # seri satırları kompakt, küçük resimli görüntü satırları okunabilirdir.
    app.viewer_file_tree.setUniformRowHeights(False)
    # Ağaç sol panelin geri kalanının tamamını kullanır. Böylece sabit
    # yükseklikten kaynaklanan, kutunun altında kalan boş alan oluşmaz.
    app.viewer_file_tree.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    app.viewer_file_tree.setToolTip("Açılan görüntüler; sol panelin kullanılabilir yüksekliğini doldurur ve uzun listelerde kendi içinde kaydırılır.")
    app.viewer_file_tree.itemSelectionChanged.connect(app.show_selected_viewer_file)
    app.viewer_file_tree.setContextMenuPolicy(Qt.CustomContextMenu)
    app.viewer_file_tree.customContextMenuRequested.connect(app.show_viewer_file_context_menu)
    viewer_list_layout.addWidget(app.viewer_file_tree, 1)
    viewer_splitter.addWidget(viewer_list_panel)

    app.viewer_scene = QGraphicsScene()
    app.viewer_view = view_class(app.viewer_scene, 'viewer')
    app.viewer_view.parent_app = app
    viewer_splitter.addWidget(app.viewer_view)
    viewer_splitter.setStretchFactor(0, 0)
    viewer_splitter.setStretchFactor(1, 1)
    viewer_splitter.setSizes([230, 1170])
    viewer_layout.addWidget(viewer_splitter, 1)

    viewer_tab_index = app.tabs.addTab(app.viewer_tab, "Görüntüleyici")
    app.tabs.setTabToolTip(viewer_tab_index, "DICOM veya görüntüyü açın, inceleyin ve ölçün")

    viewer_shortcuts = [
        ("F", app.fit_viewer_image),
        ("M", app.toggle_viewer_cobb_measurement),
        ("L", app.toggle_viewer_length_measurement),
        ("A", lambda: app.activate_viewer_markup("arrow")),
        ("R", app.reset_viewer_transform),
        ("+", lambda: app.adjust_viewer_zoom(1.15)),
        ("-", lambda: app.adjust_viewer_zoom(1 / 1.15)),
        ("Space", app.toggle_viewer_cine),
        ("Ctrl+Z", app.undo_last_action),
        ("Ctrl+Y", app.redo_last_action),
        ("Ctrl+Shift+Z", app.redo_last_action),
    ]
    app.viewer_shortcuts = []
    for sequence, callback in viewer_shortcuts:
        shortcut = QShortcut(QKeySequence(sequence), app.viewer_tab)
        shortcut.setContext(Qt.WidgetWithChildrenShortcut)
        shortcut.activated.connect(callback)
        app.viewer_shortcuts.append(shortcut)

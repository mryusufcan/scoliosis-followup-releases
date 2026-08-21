"""Skolyoz Takip / karşılaştırma sekmesinin UI kurucusu."""

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon
from modular_app.ui.ui_icons import make_icon
from modular_app.ui.ui_clarity import configure_action, create_context_banner

from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QGraphicsScene,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QSizePolicy,
    QSlider,
    QStyle,
    QSplitter,
    QTreeWidget,
    QVBoxLayout,
    QWidget,
)


def _filter_study_tree(app, text):
    """Hasta/tetkik/seri kartlarını arama metnine göre görünür tutar."""
    query = str(text or "").strip().casefold()

    def filter_item(item):
        own_match = not query or query in item.text(0).casefold()
        child_match = False
        for index in range(item.childCount()):
            child_match = filter_item(item.child(index)) or child_match
        visible = own_match or child_match
        item.setHidden(not visible)
        if child_match:
            item.setExpanded(True)
        return visible

    for index in range(app.study_tree_widget.topLevelItemCount()):
        filter_item(app.study_tree_widget.topLevelItem(index))


def build_workspace_tab(app, view_class):
    _style = app.style()
    def _set_icon(button, name):
        button.setProperty("iconName", name)
        button.setProperty("iconSizePx", 20)
        button.setIcon(make_icon(name, 20))
        button.setIconSize(QSize(20, 20))

    app.workspace_tab = QWidget()
    workspace_layout = QVBoxLayout(app.workspace_tab)
    workspace_layout.setContentsMargins(5, 3, 5, 3)
    workspace_layout.setSpacing(3)

    app.tracking_context_banner, app.tracking_context_label = create_context_banner(
        "Takip ve Karşılaştırma",
        "Görüntüleyicide açılan tetkikler burada otomatik görünür · Bir veya iki görüntü seçip karşılaştırın.",
        object_name="workflowContextBanner",
    )
    workspace_layout.addWidget(app.tracking_context_banner)

    # ============================================================
    # UI REFRESH STAGE 4 — Skolyoz Takip kategori/ribbon araç alanı
    # ============================================================
    controls_box = QWidget()
    controls_box.setObjectName("trackingControlsBox")
    controls_box.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    controls_box.setStyleSheet("""
        QWidget#trackingControlsBox {
            background-color: #151C24;
            border: 1px solid #2A3542;
            border-radius: 8px;
        }
        QWidget#trackingControlsBox QLabel {
            background: transparent;
            border: none;
            color: #c7d0d7;
        }
        QFrame[trackingGroup="true"] {
            background-color: #1C2630;
            border: 1px solid #2A3542;
            border-radius: 7px;
        }
        QLabel[trackingTitle="true"] {
            background: transparent;
            color: #7F95A5;
            border: none;
            font-size: 10px;
            font-weight: 600;
            padding: 0px 2px;
        }
        QPushButton[trackingCompact="true"] {
            background-color: #1E2833;
            color: #F1F5F9;
            border: 1px solid #2A3542;
            border-radius: 3px;
            padding: 3px 7px;
            min-height: 21px;
        }
        QPushButton[trackingCompact="true"]:hover {
            background-color: #263846;
            border-color: #36C5D8;
        }
        QPushButton[trackingCompact="true"]:pressed {
            background-color: #28343d;
        }
        QPushButton[trackingPrimary="true"] {
            background-color: #1D8478;
            color: #F1F5F9;
            border: 1px solid #36C5D8;
            border-radius: 3px;
            padding: 3px 8px;
            font-weight: 600;
            min-height: 21px;
        }
        QPushButton[trackingPrimary="true"]:hover {
            background-color: #168f80;
        }
        QPushButton[trackingMode="true"] {
            background-color: #1E2833;
            color: #d8e1e7;
            border: 1px solid #2A3542;
            border-radius: 3px;
            padding: 3px 7px;
            min-height: 21px;
        }
        QPushButton[trackingMode="true"]:checked {
            background-color: #17424D;
            color: #F1F5F9;
            border: 1px solid #36C5D8;
            font-weight: 600;
        }
        QPushButton[trackingMode="true"]:checked:hover {
            background-color: #1C5260;
        }
        QPushButton[trackingActive="true"] {
            background-color: #17424D;
            color: #F1F5F9;
            border: 1px solid #36C5D8;
            border-radius: 6px;
            padding: 3px 7px;
            min-height: 21px;
        }
        QPushButton[trackingMeasurementActive="true"] {
            background-color: #604B22;
            color: #FFF7E0;
            border: 1px solid #F2B84B;
            border-radius: 6px;
            padding: 3px 7px;
            min-height: 21px;
            font-weight: 700;
        }
        QSlider {
            background: transparent;
            border: none;
        }
        QSlider::groove:horizontal {
            height: 4px;
            background: #3a444c;
            border-radius: 2px;
        }
        QSlider::sub-page:horizontal {
            background: #4f93a8;
            border-radius: 2px;
        }
        QSlider::handle:horizontal {
            background: #aebac3;
            border: 1px solid #667681;
            width: 11px;
            margin: -4px 0;
            border-radius: 5px;
        }
    """)

    controls_layout = QVBoxLayout(controls_box)
    controls_layout.setContentsMargins(4, 3, 4, 3)
    controls_layout.setSpacing(3)

    def _tracking_group(title):
        frame = QFrame()
        frame.setProperty("trackingGroup", True)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(4, 2, 4, 3)
        layout.setSpacing(2)
        title_lbl = QLabel(title.upper())
        title_lbl.setProperty("trackingTitle", True)
        layout.addWidget(title_lbl)
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(3)
        layout.addLayout(row)
        return frame, row

    def _track_btn(text, tooltip=None):
        b = QPushButton(text)
        b.setProperty("trackingCompact", True)
        if tooltip:
            b.setToolTip(tooltip)
        return b

    top_ribbon = QHBoxLayout()
    top_ribbon.setContentsMargins(0, 0, 0, 0)
    top_ribbon.setSpacing(6)

    # ----- DOSYA -----
    file_group, file_row = _tracking_group("▣ Dosya")
    app.btn_load_dicom = QPushButton("Tetkik Yükle")
    _set_icon(app.btn_load_dicom, "open")
    app.btn_load_dicom.setProperty("trackingPrimary", True)
    configure_action(app.btn_load_dicom, label="Tetkik yükle", role="primary", tooltip="Takip için DICOM veya görüntü dosyası yükle", shortcut="Ctrl+O")
    app.btn_load_dicom.clicked.connect(app.load_dicoms)
    file_row.addWidget(app.btn_load_dicom)
    top_ribbon.addWidget(file_group)

    # ----- KARŞILAŞTIRMA -----
    compare_group, compare_row = _tracking_group("◫ Karşılaştırma")
    app.btn_side_by_side = QPushButton("Yan Yana Karşılaştır")
    _set_icon(app.btn_side_by_side, "compare")
    app.btn_side_by_side.setProperty("trackingActive", True)
    configure_action(app.btn_side_by_side, label="Yan yana karşılaştırma", role="secondary", tooltip="İki tetkiki yan yana karşılaştır")
    app.btn_side_by_side.clicked.connect(app.set_side_by_side_mode)
    app.btn_side_by_side.clicked.connect(
        lambda checked: app.btn_overlay.setChecked(False) if checked else None
    )
    compare_row.addWidget(app.btn_side_by_side)

    app.btn_overlay = _track_btn("Overlay Karşılaştırma", "İki tetkiki üst üste çakıştır")
    _set_icon(app.btn_overlay, "stitch")
    configure_action(app.btn_overlay, label="Overlay karşılaştırma", role="secondary", tooltip="İki tetkiki üst üste çakıştır")
    app.btn_overlay.clicked.connect(app.set_overlay_mode)
    compare_row.addWidget(app.btn_overlay)
    top_ribbon.addWidget(compare_group)

    # ----- ÖLÇÜM -----
    measure_group, measure_row = _tracking_group("∠ Ölçüm")
    app.btn_measure_cobb = _track_btn("Cobb Ölç", "Karşılaştırma görüntüsünde Cobb açısı ölç")
    _set_icon(app.btn_measure_cobb, "cobb")
    configure_action(app.btn_measure_cobb, label="Karşılaştırmada Cobb ölçümü", role="measurement", tooltip="Karşılaştırma görüntüsünde Cobb açısı ölç", shortcut="M")
    app.btn_measure_cobb.clicked.connect(app.toggle_cobb_measurement)
    measure_row.addWidget(app.btn_measure_cobb)
    top_ribbon.addWidget(measure_group)

    # ----- OVERLAY HIZALAMA -----
    align_group, align_row = _tracking_group("⌖ Hizalama")
    app.btn_overlay_auto_align = QPushButton("Otomatik Hizala")
    _set_icon(app.btn_overlay_auto_align, "align")
    app.btn_overlay_auto_align.setProperty("trackingPrimary", True)
    configure_action(
        app.btn_overlay_auto_align,
        label="Otomatik hizala",
        role="primary",
        tooltip="İki seçili tetkiki otomatik yatay/dikey konum, ölçek ve rotasyon ile hizala",
    )
    app.btn_overlay_auto_align.clicked.connect(app.auto_align_overlay)
    align_row.addWidget(app.btn_overlay_auto_align)

    app.btn_overlay_reset = _track_btn("Hizalamayı Sıfırla", "Overlay hizalamasını sıfırla")
    _set_icon(app.btn_overlay_reset, "reset")
    configure_action(app.btn_overlay_reset, label="Overlay hizalamasını sıfırla", role="quiet", tooltip="Overlay hizalamasını sıfırla")
    app.btn_overlay_reset.clicked.connect(app.reset_overlay_adjustment)
    align_row.addWidget(app.btn_overlay_reset)
    top_ribbon.addWidget(align_group)

    top_ribbon.addStretch(1)

    app.lbl_overlay_offset = QLabel("Yatay 0 · Dikey 0 · Ölçek 1.00x · Döndürme +0.0°")
    app.lbl_overlay_offset.setStyleSheet(
        "color:#8fa0ad; font-size:11px; padding:3px 5px; "
        "background:transparent; border:none;"
    )
    app.lbl_overlay_offset.setToolTip("Aktif Overlay dönüşüm değerleri")
    app.lbl_overlay_offset.setMinimumWidth(150)
    app.lbl_overlay_offset.setMaximumWidth(245)
    top_ribbon.addWidget(app.lbl_overlay_offset)

    controls_layout.addLayout(top_ribbon)

    # ----- GÖRÜNTÜ AYARI + HASSAS OVERLAY KONTROLLERİ -----
    adjust_frame = QFrame()
    adjust_frame.setProperty("trackingGroup", True)
    adjust_row = QHBoxLayout(adjust_frame)
    adjust_row.setContentsMargins(6, 4, 6, 4)
    adjust_row.setSpacing(4)

    adjust_title = QLabel("◐ GÖRÜNTÜ VE OVERLAY AYARLARI")
    adjust_title.setProperty("trackingTitle", True)
    adjust_row.addWidget(adjust_title)
    adjust_row.addSpacing(4)

    adjust_row.addWidget(QLabel("W/L:"))
    app.tracking_window_preset_buttons = {}
    for label, key in [("Yumuşak", "soft"), ("Orijinal", "original"), ("Sert", "bone")]:
        b = _track_btn(label)
        b.setFixedHeight(25)
        b.setCheckable(True)
        b.setAccessibleName(f"Takip Window/Level: {label}")
        b.setToolTip({
            "soft": "Takip görüntülerinde yumuşak doku Window/Level presetini uygula",
            "original": "Takip görüntülerinin orijinal Window/Level değerlerini geri yükle",
            "bone": "Takip görüntülerinde kemik yapıları için yüksek kontrastlı preset uygula",
        }[key])
        b.setProperty("trackingMode", True)
        b.setChecked(key == "original")
        b.clicked.connect(lambda checked=False, k=key: app.apply_window_preset(k))
        b.clicked.connect(
            lambda checked=False, k=key: [
                btn.setChecked(name == k) for name, btn in app.tracking_window_preset_buttons.items()
            ] if checked else None
        )
        app.tracking_window_preset_buttons[key] = b
        adjust_row.addWidget(b)

    app.lbl_windowing = QLabel("DICOM varsayılanı")
    app.lbl_windowing.setStyleSheet("color:#aebdca; font-size:11px; padding:2px 5px;")
    adjust_row.addWidget(app.lbl_windowing)

    adjust_row.addSpacing(6)
    adjust_row.addWidget(QLabel("Parlaklık"))
    app.brightness_slider = QSlider(Qt.Horizontal)
    app.brightness_slider.setRange(-100, 100)
    app.brightness_slider.setValue(0)
    app.brightness_slider.setFixedWidth(62)
    app.brightness_slider.setAccessibleName("Takip görüntüleri parlaklığı")
    app.brightness_slider.setToolTip("Yan yana veya Overlay görüntülerinin parlaklığını artır veya azalt")
    app.brightness_slider.valueChanged.connect(app.schedule_workspace_render)
    adjust_row.addWidget(app.brightness_slider)

    adjust_row.addWidget(QLabel("Saydamlık"))
    app.overlay_opacity_slider = QSlider(Qt.Horizontal)
    app.overlay_opacity_slider.setRange(10, 90)
    app.overlay_opacity_slider.setValue(50)
    app.overlay_opacity_slider.setFixedWidth(64)
    app.overlay_opacity_slider.setAccessibleName("Overlay saydamlığı")
    app.overlay_opacity_slider.setToolTip("Öndeki Overlay tetkikinin saydamlığını ayarla")
    app.overlay_opacity_slider.valueChanged.connect(app.on_overlay_opacity_changed)
    adjust_row.addWidget(app.overlay_opacity_slider)

    adjust_row.addWidget(QLabel("Z"))
    app.overlay_zoom_slider = QSlider(Qt.Horizontal)
    app.overlay_zoom_slider.setRange(50, 160)
    app.overlay_zoom_slider.setValue(100)
    app.overlay_zoom_slider.setFixedWidth(66)
    app.overlay_zoom_slider.setAccessibleName("Overlay ölçeği")
    app.overlay_zoom_slider.setToolTip("Overlay tetkikinin ölçeğini ve yakınlaştırmasını ayarla")
    app.overlay_zoom_slider.valueChanged.connect(app.on_overlay_zoom_changed)
    adjust_row.addWidget(app.overlay_zoom_slider)

    adjust_row.addWidget(QLabel("X"))
    app.overlay_x_slider = QSlider(Qt.Horizontal)
    app.overlay_x_slider.setRange(-3000, 3000)
    app.overlay_x_slider.setValue(0)
    app.overlay_x_slider.setFixedWidth(62)
    app.overlay_x_slider.setAccessibleName("Overlay yatay konumu")
    app.overlay_x_slider.setToolTip("Overlay tetkikini yatay eksende kaydır")
    app.overlay_x_slider.valueChanged.connect(app.on_overlay_x_changed)
    adjust_row.addWidget(app.overlay_x_slider)

    adjust_row.addWidget(QLabel("Y"))
    app.overlay_y_slider = QSlider(Qt.Horizontal)
    app.overlay_y_slider.setRange(-3000, 3000)
    app.overlay_y_slider.setValue(0)
    app.overlay_y_slider.setFixedWidth(62)
    app.overlay_y_slider.setAccessibleName("Overlay dikey konumu")
    app.overlay_y_slider.setToolTip("Overlay tetkikini dikey eksende kaydır")
    app.overlay_y_slider.valueChanged.connect(app.on_overlay_y_changed)
    adjust_row.addWidget(app.overlay_y_slider)

    adjust_row.addWidget(QLabel("R"))
    app.overlay_rotation_slider = QSlider(Qt.Horizontal)
    app.overlay_rotation_slider.setRange(-150, 150)
    app.overlay_rotation_slider.setValue(0)
    app.overlay_rotation_slider.setFixedWidth(60)
    app.overlay_rotation_slider.setAccessibleName("Overlay rotasyonu")
    app.overlay_rotation_slider.setToolTip("Overlay tetkikini -15° ile +15° arasında döndür")
    app.overlay_rotation_slider.valueChanged.connect(app.on_overlay_rotation_changed)
    adjust_row.addWidget(app.overlay_rotation_slider)

    adjust_row.addStretch(1)
    controls_layout.addWidget(adjust_frame)

    workspace_layout.addWidget(controls_box)

    main_splitter = QSplitter(Qt.Horizontal)
    main_splitter.setChildrenCollapsible(False)
    main_splitter.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    left_panel = QWidget()
    left_panel.setObjectName("trackingListPanel")
    left_panel.setMinimumWidth(180)
    left_panel.setMaximumWidth(280)
    left_panel.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
    left_layout = QVBoxLayout(left_panel)
    left_layout.setContentsMargins(0, 0, 4, 0)
    left_layout.setSpacing(3)

    left_header = QLabel("HASTA VE TETKİKLER")
    left_header.setObjectName("trackingListHeader")
    left_header.setStyleSheet("padding:4px 2px 1px 2px; color:#AAB7C5; font-size:12px; font-weight:700;")
    left_layout.addWidget(left_header)

    app.study_search = QLineEdit()
    app.study_search.setObjectName("studySearch")
    app.study_search.setPlaceholderText("Hasta, PatientID veya tetkik ara")
    app.study_search.setClearButtonEnabled(True)
    app.study_search.setToolTip("Hasta adı, PatientID, tarih veya seri adıyla filtrele")
    app.study_search.textChanged.connect(lambda text: _filter_study_tree(app, text))
    left_layout.addWidget(app.study_search)

    history_label = QLabel("SEÇİLEN TETKİKLER")
    history_label.setObjectName("trackingHistoryLabel")
    history_label.setStyleSheet("padding:5px 2px 2px 2px; color:#718096; font-size:10px; font-weight:600;")
    left_layout.addWidget(history_label)

    app.study_list_widget = QListWidget()
    app.study_list_widget.setObjectName("studyModelList")
    app.study_list_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
    app.study_list_widget.setIconSize(QSize(44, 44))
    app.study_list_widget.setSelectionMode(QListWidget.MultiSelection)
    app._study_tree_syncing = False
    app.study_list_widget.itemSelectionChanged.connect(app._on_study_model_selection_changed)

    app.study_tree_widget = QTreeWidget()
    app.study_tree_widget.setObjectName("studyTree")
    app.study_tree_widget.setHeaderHidden(True)
    app.study_tree_widget.setIconSize(QSize(44, 44))
    app.study_tree_widget.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
    app.study_tree_widget.itemSelectionChanged.connect(app._on_study_tree_selection_changed)
    app.study_tree_widget.setContextMenuPolicy(Qt.CustomContextMenu)
    app.study_tree_widget.customContextMenuRequested.connect(app.show_study_file_context_menu)
    left_layout.addWidget(app.study_tree_widget, 1)

    main_splitter.addWidget(left_panel)

    app.viewer_container = QWidget()
    app.viewer_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
    app.viewer_layout = QHBoxLayout(app.viewer_container)
    app.viewer_layout.setContentsMargins(0, 0, 0, 0)
    app.viewer_layout.setSpacing(3)

    app.scene_left = QGraphicsScene()
    app.view_left = view_class(app.scene_left, 'left')
    app.view_left.parent_app = app
    app.view_left.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    app.scene_right = QGraphicsScene()
    app.view_right = view_class(app.scene_right, 'right')
    app.view_right.parent_app = app
    app.view_right.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    app.viewer_layout.addWidget(app.view_left, 1)
    app.viewer_layout.addWidget(app.view_right, 1)
    main_splitter.addWidget(app.viewer_container)

    main_splitter.setStretchFactor(0, 0)
    main_splitter.setStretchFactor(1, 1)
    main_splitter.setSizes([215, 1180])

    workspace_layout.addWidget(main_splitter, 1)
    workspace_layout.setStretch(0, 0)
    workspace_layout.setStretch(1, 1)

    tracking_tab_index = app.tabs.addTab(app.workspace_tab, "Takip ve Karşılaştırma")
    app.tabs.setTabToolTip(tracking_tab_index, "Tetkikleri seçin, karşılaştırın, hizalayın ve ölçün")

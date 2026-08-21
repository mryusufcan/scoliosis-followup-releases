"""Genel amaçlı Görüntü Birleştirme sekmesinin UI kurucusu."""
from modular_app.ui.ui_icons import make_icon
from modular_app.ui.ui_clarity import configure_action, create_context_banner
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QCheckBox, QFrame, QGraphicsScene, QGraphicsView, QGridLayout, QHBoxLayout,
    QLabel, QPushButton, QScrollArea, QSlider, QVBoxLayout, QWidget,
)

def build_stitcher_tab(app, view_class):
    def _set_icon(button, name, size=20):
        button.setProperty("iconName", name)
        button.setProperty("iconSizePx", size)
        button.setIcon(make_icon(name, size))
        button.setIconSize(QSize(size, size))

    app.stitcher_tab = QWidget()

    def _section(title):
        frame = QFrame()
        frame.setProperty("stitchSection", True)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(8, 6, 8, 7)
        layout.setSpacing(6)
        lbl = QLabel(title.upper())
        lbl.setProperty("stitchSectionTitle", True)
        layout.addWidget(lbl)
        return frame, layout

    def _compact(text):
        b = QPushButton(text)
        b.setProperty("stitchCompact", True)
        return b

    stitcher_layout = QHBoxLayout(app.stitcher_tab)
    stitcher_layout.setContentsMargins(7, 6, 7, 6)

    left_pane = QVBoxLayout()
    app.stitch_context_banner, app.stitch_context_label = create_context_banner(
        "Görüntü Birleştirme",
        "1. Üst, Orta ve Alt parçaları yükleyin; gerekirse 4. parçayı ekleyin · 2. Hizala ve Birleştir · 3. Kaliteyi kontrol edin.",
        object_name="workflowContextBanner",
    )
    left_pane.addWidget(app.stitch_context_banner)
    header_box = QHBoxLayout()

    title_box_widget = QWidget()
    title_box_layout = QVBoxLayout(title_box_widget)
    title_box_layout.setContentsMargins(0, 0, 0, 0)

    title_lbl = QLabel("<b>DICOM Görüntü Birleştirme</b>")
    title_lbl.setStyleSheet("color:#e1e8ed; font-size:14px; font-weight:600;")
    sub_desc = QLabel("2–4 görüntü | Otomatik hizalama ve manuel düzeltme")
    sub_desc.setStyleSheet("color:#8796a1; font-size:10px;")

    title_box_layout.addWidget(title_lbl)
    title_box_layout.addWidget(sub_desc)
    header_box.addWidget(title_box_widget)
    header_box.addStretch()

    app.lbl_status_badge = QLabel("Hazır: parçaları yükleyin")
    app.lbl_status_badge.setStyleSheet("background-color:#263640; color:#7fb3cf; padding: 5px 10px; border-radius: 4px; font-weight: bold; font-size: 11px;")
    header_box.addWidget(app.lbl_status_badge)
    left_pane.addLayout(header_box)

    app.stitch_scene = QGraphicsScene()
    app.stitch_view = view_class(app.stitch_scene, 'stitch')
    app.stitch_view.parent_app = app
    left_pane.addWidget(app.stitch_view)

    stitcher_layout.addLayout(left_pane, stretch=3)

    right_panel = QWidget()
    right_panel.setObjectName("stitchRightPanel")
    right_panel.setStyleSheet("""
        QWidget#stitchRightPanel {
            background-color: #20262c;
            border: 1px solid #333e47;
            border-radius: 6px;
        }
        QWidget#stitchRightPanel QLabel {
            background: transparent;
            border: none;
            color: #c8d1d8;
        }
        QFrame[stitchSection="true"] {
            background-color: #262d34;
            border: 1px solid #36424c;
            border-radius: 5px;
        }
        QLabel[stitchSectionTitle="true"] {
            color: #8fa0ad;
            font-size: 10px;
            font-weight: 600;
            padding: 0px 1px;
        }
        QPushButton[stitchCompact="true"] {
            background-color: #303b45;
            color: #e1e8ed;
            border: 1px solid #41505d;
            border-radius: 3px;
            padding: 7px 10px;
            min-height: 28px;
        }
        QPushButton[stitchCompact="true"]:hover {
            background-color: #394854;
            border-color: #526675;
        }
        QCheckBox {
            color: #d5dde3;
            spacing: 7px;
            padding: 3px 2px;
        }
        QCheckBox::indicator {
            width: 16px;
            height: 16px;
            border: 1px solid #56636e;
            border-radius: 3px;
            background: #22292f;
        }
        QCheckBox::indicator:checked {
            background: #2f6687;
            border: 1px solid #6aa1bf;
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
    right_panel.setMinimumWidth(300)
    right_panel.setMaximumWidth(385)
    app.right_panel_layout = QVBoxLayout(right_panel)
    app.right_panel_layout.setContentsMargins(10, 10, 10, 10)

    # === YENİ: Görüntüleyici ile aynı seçim penceresini açan buton ===
    app.btn_pick_viewer_files = QPushButton("Açık Görüntüleri Kullan")
    _set_icon(app.btn_pick_viewer_files, "open")
    app.btn_pick_viewer_files.setProperty("stitchCompact", True)
    configure_action(
        app.btn_pick_viewer_files,
        label="Açık görüntüleri birleştirmede kullan",
        role="primary",
        tooltip="Açık dosyaları yeniden klasör taramadan Üst, Orta, Alt ve isteğe bağlı 4. parçaya atayın",
    )
    app.btn_pick_viewer_files.clicked.connect(app.open_viewer_selection_for_stitcher)
    app.right_panel_layout.addWidget(app.btn_pick_viewer_files)

    parts_section, parts_layout = _section("▣ Görüntü Parçaları")
    # ============================================================

    parts_loader_box = QVBoxLayout()
    parts_loader_box.addWidget(QLabel("<b>Görüntü Parçaları</b>"))

    for p_key, p_name in [('servical', 'Üst Yükle'), ('dorsal', 'Orta Yükle'), ('lumbar', 'Alt Yükle'), ('extra', '4. Parça Yükle')]:
        row_box = QHBoxLayout()
        btn_load = QPushButton(p_name)
        btn_load.setProperty("stitchCompact", True)
        _set_icon(btn_load, "open")
        btn_load.setAccessibleName(f"{p_name.replace(' Yükle', '')} parçası yükle")
        btn_load.setToolTip(f"{p_name.replace(' Yükle', '')} DICOM parçasını seç ve önizle")
        btn_load.clicked.connect(lambda checked=False, k=p_key: app.open_preview_dialog(k))
        btn_load.setContextMenuPolicy(Qt.CustomContextMenu)
        btn_load.customContextMenuRequested.connect(lambda pos, k=p_key, b=btn_load: app.show_stitch_part_context_menu(k, b, pos))
        app.stitch_load_buttons[p_key] = btn_load
        if app.stitch_files.get(p_key):
            btn_load.setText(f"{p_name.replace(' Yükle', '')} ✓")

        btn_rem = QPushButton("Parçayı Kaldır")
        btn_rem.setProperty("stitchCompact", True)
        _set_icon(btn_rem, "trash")
        configure_action(
            btn_rem,
            label=f"{p_name.replace(' Yükle', '')} parçasını kaldır",
            role="danger",
            tooltip=f"Yüklenmiş {p_name.replace(' Yükle', '')} parçasını birleştirme listesinden kaldır",
        )
        btn_rem.clicked.connect(lambda checked=False, k=p_key: app.remove_stitch_part(k))
        btn_rem.setVisible(False)
        app.stitch_remove_buttons[p_key] = btn_rem

        row_box.addWidget(btn_load)
        row_box.addWidget(btn_rem)
        parts_loader_box.addLayout(row_box)

    app.right_panel_layout.addLayout(parts_loader_box)

    app.stitch_top_preview_view = QGraphicsView()
    app.stitch_top_preview_scene = QGraphicsScene()
    app.stitch_top_preview_view.setScene(app.stitch_top_preview_scene)
    app.stitch_top_preview_view.setFixedHeight(70)
    app.stitch_top_preview_view.setStyleSheet("background-color: #111; border: 1px dashed #555;")
    app.right_panel_layout.addWidget(app.stitch_top_preview_view)

    app.right_panel_layout.addWidget(parts_section)

    align_section, align_layout = _section("⌖ Hizalama")
    align_layout.addWidget(QLabel("Manuel Nokta Modu"))
    mode_btns_layout = QHBoxLayout()
    app.btn_mode_off = QPushButton("Kapalı")
    app.btn_mode_off.setProperty("stitchCompact", True)
    _set_icon(app.btn_mode_off, "reset")
    app.btn_mode_off.setCheckable(True)
    configure_action(
        app.btn_mode_off,
        label="Manuel nokta modunu aç/kapat",
        role="secondary",
        tooltip="Manuel hizalama noktası yerleştirme modunu aç veya kapat",
    )
    app.btn_mode_off.clicked.connect(app.toggle_manual_point_mode)
    app.btn_clear_pts = QPushButton("Noktaları Temizle")
    app.btn_clear_pts.setProperty("stitchCompact", True)
    _set_icon(app.btn_clear_pts, "clear")
    configure_action(
        app.btn_clear_pts,
        label="Manuel noktaları temizle",
        role="quiet",
        tooltip="Manuel hizalama için yerleştirilen tüm noktaları temizle",
    )
    app.btn_clear_pts.clicked.connect(app.clear_manual_points)
    mode_btns_layout.addWidget(app.btn_mode_off)
    mode_btns_layout.addWidget(app.btn_clear_pts)
    app.right_panel_layout.addLayout(mode_btns_layout)

    app.lbl_manual_mode_info = QLabel("<font color='#95a5a6' size='2'>Otomatik hizalama kullanılacak.</font>")
    app.lbl_manual_mode_info.setWordWrap(True)
    app.right_panel_layout.addWidget(app.lbl_manual_mode_info)

    app.btn_manual_next_stage = QPushButton("Aşamayı Tamamla ve Sonraki Parçaya Geç")
    _set_icon(app.btn_manual_next_stage, "forward")
    app.btn_manual_next_stage.setVisible(False)
    app.btn_manual_next_stage.setEnabled(False)
    app.btn_manual_next_stage.setMinimumHeight(36)
    configure_action(
        app.btn_manual_next_stage,
        label="Manuel aşamayı tamamla ve sonraki parçaya geç",
        role="primary",
        tooltip="Bu parçadaki manuel noktaları onayla ve sonraki birleştirme aşamasına geç",
    )
    app.btn_manual_next_stage.clicked.connect(app.advance_manual_stage)
    app.right_panel_layout.addWidget(app.btn_manual_next_stage)

    app.chk_histogram = QCheckBox("Pozlama Eşitleme (Histogram Matching)")
    app.chk_histogram.setToolTip("Parçaların görsel parlaklık dağılımını eşitle; hizalama hesabını değiştirmez")
    app.chk_histogram.setAccessibleName("Pozlama eşitleme")
    app.chk_histogram.stateChanged.connect(app.update_stitched_spine)
    app.right_panel_layout.addWidget(app.chk_histogram)
    lbl_hist_note = QLabel("<font color='#7f8c8d' size='2'>(Sadece görseldir; hizalama hesabını etkilemez)</font>")
    lbl_hist_note.setWordWrap(True)
    app.right_panel_layout.addWidget(lbl_hist_note)

    app.chk_auto_align = QCheckBox("Otomatik Hizalama (kenar korelasyonu)")
    app.chk_auto_align.setStyleSheet("color: #ecf0f1; margin-top: 3px;")
    app.chk_auto_align.setChecked(True)
    app.chk_auto_align.setToolTip(
        "İşaretliyken parça birleşimleri otomatik kenar korelasyonu ile hizalanır"
    )
    app.chk_auto_align.setAccessibleName("Otomatik hizalama")
    app.chk_auto_align.stateChanged.connect(app.update_stitched_spine)
    align_layout.addWidget(app.chk_auto_align)
    lbl_auto_note = QLabel("<font color='#7f8c8d' size='2'>Çakışma bandını kenarlarına göre otomatik hizalar.</font>")
    lbl_auto_note.setWordWrap(True)
    app.right_panel_layout.addWidget(lbl_auto_note)

    app.btn_stitch_action = QPushButton("Hizala ve Birleştir")
    _set_icon(app.btn_stitch_action, "stitch")
    configure_action(
        app.btn_stitch_action,
        label="Görüntü parçalarını hizala ve birleştir",
        role="primary",
        tooltip="Yüklenen parçaları otomatik olarak hizala ve önizlemeyi oluştur",
    )
    app.btn_stitch_action.clicked.connect(app.trigger_stitch_action)
    app.right_panel_layout.addWidget(app.btn_stitch_action)

    app.right_panel_layout.addWidget(align_section)

    app.controls_container = QWidget()
    app.controls_layout = QVBoxLayout(app.controls_container)
    app.controls_layout.setContentsMargins(0, 0, 0, 0)

    app.controls_layout.addWidget(QLabel("KALİTE / HASSAS DÜZELTME"))

    app.lbl_stitch_stage_info = QLabel("Aşama: Otomatik hizalama ve birleştirme")
    app.lbl_stitch_stage_info.setStyleSheet("color: #bdc3c7; font-size: 11px;")
    app.controls_layout.addWidget(app.lbl_stitch_stage_info)

    zoom_box = QHBoxLayout()
    zoom_box.addWidget(QLabel("Yakınlaştırma:"))
    app.lbl_zoom_val = QLabel("1.00x")
    zoom_box.addWidget(app.lbl_zoom_val)
    zoom_box.addStretch()
    app.controls_layout.addLayout(zoom_box)

    app.stitch_slider = QSlider(Qt.Horizontal)
    app.stitch_slider.setRange(10, 300)
    app.stitch_slider.setValue(100)
    app.stitch_slider.valueChanged.connect(app.on_stitch_zoom_changed)
    app.controls_layout.addWidget(app.stitch_slider)

    app.lbl_confidence = QLabel("Güven skoru: 0.00")
    app.lbl_confidence.setStyleSheet("color: #2ecc71; font-weight: bold; font-size: 11px;")
    app.controls_layout.addWidget(app.lbl_confidence)
    app.lbl_quality_note = QLabel(
        "<font color='#7f8c8d' size='2'>"
        "Düşük güvenli otomatik hizalama kaydetme öncesi uyarılır; "
        "dama tahtası ile dikiş kontrolü önerilir."
        "</font>"
    )
    app.lbl_quality_note.setWordWrap(True)
    app.controls_layout.addWidget(app.lbl_quality_note)

    app.lbl_junction_quality_title = QLabel("✓ Birleşim Kalitesi")
    app.controls_layout.addWidget(app.lbl_junction_quality_title)

    app.lbl_junction_quality_1 = QLabel("1. birleşim: —")
    app.lbl_junction_quality_1.setStyleSheet("color:#95a5a6;font-size:10px;")
    app.controls_layout.addWidget(app.lbl_junction_quality_1)

    app.lbl_junction_quality_2 = QLabel("2. birleşim: —")
    app.lbl_junction_quality_2.setStyleSheet("color:#95a5a6;font-size:10px;")
    app.controls_layout.addWidget(app.lbl_junction_quality_2)

    app.lbl_junction_quality_3 = QLabel("3. birleşim: —")
    app.lbl_junction_quality_3.setStyleSheet("color:#95a5a6;font-size:10px;")
    app.controls_layout.addWidget(app.lbl_junction_quality_3)

    app.lbl_junction_quality_overall = QLabel("Genel: —")
    app.lbl_junction_quality_overall.setStyleSheet("color:#95a5a6;font-size:10px;")
    app.controls_layout.addWidget(app.lbl_junction_quality_overall)

    app.lbl_manual_offset = QLabel(f"Manuel düzeltme: sağ/sol {app.stitch_offset_x:+.2f} px, yukarı/aşağı {app.stitch_offset_y:+.2f} px")
    app.lbl_manual_offset.setStyleSheet("color: #95a5a6; font-size: 10px;")
    app.controls_layout.addWidget(app.lbl_manual_offset)

    app.chk_checkerboard = QCheckBox("Dama tahtası (dikiş kontrolü)")
    app.chk_checkerboard.setStyleSheet("color: #ecf0f1; font-size: 11px;")
    app.chk_checkerboard.stateChanged.connect(app.update_stitched_spine)
    app.controls_layout.addWidget(app.chk_checkerboard)

    app.controls_layout.addWidget(QLabel("Hassas Kaydırma"))
    app.step_input = QLabel("1.0")
    app.step_input.setStyleSheet("background-color: #1e1e1e; padding: 5px; border: 1px solid #444;")
    app.controls_layout.addWidget(app.step_input)

    step_btns_layout = QHBoxLayout()
    for val_str in ["0.5", "1", "3", "5", "10"]:
        b = QPushButton(val_str)
        b.setStyleSheet("background-color:#303b45; color:#e1e8ed; border:1px solid #41505d; border-radius:3px; padding:5px;")
        b.clicked.connect(lambda checked=False, s=val_str: app.set_shift_step(s))
        step_btns_layout.addWidget(b)
    app.controls_layout.addLayout(step_btns_layout)

    app.lbl_move_part = QLabel("Manuel düzeltilecek parça")
    app.controls_layout.addWidget(app.lbl_move_part)
    move_part_layout = QHBoxLayout()
    app.btn_move_servical = QPushButton("Üst · Sabit")
    app.btn_move_dorsal = QPushButton("Orta")
    app.btn_move_lumbar = QPushButton("Alt")
    app.btn_move_extra = QPushButton("4. Parça")
    app.btn_move_servical.setEnabled(False)
    app.btn_move_dorsal.clicked.connect(lambda: app.select_stitch_part("dorsal"))
    app.btn_move_lumbar.clicked.connect(lambda: app.select_stitch_part("lumbar"))
    app.btn_move_extra.clicked.connect(lambda: app.select_stitch_part("extra"))
    for b in [app.btn_move_servical, app.btn_move_dorsal, app.btn_move_lumbar, app.btn_move_extra]:
        b.setStyleSheet("background-color: #34495e; color: white; padding: 5px; border-radius: 3px;")
        move_part_layout.addWidget(b)
    app.controls_layout.addLayout(move_part_layout)

    grid_dir = QGridLayout()
    btn_up = QPushButton("Yukarı")
    btn_up.setProperty("stitchCompact", True)
    _set_icon(btn_up, "up")
    btn_up.setToolTip("Seçili parçayı yukarı kaydır")
    btn_left = QPushButton("Sola")
    btn_left.setProperty("stitchCompact", True)
    _set_icon(btn_left, "left")
    btn_left.setToolTip("Seçili parçayı sola kaydır")
    btn_zero = QPushButton("Sıfırla")
    btn_zero.setProperty("stitchCompact", True)
    _set_icon(btn_zero, "reset")
    btn_zero.setToolTip("Seçili parçanın manuel kaydırmasını sıfırla")
    btn_right = QPushButton("Sağa")
    btn_right.setProperty("stitchCompact", True)
    _set_icon(btn_right, "right")
    btn_right.setToolTip("Seçili parçayı sağa kaydır")
    btn_down = QPushButton("Aşağı")
    btn_down.setProperty("stitchCompact", True)
    _set_icon(btn_down, "down")
    btn_down.setToolTip("Seçili parçayı aşağı kaydır")
    app.btn_move_up = btn_up
    app.btn_move_left = btn_left
    app.btn_move_zero = btn_zero
    app.btn_move_right = btn_right
    app.btn_move_down = btn_down

    btn_up.clicked.connect(lambda: app.adjust_stitch_offset(0, -app.current_step_val))
    btn_down.clicked.connect(lambda: app.adjust_stitch_offset(0, app.current_step_val))
    btn_left.clicked.connect(lambda: app.adjust_stitch_offset(-app.current_step_val, 0))
    btn_right.clicked.connect(lambda: app.adjust_stitch_offset(app.current_step_val, 0))
    btn_zero.clicked.connect(lambda: app.reset_stitch_offset())

    for b in [btn_up, btn_left, btn_zero, btn_right, btn_down]:
        b.setAccessibleDescription(b.toolTip())
        b.setStyleSheet("background-color:#303b45; color:#e1e8ed; border:1px solid #41505d; border-radius:3px; padding:5px;")

    grid_dir.addWidget(btn_up, 0, 1)
    grid_dir.addWidget(btn_left, 1, 0)
    grid_dir.addWidget(btn_zero, 1, 1)
    grid_dir.addWidget(btn_right, 1, 2)
    grid_dir.addWidget(btn_down, 2, 1)
    app.controls_layout.addLayout(grid_dir)
    app._refresh_stitch_part_buttons()

    app.btn_confirm_finish = QPushButton("Sonucu Onayla ve Kayda Hazırla")
    _set_icon(app.btn_confirm_finish, "save")
    configure_action(
        app.btn_confirm_finish,
        label="Birleşik sonucu onayla ve kayda hazırla",
        role="primary",
        tooltip="Birleşik görüntüyü onayla ve PNG/DICOM kaydı için hazırla",
    )
    app.btn_confirm_finish.clicked.connect(app.on_confirm_finish_clicked)
    app.controls_layout.addWidget(app.btn_confirm_finish)

    app.controls_container.setVisible(False)

    app.controls_scroll = QScrollArea()
    app.controls_scroll.setWidgetResizable(True)
    app.controls_scroll.setFrameShape(QScrollArea.NoFrame)
    app.controls_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    app.controls_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
    app.controls_scroll.setStyleSheet(
        "QScrollArea { background: transparent; border: none; }"
        "QScrollBar:vertical { width: 9px; background:#20262c; } QScrollBar::handle:vertical { background:#44515c; border-radius:4px; min-height:24px; }"
    )
    app.controls_scroll.setWidget(app.controls_container)
    app.controls_scroll.setVisible(False)
    app.right_panel_layout.addWidget(app.controls_scroll, 1)

    # Final save is a sticky footer: it must remain visible even when the
    # final controls exceed the available vertical height.
    app.btn_final_save_sticky = QPushButton("Kaydet (PNG + DICOM)")
    _set_icon(app.btn_final_save_sticky, "export")
    configure_action(
        app.btn_final_save_sticky,
        label="Birleşik sonucu PNG ve DICOM olarak kaydet",
        role="primary",
        tooltip="Onaylanmış birleşik görüntüyü PNG ve Secondary Capture DICOM olarak kaydet",
    )
    app.btn_final_save_sticky.setStyleSheet(
        "background-color:#2f6687; color:white; font-weight:600; "
        "padding:10px; border:1px solid #427d9e; border-radius:4px; "
        "margin-top:5px;"
    )
    app.btn_final_save_sticky.setToolTip(
        "Onaylanmış birleşik görüntüyü PNG ve Secondary Capture DICOM olarak kaydet"
    )
    app.btn_final_save_sticky.clicked.connect(app.save_final_result)
    app.btn_final_save_sticky.setVisible(False)
    app.right_panel_layout.addWidget(app.btn_final_save_sticky)

    app.right_panel_layout.addStretch()
    stitcher_layout.addWidget(right_panel, stretch=1)
    stitch_tab_index = app.tabs.addTab(app.stitcher_tab, "Görüntü Birleştirme")
    app.tabs.setTabToolTip(stitch_tab_index, "İki, üç veya dört DICOM görüntüsünü hizalayın ve birleştirin")

    app.shortcut_up = QShortcut(QKeySequence(Qt.Key_Up), app.stitcher_tab)
    app.shortcut_up.activated.connect(lambda: app.handle_shortcut_move(0, -app.current_step_val))

    app.shortcut_down = QShortcut(QKeySequence(Qt.Key_Down), app.stitcher_tab)
    app.shortcut_down.activated.connect(lambda: app.handle_shortcut_move(0, app.current_step_val))

    app.shortcut_left = QShortcut(QKeySequence(Qt.Key_Left), app.stitcher_tab)
    app.shortcut_left.activated.connect(lambda: app.handle_shortcut_move(-app.current_step_val, 0))

    app.shortcut_right = QShortcut(QKeySequence(Qt.Key_Right), app.stitcher_tab)
    app.shortcut_right.activated.connect(lambda: app.handle_shortcut_move(app.current_step_val, 0))

# STITCH_UI_ACTIONS_STAGE22
# main.py'den ayrilan stitching UI/callback fonksiyonlarinin gereksinimleri.
from PySide6.QtCore import QTimer
from PySide6.QtGui import QPen
from PySide6.QtWidgets import QMessageBox, QMenu

def _manual_pairs(app):
    return app.stitch_controller.active_pairs(app.stitch_files)


def toggle_manual_point_mode(app):
    pairs = app._manual_pairs()
    if not pairs:
        QMessageBox.information(app, "Manuel Hizalama", "Önce en az iki omurga parçası yükleyin.")
        return

    app.manual_mode_active = not app.manual_mode_active
    app.stitch_view.refresh_cursor()

    if app.manual_mode_active:
        manual_state = app.stitch_controller.reset_points_state()
        app.manual_stage_index = manual_state["stage_index"]
        app.manual_points = manual_state["points"]
        app._manual_point_marker_by_part = {}
        app.btn_mode_off.setText("Açık")
        app.btn_mode_off.setChecked(True)
        app.btn_manual_next_stage.setVisible(True)
        app.btn_manual_next_stage.setEnabled(False)
        app.btn_manual_next_stage.setText("Önce 2+2 nokta seçin")
        app.render_manual_pick_view()
        pair = app._manual_pairs()[app.manual_stage_index]
        app.lbl_manual_mode_info.setText(
            f"<font color='#f39c12' size='2'><b>Manuel Aşama {app.manual_stage_index + 1}/{len(pairs)}</b> — "
            f"{pair[0].capitalize()} sabit, {pair[1].capitalize()} hareketli. "
            f"Her görüntüde 2 karşılık gelen noktayı aynı sırayla seçin.</font>"
        )
        app.statusBar().showMessage(f"Manuel hizalama: {pair[0].capitalize()} sabit, {pair[1].capitalize()} hizalanıyor.")
    else:
        app.btn_mode_off.setText("Kapalı")
        app.btn_mode_off.setChecked(False)
        app.btn_manual_next_stage.setVisible(False)
        app.btn_manual_next_stage.setEnabled(False)
        app.lbl_manual_mode_info.setText("<font color='#95a5a6' size='2'>Otomatik hizalama kullanılacak.</font>")
        app.clear_manual_points()
        if app.is_stitched_completed:
            app.update_stitched_spine()
        app.statusBar().showMessage("Manuel Nokta Modu kapalı.")


def render_manual_pick_view(app):
    pairs = app._manual_pairs()
    app.stitch_scene.clear()
    app._stitch_result_item = None
    app._manual_point_markers = []

    if not pairs or app.manual_stage_index >= len(pairs):
        app._pick_pixmaps = []
        app._pick_positions = []
        return

    upper, lower = pairs[app.manual_stage_index]
    paths = [app.stitch_files[upper], app.stitch_files[lower]]
    pixmaps = []
    for path in paths:
        pix = app._stitch_pixmap_cache.get(path)
        if pix is None or pix.isNull():
            pix = app.get_image_pixmap(path)
            if not pix.isNull():
                app._stitch_pixmap_cache[path] = pix
        if not pix.isNull():
            pixmaps.append(pix)

    if len(pixmaps) != 2:
        app.statusBar().showMessage("Manuel hizalama için iki görüntünün de okunması gerekiyor.")
        app._pick_pixmaps = []
        app._pick_positions = []
        return

    gap = 40
    pos0 = (0, 0)
    pos1 = (pixmaps[0].width() + gap, 0)
    app._pick_pixmaps = pixmaps
    app._pick_positions = [pos0, pos1]
    app._manual_pair_parts = (upper, lower)
    app.manual_points = {}
    app._manual_point_marker_by_part = {}

    app.stitch_scene.addPixmap(pixmaps[0])
    item1 = app.stitch_scene.addPixmap(pixmaps[1])
    item1.setPos(pos1[0], pos1[1])

    divider_x = pixmaps[0].width() + gap / 2
    max_h = max(pixmaps[0].height(), pixmaps[1].height())
    app.stitch_scene.addLine(divider_x, 0, divider_x, max_h, QPen(Qt.darkGray, 2))

    lbl0 = app.stitch_scene.addText(f"{upper.capitalize()} (SABİT) — 2 nokta seç")
    lbl0.setDefaultTextColor(Qt.green)
    lbl0.setPos(10, 10)
    lbl1 = app.stitch_scene.addText(f"{lower.capitalize()} — aynı 2 noktayı seç")
    lbl1.setDefaultTextColor(Qt.red)
    lbl1.setPos(pos1[0] + 10, 10)

    QTimer.singleShot(0, lambda: app.stitch_view.fitInView(
        app.stitch_scene.itemsBoundingRect(), Qt.KeepAspectRatio
    ))


def clear_manual_points(app):
    app.manual_points = {}
    app._manual_point_marker_by_part = {}
    app._manual_point_markers = []
    if app.manual_mode_active:
        app.render_manual_pick_view()
    else:
        app.statusBar().showMessage("Manuel noktalar temizlendi.")


def handle_manual_point_click(app, scene_pos):
    if not app.manual_mode_active or not getattr(app, '_pick_pixmaps', None) or len(app._pick_pixmaps) != 2:
        return

    x, y = scene_pos.x(), scene_pos.y()
    pos0, pos1 = app._pick_positions

    if pos0[0] <= x < pos0[0] + app._pick_pixmaps[0].width() and 0 <= y < app._pick_pixmaps[0].height():
        part_idx = 0
        local = (float(x - pos0[0]), float(y - pos0[1]))
        marker_color = Qt.green
    elif pos1[0] <= x < pos1[0] + app._pick_pixmaps[1].width() and 0 <= y < app._pick_pixmaps[1].height():
        part_idx = 1
        local = (float(x - pos1[0]), float(y - pos1[1]))
        marker_color = Qt.red
    else:
        return

    pts0 = app.manual_points.setdefault(0, [])
    pts1 = app.manual_points.setdefault(1, [])

    target_list = pts0 if part_idx == 0 else pts1

    if len(target_list) >= 2:
        app.statusBar().showMessage(
            "Bu görüntüde zaten 2 nokta var. Önce 'Noktaları Temizle' ile yeniden işaretleyin."
        )
        return

    target_list.append(local)

    r = 6
    ellipse = app.stitch_scene.addEllipse(
        x - r, y - r, r * 2, r * 2, QPen(marker_color, 3)
    )
    text_item = app.stitch_scene.addText(str(len(target_list)))
    text_item.setDefaultTextColor(marker_color)
    text_item.setPos(x + 7, y - 10)
    app._manual_point_markers.extend([ellipse, text_item])

    if part_idx == 0 and len(pts0) == 1:
        app.statusBar().showMessage(
            "Sabit görüntüde 1. nokta seçildi. Aynı görüntüde 2. noktayı seçin."
        )
        return

    if part_idx == 0 and len(pts0) == 2:
        app.statusBar().showMessage(
            "Sabit görüntünün 2 noktası tamam. Şimdi hareketli görüntüde aynı iki anatomik noktayı aynı sırayla seçin."
        )
        return

    if part_idx == 1 and len(pts1) == 1:
        app.statusBar().showMessage(
            "Hareketli görüntüde 1. nokta seçildi. Aynı anatomik noktanın karşılığını 2. noktada seçin."
        )
        return

    if len(pts0) < 2 or len(pts1) < 2:
        return

    try:
        alignment = app.stitch_controller.calculate_manual_alignment(
            pts0,
            pts1,
            moving_width=app._pick_pixmaps[1].width(),
            moving_height=app._pick_pixmaps[1].height(),
            top_height=app._pick_pixmaps[0].height(),
            overlap_px=app.OVERLAP_PX,
        )
    except ValueError as exc:
        if str(exc) == "POINTS_TOO_CLOSE":
            app.statusBar().showMessage(
                "İki nokta birbirine çok yakın. Lütfen daha belirgin iki anatomik nokta seçin."
            )
            return
        raise

    upper, lower = app._manual_pair_parts

    app.manual_junction_offsets[(upper, lower)] = (
        alignment.dx,
        alignment.target_y,
        alignment.angle_deg,
    )

    dx_adjust = alignment.dx
    dy_adjust = alignment.dy_adjust
    angle_deg = alignment.angle_deg
    app.is_stitched_completed = True
    app.lbl_manual_offset.setText(
        f"Manuel {upper.capitalize()}→{lower.capitalize()}: "
        f"Δx {dx_adjust:+.1f}px, Δy {dy_adjust:+.1f}px, açı {angle_deg:+.2f}°"
    )

    pairs = app._manual_pairs()
    is_last_stage = (app.manual_stage_index + 1 >= len(pairs))
    app.btn_manual_next_stage.setVisible(True)
    app.btn_manual_next_stage.setEnabled(True)
    app.btn_manual_next_stage.setText(
        f"{lower.capitalize()} parçasını sabitle ve birleştirmeyi tamamla" if is_last_stage
        else f"{upper.capitalize()}–{lower.capitalize()} sabitle → sonraki parçaya geç"
    )
    app.lbl_manual_mode_info.setText(
        f"<font color='#2ecc71' size='2'><b>Aşama {app.manual_stage_index + 1}/{len(pairs)} hazır.</b> "
        f"{upper.capitalize()} sabit, {lower.capitalize()} için 2+2 nokta tamamlandı. "
        f"Sabitleme düğmesine basın.</font>"
    )
    app.statusBar().showMessage(
        f"{upper.capitalize()} → {lower.capitalize()} hazır. Sabitlemek için düğmeye basın."
    )


def advance_manual_stage(app):
    if not app.manual_mode_active:
        return
    pairs = app._manual_pairs()
    if not app.stitch_controller.can_advance_stage(
        app.manual_stage_index,
        pairs,
        app.manual_points,
    ):
        QMessageBox.information(
            app,
            "Manuel Hizalama",
            "Önce SABİT görüntüde 2 ve HAREKETLİ görüntüde 2 karşılık gelen nokta seçin.",
        )
        return
    next_stage = app.stitch_controller.next_stage_index(
        app.manual_stage_index,
        pairs,
    )
    if next_stage is not None:
        upper, lower = pairs[app.manual_stage_index]
        app.manual_stage_index = next_stage
        app.manual_points = {}
        app._manual_point_marker_by_part={}
        app._manual_point_markers=[]
        app.btn_manual_next_stage.setEnabled(False)
        app.btn_manual_next_stage.setText("Önce 2+2 nokta seçin")
        app.render_manual_pick_view()
        nu,nl=pairs[app.manual_stage_index]
        app.lbl_manual_mode_info.setText(
            f"<font color='#f39c12' size='2'><b>Manuel Aşama {app.manual_stage_index+1}/{len(pairs)}</b> — "
            f"{nu.capitalize()} SABİT, {nl.capitalize()} hareketli. Her görüntüde 2 karşılık gelen nokta seçin.</font>"
        )
        app.statusBar().showMessage(f"{upper.capitalize()}–{lower.capitalize()} sabitlendi. Şimdi {nu.capitalize()} sabit; {nl.capitalize()} hizalanacak.")
        return
    app.manual_mode_active=False
    app.btn_manual_next_stage.setVisible(False)
    app.btn_manual_next_stage.setEnabled(False)
    app.btn_mode_off.setText("Kapalı")
    app.btn_mode_off.setStyleSheet("background-color: #2980b9; color: white; padding: 5px;")
    app.stitch_view.refresh_cursor()
    app.lbl_manual_mode_info.setText("<font color='#2ecc71' size='2'><b>Manuel hizalama tamamlandı.</b> Yüklenen görüntü parçaları sırayla sabitlendi.</font>")
    app.is_stitched_completed=True
    app.update_stitched_spine()
    app.statusBar().showMessage("Manuel hizalama tamamlandı: yüklenen görüntü parçaları sırayla sabitlendi.")


def set_shift_step(app, val_str):
    try:
        app.current_step_val = float(val_str)
        app.step_input.setText(val_str)
    except ValueError:
        pass


def _refresh_stitch_part_buttons(app):
    has_dorsal = app.stitch_files.get("dorsal") is not None
    has_lumbar = app.stitch_files.get("lumbar") is not None
    has_extra = app.stitch_files.get("extra") is not None
    app.btn_move_dorsal.setEnabled(has_dorsal)
    app.btn_move_lumbar.setEnabled(has_lumbar)
    app.btn_move_extra.setEnabled(has_extra)
    available = [key for key, loaded in (("dorsal", has_dorsal), ("lumbar", has_lumbar), ("extra", has_extra)) if loaded]
    if app.active_stitch_part not in available and available:
        app.active_stitch_part = available[0]
    active = app.active_stitch_part
    for key, btn in [("dorsal", app.btn_move_dorsal), ("lumbar", app.btn_move_lumbar), ("extra", app.btn_move_extra)]:
        if btn.isEnabled() and key == active:
            btn.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold; padding: 5px; border-radius: 3px;")
        else:
            btn.setStyleSheet("background-color: #34495e; color: white; padding: 5px; border-radius: 3px;")
    app.btn_move_servical.setStyleSheet("background-color: #1f4f6e; color: #b9d7ea; padding: 5px; border-radius: 3px;")
    app._update_move_offset_label()


def select_stitch_part(app, part_key):
    if part_key == "servical":
        return
    if app.stitch_files.get(part_key) is None:
        return
    app.active_stitch_part = part_key
    app._refresh_stitch_part_buttons()
    app.statusBar().showMessage(f"{part_key.capitalize()} seçildi. Ok tuşları artık bu parçayı hareket ettirir.")


def _update_move_offset_label(app):
    dx, dy = app.stitch_part_offsets.get(app.active_stitch_part, [0.0, 0.0])
    app.lbl_manual_offset.setText(
        f"{app.active_stitch_part.capitalize()} kaydırma: sağ/sol {dx:+.2f} px, yukarı/aşağı {dy:+.2f} px"
    )


def adjust_stitch_offset(app, dx, dy):
    app._stitch_final_verified = False
    app._stitch_final_quality_snapshot = None
    if hasattr(app, "btn_final_save_sticky"):
        app.btn_final_save_sticky.setVisible(False)
    part = app.active_stitch_part
    if part == "servical" or app.stitch_files.get(part) is None:
        return
    app.stitch_part_offsets.setdefault(part, [0.0, 0.0])
    app.stitch_part_offsets[part][0] += float(dx)
    app.stitch_part_offsets[part][1] += float(dy)
    app.stitch_offset_x = app.stitch_part_offsets[part][0]
    app.stitch_offset_y = app.stitch_part_offsets[part][1]
    app._update_move_offset_label()
    app._stitch_interactive = True
    if hasattr(app, "_stitch_render_timer"):
        app._stitch_render_timer.start()
    else:
        app.update_stitched_spine()
    if hasattr(app, "_stitch_full_render_timer"):
        app._stitch_full_render_timer.start()


def reset_stitch_offset(app):
    app._stitch_final_verified = False
    app._stitch_final_quality_snapshot = None
    if hasattr(app, "btn_final_save_sticky"):
        app.btn_final_save_sticky.setVisible(False)
    part = app.active_stitch_part
    if part == "servical":
        return
    app.stitch_part_offsets[part] = [0.0, 0.0]
    app.stitch_offset_x = 0.0
    app.stitch_offset_y = 0.0
    app._update_move_offset_label()
    if hasattr(app, "_stitch_render_timer"):
        app._stitch_render_timer.stop()
    if hasattr(app, "_stitch_full_render_timer"):
        app._stitch_full_render_timer.stop()
    app._stitch_interactive = False
    app.update_stitched_spine()


def on_stitch_zoom_changed(app, value):
    factor = value / 100.0
    app.lbl_zoom_val.setText(f"{factor:.2f}x")
    app.stitch_view.resetTransform()
    app.stitch_view.scale(factor, factor)


def show_stitch_part_context_menu(app, part_name, button, pos):
    if not app.stitch_files.get(part_name):
        return
    labels = {"servical": "Üst", "dorsal": "Orta", "lumbar": "Alt", "extra": "4. Parça"}
    menu = QMenu(app)
    action = menu.addAction(f"{labels.get(part_name, part_name.capitalize())} dosyasını birleştirmeden kaldır")
    pool_action = menu.addAction("Ortak havuzdan ve tüm modüllerden kaldır")
    chosen = menu.exec(button.mapToGlobal(pos))
    if chosen == pool_action:
        path = app.stitch_files.get(part_name)
        if path:
            app._remove_paths_from_all_modules([path])
            app.statusBar().showMessage("Dosya ortak havuzdan kaldırıldı. Diskteki dosya silinmedi.")
    elif chosen == action:
        app.remove_stitch_part(part_name)


def remove_stitch_part(app, part_name):
    old_path = app.stitch_files.get(part_name)
    app.stitch_files[part_name] = None
    if old_path:
        app._stitch_pixmap_cache.pop(old_path, None)
        app._stitch_array_cache.pop(old_path, None)
        app._stitch_gray_cache.pop(old_path, None)
        app._stitch_gray_flag_cache.pop(old_path, None)
        app._auto_align_cache = {k: v for k, v in app._auto_align_cache.items() if old_path not in k}
    if part_name in app.stitch_scenes:
        app.stitch_scenes[part_name].clear()

    app.manual_junction_offsets = (
        app.stitch_controller.remove_part_from_junction_offsets(
            app.manual_junction_offsets,
            part_name,
        )
    )
    app.manual_stage_index = 0

    btn_rem = app.stitch_remove_buttons.get(part_name)
    if btn_rem is not None:
        btn_rem.setVisible(False)
    labels = {"servical": "Üst", "dorsal": "Orta", "lumbar": "Alt", "extra": "4. Parça"}
    btn_load = app.stitch_load_buttons.get(part_name)
    if btn_load is not None:
        btn_load.setText(f"{labels.get(part_name, part_name.capitalize())} Yükle")

    app.update_stitched_spine()
    app.statusBar().showMessage(f"{labels.get(part_name, part_name.capitalize())} dosyası birleştirme modülünden kaldırıldı. Diskteki dosya silinmedi.")


def trigger_stitch_action(app):
    # New alignment invalidates any previous final approval.
    app._stitch_final_verified = False
    app._stitch_final_quality_snapshot = None
    if hasattr(app, "btn_final_save_sticky"):
        app.btn_final_save_sticky.setVisible(False)

    app.update_stitched_spine()
    app.is_stitched_completed = True

    # Do NOT overwrite the quality badge produced by update_stitched_spine().
    # Only use a generic badge when no quality result exists.
    quality = getattr(app, "_last_stitch_quality", {}) or {}
    if quality.get("status") in (None, "unknown"):
        app.lbl_status_badge.setText("Önizleme hazır — kontrol edin")
        app.lbl_status_badge.setStyleSheet(
            "background-color:#2c3e50;color:#3498db;padding:5px 10px;"
            "border-radius:4px;font-weight:bold;font-size:11px;"
        )

    app.controls_container.setVisible(True)
    if hasattr(app, "controls_scroll"):
        app.controls_scroll.setVisible(True)
    if hasattr(app, "stitch_context_label"):
        app.stitch_context_label.setText(
            "Önizleme hazır. Kalite skorunu ve birleşim bölgelerini kontrol edin; sonra sonucu onaylayın."
        )


def _clear_layout_recursive(app, layout):
    while layout.count():
        item = layout.takeAt(0)
        child_layout = item.layout()
        child_widget = item.widget()
        if child_layout is not None:
            app._clear_layout_recursive(child_layout)
            child_layout.deleteLater()
        elif child_widget is not None:
            child_widget.hide()
            child_widget.setParent(None)
            child_widget.deleteLater()


def _final_quality_summary(app):
    quality = getattr(app, "_last_stitch_quality", {}) or {}
    valid_parts = [
        p for p in ["servical", "dorsal", "lumbar", "extra"]
        if app.stitch_files.get(p) is not None
    ]

    status_map = {
        "good": "İyi",
        "warning": "Orta",
        "poor": "Düşük",
        "unknown": "Bilinmiyor",
    }

    lines = []
    for idx, row in enumerate(quality.get("junctions", [])):
        if idx + 1 >= len(valid_parts):
            continue
        upper = valid_parts[idx].capitalize()
        lower = valid_parts[idx + 1].capitalize()
        score = float(row.get("score", 0.0))
        status = status_map.get(row.get("status"), "Bilinmiyor")
        raw = row.get("raw_score")
        if raw is not None and abs(float(raw) - score) >= 0.03:
            lines.append(
                f"{upper} → {lower}: {score:.2f} | {status} (ham {float(raw):.2f})"
            )
        else:
            lines.append(f"{upper} → {lower}: {score:.2f} | {status}")

    avg = quality.get("average_score")
    overall_status = status_map.get(quality.get("status"), "Bilinmiyor")
    overall = (
        f"Genel: {float(avg):.2f} | {overall_status}"
        if avg is not None
        else f"Genel: — | {overall_status}"
    )

    return quality, lines, overall


def _turkish_question(app, title, text, *, approve_text="Onayla", cancel_text="İptal", approve_default=True):
    box = QMessageBox(app)
    box.setIcon(QMessageBox.Icon.Question)
    box.setWindowTitle(title)
    box.setText(text)
    approve_btn = box.addButton(approve_text, QMessageBox.ButtonRole.AcceptRole)
    cancel_btn = box.addButton(cancel_text, QMessageBox.ButtonRole.RejectRole)
    box.setDefaultButton(approve_btn if approve_default else cancel_btn)
    box.exec()
    return box.clickedButton() is approve_btn


def _confirm_final_stitch_quality(app):
    quality, lines, overall = _final_quality_summary(app)
    status = quality.get("status", "unknown")

    if status == "poor":
        QMessageBox.warning(
            app,
            "Son doğrulama başarısız",
            "En az bir birleşim noktasında teknik hizalama güveni düşük.\n\n"
            + ("\n".join(lines) if lines else "Birleşim kalite ayrıntısı yok.")
            + "\n"
            + overall
            + "\\n\\nDama tahtası veya manuel hizalama ile düzeltmeden sonuç kilitlenmeyecek.",
        )
        return False

    if status == "unknown":
        return _turkish_question(
            app,
            "Kalite skoru yok",
            "Birleştirme için güvenilir bir teknik kalite özeti üretilemedi.\n\n"
            "Yine de sonucu sonlandırmak istiyor musunuz?",
            approve_text="Yine de Onayla",
            cancel_text="İptal",
            approve_default=False,
        )

    message = (
        "Birleştirme kalite özeti\n\n"
        + ("\n".join(lines) if lines else "Birleşim kalite ayrıntısı yok.")
        + "\n"
        + overall
        + "\n\n"
    )

    if status == "warning":
        message += (
            "En az bir birleşim 'Orta' düzeyde. Dama tahtasıyla görsel kontrol "
            "önerilir. Kontrol ederek sonucu kilitlemek istiyor musunuz?"
        )
        default = QMessageBox.StandardButton.No
    else:
        message += (
            "Teknik kalite kontrolü uygun. Sonucu kilitleyip final aşamasına "
            "geçmek istiyor musunuz?"
        )
        default = QMessageBox.StandardButton.Yes

    return _turkish_question(
        app,
        "Birleştirme Son Doğrulama",
        message,
        approve_text="Onayla ve Kilitle",
        cancel_text="Geri Dön",
        approve_default=(status == "good"),
    )


def on_confirm_finish_clicked(app):
    if not _confirm_final_stitch_quality(app):
        app.statusBar().showMessage(
            "Birleştirme henüz sonlandırılmadı; kalite kontrolü veya manuel düzeltme yapabilirsiniz."
        )
        return

    # Freeze the currently approved technical quality snapshot.
    quality = getattr(app, "_last_stitch_quality", {}) or {}
    app._stitch_final_verified = True
    app._stitch_final_quality_snapshot = {
        "status": quality.get("status", "unknown"),
        "average_score": quality.get("average_score"),
        "minimum_score": quality.get("minimum_score"),
        "junctions": [dict(row) for row in quality.get("junctions", [])],
    }

    app._clear_layout_recursive(app.controls_layout)
    app.controls_layout.setContentsMargins(0, 0, 0, 0)
    app.controls_layout.setSpacing(6)

    app.controls_layout.addWidget(QLabel("FINAL SONUÇ"))

    snapshot = getattr(app, "_stitch_final_quality_snapshot", {}) or {}
    avg = snapshot.get("average_score")
    status_map = {"good": "İyi", "warning": "Orta", "poor": "Düşük", "unknown": "Bilinmiyor"}
    status_text = status_map.get(snapshot.get("status"), "Bilinmiyor")
    score_text = f"{float(avg):.2f}" if avg is not None else "—"

    lbl_verified = QLabel(
        f"✓ Birleştirme onaylandı ve kilitlendi | Teknik kalite: {score_text} | {status_text}"
    )
    lbl_verified.setWordWrap(True)
    lbl_verified.setStyleSheet(
        "background-color:#1e4d36;color:#2ecc71;padding:7px;"
        "border-radius:4px;font-weight:bold;font-size:10px;"
    )
    app.controls_layout.addWidget(lbl_verified)

    zoom_box = QHBoxLayout()
    zoom_box.addWidget(QLabel("Yakınlaştırma:"))
    app.lbl_zoom_val = QLabel("1.00x")
    zoom_box.addWidget(app.lbl_zoom_val)
    zoom_box.addStretch()
    app.controls_layout.addLayout(zoom_box)

    app.stitch_slider = QSlider(Qt.Horizontal)
    app.stitch_slider.setRange(10, 300)
    app.stitch_slider.setValue(100)
    app.stitch_slider.valueChanged.connect(app.on_stitch_zoom_changed)
    app.controls_layout.addWidget(app.stitch_slider)

    img_adjust_box = QVBoxLayout()
    img_adjust_box.addWidget(QLabel("<b>Görüntü Ayarı (sadece görsel)</b>"))

    b_box = QHBoxLayout()
    b_box.addWidget(QLabel("Parlaklık:"))
    app.sl_brightness = QSlider(Qt.Horizontal)
    app.sl_brightness.setRange(-100, 100)
    app.sl_brightness.setValue(app.final_brightness)
    app.sl_brightness.valueChanged.connect(app._on_final_brightness_changed)
    b_box.addWidget(app.sl_brightness)
    img_adjust_box.addLayout(b_box)

    c_box = QHBoxLayout()
    c_box.addWidget(QLabel("Kontrast:"))
    app.sl_contrast = QSlider(Qt.Horizontal)
    app.sl_contrast.setRange(-100, 100)
    app.sl_contrast.setValue(app.final_contrast)
    app.sl_contrast.valueChanged.connect(app._on_final_contrast_changed)
    c_box.addWidget(app.sl_contrast)
    img_adjust_box.addLayout(c_box)

    btn_reset_img = QPushButton("Görüntü Ayarını Sıfırla")
    btn_reset_img.setStyleSheet("background-color: #34495e; color: white; padding: 6px;")
    btn_reset_img.clicked.connect(app._reset_final_image_adjustment)
    img_adjust_box.addWidget(btn_reset_img)
    app.controls_layout.addLayout(img_adjust_box)

    if hasattr(app, "btn_final_save_sticky"):
        app.btn_final_save_sticky.setVisible(True)

    app.controls_container.adjustSize()
    app.controls_container.updateGeometry()
    if hasattr(app, "controls_scroll"):
        app.controls_scroll.updateGeometry()
        app.controls_scroll.verticalScrollBar().setValue(0)

    app.statusBar().showMessage("Omurga birleştirme kalite kontrolü onaylandı; final sonuç kilitlendi ve kaydetmeye hazır.")


def _on_final_brightness_changed(app, val):
    app.final_brightness = val
    app._apply_final_image_adjustment()


def _on_final_contrast_changed(app, val):
    app.final_contrast = val
    app._apply_final_image_adjustment()


def _reset_final_image_adjustment(app):
    app.final_brightness = 0
    app.final_contrast = 0
    if hasattr(app, 'sl_brightness'):
        app.sl_brightness.blockSignals(True)
        app.sl_brightness.setValue(0)
        app.sl_brightness.blockSignals(False)
    if hasattr(app, 'sl_contrast'):
        app.sl_contrast.blockSignals(True)
        app.sl_contrast.setValue(0)
        app.sl_contrast.blockSignals(False)
    app._apply_final_image_adjustment()

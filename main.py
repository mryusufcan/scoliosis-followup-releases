import sys
import os
import re

import math
import datetime
import json
import copy
from types import SimpleNamespace
import pydicom

import numpy as np

cv2 = None
_cv2_import_checked = False


def optional_cv2():
    """OpenCV'yi yalnızca otomatik hizalama ilk kez kullanıldığında yükle."""
    global cv2, _cv2_import_checked
    if not _cv2_import_checked:
        _cv2_import_checked = True
        try:
            import cv2 as loaded_cv2
            cv2 = loaded_cv2
        except ImportError:
            cv2 = None
    return cv2


from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTabWidget, QFileDialog, QGraphicsView,
    QGraphicsScene, QGraphicsPixmapItem, QGraphicsItem, QSplitter, QAbstractItemView, QListWidget, QListWidgetItem, QTreeWidget, QTreeWidgetItem, QSlider, QStatusBar,
        QDialog, QCheckBox, QGridLayout, QMessageBox, QScrollArea, QSizePolicy, QMenu, QInputDialog,
    QStyleFactory

)
from PySide6.QtCore import Qt, QPointF, QSize, QTimer, QRectF, QSettings, QEvent, QObject, QThreadPool

from PySide6.QtGui import (
        QFont, QPixmap, QImage, QPainter, QPen, QIcon, QPalette, QColor, QActionGroup,

    QWheelEvent, QMouseEvent, QAction, QShortcut, QKeySequence, QTransform,
    QPdfWriter, QPageSize
)




from modular_app.ui.dicom_viewer_components import (

    process_dicom_array,
    DicomPreviewDialog,
    StudySelectionDialog,
    InteractiveGraphicsView,
)
from modular_app.core.stitching_engine import StitchingEngine
from modular_app.core.stitch_controller import StitchController
from modular_app.core import app_session
from modular_app.ui.stitch_widget import build_stitcher_tab
from modular_app.ui.viewer_widget import build_viewer_tab
from modular_app.ui.workspace_widget import build_workspace_tab
from modular_app.ui import workspace_actions
from modular_app.ui import viewer_actions
from modular_app.ui import viewer_records
from modular_app.ui import viewer_core
from modular_app.ui import stitch_widget as stitch_ui_actions
from modular_app.ui import stitch_io
from modular_app.performance_utils import cache_get, cache_put, cache_put_sized
from modular_app.ui.dicom_preload_worker import (
    DicomPreloadController,
    PreloadError,
    PreloadResult,
)








DARK_THEME_QSS = r"""
/* Scoliosis Follow-Up — dark-first clinical desktop theme */
QMainWindow, QWidget#appRoot {
    background-color: #11161D;
    color: #F1F5F9;
}

QWidget {
    color: #F1F5F9;
    font-family: "Segoe UI";
    font-size: 13px;
}

QLabel {
    color: #F1F5F9;
}

QToolTip {
    background-color: #1E2833;
    color: #F1F5F9;
    border: 1px solid #36C5D8;
    padding: 6px 8px;
}

QMenuBar#mainMenuBar {
    background-color: #171E27;
    color: #AAB7C5;
    border-bottom: 1px solid #2A3542;
    padding: 0 4px;
    min-height: 24px;
}

QMenuBar#mainMenuBar::item {
    background: transparent;
    min-width: 48px;
    padding: 2px 6px;
    border-radius: 3px;
    font-size: 12px;
    font-weight: 600;
}

QMenuBar#mainMenuBar::item:selected,
QMenuBar#mainMenuBar::item:pressed {
    background-color: #1E2833;
    color: #F1F5F9;
}

QMenu {
    background-color: #171E27;
    color: #F1F5F9;
    border: 1px solid #2A3542;
    padding: 5px;
}

QMenu::item {
    padding: 8px 28px 8px 12px;
    border-radius: 4px;
}

QMenu::item:selected {
    background-color: #263846;
    color: #36C5D8;
}

QTabWidget::pane {
    background-color: #11161D;
    border: 1px solid #2A3542;
    border-top: none;
}

QTabBar {
    background-color: #171E27;
}

QTabBar::tab {
    background-color: #171E27;
    color: #AAB7C5;
    min-width: 104px;
    min-height: 24px;
    padding: 0 8px;
    margin-right: 1px;
    border: 1px solid transparent;
    border-top-left-radius: 5px;
    border-top-right-radius: 5px;
}

QTabBar::tab:hover {
    background-color: #1E2833;
    color: #F1F5F9;
}

QTabBar::tab:selected {
    background-color: #1E2833;
    color: #36C5D8;
    border: 1px solid #2A3542;
    border-bottom: 2px solid #36C5D8;
}

QPushButton, QToolButton {
    background-color: #1E2833;
    color: #F1F5F9;
    border: 1px solid #2A3542;
    border-radius: 6px;
    padding: 7px 12px;
    min-height: 22px;
}

QPushButton:hover, QToolButton:hover {
    background-color: #263846;
    border-color: #36C5D8;
}

QPushButton:pressed, QToolButton:pressed,
QPushButton:checked, QToolButton:checked {
    background-color: #17424D;
    border-color: #36C5D8;
    color: #F1F5F9;
}

QPushButton:disabled, QToolButton:disabled {
    background-color: #171E27;
    color: #718096;
    border-color: #202833;
}

/* Shared action hierarchy used by viewer, tracking and stitching surfaces. */
QPushButton[uiPrimaryAction="true"] {
    background-color: #1D8478;
    border-color: #36C5D8;
    font-weight: 700;
}

QPushButton[uiPrimaryAction="true"]:hover {
    background-color: #249987;
}

QPushButton[uiMeasurementAction="true"] {
    border-color: #F2B84B;
}

QPushButton[uiMeasurementAction="true"]:checked,
QPushButton[uiMeasurementAction="true"][active="true"] {
    background-color: #604B22;
    color: #FFF7E0;
    border-color: #F2B84B;
    font-weight: 700;
}

QPushButton[uiDangerAction="true"] {
    background-color: #512B31;
    border-color: #E06C75;
    color: #FFF1F2;
}

QPushButton[uiQuietAction="true"] {
    color: #AAB7C5;
}

QFrame#workflowContextBanner {
    background-color: #17232C;
    border: 1px solid #2A5662;
    border-radius: 7px;
}

QLabel#workflowContextTitle {
    color: #36C5D8;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.5px;
}

QLabel#workflowContextMessage {
    color: #D8E1E7;
    font-size: 12px;
}

QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox,
QComboBox, QDateEdit, QDateTimeEdit {
    background-color: #0F141A;
    color: #F1F5F9;
    border: 1px solid #2A3542;
    border-radius: 6px;
    padding: 7px 9px;
    selection-background-color: #236A78;
    selection-color: #F1F5F9;
}

QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus,
QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus,
QDateEdit:focus, QDateTimeEdit:focus {
    border: 1px solid #36C5D8;
}

QComboBox::drop-down {
    width: 26px;
    border: none;
    border-left: 1px solid #2A3542;
}

QListWidget, QTreeWidget, QTableWidget, QTableView, QListView, QTreeView {
    background-color: #171E27;
    alternate-background-color: #141B23;
    color: #F1F5F9;
    border: 1px solid #2A3542;
    border-radius: 6px;
    outline: 0;
}

QListWidget::item, QTreeWidget::item, QTableWidget::item,
QTableView::item, QListView::item, QTreeView::item {
    padding: 6px;
    border-radius: 4px;
}

QListWidget::item:hover, QTreeWidget::item:hover,
QTableWidget::item:hover, QTableView::item:hover,
QListView::item:hover, QTreeView::item:hover {
    background-color: #1E2833;
}

QListWidget::item:selected, QTreeWidget::item:selected,
QTableWidget::item:selected, QTableView::item:selected,
QListView::item:selected, QTreeView::item:selected {
    background-color: #17424D;
    color: #F1F5F9;
    border-left: 2px solid #36C5D8;
}

QLineEdit#studySearch {
    background-color: #0F141A;
    color: #F1F5F9;
    border: 1px solid #2A3542;
    border-radius: 7px;
    padding: 8px 10px;
    min-height: 20px;
}

QLineEdit#studySearch:focus {
    border-color: #36C5D8;
}

QTreeWidget#studyTree, QTreeWidget#viewerFileTree {
    background-color: #141B23;
    border: 1px solid #2A3542;
    border-radius: 8px;
    padding: 4px;
}

QTreeWidget#studyTree::item, QTreeWidget#viewerFileTree::item {
    min-height: 48px;
    padding: 7px 8px;
    margin: 2px 0;
    border: 1px solid transparent;
    border-radius: 7px;
}

QTreeWidget#studyTree::item:hover, QTreeWidget#viewerFileTree::item:hover {
    background-color: #1E2833;
    border-color: #2A3542;
}

QTreeWidget#studyTree::item:selected, QTreeWidget#viewerFileTree::item:selected {
    background-color: #17424D;
    color: #F1F5F9;
    border: 1px solid #236A78;
    border-left: 3px solid #36C5D8;
}

QHeaderView::section {
    background-color: #1E2833;
    color: #AAB7C5;
    padding: 7px;
    border: none;
    border-bottom: 1px solid #2A3542;
}

QCheckBox, QRadioButton {
    color: #F1F5F9;
    spacing: 8px;
}

QCheckBox::indicator, QRadioButton::indicator {
    width: 16px;
    height: 16px;
}

QSlider::groove:horizontal {
    height: 4px;
    background: #2A3542;
    border-radius: 2px;
}

QSlider::handle:horizontal {
    width: 14px;
    margin: -5px 0;
    background: #36C5D8;
    border: 2px solid #0B0F14;
    border-radius: 7px;
}

QSlider::sub-page:horizontal {
    background: #236A78;
    border-radius: 2px;
}

QProgressBar {
    background-color: #0F141A;
    color: #F1F5F9;
    border: 1px solid #2A3542;
    border-radius: 5px;
    text-align: center;
}

QProgressBar::chunk {
    background-color: #36C5D8;
    border-radius: 4px;
}

QSplitter::handle {
    background-color: #2A3542;
}

QSplitter::handle:hover {
    background-color: #36C5D8;
}

QGraphicsView {
    background-color: #0B0F14;
    border: 1px solid #2A3542;
}

QScrollBar:vertical, QScrollBar:horizontal {
    background-color: #11161D;
    border: none;
    margin: 0;
}

QScrollBar:vertical {
    width: 10px;
}

QScrollBar:horizontal {
    height: 10px;
}

QScrollBar::handle:vertical, QScrollBar::handle:horizontal {
    background-color: #344252;
    border-radius: 4px;
    min-height: 24px;
    min-width: 24px;
}

QScrollBar::handle:vertical:hover, QScrollBar::handle:horizontal:hover {
    background-color: #36C5D8;
}

QScrollBar::add-line, QScrollBar::sub-line,
QScrollBar::add-page, QScrollBar::sub-page {
    background: none;
    border: none;
}

QStatusBar#mainStatusBar {
    background-color: #171E27;
    color: #AAB7C5;
    border-top: 1px solid #2A3542;
}

QStatusBar#mainStatusBar::item {
    border: none;
}

QDialog, QMessageBox, QInputDialog {
    background-color: #171E27;
    color: #F1F5F9;
}

QDialog#workflowDialog {
    background-color: #171E27;
}

QDialog QLabel#dialogSubtitle {
    color: #AAB7C5;
    font-size: 12px;
}

QDialog QPushButton[uiPrimaryAction="true"] {
    min-width: 150px;
}

QDialog QPushButton[uiDangerAction="true"] {
    min-width: 125px;
}

QGroupBox {
    background-color: #171E27;
    border: 1px solid #2A3542;
    border-radius: 8px;
    margin-top: 12px;
    padding: 14px 10px 10px 10px;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 6px;
    color: #AAB7C5;
}
"""


_LIGHT_THEME_REPLACEMENTS = {
    "#11161D": "#F4F7FA",
    "#0B0F14": "#E8EEF3",
    "#0F141A": "#FFFFFF",
    "#171E27": "#FFFFFF",
    "#1E2833": "#EEF3F7",
    "#202833": "#D8E1E8",
    "#263846": "#DCEEF2",
    "#2A3542": "#C7D2DC",
    "#344252": "#94A3B8",
    "#36C5D8": "#147D8A",
    "#236A78": "#2D8B98",
    "#17424D": "#D5F0F3",
    "#F1F5F9": "#17212B",
    "#AAB7C5": "#526273",
    "#718096": "#64748B",
    "#D8E1E7": "#334155",
    "#1D8478": "#177E89",
    "#249987": "#1E9A8C",
    "#604B22": "#FFF3CD",
    "#FFF7E0": "#6B4F00",
    "#512B31": "#FDE8EA",
    "#E06C75": "#C2414B",
    "#17232C": "#E7F5F7",
    "#2A5662": "#A7D7DF",
    "#95A5A6": "#64748B",
    "#7F95A5": "#64748B",
    "#DCE5EB": "#334155",
    "#111111": "#FFFFFF",
    "#137f72": "#177E89",
    "#141b23": "#F4F7FA",
    "#151c24": "#FFFFFF",
    "#168f80": "#177E89",
    "#f2b84b": "#B7791F",
    "#f39c12": "#B45309",
    "#fff1f2": "#7F1D1D",
    "#151c24": "#F8FAFC",
    "#1c2630": "#FFFFFF",
    "#c7d0d7": "#475569",
    "#1c5260": "#CDEFF2",
    "#28343d": "#E2E8F0",
    "#3a444c": "#CBD5E1",
    "#4f93a8": "#5EA7B5",
    "#aebac3": "#64748B",
    "#667681": "#94A3B8",
    "#20262c": "#F4F7FA",
    "#333e47": "#CBD5E1",
    "#c8d1d8": "#475569",
    "#262d34": "#FFFFFF",
    "#36424c": "#CBD5E1",
    "#303b45": "#E7EEF3",
    "#e1e8ed": "#334155",
    "#41505d": "#B6C2CC",
    "#394854": "#DCE7EC",
    "#526675": "#5D7A84",
    "#d5dde3": "#334155",
    "#22292f": "#FFFFFF",
    "#2f6687": "#277F8C",
    "#6aa1bf": "#3B93A3",
    "#bdc3c7": "#475569",
    "#2ecc71": "#15803D",
    "#7f8c8d": "#64748B",
    "#1e1e1e": "#F8FAFC",
    "#444": "#CBD5E1",
    "#27ae60": "#168A56",
    "#427d9e": "#6CA3AF",
    "#c0392b": "#B42318",
    "#ecf0f1": "#17212B",
    "#242424": "#FFFFFF",
    "#3498db": "#2074A3",
    "#f1c40f": "#A16207",
    "#e74c3c": "#B42318",
    "#5a4317": "#FEF3C7",
    "#5a2525": "#FEE2E2",
    "#2c3e50": "#E2E8F0",
}


def _translate_theme_colors(style_text: str) -> str:
    """Translate six- and three-digit hex colors without case sensitivity."""
    if not style_text:
        return style_text
    replacements = {key.lower(): value for key, value in _LIGHT_THEME_REPLACEMENTS.items()}

    def replace_match(match):
        return replacements.get(match.group(0).lower(), match.group(0))

    return re.sub(r"#[0-9A-Fa-f]{6}|#[0-9A-Fa-f]{3}(?![0-9A-Fa-f])", replace_match, str(style_text))


def _build_light_theme_qss() -> str:
    translated = _translate_theme_colors(DARK_THEME_QSS)
    return translated + """

/* Light-theme action contrast overrides. Text and icon contrast must not rely on hue alone. */
QPushButton[uiPrimaryAction="true"],
QPushButton[uiPrimary="true"],
QPushButton[trackingPrimary="true"] {
    background-color: #0F6B75;
    color: #FFFFFF;
    border-color: #09545C;
}

QPushButton[uiPrimaryAction="true"]:hover,
QPushButton[uiPrimary="true"]:hover,
QPushButton[trackingPrimary="true"]:hover {
    background-color: #0B7D88;
    color: #FFFFFF;
    border-color: #07454C;
}

QPushButton[uiDangerAction="true"] {
    background-color: #B42318;
    color: #FFFFFF;
    border-color: #8F1D14;
}

QPushButton[uiDangerAction="true"]:hover {
    background-color: #C73A2F;
    color: #FFFFFF;
    border-color: #7F1D1D;
}

QPushButton[uiMeasurementAction="true"]:checked,
QPushButton[uiMeasurementAction="true"][active="true"],
QPushButton[uiMeasurementActive="true"],
QPushButton[trackingMeasurementActive="true"] {
    background-color: #FFF3CD;
    color: #6B4F00;
    border-color: #A16207;
}

QTabBar::tab:selected {
    color: #0F6B75;
    border-bottom-color: #0F6B75;
}

QToolTip {
    background-color: #FFFFFF;
    color: #17212B;
    border-color: #0F6B75;
}
"""


LIGHT_THEME_QSS = _build_light_theme_qss()


_THEME_PALETTES = {
    "dark": {
        "window": "#11161D",
        "window_text": "#F1F5F9",
        "base": "#0F141A",
        "alternate": "#171E27",
        "button": "#1E2833",
        "button_text": "#F1F5F9",
        "highlight": "#236A78",
        "highlighted_text": "#F1F5F9",
        "tooltip_base": "#1E2833",
        "tooltip_text": "#F1F5F9",
    },
    "light": {
        "window": "#F4F7FA",
        "window_text": "#17212B",
        "base": "#FFFFFF",
        "alternate": "#EEF3F7",
        "button": "#EEF3F7",
        "button_text": "#17212B",
        "highlight": "#2D8B98",
        "highlighted_text": "#FFFFFF",
        "tooltip_base": "#FFFFFF",
        "tooltip_text": "#17212B",
    },
}


def _apply_local_widget_styles(app, theme: str) -> None:
    """Translate construction-time local styles so theme switching reaches all panels."""
    for widget in app.allWidgets():
        base_style = widget.property("_themeBaseStyleSheet")
        if base_style is None:
            base_style = widget.styleSheet()
            widget.setProperty("_themeBaseStyleSheet", base_style)
        if not base_style:
            continue
        target_style = str(base_style)
        if theme == "light":
            target_style = _translate_theme_colors(target_style)
            object_name = widget.objectName()
            if object_name == "viewerControlsBox":
                target_style += """
                QWidget#viewerControlsBox QPushButton[uiPrimary="true"] {
                    background-color: #0F6B75; color: #FFFFFF; border-color: #09545C;
                }
                QWidget#viewerControlsBox QPushButton[uiPrimary="true"]:hover {
                    background-color: #0B7D88; color: #FFFFFF; border-color: #07454C;
                }
                """
            elif object_name == "trackingControlsBox":
                target_style += """
                QWidget#trackingControlsBox QPushButton[trackingPrimary="true"] {
                    background-color: #0F6B75; color: #FFFFFF; border-color: #09545C;
                }
                QWidget#trackingControlsBox QPushButton[trackingPrimary="true"]:hover {
                    background-color: #0B7D88; color: #FFFFFF; border-color: #07454C;
                }
                """
            elif object_name == "stitchRightPanel":
                target_style += """
                QWidget#stitchRightPanel QPushButton[uiPrimaryAction="true"] {
                    background-color: #0F6B75; color: #FFFFFF; border-color: #09545C;
                }
                QWidget#stitchRightPanel QPushButton[uiPrimaryAction="true"]:hover {
                    background-color: #0B7D88; color: #FFFFFF; border-color: #07454C;
                }
                """
        if widget.styleSheet() != target_style:
            widget.setStyleSheet(target_style)


class _ThemeEventFilter(QObject):
    """Apply the active palette to local styles when a new popup is shown."""

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.Show and hasattr(watched, "styleSheet"):
            theme = str(QApplication.instance().property("appTheme") or "dark")
            base_style = watched.property("_themeBaseStyleSheet")
            if base_style is None:
                base_style = watched.styleSheet()
                watched.setProperty("_themeBaseStyleSheet", base_style)
            if base_style and theme == "light":
                target_style = _translate_theme_colors(str(base_style))
                if watched.styleSheet() != target_style:
                    watched.setStyleSheet(target_style)
        return False


def apply_app_theme(app, theme: str = "dark") -> str:
    """Apply the selected theme to the complete Qt application and return its key."""
    key = "light" if str(theme).casefold() == "light" else "dark"
    colors = _THEME_PALETTES[key]
    app.setStyle(QStyleFactory.create("Fusion"))
    palette = QPalette()
    roles = {
        QPalette.ColorRole.Window: "window",
        QPalette.ColorRole.WindowText: "window_text",
        QPalette.ColorRole.Base: "base",
        QPalette.ColorRole.AlternateBase: "alternate",
        QPalette.ColorRole.Text: "window_text",
        QPalette.ColorRole.Button: "button",
        QPalette.ColorRole.ButtonText: "button_text",
        QPalette.ColorRole.Highlight: "highlight",
        QPalette.ColorRole.HighlightedText: "highlighted_text",
        QPalette.ColorRole.ToolTipBase: "tooltip_base",
        QPalette.ColorRole.ToolTipText: "tooltip_text",
    }
    for role, name in roles.items():
        palette.setColor(role, QColor(colors[name]))
    app.setPalette(palette)
    from modular_app.ui.ui_icons import make_icon, set_icon_theme
    set_icon_theme(key)
    app.setProperty("appTheme", key)
    if not hasattr(app, "_theme_event_filter"):
        app._theme_event_filter = _ThemeEventFilter(app)
        app.installEventFilter(app._theme_event_filter)
    app.setStyleSheet(DARK_THEME_QSS if key == "dark" else LIGHT_THEME_QSS)
    _apply_local_widget_styles(app, key)
    for widget in app.allWidgets():
        icon_name = widget.property("iconName")
        if icon_name and hasattr(widget, "setIcon"):
            try:
                icon_size = int(widget.property("iconSizePx") or 22)
            except (TypeError, ValueError):
                icon_size = 22
            icon_color = None
            if key == "light":
                is_primary = any(
                    widget.property(name) is True
                    for name in ("uiPrimaryAction", "uiPrimary", "trackingPrimary")
                )
                is_danger = widget.property("uiDangerAction") is True
                is_measurement_active = (
                    widget.property("uiMeasurementActive") is True
                    or widget.property("active") is True
                    or widget.property("trackingMeasurementActive") is True
                    or (hasattr(widget, "isChecked") and widget.isChecked())
                ) and any(
                    widget.property(name) is True
                    for name in ("uiMeasurementAction", "trackingMeasurementActive")
                )
                if is_primary or is_danger:
                    icon_color = "#FFFFFF"
                elif is_measurement_active:
                    icon_color = "#6B4F00"
            widget.setIcon(make_icon(str(icon_name), icon_size, color=icon_color))
    return key


def apply_dark_theme(app):
    """Backward-compatible wrapper; dark remains the safe default."""
    return apply_app_theme(app, "dark")


class ScoliosisFollowUpApp(QMainWindow):

    OVERLAP_PX = 80

    def __init__(self):
        super().__init__()
        app = QApplication.instance()
        self._theme_settings = QSettings("MRYusufCan", "ScoliosisFollowUp")
        self._theme_name = "dark"
        if app is not None:
            saved_theme = self._theme_settings.value("ui/theme", "dark")
            requested_theme = (
                "light"
                if str(saved_theme).casefold() == "light"
                else "dark"
            )
            # QApplication teması süreçte zaten hazırsa aynı native Qt stilini
            # yeniden kurmak gereksizdir. Özellikle çok sayıda pencere açıp
            # kapatan otomatik testlerde QStyle nesnesini tekrar değiştirmek
            # Windows/Qt tarafında erişim ihlaline yol açabilir.
            if app.property("appTheme") == requested_theme:
                self._theme_name = requested_theme
            else:
                self._theme_name = apply_app_theme(app, requested_theme)

        self.setWindowTitle("Scoliosis Follow-Up")
        self.setMinimumSize(1180, 720)
        self.setGeometry(100, 100, 1400, 900)



        self.loaded_files = {}
        # Tüm modüllerin gördüğü tek kaynak dosya havuzu.
        # Modül listeleri çalışma görünümüdür; bu havuz dosyanın uygulama oturumundaki varlığını temsil eder.
        self.shared_image_paths = []
        self.current_mode = "side_by_side"
        self.overlay_item = None
        self.overlay_offset_x = 0.0
        self.overlay_offset_y = 0.0
        self.overlay_opacity = 0.50
        self.overlay_scale = 1.0
        self._overlay_initial_scale = 1.0
        self.window_settings = {}
        self._default_window_cache = {}
        self._default_window_cache_limit = 128

        self.cobb_mode_active = False
        self.cobb_points = []
        self.cobb_items = []
        self.cobb_target_side = None

        self.final_result_qimage = None
        self.final_brightness = 0
        self.final_contrast = 0

        self.stitch_files = {'servical': None, 'dorsal': None, 'lumbar': None, 'extra': None}
        self.stitch_scenes = {}
        self.stitch_load_buttons = {}
        self.stitch_remove_buttons = {}
        self.last_stitch_folder = ''
        self.is_stitched_completed = False

        self.stitch_offset_x = 0.0
        self.stitch_offset_y = 0.0
        self.stitch_part_offsets = {"servical": [0.0, 0.0], "dorsal": [0.0, 0.0], "lumbar": [0.0, 0.0], "extra": [0.0, 0.0]}
        self.active_stitch_part = "dorsal"
        self.current_step_val = 1.0
        self.manual_mode_active = False
        self.manual_points = {}
        self.manual_junction_offsets = {}
        self.manual_stage_index = 0
        self._pick_pixmaps = []
        self._pick_positions = []
        self._manual_point_marker_by_part = {}
        self._last_pixmaps = []
        self._last_positions = []
        self._last_overlap = self.OVERLAP_PX
        self._manual_point_markers = []

        self._stitch_pixmap_cache = {}
        self._stitch_pixmap_cache_limit = 6
        self._stitch_array_cache = {}
        self._stitch_array_cache_bytes = 256 * 1024 * 1024

        self._auto_align_cache = {}
        self._auto_align_cache_limit = 12

        self._stitch_mask_cache = {}
        self.stitch_engine = StitchingEngine(mask_cache=self._stitch_mask_cache)
        self.stitch_controller = StitchController(self.stitch_engine)
        self.stitch_controller.manual_stage_index = getattr(
            self, "_manual_stage_index_fallback", 0
        )
        self.stitch_controller.manual_points = getattr(
            self, "_manual_points_fallback", {}
        )
        self.stitch_controller.manual_junction_offsets = getattr(
            self, "_manual_junction_offsets_fallback", {}
        )
        self._stitch_gray_cache = {}
        self._stitch_gray_cache_bytes = 256 * 1024 * 1024

        self._stitch_gray_flag_cache = {}
        self._stitch_result_item = None
        self._viewer_pixmap_cache = {}

        self.viewer_current_path = None
        self.viewer_window_settings = {}
        self.viewer_brightness_value = 0
        self.viewer_cobb_mode_active = False
        self.viewer_cobb_points = []
        self.viewer_cobb_items = []
        self.viewer_cobb_preview_items = []
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
        # Undo / Redo geçmişi: görüntüleyici ölçümleri, işaretlemeler ve overlay hizalaması.
        self._undo_stack = []
        self._redo_stack = []
        self._history_limit = 100
        self._overlay_drag_history_before = None
        self.viewer_pixmap_item = None
        self._viewer_only_pixmap_cache = {}
        self._viewer_dataset_cache = {}
        self._viewer_dataset_cache_limit = 1
        self._viewer_dataset_cache_bytes = 32 * 1024 * 1024
        self._viewer_decoded_array_cache = {}
        self._viewer_decoded_array_cache_limit = 2
        self._viewer_decoded_array_cache_bytes = 128 * 1024 * 1024
        self._viewer_pixmap_cache_limit = 10
        self._viewer_pixmap_cache_bytes = 128 * 1024 * 1024
        self._tracking_dataset_cache = {}
        self._tracking_dataset_cache_limit = 2

        self._viewer_dicom_flags = {}
        self._viewer_metadata_cache = {}
        # Pixel Data içermeyen DICOM başlıklarını sınırlı cache'te tut.
        self._viewer_header_cache = {}
        self._viewer_header_cache_limit = 32
        self._viewer_path_cache_limit = 128

        self._viewer_frame_counts = {}
        self._viewer_fit_scale = 0.0
        self._viewer_preload_enabled = True
        self._viewer_preload_pending = {}
        self._viewer_preload_pool = QThreadPool(self)
        self._viewer_preload_pool.setMaxThreadCount(1)
        self._viewer_preload_controller = DicomPreloadController(
            pool=self._viewer_preload_pool,
            parent=self,
        )

        self._viewer_preload_controller.image_ready.connect(self._on_viewer_preload_ready)
        self._viewer_preload_controller.decode_failed.connect(self._on_viewer_preload_failed)
        self._viewer_preload_controller.decode_cancelled.connect(self._on_viewer_preload_cancelled)
        self.viewer_frame_index = 0

        self.viewer_frame_count = 1
        self.viewer_rotation = 0
        self.viewer_flip_horizontal = False
        self.viewer_flip_vertical = False
        self.viewer_inverted = False
        self.viewer_cine_timer = QTimer(self)
        self.viewer_cine_timer.setInterval(120)
        self.viewer_cine_timer.timeout.connect(self.advance_viewer_frame)

        self._stitch_render_timer = QTimer(self)
        self._stitch_render_timer.setSingleShot(True)
        self._stitch_render_timer.setInterval(16)
        self._stitch_render_timer.timeout.connect(self._render_interactive_preview)
        self._stitch_full_render_timer = QTimer(self)
        self._stitch_full_render_timer.setSingleShot(True)
        self._stitch_full_render_timer.setInterval(140)
        self._stitch_full_render_timer.timeout.connect(self._render_full_after_move)
        self._workspace_render_timer = QTimer(self)
        self._workspace_render_timer.setSingleShot(True)
        self._workspace_render_timer.setInterval(45)
        self._workspace_render_timer.timeout.connect(self._flush_workspace_render)
        self._viewer_render_timer = QTimer(self)
        self._viewer_render_timer.setSingleShot(True)
        self._viewer_render_timer.setInterval(45)
        self._viewer_render_timer.timeout.connect(self._flush_viewer_render)
        self._stitch_interactive = False

        self._stitch_preview_scale = 0.55

        menubar = self.menuBar()
        menubar.setObjectName("mainMenuBar")

        file_menu = menubar.addMenu("Dosya")
        file_menu.addAction("Görüntü Aç", self.load_dicoms)
        file_menu.addAction("Çıkış", self.close)

        view_menu = menubar.addMenu("Görüntüleme")
        view_menu.addAction("Yan Yana Karşılaştır", self.set_side_by_side_mode)
        view_menu.addAction("Overlay Karşılaştırma", self.set_overlay_mode)

        theme_menu = view_menu.addMenu("Tema")
        theme_group = QActionGroup(self)
        theme_group.setExclusive(True)
        self._theme_actions = {}
        for theme_key, theme_label in (("dark", "Koyu Tema"), ("light", "Açık Tema")):
            theme_action = theme_menu.addAction(theme_label)
            theme_action.setCheckable(True)
            theme_action.setChecked(self._theme_name == theme_key)
            theme_action.triggered.connect(
                lambda checked=False, selected=theme_key: self.set_theme(selected)
            )
            theme_group.addAction(theme_action)
            self._theme_actions[theme_key] = theme_action

        tools_menu = menubar.addMenu("Ölçüm ve Düzenleme")
        tools_menu.addAction("Cobb Açısı Ölç", self.toggle_cobb_measurement)
        tools_menu.addSeparator()
        self.action_undo = tools_menu.addAction("Geri Al", self.undo_last_action)
        self.action_redo = tools_menu.addAction("Yinele", self.redo_last_action)

        self.action_undo.setEnabled(False)
        self.action_redo.setEnabled(False)

        help_menu = menubar.addMenu("Yardım")
        help_menu.addAction("Hakkında", lambda: QMessageBox.information(self, "Hakkında", "Scoliosis Follow-Up v1.2"))

        self.central_widget = QWidget()
        self.central_widget.setObjectName("appRoot")
        self.setCentralWidget(self.central_widget)

        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.setUsesScrollButtons(True)
        self.main_layout.addWidget(self.tabs)

        self.init_viewer_tab()
        self.init_stitcher_tab()
        self.init_workspace_tab()
        self.tabs.setCurrentWidget(self.viewer_tab)

        self.setStatusBar(QStatusBar(self))
        self.statusBar().setObjectName("mainStatusBar")
        self.statusBar().showMessage("Hazır.")

        # Otomatik çalışma oturumu: modüler başlatıcı kendi __init__ işlemlerini
        # tamamladıktan sonra event-loop'un ilk turunda geri yüklenir.
        # Yalnızca kullanıcının önceki kapanışta açıkça kaydettiği çalışma
        # oturumu varsa açılışta geri yüklenir.
        QTimer.singleShot(0, self._restore_auto_session)

    def set_theme(self, theme: str, *, persist: bool = True) -> str:
        """Switch the complete application theme and persist the user preference."""
        app = QApplication.instance()
        if app is None:
            return "dark"
        self._theme_name = apply_app_theme(app, theme)
        for key, action in getattr(self, "_theme_actions", {}).items():
            action.blockSignals(True)
            action.setChecked(key == self._theme_name)
            action.blockSignals(False)
        if persist:
            self._theme_settings.setValue("ui/theme", self._theme_name)
            self._theme_settings.sync()
            repository = getattr(self, "exam_repository", None)
            if repository is not None:
                try:
                    repository.set_setting("ui/theme", self._theme_name)
                except Exception:
                    pass
            if hasattr(self, "statusBar"):
                self.statusBar().showMessage(
                    "Açık tema etkinleştirildi." if self._theme_name == "light" else "Koyu tema etkinleştirildi."
                )
        return self._theme_name


    def closeEvent(self, event):

        return app_session.closeEvent(self, event)


    def _auto_session_path(self):
        return app_session._auto_session_path(self)


    def _build_auto_session(self):
        return app_session._build_auto_session(self)


    def _save_auto_session(self):
        return app_session._save_auto_session(self)


    def _restore_auto_session(self):
        return app_session._restore_auto_session(self)


    def _remember_shared_paths(self, paths):
        return app_session._remember_shared_paths(self, paths)


    def _shared_pool_paths(self):
        return app_session._shared_pool_paths(self)


    def _forget_shared_paths(self, paths):
        return app_session._forget_shared_paths(self, paths)


    def _remove_paths_from_all_modules(self, paths):
        return app_session._remove_paths_from_all_modules(self, paths)


    def _capture_edit_state(self):
        return app_session._capture_edit_state(self)


    def _history_commit(self, label, before):
        return app_session._history_commit(self, label, before)


    def _update_history_actions(self):
        return app_session._update_history_actions(self)


    def _apply_edit_state(self, state):
        return app_session._apply_edit_state(self, state)


    def undo_last_action(self):
        return app_session.undo_last_action(self)


    def redo_last_action(self):
        return app_session.redo_last_action(self)


    def init_viewer_tab(self):
        """Viewer UI kurulumunu moduler dosyaya devreder."""
        build_viewer_tab(self, InteractiveGraphicsView)

    def open_viewer_files(self):
        # Seçici yalnızca Görüntüleyici listesini değil, ortak havuzun tamamını gösterir.
        initial_paths = self._shared_pool_paths()
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
        return viewer_core._add_viewer_paths(self, paths)


    def _viewer_file_items(self):
        return viewer_core._viewer_file_items(self)


    def _viewer_tree_find_or_add(self, parent, title):
        return viewer_core._viewer_tree_find_or_add(self, parent, title)


    def _viewer_tree_group(self, metadata):
        return viewer_core._viewer_tree_group(self, metadata)


    def _remove_tree_item_and_empty_groups(self, tree, item):
        return viewer_core._remove_tree_item_and_empty_groups(self, tree, item)


    def show_viewer_file_context_menu(self, pos):
        return viewer_core.show_viewer_file_context_menu(self, pos)


    def _viewer_decoded_array_cache_key(self, file_path, frame_index=0):
        absolute_path = os.path.abspath(file_path)
        try:
            stat = os.stat(absolute_path)
            source_signature = (int(stat.st_mtime_ns), int(stat.st_size))
        except OSError:
            source_signature = (0, 0)
        return (absolute_path, source_signature, int(frame_index))


    def _evict_stale_viewer_signature(self, absolute_path, source_signature):
        """Drop old decoded/pixmap entries when a path is replaced in place."""
        for cache_name in ("_viewer_decoded_array_cache", "_viewer_only_pixmap_cache"):
            cache = getattr(self, cache_name, None)
            if not isinstance(cache, dict):
                continue
            for key in list(cache):
                if not isinstance(key, tuple) or len(key) < 2:
                    continue
                if os.path.abspath(str(key[0])) == absolute_path and key[1] != source_signature:
                    cache.pop(key, None)


    def _viewer_pixmap_cache_key(self, file_path, frame_index=None):

        absolute_path = os.path.abspath(file_path)
        try:
            stat = os.stat(absolute_path)
            source_signature = (int(stat.st_mtime_ns), int(stat.st_size))
        except OSError:
            source_signature = (0, 0)
        self._evict_stale_viewer_signature(absolute_path, source_signature)
        brightness = int(getattr(self, 'viewer_brightness_value', 0))
        default_wc, default_ww = self._default_window(absolute_path)
        wc, ww = self.viewer_window_settings.get(absolute_path, (default_wc, default_ww))
        if frame_index is None:
            frame_index = self.viewer_frame_index if absolute_path == self.viewer_current_path else 0
        return (
            absolute_path,
            source_signature,
            brightness,
            round(float(wc), 3),
            round(float(ww), 3),
            int(frame_index),
            self.viewer_rotation,
            self.viewer_flip_horizontal,
            self.viewer_flip_vertical,
            self.viewer_inverted,
        )


    def get_viewer_file_pixmap(self, file_path, *, cache_result=True):
        absolute_path = os.path.abspath(file_path)
        brightness = int(getattr(self, 'viewer_brightness_value', 0))
        default_wc, default_ww = self._default_window(absolute_path)
        wc, ww = self.viewer_window_settings.get(absolute_path, (default_wc, default_ww))
        frame_index = self.viewer_frame_index if absolute_path == self.viewer_current_path else 0
        cache_key = self._viewer_pixmap_cache_key(absolute_path, frame_index)
        cached = cache_get(self._viewer_only_pixmap_cache, cache_key)
        if cached is not None and not cached.isNull():
            return cached

        try:
            decoded_key = self._viewer_decoded_array_cache_key(absolute_path, frame_index)
            source = cache_get(self._viewer_decoded_array_cache, decoded_key)
            ds = cache_get(self._viewer_dataset_cache, absolute_path)
            if source is None:
                if ds is None:
                    ds = pydicom.dcmread(absolute_path)
                    cache_put_sized(
                        self._viewer_dataset_cache,
                        absolute_path,
                        ds,
                        max_bytes=self._viewer_dataset_cache_bytes,
                        max_entries=self._viewer_dataset_cache_limit,
                    )
                source = ds.pixel_array
                if getattr(source, "ndim", 0) == 3:
                    samples = int(getattr(ds, "SamplesPerPixel", 1) or 1)
                    if samples > 1 and source.shape[-1] in (3, 4):
                        source = source[..., 0]
                    else:
                        source = source[min(max(0, frame_index), source.shape[0] - 1)]
                source = np.ascontiguousarray(np.array(source, copy=True))
                source.setflags(write=False)
                cache_put_sized(
                    self._viewer_decoded_array_cache,
                    decoded_key,
                    source,
                    max_bytes=self._viewer_decoded_array_cache_bytes,
                    max_entries=self._viewer_decoded_array_cache_limit,
                )
            elif ds is None:
                # An array hit can outlive the one-entry Dataset cache. Header-only
                # metadata is enough for render transforms when source_array exists.
                header_loader = getattr(viewer_core, "_viewer_header_for_path", None)
                ds = header_loader(self, absolute_path) if callable(header_loader) else None
                if ds is None:
                    ds = pydicom.dcmread(absolute_path, stop_before_pixels=True)

            arr = process_dicom_array(
                ds,
                brightness,
                wc,
                ww,
                source_array=source,
            )
            if arr is not None and arr.ndim == 2:
                if self.viewer_inverted:
                    arr = 255 - arr
                rotations = (self.viewer_rotation // 90) % 4
                if rotations:
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
                if cache_result:
                    cache_put_sized(
                        self._viewer_only_pixmap_cache,
                        cache_key,
                        pixmap,
                        max_bytes=self._viewer_pixmap_cache_bytes,
                        max_entries=self._viewer_pixmap_cache_limit,
                    )
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
            if cache_result:
                cache_put_sized(
                    self._viewer_only_pixmap_cache,
                    cache_key,
                    pixmap,
                    max_bytes=self._viewer_pixmap_cache_bytes,
                    max_entries=self._viewer_pixmap_cache_limit,
                )
        return pixmap

    def _on_viewer_preload_ready(self, result: PreloadResult):
        request = result.request
        fit = bool(self._viewer_preload_pending.pop(request.request_id, False))
        is_current = (
            os.path.abspath(request.path) == os.path.abspath(self.viewer_current_path or '')
            and int(request.frame_index) == int(self.viewer_frame_index)
        )
        try:
            stat = os.stat(request.path)
            current_signature = (int(stat.st_mtime_ns), int(stat.st_size))
        except OSError:
            current_signature = (0, 0)
        if tuple(getattr(request, 'source_signature', (0, 0))) != current_signature:
            if is_current and getattr(self, '_viewer_preload_enabled', False):
                self.request_viewer_preload(request.path, fit=fit, reason='source-replaced')
            return
        try:
            decoded_array = result.decoded.array
            if not is_current:
                if str(getattr(request, 'reason', '')).startswith('prefetch'):
                    decoded_array.setflags(write=False)
                    decoded_key = self._viewer_decoded_array_cache_key(request.path, request.frame_index)
                    cache_put_sized(
                        self._viewer_decoded_array_cache,
                        decoded_key,
                        decoded_array,
                        max_bytes=self._viewer_decoded_array_cache_bytes,
                        max_entries=self._viewer_decoded_array_cache_limit,
                    )
                return
            decoded_array.setflags(write=False)
            decoded_key = self._viewer_decoded_array_cache_key(request.path, request.frame_index)
            cache_put_sized(
                self._viewer_decoded_array_cache,
                decoded_key,
                decoded_array,
                max_bytes=self._viewer_decoded_array_cache_bytes,
                max_entries=self._viewer_decoded_array_cache_limit,
            )
            default_wc, default_ww = self._default_window(request.path)

            wc, ww = self.viewer_window_settings.get(
                os.path.abspath(request.path),
                (default_wc, default_ww),
            )
            arr = process_dicom_array(
                SimpleNamespace(**dict(result.decoded.render_context)),
                int(getattr(self, 'viewer_brightness_value', 0)),
                wc,
                ww,
                source_array=result.decoded.array,
            )
            if arr is None or arr.ndim != 2:
                raise ValueError("DICOM görünüm dönüşümü sonuç üretmedi.")
            if self.viewer_inverted:
                arr = 255 - arr
            rotations = (self.viewer_rotation // 90) % 4
            if rotations:
                arr = np.rot90(arr, -rotations)
            if self.viewer_flip_horizontal:
                arr = np.fliplr(arr)
            if self.viewer_flip_vertical:
                arr = np.flipud(arr)
            arr = np.ascontiguousarray(arr)
            height, width = arr.shape
            pixmap = QPixmap.fromImage(
                QImage(arr.data, width, height, int(arr.strides[0]), QImage.Format.Format_Grayscale8).copy()
            )
            cache_key = self._viewer_pixmap_cache_key(request.path, request.frame_index)
            cache_put_sized(
                self._viewer_only_pixmap_cache,
                cache_key,
                pixmap,
                max_bytes=self._viewer_pixmap_cache_bytes,
                max_entries=self._viewer_pixmap_cache_limit,
            )
            self._apply_viewer_preloaded_pixmap(pixmap, fit=fit)
            self._schedule_viewer_neighbor_prefetch(request.path)
        except Exception as exc:
            self._on_viewer_preload_failed(
                PreloadError(request=request, message=str(exc), exception_type=exc.__class__.__name__)
            )


    def _apply_viewer_preloaded_pixmap(self, pixmap, *, fit=False):
        if self.viewer_pixmap_item is None:
            self.viewer_pixmap_item = self.viewer_scene.addPixmap(pixmap)
        else:
            self.viewer_pixmap_item.setPixmap(pixmap)
        self._add_viewer_annotations(self.viewer_current_path, pixmap)
        self._update_viewer_window_label()
        self._refresh_viewer_frame_controls()
        self.viewer_info_label.setText(
            f"{os.path.basename(self.viewer_current_path)}  | {pixmap.width()} × {pixmap.height()} px"
        )
        set_context = getattr(viewer_core, "set_context", None)
        if callable(set_context):
            set_context(
                getattr(self, "viewer_context_label", None),
                f"Aktif görüntü: {os.path.basename(self.viewer_current_path)} · Sıradaki adım: Görüntüyü Sığdır, W/L ayarla veya ölçüm aracı seç.",
            )
        if fit:
            self.fit_viewer_image()
        else:
            self._update_viewer_zoom_label()


    def _on_viewer_preload_failed(self, error: PreloadError):
        fit = bool(self._viewer_preload_pending.pop(error.request.request_id, False))
        self.statusBar().showMessage(
            f"DICOM ön yükleme başarısız; güvenli senkron fallback kullanılıyor: {error.message}",
            5000,
        )
        self._viewer_preload_enabled = False
        try:
            viewer_core.render_viewer_file(self, error.request.path, fit=fit, allow_preload=False)
        finally:
            self._viewer_preload_enabled = True


    def _on_viewer_preload_cancelled(self, cancelled):
        request_id = getattr(cancelled.request, "request_id", None)
        if request_id is not None:
            self._viewer_preload_pending.pop(request_id, None)


    def _schedule_viewer_neighbor_prefetch(self, current_path):
        """Queue at most two adjacent full-resolution frames after current render."""
        try:
            items = self._viewer_file_items()
        except Exception:
            return
        normalized = os.path.abspath(str(current_path))
        paths = [
            os.path.abspath(str(item.data(0, Qt.UserRole)))
            for item in items
            if item.data(0, Qt.UserRole)
        ]
        if normalized not in paths:
            return
        index = paths.index(normalized)
        neighbors = []
        if index > 0:
            neighbors.append(paths[index - 1])
        if index + 1 < len(paths):
            neighbors.append(paths[index + 1])
        for neighbor in neighbors[:2]:
            if not self._viewer_is_dicom(neighbor):
                continue
            frame = 0
            key = self._viewer_decoded_array_cache_key(neighbor, frame)
            if cache_get(self._viewer_decoded_array_cache, key) is not None:
                continue
            slot = f"prefetch:{neighbor}:{frame}"
            self._viewer_preload_controller.request(
                neighbor,
                frame,
                slot=slot,
                priority=10,
                reason="prefetch-neighbor",
            )


    def request_viewer_preload(self, path, *, fit=False, priority=0, reason="current"):
        request = self._viewer_preload_controller.request(
            path,
            self.viewer_frame_index,
            slot="viewer",
            priority=priority,
            reason=reason,
        )
        self._viewer_preload_pending[request.request_id] = bool(fit)
        self.viewer_info_label.setText("DICOM hazırlanıyor…")
        self.statusBar().showMessage("DICOM piksel verisi arka planda hazırlanıyor…", 3000)
        return request


    def show_selected_viewer_file(self):
        return viewer_core.show_selected_viewer_file(self)


    def render_viewer_file(self, path, fit=False):
        return viewer_core.render_viewer_file(self, path, fit)


    def schedule_viewer_render(self):
        """Coalesce rapid brightness/window-level mouse events."""
        self._viewer_render_timer.start()


    def _flush_viewer_render(self):
        if self.viewer_current_path:
            return viewer_core.render_viewer_file(self, self.viewer_current_path, fit=False)
        return None


    def _viewer_is_dicom(self, file_path):

        return viewer_core._viewer_is_dicom(self, file_path)


    def _viewer_frame_count_for_path(self, file_path):
        return viewer_core._viewer_frame_count_for_path(self, file_path)


    def _viewer_header_for_path(self, file_path):
        return viewer_core._viewer_header_for_path(self, file_path)


    def _clear_viewer_path_caches(self, file_path):
        return viewer_core.clear_viewer_path_caches(self, file_path)


    def _refresh_viewer_frame_controls(self):
        return viewer_actions._refresh_viewer_frame_controls(self)


    def set_viewer_frame(self, frame_index):
        return viewer_actions.set_viewer_frame(self, frame_index)


    def advance_viewer_frame(self):
        return viewer_actions.advance_viewer_frame(self)


    def toggle_viewer_cine(self):
        return viewer_actions.toggle_viewer_cine(self)


    def stop_viewer_cine(self):
        return viewer_actions.stop_viewer_cine(self)


    def rotate_viewer(self, degrees):
        return viewer_actions.rotate_viewer(self, degrees)


    def flip_viewer_horizontal(self):
        return viewer_actions.flip_viewer_horizontal(self)


    def flip_viewer_vertical(self):
        return viewer_actions.flip_viewer_vertical(self)


    def set_viewer_inverted(self, enabled):
        return viewer_actions.set_viewer_inverted(self, enabled)


    def reset_viewer_transform(self):
        return viewer_actions.reset_viewer_transform(self)


    def _refresh_viewer_after_transform(self, message):
        return viewer_actions._refresh_viewer_after_transform(self, message)


    def _viewer_pixel_spacing(self):
        return viewer_core._viewer_pixel_spacing(self)


    def show_viewer_dicom_info(self):
        return viewer_core.show_viewer_dicom_info(self)


    def _viewer_metadata(self, file_path):
        return viewer_core._viewer_metadata(self, file_path)


    def _clear_viewer_annotations(self):
        return viewer_core._clear_viewer_annotations(self)


    def _add_viewer_annotations(self, file_path, pixmap):
        return viewer_core._add_viewer_annotations(self, file_path, pixmap)


    def set_viewer_annotations_visible(self, visible):
        return viewer_actions.set_viewer_annotations_visible(self, visible)


    @staticmethod
    def _viewer_point_data(point):
        return [round(float(point.x()), 3), round(float(point.y()), 3)]

    @staticmethod
    def _viewer_point_from_data(data):
        return QPointF(float(data[0]), float(data[1]))

    def activate_viewer_markup(self, mode):
        return viewer_records.activate_viewer_markup(self, mode)


    def handle_viewer_markup_click(self, pos):
        return viewer_records.handle_viewer_markup_click(self, pos)


    def _draw_viewer_markup(self, record):
        return viewer_records._draw_viewer_markup(self, record)


    def _render_viewer_saved_items(self, path):
        return viewer_records._render_viewer_saved_items(self, path)


    def clear_viewer_markups(self):
        return viewer_records.clear_viewer_markups(self)


    def _draw_viewer_measurement(self, record):
        return viewer_records._draw_viewer_measurement(self, record)


    def apply_viewer_window_preset(self, preset):
        return viewer_actions.apply_viewer_window_preset(self, preset)


    def on_viewer_brightness_changed(self, value):
        return viewer_actions.on_viewer_brightness_changed(self, value)


    def adjust_viewer_window_level(self, dx, dy):
        return viewer_actions.adjust_viewer_window_level(self, dx, dy)


    def _update_viewer_window_label(self):
        return viewer_actions._update_viewer_window_label(self)


    def adjust_viewer_zoom(self, factor):
        return viewer_actions.adjust_viewer_zoom(self, factor)


    def _update_viewer_zoom_label(self):
        return viewer_actions._update_viewer_zoom_label(self)


    def fit_viewer_image(self):
        return viewer_actions.fit_viewer_image(self)


    def _refresh_viewer_cobb_button(self):
        return viewer_actions._refresh_viewer_cobb_button(self)


    def toggle_viewer_cobb_measurement(self):
        return viewer_actions.toggle_viewer_cobb_measurement(self)


    def handle_viewer_cobb_click(self, pos):
        return viewer_records.handle_viewer_cobb_click(self, pos)


    def save_viewer_cobb_measurement(
        self,
        *,
        side=None,
        upper_vertebra=None,
        lower_vertebra=None,
        curve_direction=None,
    ):
        return viewer_records.save_viewer_cobb_measurement(
            self,
            side=side,
            upper_vertebra=upper_vertebra,
            lower_vertebra=lower_vertebra,
            curve_direction=curve_direction,
        )


    def _refresh_viewer_length_button(self):
        return viewer_actions._refresh_viewer_length_button(self)


    def toggle_viewer_length_measurement(self):
        return viewer_actions.toggle_viewer_length_measurement(self)


    def handle_viewer_length_click(self, pos):
        return viewer_records.handle_viewer_length_click(self, pos)


    def clear_viewer_measurements(self, notify=True):
        return viewer_records.clear_viewer_measurements(self, notify)


    def clear_viewer_files(self):
        return viewer_records.clear_viewer_files(self)


    def _viewer_session_paths(self):
        return viewer_records._viewer_session_paths(self)


    def save_viewer_session(self):
        return viewer_records.save_viewer_session(self)


    def load_viewer_session(self):
        return viewer_records.load_viewer_session(self)


    def show_viewer_markup_summary(self):
        return viewer_records.show_viewer_markup_summary(self)


    def _viewer_export_image(self):
        return viewer_records._viewer_export_image(self)


    def export_viewer_snapshot(self, format_name):
        return viewer_records.export_viewer_snapshot(self, format_name)


    def init_workspace_tab(self):
        """Skolyoz Takip UI kurulumunu moduler dosyaya devreder."""
        build_workspace_tab(self, InteractiveGraphicsView)


    def _study_tree_file_items(self):
        return workspace_actions._study_tree_file_items(self)


    def _study_tree_find_or_add(self, parent, title):
        return workspace_actions._study_tree_find_or_add(self, parent, title)


    def _study_tree_group(self, metadata):
        return workspace_actions._study_tree_group(self, metadata)


    def _add_path_to_study_tree(self, path, model_item=None):
        return workspace_actions._add_path_to_study_tree(self, path, model_item)


    def _ensure_tracking_path(self, path):
        return workspace_actions._ensure_tracking_path(self, path)


    def _sync_study_tree_selection_from_model(self):
        return workspace_actions._sync_study_tree_selection_from_model(self)


    def _on_study_model_selection_changed(self):
        return workspace_actions._on_study_model_selection_changed(self)


    def _on_study_tree_selection_changed(self):
        return workspace_actions._on_study_tree_selection_changed(self)


    def show_study_file_context_menu(self, pos):
        return workspace_actions.show_study_file_context_menu(self, pos)


    def _activate_viewer_path_for_tracking(self, path):
        return workspace_actions._activate_viewer_path_for_tracking(self, path)


    def init_stitcher_tab(self):
        """Stitching UI kurulumunu modüler dosyaya devreder."""
        build_stitcher_tab(self, InteractiveGraphicsView)

    def open_preview_dialog(self, part_name):
        return stitch_io.open_preview_dialog(self, part_name)


    def open_viewer_selection_for_stitcher(self):
        return stitch_io.open_viewer_selection_for_stitcher(self)


    def handle_shortcut_move(self, dx, dy):
        return stitch_io.handle_shortcut_move(self, dx, dy)


    def _render_interactive_preview(self):
        return stitch_io._render_interactive_preview(self)


    def _render_full_after_move(self):
        return stitch_io._render_full_after_move(self)



    def _auto_estimate_offset(
        self,
        arr_top,
        arr_bottom,
        min_ratio=0.12,
        max_ratio=0.32,
        max_dx=50,
    ):
        cv = optional_cv2()
        return self.stitch_engine.auto_estimate_offset(
            arr_top,
            arr_bottom,
            min_ratio=min_ratio,
            max_ratio=max_ratio,
            max_dx=max_dx,
            cv=cv,
        )

    @staticmethod
    def _resize_gray_fast(gray, width, height):
        return StitchingEngine.resize_gray_fast(gray, width, height)

    def update_stitched_spine(self):
        return stitch_io.update_stitched_spine(self)



    @property
    def manual_stage_index(self):
        controller = getattr(self, "stitch_controller", None)
        if controller is not None:
            return controller.manual_stage_index
        return getattr(self, "_manual_stage_index_fallback", 0)

    @manual_stage_index.setter
    def manual_stage_index(self, value):
        controller = getattr(self, "stitch_controller", None)
        if controller is not None:
            controller.manual_stage_index = int(value)
        else:
            self._manual_stage_index_fallback = int(value)

    @property
    def manual_points(self):
        controller = getattr(self, "stitch_controller", None)
        if controller is not None:
            return controller.manual_points
        return getattr(self, "_manual_points_fallback", {})

    @manual_points.setter
    def manual_points(self, value):
        controller = getattr(self, "stitch_controller", None)
        if controller is not None:
            controller.manual_points = value
        else:
            self._manual_points_fallback = value

    @property
    def manual_junction_offsets(self):
        controller = getattr(self, "stitch_controller", None)
        if controller is not None:
            return controller.manual_junction_offsets
        return getattr(self, "_manual_junction_offsets_fallback", {})

    @manual_junction_offsets.setter
    def manual_junction_offsets(self, value):
        controller = getattr(self, "stitch_controller", None)
        if controller is not None:
            controller.manual_junction_offsets = value
        else:
            self._manual_junction_offsets_fallback = value

    def _manual_pairs(self):
        return stitch_ui_actions._manual_pairs(self)


    def toggle_manual_point_mode(self):
        return stitch_ui_actions.toggle_manual_point_mode(self)


    def render_manual_pick_view(self):
        return stitch_ui_actions.render_manual_pick_view(self)


    def clear_manual_points(self):
        return stitch_ui_actions.clear_manual_points(self)


    def handle_manual_point_click(self, scene_pos):
        return stitch_ui_actions.handle_manual_point_click(self, scene_pos)


    def advance_manual_stage(self):
        return stitch_ui_actions.advance_manual_stage(self)


    def set_shift_step(self, val_str):
        return stitch_ui_actions.set_shift_step(self, val_str)


    def _refresh_stitch_part_buttons(self):
        return stitch_ui_actions._refresh_stitch_part_buttons(self)


    def select_stitch_part(self, part_key):
        return stitch_ui_actions.select_stitch_part(self, part_key)


    def _update_move_offset_label(self):
        return stitch_ui_actions._update_move_offset_label(self)


    def adjust_stitch_offset(self, dx, dy):
        return stitch_ui_actions.adjust_stitch_offset(self, dx, dy)


    def reset_stitch_offset(self):
        return stitch_ui_actions.reset_stitch_offset(self)


    def on_stitch_zoom_changed(self, value):
        return stitch_ui_actions.on_stitch_zoom_changed(self, value)



    def show_stitch_part_context_menu(self, part_name, button, pos):
        return stitch_ui_actions.show_stitch_part_context_menu(self, part_name, button, pos)


    def remove_stitch_part(self, part_name):
        return stitch_ui_actions.remove_stitch_part(self, part_name)


    def trigger_stitch_action(self):
        return stitch_ui_actions.trigger_stitch_action(self)


    def _clear_layout_recursive(self, layout):
        return stitch_ui_actions._clear_layout_recursive(self, layout)


    def on_confirm_finish_clicked(self):
        return stitch_ui_actions.on_confirm_finish_clicked(self)


    def _on_final_brightness_changed(self, val):
        return stitch_ui_actions._on_final_brightness_changed(self, val)


    def _on_final_contrast_changed(self, val):
        return stitch_ui_actions._on_final_contrast_changed(self, val)


    def _reset_final_image_adjustment(self):
        return stitch_ui_actions._reset_final_image_adjustment(self)


    def _apply_final_image_adjustment(self):
        return stitch_io._apply_final_image_adjustment(self)


    def _on_cobb_checkbox_toggled(self, checked):
        return stitch_io._on_cobb_checkbox_toggled(self, checked)


    def save_final_result(self):
        return stitch_io.save_final_result(self)


    def _stitch_source_patient_info(self):
        return stitch_io._stitch_source_patient_info(self)


    def _offer_stitched_result_to_patient_history(self, dicom_path):
        return stitch_io._offer_stitched_result_to_patient_history(self, dicom_path)


    def _save_as_dicom(self, gray_arr, path):
        return stitch_io._save_as_dicom(self, gray_arr, path)


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
        return StitchingEngine.match_histogram_linear(arr_src, arr_ref, y_src_slice, y_ref_slice)

    @staticmethod
    def _to_gray(arr_bgra):
        return StitchingEngine.to_gray(arr_bgra)

    @staticmethod
    def _tile_normalize(gray, tile=24):
        return StitchingEngine.tile_normalize(gray, tile)

    @staticmethod
    def _sobel_magnitude(gray):
        return StitchingEngine.sobel_magnitude(gray)

    @staticmethod
    def _phase_correlate(img_a, img_b):
        return StitchingEngine.phase_correlate(img_a, img_b)

    @staticmethod
    def _rotate_array(arr, angle_deg, fill=0):
        return StitchingEngine.rotate_array(arr, angle_deg, fill)

    @staticmethod
    def _gray_to_bgra(gray, alpha=None):
        return StitchingEngine.gray_to_bgra(gray, alpha)

    def _get_stitch_mask(self, img_h, img_w, top_overlap, bottom_overlap):
        return self.stitch_engine.get_stitch_mask(img_h, img_w, top_overlap, bottom_overlap)

    @staticmethod
    def _apply_checker_bw(arr, y_start, y_end, cell=20, intensity=0.32):
        return StitchingEngine.apply_checker_bw(arr, y_start, y_end, cell, intensity)

    def load_dicoms(self):
        return stitch_io.load_dicoms(self)


    def _default_window(self, file_path):
        return stitch_io._default_window(self, file_path)


    def get_image_pixmap(self, file_path):
        return stitch_io.get_image_pixmap(self, file_path)


    def _selected_window_paths(self):
        return workspace_actions._selected_window_paths(self)


    def apply_window_preset(self, preset):
        return workspace_actions.apply_window_preset(self, preset)


    def reset_window_level(self):
        return workspace_actions.reset_window_level(self)


    def adjust_window_level(self, side, dx, dy):
        return workspace_actions.adjust_window_level(self, side, dx, dy)


    def schedule_workspace_render(self):
        """Coalesce rapid slider changes into one follow-up render."""
        self._workspace_render_timer.start()


    def _flush_workspace_render(self):
        return workspace_actions.update_viewers(self)


    def update_viewers(self):
        return workspace_actions.update_viewers(self)


    def _update_overlay_label(self):

        return workspace_actions._update_overlay_label(self)


    def move_overlay(self, dx, dy):
        return workspace_actions.move_overlay(self, dx, dy)


    def _sync_overlay_sliders(self):
        return workspace_actions._sync_overlay_sliders(self)


    def on_overlay_x_changed(self, value):
        return workspace_actions.on_overlay_x_changed(self, value)


    def on_overlay_y_changed(self, value):
        return workspace_actions.on_overlay_y_changed(self, value)


    def on_overlay_zoom_changed(self, value):
        return workspace_actions.on_overlay_zoom_changed(self, value)


    def on_overlay_opacity_changed(self, value):
        return workspace_actions.on_overlay_opacity_changed(self, value)


    def reset_overlay_adjustment(self):
        return workspace_actions.reset_overlay_adjustment(self)


    def set_side_by_side_mode(self):
        return workspace_actions.set_side_by_side_mode(self)


    def set_overlay_mode(self):
        return workspace_actions.set_overlay_mode(self)


    def toggle_cobb_measurement(self):
        return workspace_actions.toggle_cobb_measurement(self)


    def handle_cobb_click(self, side, pos):
        return workspace_actions.handle_cobb_click(self, side, pos)


    def clear_cobb_measurement(self):
        return workspace_actions.clear_cobb_measurement(self)



if __name__ == "__main__":
    from modular_app.run_modular import main as start_application
    start_application(ScoliosisFollowUpApp)


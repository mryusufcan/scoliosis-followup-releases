"""Shared UI clarity primitives for the desktop workflow."""
from __future__ import annotations

from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy, QWidget


ROLE_PROPERTIES = {
    "primary": "uiPrimaryAction",
    "secondary": "uiSecondaryAction",
    "measurement": "uiMeasurementAction",
    "danger": "uiDangerAction",
    "quiet": "uiQuietAction",
}


def configure_action(
    widget: QWidget,
    *,
    label: str | None = None,
    role: str = "secondary",
    tooltip: str = "",
    shortcut: str = "",
    object_name: str = "",
) -> QWidget:
    """Apply consistent naming, tooltip and visual-role metadata to an action."""
    if label:
        widget.setAccessibleName(label)
    if object_name:
        widget.setObjectName(object_name)
    property_name = ROLE_PROPERTIES.get(role, ROLE_PROPERTIES["secondary"])
    widget.setProperty(property_name, True)
    if tooltip:
        suffix = f"  |  Kısayol: {shortcut}" if shortcut else ""
        widget.setToolTip(f"{tooltip}{suffix}")
        widget.setAccessibleDescription(tooltip)
    if hasattr(widget, "setMinimumHeight"):
        compact_properties = (
            "uiCompact",
            "uiPrimary",
            "trackingCompact",
            "trackingPrimary",
            "stitchCompact",
        )
        is_compact = any(widget.property(name) is True for name in compact_properties)
        minimum_height = 22 if is_compact else 30
        widget.setMinimumHeight(max(minimum_height, widget.minimumHeight()))
    polish(widget)
    return widget


def polish(widget: QWidget) -> None:
    """Refresh dynamic QSS properties without replacing local stylesheets."""
    style = widget.style()
    style.unpolish(widget)
    style.polish(widget)
    widget.update()


def create_context_banner(
    title: str,
    message: str,
    *,
    object_name: str = "workflowContextBanner",
    parent=None,
) -> tuple[QFrame, QLabel]:
    """Create a compact title/message strip that keeps the active context visible."""
    frame = QFrame(parent)
    frame.setObjectName(object_name)
    frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    layout = QHBoxLayout(frame)
    layout.setContentsMargins(10, 6, 10, 6)
    layout.setSpacing(10)

    title_label = QLabel(title.upper(), frame)
    title_label.setObjectName("workflowContextTitle")
    title_label.setProperty("contextTone", "accent")
    title_label.setAccessibleName(f"İş akışı: {title}")
    layout.addWidget(title_label)

    message_label = QLabel(message, frame)
    message_label.setObjectName("workflowContextMessage")
    message_label.setWordWrap(False)
    message_label.setTextInteractionFlags(message_label.textInteractionFlags())
    message_label.setAccessibleName("Sonraki adım bilgisi")
    layout.addWidget(message_label, 1)
    return frame, message_label


def set_context(message_label: QLabel | None, text: str) -> None:
    if message_label is None:
        return
    message_label.setText(str(text or ""))
    message_label.setToolTip(str(text or ""))

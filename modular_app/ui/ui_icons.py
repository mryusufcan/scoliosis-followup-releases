from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap, QPolygonF


_ICON_CACHE = {}
_CURRENT_ICON_COLOR = "#D7E0E6"


def set_icon_theme(theme: str) -> None:
    """Set the default monochrome icon color and clear stale cached icons."""
    global _CURRENT_ICON_COLOR
    _CURRENT_ICON_COLOR = "#334155" if str(theme).casefold() == "light" else "#D7E0E6"
    _ICON_CACHE.clear()


def make_icon(name: str, size: int = 20, color: str | None = None) -> QIcon:

    """Small monochrome workstation-style icon drawn with Qt; no font/emoji dependency."""
    s = max(16, int(size))
    color = color or _CURRENT_ICON_COLOR
    cache_key = ((name or "").lower(), s, str(color))
    cached = _ICON_CACHE.get(cache_key)
    if cached is not None:
        return cached
    pm = QPixmap(s, s)
    pm.fill(Qt.transparent)

    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)
    c = QColor(color)
    pen = QPen(c, max(1.4, s / 12.0), Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)

    u = s / 20.0
    def R(x, y, w, h):
        return QRectF(x*u, y*u, w*u, h*u)
    def L(x1, y1, x2, y2):
        p.drawLine(QPointF(x1*u, y1*u), QPointF(x2*u, y2*u))

    name = (name or "").lower()

    if name in {"folder", "open"}:
        p.drawRoundedRect(R(2.5, 5.5, 15, 11), 1.4*u, 1.4*u)
        p.drawLine(QPointF(3.2*u, 5.5*u), QPointF(8*u, 5.5*u))
        p.drawLine(QPointF(5*u, 3.5*u), QPointF(9*u, 3.5*u))
        L(9, 3.5, 11, 5.5)

    elif name in {"viewer", "image"}:
        p.drawRoundedRect(R(3, 3, 14, 14), 1.6*u, 1.6*u)
        p.drawEllipse(R(6, 6, 2.5, 2.5))
        p.drawPolyline(QPolygonF([
            QPointF(4.5*u, 14.5*u), QPointF(8.5*u, 10.5*u),
            QPointF(11*u, 13*u), QPointF(13*u, 11*u), QPointF(16*u, 14.5*u)
        ]))

    elif name in {"stitch", "compare"}:
        p.drawRoundedRect(R(2.5, 4, 8, 12), 1*u, 1*u)
        p.drawRoundedRect(R(9.5, 4, 8, 12), 1*u, 1*u)
        L(8.5, 8, 11.5, 8)
        L(8.5, 12, 11.5, 12)

    elif name in {"track", "chart"}:
        L(3, 16, 3, 4)
        L(3, 16, 17, 16)
        p.drawPolyline(QPolygonF([
            QPointF(5*u, 13*u), QPointF(9*u, 10*u),
            QPointF(12*u, 11*u), QPointF(16*u, 6*u)
        ]))
        for x,y in [(5,13),(9,10),(12,11),(16,6)]:
            p.drawEllipse(QPointF(x*u,y*u), 1.0*u, 1.0*u)

    elif name in {"cobb", "measure", "angle"}:
        L(3, 15, 9, 9)
        L(9, 9, 17, 7)
        p.drawArc(R(7, 8, 6, 6), 25*16, 75*16)

    elif name in {"distance"}:
        L(3, 10, 17, 10)
        L(3, 10, 6, 7)
        L(3, 10, 6, 13)
        L(17, 10, 14, 7)
        L(17, 10, 14, 13)

    elif name in {"fit"}:
        L(3, 8, 3, 3); L(3, 3, 8, 3)
        L(12, 3, 17, 3); L(17, 3, 17, 8)
        L(3, 12, 3, 17); L(3, 17, 8, 17)
        L(12, 17, 17, 17); L(17, 17, 17, 12)

    elif name in {"undo", "back"}:
        p.drawArc(R(4, 5, 12, 10), 35*16, 250*16)
        L(5, 6, 2.5, 8.5); L(2.5, 8.5, 6, 9.5)

    elif name in {"redo", "forward"}:
        p.drawArc(R(4, 5, 12, 10), -105*16, 250*16)
        L(15, 6, 17.5, 8.5); L(17.5, 8.5, 14, 9.5)

    elif name in {"trash", "clear"}:
        p.drawRoundedRect(R(6, 6, 8, 10), 0.8*u, 0.8*u)
        L(5, 5, 15, 5); L(8, 3.5, 12, 3.5)
        L(8.5, 8, 8.5, 14); L(11.5, 8, 11.5, 14)

    elif name in {"notes", "markup"}:
        p.drawRoundedRect(R(4, 3, 12, 14), 1*u, 1*u)
        L(7, 7, 13, 7); L(7, 10, 13, 10); L(7, 13, 11, 13)

    elif name in {"align"}:
        L(4, 5, 16, 5); L(7, 10, 13, 10); L(5, 15, 15, 15)
        L(10, 2.5, 10, 17.5)

    elif name in {"reset"}:
        p.drawArc(R(4, 4, 12, 12), 25*16, 285*16)
        L(4.5, 6, 2.5, 4); L(2.5, 4, 6, 3.5)

    elif name in {"dicom"}:
        p.drawRoundedRect(R(4, 2.5, 12, 15), 1*u, 1*u)
        L(7, 6, 13, 6); L(7, 9, 13, 9); L(7, 12, 13, 12)

    elif name in {"tools"}:
        p.drawEllipse(R(7, 7, 6, 6))
        for a,b,c1,d in [(10,2,10,5),(10,15,10,18),(2,10,5,10),(15,10,18,10)]:
            L(a,b,c1,d)

    elif name in {"export", "save"}:
        p.drawRoundedRect(R(4, 8, 12, 9), 1*u, 1*u)
        L(10, 3, 10, 12)
        L(10, 3, 7, 6); L(10, 3, 13, 6)

    elif name in {"session"}:
        p.drawRoundedRect(R(3, 3, 14, 14), 1*u, 1*u)
        p.drawRoundedRect(R(6, 4, 8, 5), 0.5*u, 0.5*u)
        p.drawRoundedRect(R(6, 11, 8, 4), 0.5*u, 0.5*u)

    elif name in {"up", "down", "left", "right"}:
        if name in {"up", "down"}:
            x = 10
            if name == "up":
                L(x, 16, x, 4)
                L(x, 4, 6, 8); L(x, 4, 14, 8)
            else:
                L(x, 4, x, 16)
                L(x, 16, 6, 12); L(x, 16, 14, 12)
        else:
            y = 10
            if name == "left":
                L(16, y, 4, y)
                L(4, y, 8, 6); L(4, y, 8, 14)
            else:
                L(4, y, 16, y)
                L(16, y, 12, 6); L(16, y, 12, 14)

    elif name in {"patient"}:
        p.drawEllipse(R(7, 3, 6, 6))
        p.drawArc(R(4, 9, 12, 8), 0, 180*16)

    elif name in {"data", "database"}:
        p.drawEllipse(R(4, 3, 12, 4))
        p.drawArc(R(4, 6, 12, 4), 180*16, 180*16)
        p.drawArc(R(4, 10, 12, 4), 180*16, 180*16)
        L(4,5,4,13); L(16,5,16,13)

    elif name in {"report"}:
        p.drawRoundedRect(R(4, 2.5, 12, 15), 1*u, 1*u)
        L(7, 7, 13, 7); L(7, 10, 13, 10); L(7, 13, 11, 13)

    elif name in {"experiment"}:
        L(8,3,8,7); L(12,3,12,7)
        p.drawPolyline(QPolygonF([
            QPointF(8*u,7*u), QPointF(5*u,15*u),
            QPointF(15*u,15*u), QPointF(12*u,7*u)
        ]))
        L(6.5,12,13.5,12)

    elif name in {"help"}:
        p.drawEllipse(R(3,3,14,14))
        p.drawArc(R(7,5,6,6), 20*16, 190*16)
        L(10,10,10,12)
        p.drawEllipse(QPointF(10*u,14.5*u), 0.7*u, 0.7*u)

    else:
        p.drawRoundedRect(R(4,4,12,12), 2*u, 2*u)

    p.end()
    icon = QIcon(pm)
    _ICON_CACHE[cache_key] = icon
    return icon

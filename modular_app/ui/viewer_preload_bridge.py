"""Minimal GUI-thread bridge for integrating DicomPreloadController.

The bridge is intentionally framework-light: the real application supplies its
existing pixmap cache, cache-key builder, scene update callback and status bar.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QPixmap

from dicom_preload_worker import (
    DicomPreloadController,
    PreloadError,
    PreloadRequest,
    PreloadResult,
    array_to_grayscale_qimage,
)


@dataclass(frozen=True)
class PendingDisplay:
    request: PreloadRequest
    cache_key: Any
    slot: str


class ViewerPreloadBridge(QObject):
    """Connect worker output to the existing viewer cache and scene.

    `cache_get`, `cache_put`, and `apply_pixmap` are called on the GUI thread.
    The worker never receives any Qt GUI object.
    """

    ready = Signal(object)
    cache_hit = Signal(object)
    failed = Signal(object)
    status = Signal(str)

    def __init__(
        self,
        *,
        cache_get: Callable[[Any], QPixmap | None],
        cache_put: Callable[[Any, QPixmap], None],
        apply_pixmap: Callable[[PreloadResult, QPixmap], None],
        build_cache_key: Callable[[str, int], Any],
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.cache_get = cache_get
        self.cache_put = cache_put
        self.apply_pixmap = apply_pixmap
        self.build_cache_key = build_cache_key
        self.controller = DicomPreloadController(parent=self)
        self._pending: dict[int, PendingDisplay] = {}
        self.controller.image_ready.connect(self._on_ready)
        self.controller.decode_failed.connect(self._on_failed)
        self.controller.decode_cancelled.connect(self._on_cancelled)

    def request(self, path: str, frame_index: int = 0, *, slot: str = "viewer") -> PreloadRequest | None:
        cache_key = self.build_cache_key(str(path), int(frame_index))
        cached = self.cache_get(cache_key)
        if cached is not None and not cached.isNull():
            self.cache_hit.emit((cache_key, cached))
            self.status.emit("Görüntü cache'den hazırlandı.")
            return None

        request = self.controller.request(path, frame_index, slot=slot)
        self._pending[request.request_id] = PendingDisplay(request, cache_key, slot)
        self.status.emit("DICOM piksel verisi hazırlanıyor…")
        return request

    def cancel(self, *, slot: str = "viewer") -> None:
        self.controller.cancel(slot=slot)
        self.status.emit("DICOM hazırlama isteği iptal edildi.")

    def _on_ready(self, result: PreloadResult) -> None:
        pending = self._pending.pop(result.request.request_id, None)
        if pending is None:
            return
        # This slot runs in the receiver's GUI thread. QImage/QPixmap creation is safe here.
        qimage = array_to_grayscale_qimage(result.decoded.array)
        pixmap = QPixmap.fromImage(qimage)
        self.cache_put(pending.cache_key, pixmap)
        self.apply_pixmap(result, pixmap)
        self.ready.emit(result)
        self.status.emit("DICOM görüntüsü hazır.")

    def _on_failed(self, error: PreloadError) -> None:
        self._pending.pop(error.request.request_id, None)
        self.failed.emit(error)
        self.status.emit(f"DICOM açılamadı: {error.message}")

    def _on_cancelled(self, cancelled: object) -> None:
        request_id = getattr(getattr(cancelled, "request", None), "request_id", None)
        if request_id is not None:
            self._pending.pop(int(request_id), None)

    def shutdown(self) -> None:
        self.controller.shutdown()
        self._pending.clear()


__all__ = ["PendingDisplay", "ViewerPreloadBridge"]

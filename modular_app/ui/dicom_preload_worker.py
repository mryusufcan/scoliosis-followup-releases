"""Qt-safe DICOM decode/preload reference implementation.

This module deliberately keeps all QImage/QPixmap creation on the GUI thread.
The worker only performs pydicom I/O and NumPy array preparation.
It is a reference scaffold for integration into the existing viewer/cache layer;
it does not modify DICOM pixels or metadata on disk.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from threading import Event
from typing import Any, Callable, Mapping

import numpy as np
import pydicom
from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot
from PySide6.QtGui import QImage


class DecodeCancelled(Exception):
    """Raised internally when a queued decode is superseded or cancelled."""


@dataclass(frozen=True)
class DecodeLimits:
    """Preflight limits to prevent unbounded multi-frame allocations."""

    max_source_bytes: int = 768 * 1024 * 1024
    max_frame_bytes: int = 128 * 1024 * 1024


@dataclass(frozen=True)
class DecodedImage:
    """Decoded NumPy frame plus non-PHI render metadata.

    The array is a private, contiguous copy. The source Dataset is never
    returned or mutated by this module.
    """

    path: str
    frame_index: int
    array: np.ndarray
    rows: int
    columns: int
    frame_count: int
    transfer_syntax: str
    render_context: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PreloadRequest:
    """Stable request identity used to reject stale worker results."""

    request_id: int
    path: str
    frame_index: int = 0


@dataclass(frozen=True)
class PreloadResult:
    request: PreloadRequest
    decoded: DecodedImage


@dataclass(frozen=True)
class PreloadError:
    request: PreloadRequest
    message: str
    exception_type: str


@dataclass(frozen=True)
class PreloadCancelled:
    request: PreloadRequest


class _WorkerSignals(QObject):
    finished = Signal(object)
    failed = Signal(object)
    cancelled = Signal(object)


class DicomDecodeWorker(QRunnable):
    """QRunnable that never creates Qt GUI image objects."""

    def __init__(
        self,
        request: PreloadRequest,
        cancel_event: Event,
        decoder: Callable[[str, int, Event], DecodedImage] | None = None,
        limits: DecodeLimits | None = None,
    ) -> None:
        super().__init__()
        self.request = request
        self.cancel_event = cancel_event
        self.signals = _WorkerSignals()
        self._decoder = decoder
        self.limits = limits or DecodeLimits()
        self.setAutoDelete(True)

    @Slot()
    def run(self) -> None:
        try:
            if self.cancel_event.is_set():
                self.signals.cancelled.emit(PreloadCancelled(self.request))
                return
            if self._decoder is None:
                decoded = decode_dicom_frame(
                    self.request.path,
                    self.request.frame_index,
                    self.cancel_event,
                    limits=self.limits,
                )
            else:
                decoded = self._decoder(
                    self.request.path,
                    self.request.frame_index,
                    self.cancel_event,
                )
            if self.cancel_event.is_set():
                self.signals.cancelled.emit(PreloadCancelled(self.request))
                return
            self.signals.finished.emit(PreloadResult(self.request, decoded))
        except DecodeCancelled:
            self.signals.cancelled.emit(PreloadCancelled(self.request))
        except Exception as exc:  # worker boundary: surface, never crash GUI
            self.signals.failed.emit(
                PreloadError(
                    request=self.request,
                    message=str(exc) or exc.__class__.__name__,
                    exception_type=exc.__class__.__name__,
                )
            )


def decode_dicom_frame(
    path: str,
    frame_index: int,
    cancel_event: Event,
    *,
    limits: DecodeLimits | None = None,
) -> DecodedImage:
    """Read one DICOM frame into a private NumPy array.

    No Pixel Data or metadata is written back. The array is copied before it
    crosses the worker boundary so the Dataset can be released independently.
    """
    normalized = str(Path(path).resolve())
    _check_cancel(cancel_event)
    dataset = pydicom.dcmread(normalized)
    _check_cancel(cancel_event)
    decode_limits = limits or DecodeLimits()
    _check_estimated_memory(dataset, decode_limits)

    source = dataset.pixel_array
    _check_cancel(cancel_event)
    if not isinstance(source, np.ndarray) or source.ndim not in (2, 3):
        raise ValueError("DICOM piksel matrisi 2B veya çok kareli 3B olmalıdır.")

    frame_count = 1
    if source.ndim == 3:
        samples = int(getattr(dataset, "SamplesPerPixel", 1) or 1)
        if samples > 1 and source.shape[-1] in (3, 4):
            # The viewer's grayscale pipeline needs an explicit channel policy.
            source = source[..., 0]
        else:
            frame_count = int(source.shape[0])
            if not 0 <= int(frame_index) < frame_count:
                raise IndexError(f"Kare indeksi aralık dışında: {frame_index}")
            source = source[int(frame_index)]

    if source.ndim != 2:
        raise ValueError("Bu taslak yalnızca gri tonlu 2B kareyi destekler.")

    private_array = np.ascontiguousarray(np.array(source, copy=True))
    transfer = getattr(getattr(dataset, "file_meta", None), "TransferSyntaxUID", "")
    render_context = _render_context(dataset)
    return DecodedImage(
        path=normalized,
        frame_index=int(frame_index),
        array=private_array,
        rows=int(private_array.shape[0]),
        columns=int(private_array.shape[1]),
        frame_count=frame_count,
        transfer_syntax=str(transfer or ""),
        render_context=render_context,
    )


def _estimate_source_bytes(dataset: Any) -> int:
    rows = int(getattr(dataset, "Rows", 0) or 0)
    columns = int(getattr(dataset, "Columns", 0) or 0)
    frames = int(getattr(dataset, "NumberOfFrames", 1) or 1)
    samples = int(getattr(dataset, "SamplesPerPixel", 1) or 1)
    bits = int(getattr(dataset, "BitsAllocated", 8) or 8)
    itemsize = max(1, (bits + 7) // 8)
    return max(0, rows * columns * frames * samples * itemsize)


def _check_estimated_memory(dataset: Any, limits: DecodeLimits) -> None:
    estimated = _estimate_source_bytes(dataset)
    frame_estimate = estimated // max(1, int(getattr(dataset, "NumberOfFrames", 1) or 1))
    if estimated > limits.max_source_bytes:
        raise MemoryError(
            f"DICOM piksel yükü sınırı aşıyor: {estimated} > {limits.max_source_bytes} bayt"
        )
    if frame_estimate > limits.max_frame_bytes:
        raise MemoryError(
            f"DICOM kare belleği sınırı aşıyor: {frame_estimate} > {limits.max_frame_bytes} bayt"
        )


def _render_context(dataset: Any) -> dict[str, Any]:
    """Copy display metadata without passing the Dataset across threads."""
    names = (
        "PhotometricInterpretation",
        "SamplesPerPixel",
        "BitsAllocated",
        "BitsStored",
        "HighBit",
        "PixelRepresentation",
        "RescaleSlope",
        "RescaleIntercept",
        "WindowCenter",
        "WindowWidth",
        "VOILUTFunction",
        "PixelSpacing",
        "NumberOfFrames",
    )
    numeric_scalar = {
        "SamplesPerPixel", "BitsAllocated", "BitsStored", "HighBit",
        "PixelRepresentation", "NumberOfFrames",
    }
    numeric_float = {"RescaleSlope", "RescaleIntercept"}
    context: dict[str, Any] = {}
    for name in names:
        value = getattr(dataset, name, None)
        if value is None:
            continue
        if name in {"WindowCenter", "WindowWidth"}:
            if hasattr(value, "__iter__") and not isinstance(value, (str, bytes)):
                value = list(value)[0] if value else None
            if value is not None:
                context[name] = float(value)
        elif name in numeric_float:
            context[name] = float(value)
        elif name in numeric_scalar:
            context[name] = int(value)
        elif name == "PixelSpacing":
            context[name] = tuple(float(item) for item in value)
        else:
            context[name] = str(value)
    return context


def _check_cancel(cancel_event: Event) -> None:
    if cancel_event.is_set():
        raise DecodeCancelled()


def array_to_grayscale_qimage(array: np.ndarray) -> QImage:
    """Create a detached QImage on the GUI thread from a decoded array."""
    if not isinstance(array, np.ndarray) or array.ndim != 2:
        raise ValueError("QImage dönüşümü için 2B NumPy array gereklidir.")
    if array.size == 0:
        raise ValueError("Boş NumPy array QImage'e dönüştürülemez.")

    if array.dtype != np.uint8:
        numeric = array.astype(np.float32, copy=False)
        low = float(np.nanmin(numeric))
        high = float(np.nanmax(numeric))
        if not np.isfinite(low) or not np.isfinite(high):
            raise ValueError("Piksel aralığı sonlu değil.")
        if high <= low:
            display = np.zeros(array.shape, dtype=np.uint8)
        else:
            display = np.clip((numeric - low) * 255.0 / (high - low), 0, 255).astype(np.uint8)
    else:
        display = np.ascontiguousarray(array)

    height, width = display.shape
    # copy() detaches QImage from NumPy memory before the temporary array dies.
    return QImage(
        display.data,
        int(width),
        int(height),
        int(display.strides[0]),
        QImage.Format.Format_Grayscale8,
    ).copy()


class DicomPreloadController(QObject):
    """Small controller for one active request per viewer slot.

    `image_ready` is emitted only for the latest request. The GUI callback can
    convert the decoded array to QImage/QPixmap and then update the scene/cache.
    """

    image_ready = Signal(object)
    decode_failed = Signal(object)
    decode_cancelled = Signal(object)
    busy_changed = Signal(bool)

    def __init__(
        self,
        pool: QThreadPool | None = None,
        parent: QObject | None = None,
        decoder: Callable[[str, int, Event], DecodedImage] | None = None,
        limits: DecodeLimits | None = None,
    ) -> None:
        super().__init__(parent)
        self.pool = pool or QThreadPool.globalInstance()
        self.decoder = decoder
        self.limits = limits or DecodeLimits()
        self._next_id = 0
        self._active: dict[int, Event] = {}
        self._workers: dict[int, DicomDecodeWorker] = {}
        self._latest_by_slot: dict[str, int] = {}

    def request(self, path: str, frame_index: int = 0, *, slot: str = "viewer") -> PreloadRequest:
        normalized = str(Path(path).resolve())
        previous_id = self._latest_by_slot.get(slot)
        if previous_id is not None:
            previous_event = self._active.get(previous_id)
            if previous_event is not None:
                previous_event.set()

        self._next_id += 1
        request = PreloadRequest(self._next_id, normalized, int(frame_index))
        cancel_event = Event()
        self._active[request.request_id] = cancel_event
        self._latest_by_slot[slot] = request.request_id
        self.busy_changed.emit(True)

        worker = DicomDecodeWorker(
            request,
            cancel_event,
            decoder=self.decoder,
            limits=self.limits,
        )
        # Keep the worker/signals alive until the queued GUI callback runs.
        self._workers[request.request_id] = worker
        worker.signals.finished.connect(lambda result, s=slot: self._on_finished(s, result))
        worker.signals.failed.connect(lambda error, s=slot: self._on_failed(s, error))
        worker.signals.cancelled.connect(lambda cancelled, s=slot: self._on_cancelled(s, cancelled))
        self.pool.start(worker)
        return request

    def cancel(self, *, slot: str = "viewer") -> None:
        request_id = self._latest_by_slot.get(slot)
        if request_id is not None and request_id in self._active:
            self._active[request_id].set()

    def _on_finished(self, slot: str, result: PreloadResult) -> None:
        if not self._is_latest(slot, result.request.request_id):
            self._discard(result.request.request_id)
            return
        self._discard(result.request.request_id)
        self.image_ready.emit(result)

    def _on_failed(self, slot: str, error: PreloadError) -> None:
        if not self._is_latest(slot, error.request.request_id):
            self._discard(error.request.request_id)
            return
        self._discard(error.request.request_id)
        self.decode_failed.emit(error)

    def _on_cancelled(self, slot: str, cancelled: PreloadCancelled) -> None:
        self._discard(cancelled.request.request_id)
        if self._is_latest(slot, cancelled.request.request_id):
            self.decode_cancelled.emit(cancelled)

    def _is_latest(self, slot: str, request_id: int) -> bool:
        return self._latest_by_slot.get(slot) == request_id

    def _discard(self, request_id: int) -> None:
        self._active.pop(request_id, None)
        self._workers.pop(request_id, None)
        self.busy_changed.emit(bool(self._active))

    def shutdown(self) -> None:
        for event in self._active.values():
            event.set()
        self._active.clear()
        self._workers.clear()
        self._latest_by_slot.clear()


__all__ = [
    "DecodeLimits",
    "DecodedImage",
    "DecodeCancelled",
    "DicomDecodeWorker",
    "DicomPreloadController",
    "PreloadCancelled",
    "PreloadError",
    "PreloadRequest",
    "PreloadResult",
    "array_to_grayscale_qimage",
    "decode_dicom_frame",
]

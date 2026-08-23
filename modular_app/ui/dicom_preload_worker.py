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
import heapq
import os

import pydicom
from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot
from PySide6.QtGui import QImage

from modular_app.ui.dicom_codec import decode_pixel_array


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
    """Immutable identity and scheduling metadata for one decode request."""

    request_id: int
    path: str
    frame_index: int = 0
    priority: int = 0
    generation: int = 0
    reason: str = "current"
    source_signature: tuple[int, int] = (0, 0)


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
    header = pydicom.dcmread(normalized, stop_before_pixels=True)
    _check_cancel(cancel_event)
    decode_limits = limits or DecodeLimits()
    _check_estimated_memory(header, decode_limits)
    frame_count = max(1, int(getattr(header, "NumberOfFrames", 1) or 1))
    if not 0 <= int(frame_index) < frame_count:
        raise IndexError(f"Kare indeksi aralık dışında: {frame_index}")

    # pydicom's path-based API can request one frame without retaining a full
    # Dataset with Pixel Data. This keeps multi-frame lazy navigation bounded.
    transfer = str(getattr(getattr(header, "file_meta", None), "TransferSyntaxUID", "") or "")
    source = decode_pixel_array(normalized, index=int(frame_index), transfer_syntax_uid=transfer)
    _check_cancel(cancel_event)
    if not isinstance(source, np.ndarray) or source.ndim not in (2, 3):
        raise ValueError("DICOM piksel matrisi 2B veya çok kareli 3B olmalıdır.")

    samples = int(getattr(header, "SamplesPerPixel", 1) or 1)
    if source.ndim == 3 and samples > 1 and source.shape[-1] in (3, 4):
        # The viewer's grayscale pipeline needs an explicit channel policy.
        source = source[..., 0]
    if source.ndim != 2:
        raise ValueError("Bu taslak yalnızca gri tonlu 2B kareyi destekler.")

    private_array = np.ascontiguousarray(np.array(source, copy=True))
    render_context = _render_context(header)
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
    """Priority scheduler for cancellable, one-at-a-time DICOM decodes.

    The controller owns queue ordering and cancellation while the supplied
    ``QThreadPool`` owns execution. A single active decode is intentional for
    large compressed frames; the queue may contain current and low-priority
    prefetch requests without allowing prefetch to block a newer selection.
    Qt GUI objects are still created only by the GUI callback.
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
        *,
        max_queue: int = 3,
    ) -> None:
        super().__init__(parent)
        self.pool = pool or QThreadPool.globalInstance()
        self.decoder = decoder
        self.limits = limits or DecodeLimits()
        self.max_queue = max(1, int(max_queue))
        self._next_id = 0
        self._sequence = 0
        self._active_request_id: int | None = None
        self._active: dict[int, Event] = {}
        self._workers: dict[int, DicomDecodeWorker] = {}
        self._requests: dict[int, PreloadRequest] = {}
        self._request_slots: dict[int, str] = {}
        self._queue: list[tuple[int, int, int]] = []
        self._latest_by_slot: dict[str, int] = {}
        self._generation_by_slot: dict[str, int] = {}
        self._stats = {
            "submitted": 0,
            "started": 0,
            "completed": 0,
            "failed": 0,
            "cancelled": 0,
            "stale_results": 0,
            "max_queue_depth": 0,
        }

    def request(
        self,
        path: str,
        frame_index: int = 0,
        *,
        slot: str = "viewer",
        priority: int = 0,
        reason: str = "current",
        source_signature: tuple[int, int] | None = None,
    ) -> PreloadRequest:
        """Queue a request and return its immutable identity.

        Lower numeric priorities run first. A new request supersedes the
        previous request in the same slot. Current requests also cancel queued
        lower-priority work so a selection cannot wait behind prefetch.
        """
        normalized = str(Path(path).resolve())
        signature = source_signature if source_signature is not None else _source_signature(normalized)
        previous_id = self._latest_by_slot.get(slot)
        previous_request = self._requests.get(previous_id) if previous_id is not None else None
        previous_event = self._active.get(previous_id) if previous_id is not None else None
        if (
            previous_request is not None
            and previous_event is not None
            and not previous_event.is_set()
            and previous_request.path == normalized
            and previous_request.frame_index == int(frame_index)
            and previous_request.source_signature == signature
            and int(priority) >= previous_request.priority
        ):
            return previous_request
        if previous_id is not None:
            self._cancel_request(previous_id)

        self._next_id += 1
        self._generation_by_slot[slot] = self._generation_by_slot.get(slot, 0) + 1
        request = PreloadRequest(
            request_id=self._next_id,
            path=normalized,
            frame_index=int(frame_index),
            priority=int(priority),
            generation=self._generation_by_slot[slot],
            reason=str(reason),
            source_signature=signature,
        )
        cancel_event = Event()
        self._requests[request.request_id] = request
        self._request_slots[request.request_id] = slot
        self._active[request.request_id] = cancel_event
        self._latest_by_slot[slot] = request.request_id
        self._sequence += 1
        heapq.heappush(self._queue, (request.priority, self._sequence, request.request_id))
        self._stats["submitted"] += 1

        if request.priority <= 1:
            for request_id, queued_request in list(self._requests.items()):
                if request_id != request.request_id and queued_request.priority > request.priority:
                    self._cancel_request(request_id)
        self._trim_queue()
        self._pump()
        self._emit_busy()
        return request

    def cancel(self, *, slot: str = "viewer") -> None:
        request_id = self._latest_by_slot.get(slot)
        if request_id is not None:
            self._cancel_request(request_id)
        self._pump()
        self._emit_busy()

    def cancel_path(self, path: str) -> None:
        """Cancel every current or prefetch request associated with ``path``."""
        normalized = str(Path(path).resolve())
        for request_id, request in list(self._requests.items()):
            if request.path == normalized:
                self._cancel_request(request_id)
        self._pump()
        self._emit_busy()

    def queue_stats(self) -> dict[str, int]:
        """Return scheduler counters suitable for PHI-free performance telemetry."""
        data = dict(self._stats)
        data["queue_depth"] = sum(1 for request_id in self._requests if request_id != self._active_request_id)
        data["inflight"] = int(self._active_request_id is not None)
        return data

    def _pump(self) -> None:
        if self._active_request_id is not None:
            return
        while self._queue:
            _, _, request_id = heapq.heappop(self._queue)
            request = self._requests.get(request_id)
            cancel_event = self._active.get(request_id)
            slot = self._request_slots.get(request_id, "viewer")
            if request is None or cancel_event is None or cancel_event.is_set():
                self._discard(request_id)
                continue
            if not self._is_latest(slot, request_id):
                self._stats["stale_results"] += 1
                self._discard(request_id)
                continue
            worker = DicomDecodeWorker(
                request,
                cancel_event,
                decoder=self.decoder,
                limits=self.limits,
            )
            self._workers[request_id] = worker
            self._active_request_id = request_id
            self._stats["started"] += 1
            worker.signals.finished.connect(lambda result, s=slot: self._on_finished(s, result))
            worker.signals.failed.connect(lambda error, s=slot: self._on_failed(s, error))
            worker.signals.cancelled.connect(lambda cancelled, s=slot: self._on_cancelled(s, cancelled))
            self.pool.start(worker)
            return
        self._active_request_id = None

    def _on_finished(self, slot: str, result: PreloadResult) -> None:
        self._active_request_id = None
        self._stats["completed"] += 1
        latest = self._is_latest(slot, result.request.request_id)
        self._discard(result.request.request_id)
        if latest:
            self.image_ready.emit(result)
        else:
            self._stats["stale_results"] += 1
        self._pump()
        self._emit_busy()

    def _on_failed(self, slot: str, error: PreloadError) -> None:
        self._active_request_id = None
        self._stats["failed"] += 1
        latest = self._is_latest(slot, error.request.request_id)
        self._discard(error.request.request_id)
        if latest:
            self.decode_failed.emit(error)
        else:
            self._stats["stale_results"] += 1
        self._pump()
        self._emit_busy()

    def _on_cancelled(self, slot: str, cancelled: PreloadCancelled) -> None:
        if self._active_request_id == cancelled.request.request_id:
            self._active_request_id = None
        self._stats["cancelled"] += 1
        latest = self._is_latest(slot, cancelled.request.request_id)
        self._discard(cancelled.request.request_id)
        if latest:
            self.decode_cancelled.emit(cancelled)
        self._pump()
        self._emit_busy()

    def _is_latest(self, slot: str, request_id: int) -> bool:
        return self._latest_by_slot.get(slot) == request_id

    def _cancel_request(self, request_id: int) -> None:
        event = self._active.get(request_id)
        if event is not None:
            event.set()
        if request_id != self._active_request_id:
            self._stats["cancelled"] += 1
            self._discard(request_id)

    def _trim_queue(self) -> None:
        queued = [
            request for request_id, request in self._requests.items()
            if request_id != self._active_request_id and not self._active[request_id].is_set()
        ]
        if len(queued) <= self.max_queue:
            self._stats["max_queue_depth"] = max(self._stats["max_queue_depth"], len(queued))
            return
        for request in sorted(queued, key=lambda item: (item.priority, item.request_id), reverse=True)[self.max_queue:]:
            self._cancel_request(request.request_id)
        self._stats["max_queue_depth"] = max(self._stats["max_queue_depth"], self.max_queue)

    def _discard(self, request_id: int) -> None:
        self._active.pop(request_id, None)
        self._workers.pop(request_id, None)
        self._requests.pop(request_id, None)
        self._request_slots.pop(request_id, None)

    def _emit_busy(self) -> None:
        self.busy_changed.emit(bool(self._requests) or self._active_request_id is not None)

    def shutdown(self) -> None:
        for event in self._active.values():
            event.set()
        self._queue.clear()
        self._active.clear()
        self._workers.clear()
        self._requests.clear()
        self._request_slots.clear()
        self._latest_by_slot.clear()
        self._active_request_id = None
        self._emit_busy()


def _source_signature(path: str) -> tuple[int, int]:
    try:
        stat = os.stat(path)
        return int(stat.st_mtime_ns), int(stat.st_size)
    except OSError:
        return 0, 0


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

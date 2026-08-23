from __future__ import annotations

import sys
import time
import unittest
from pathlib import Path
from threading import Event

import numpy as np
from PySide6.QtCore import QEventLoop, QThreadPool
from PySide6.QtWidgets import QApplication

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from modular_app.ui.dicom_preload_worker import (  # noqa: E402
    DecodeCancelled,
    DecodedImage,
    DicomPreloadController,
    PreloadError,
    array_to_grayscale_qimage,
)


_APP = QApplication.instance() or QApplication([])


def wait_until(predicate, timeout=2.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        _APP.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 10)
        if predicate():
            return True
        time.sleep(0.005)
    _APP.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 20)
    return bool(predicate())


def fixture_decoder(path: str, frame_index: int, cancel_event: Event) -> DecodedImage:
    if "slow" in path:
        for _ in range(100):
            if cancel_event.is_set():
                raise DecodeCancelled()
            time.sleep(0.003)
    if "error" in path:
        raise ValueError("fixture decode error")
    source = np.arange(16, dtype=np.uint16).reshape(4, 4)
    return DecodedImage(
        path=str(Path(path).resolve()),
        frame_index=frame_index,
        array=np.ascontiguousarray(source.copy()),
        rows=4,
        columns=4,
        frame_count=2,
        transfer_syntax="1.2.840.fixture",
    )


class DicomPreloadWorkerTests(unittest.TestCase):
    def setUp(self):
        self.pool = QThreadPool()
        self.pool.setMaxThreadCount(2)
        self.controller = DicomPreloadController(
            pool=self.pool,
            decoder=fixture_decoder,
        )

    def tearDown(self):
        self.controller.shutdown()
        self.pool.waitForDone(2000)

    def test_ready_result_contains_private_array_and_qimage_conversion(self):
        ready = []
        self.controller.image_ready.connect(ready.append)
        request = self.controller.request("ready.dcm", frame_index=1)

        self.assertTrue(wait_until(lambda: len(ready) == 1))
        result = ready[0]
        self.assertEqual(result.request.request_id, request.request_id)
        self.assertEqual(result.decoded.frame_index, 1)
        self.assertEqual(result.decoded.array.shape, (4, 4))
        qimage = array_to_grayscale_qimage(result.decoded.array)
        self.assertEqual(qimage.width(), 4)
        self.assertEqual(qimage.height(), 4)

        result.decoded.array[0, 0] = 999
        self.assertEqual(result.decoded.array[0, 1], 1)

    def test_latest_request_wins_and_old_result_is_not_emitted(self):
        ready = []
        cancelled = []
        self.controller.image_ready.connect(ready.append)
        self.controller.decode_cancelled.connect(cancelled.append)
        self.controller.request("slow.dcm", slot="viewer")
        newest = self.controller.request("fast.dcm", slot="viewer")

        self.assertTrue(wait_until(lambda: len(ready) == 1))
        self.assertEqual(ready[0].request.request_id, newest.request_id)
        self.assertNotIn("slow.dcm", ready[0].decoded.path)

    def test_priority_current_runs_before_queued_prefetch(self):
        started = []
        release = Event()

        def priority_decoder(path: str, frame_index: int, cancel_event: Event) -> DecodedImage:
            name = Path(path).name
            started.append(name)
            if name == "blocker.dcm":
                while not release.is_set():
                    if cancel_event.is_set():
                        raise DecodeCancelled()
                    time.sleep(0.002)
            return fixture_decoder(path, frame_index, cancel_event)

        self.controller.shutdown()
        self.controller = DicomPreloadController(
            pool=self.pool,
            decoder=priority_decoder,
            max_queue=3,
        )
        ready = []
        self.controller.image_ready.connect(ready.append)
        self.controller.request("blocker.dcm", slot="blocker", priority=5, reason="test-blocker")
        self.assertTrue(wait_until(lambda: started == ["blocker.dcm"]))
        self.controller.request("prefetch.dcm", slot="prefetch", priority=10, reason="prefetch-neighbor")
        current = self.controller.request("current.dcm", slot="viewer", priority=0, reason="current")
        self.assertEqual(current.priority, 0)
        release.set()
        self.assertTrue(wait_until(lambda: len(ready) == 1))
        self.assertEqual(started[:2], ["blocker.dcm", "current.dcm"])
        self.assertNotIn("prefetch.dcm", started)
        self.assertGreaterEqual(self.controller.queue_stats()["cancelled"], 1)

    def test_queue_depth_is_bounded_for_prefetch_requests(self):
        started = []
        release = Event()

        def bounded_decoder(path: str, frame_index: int, cancel_event: Event) -> DecodedImage:
            name = Path(path).name
            started.append(name)
            if name == "blocker.dcm":
                while not release.is_set():
                    if cancel_event.is_set():
                        raise DecodeCancelled()
                    time.sleep(0.002)
            return fixture_decoder(path, frame_index, cancel_event)

        self.controller.shutdown()
        self.controller = DicomPreloadController(pool=self.pool, decoder=bounded_decoder, max_queue=2)
        self.controller.request("blocker.dcm", slot="blocker", priority=5)
        self.assertTrue(wait_until(lambda: started == ["blocker.dcm"]))
        for index in range(4):
            self.controller.request(f"prefetch-{index}.dcm", slot=f"prefetch-{index}", priority=10, reason="prefetch-next")
        self.assertLessEqual(self.controller.queue_stats()["queue_depth"], 2)
        release.set()
        self.assertTrue(wait_until(lambda: self.controller.queue_stats()["inflight"] == 0))

    def test_duplicate_inflight_request_reuses_identity(self):
        first = self.controller.request("ready.dcm", slot="viewer", priority=0, reason="current")
        duplicate = self.controller.request("ready.dcm", slot="viewer", priority=0, reason="current")
        self.assertEqual(first.request_id, duplicate.request_id)
        self.assertTrue(wait_until(lambda: self.controller.queue_stats()["completed"] == 1))
        self.assertEqual(self.controller.queue_stats()["submitted"], 1)

    def test_request_has_source_signature_generation_and_reason(self):
        request = self.controller.request(
            "ready.dcm",
            source_signature=(123, 456),
            priority=7,
            reason="prefetch-next",
        )
        self.assertEqual(request.source_signature, (123, 456))
        self.assertEqual(request.generation, 1)
        self.assertEqual(request.reason, "prefetch-next")
        self.assertEqual(request.priority, 7)
        self.assertTrue(wait_until(lambda: self.controller.queue_stats()["completed"] == 1))

    def test_stale_result_is_not_emitted_when_decoder_ignores_cancellation(self):
        ready = []

        def stubborn_decoder(path: str, frame_index: int, cancel_event: Event) -> DecodedImage:
            if Path(path).name == "stubborn.dcm":
                time.sleep(0.03)
            return fixture_decoder(path, frame_index, cancel_event)

        self.controller.shutdown()
        self.controller = DicomPreloadController(pool=self.pool, decoder=stubborn_decoder)
        self.controller.image_ready.connect(ready.append)
        self.controller.request("stubborn.dcm", slot="viewer")
        newest = self.controller.request("ready.dcm", slot="viewer")
        self.assertTrue(wait_until(lambda: len(ready) == 1))
        self.assertEqual(ready[0].request.request_id, newest.request_id)
        self.assertGreaterEqual(self.controller.queue_stats()["cancelled"], 1)

    def test_decode_error_is_surface_as_data(self):
        errors = []
        self.controller.decode_failed.connect(errors.append)
        self.controller.request("error.dcm")

        self.assertTrue(wait_until(lambda: len(errors) == 1))
        self.assertIsInstance(errors[0], PreloadError)
        self.assertEqual(errors[0].exception_type, "ValueError")
        self.assertIn("fixture decode error", errors[0].message)

    def test_explicit_cancel_emits_cancelled_without_ready(self):
        ready = []
        cancelled = []
        self.controller.image_ready.connect(ready.append)
        self.controller.decode_cancelled.connect(cancelled.append)
        request = self.controller.request("slow.dcm")
        self.controller.cancel()

        self.assertTrue(wait_until(lambda: len(cancelled) == 1))
        self.assertEqual(cancelled[0].request.request_id, request.request_id)
        self.assertEqual(ready, [])

    def test_float_array_is_normalized_for_detached_grayscale_qimage(self):
        array = np.array([[0.0, 0.5], [1.0, 2.0]], dtype=np.float32)
        image = array_to_grayscale_qimage(array)
        self.assertEqual(image.format().name, "Format_Grayscale8")
        self.assertEqual(image.width(), 2)
        self.assertEqual(image.height(), 2)


if __name__ == "__main__":
    unittest.main()

import os
import time
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEventLoop
from PySide6.QtWidgets import QApplication

from modular_app.ui.background_task import FunctionTask
from modular_app.ui.pacs_dialog import PacsDialog


class PacsAsyncTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qt_app = QApplication.instance() or QApplication([])

    def wait_until(self, predicate, timeout=3.0):
        deadline = time.perf_counter() + timeout
        while time.perf_counter() < deadline:
            self.qt_app.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 20)
            if predicate():
                return True
            time.sleep(0.005)
        self.qt_app.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 50)
        return bool(predicate())

    def test_function_task_returns_on_gui_thread_via_signal(self):
        task = FunctionTask(lambda: {"rows": 3})
        values = []
        errors = []
        task.signals.finished.connect(values.append)
        task.signals.failed.connect(errors.append)
        # QThreadPool is created locally because QApplication has no threadPool API.
        from PySide6.QtCore import QThreadPool
        thread_pool = QThreadPool()
        thread_pool.start(task)
        self.assertTrue(self.wait_until(lambda: bool(values) or bool(errors)))
        thread_pool.waitForDone(1000)
        self.assertFalse(errors)
        self.assertEqual(values, [{"rows": 3}])

    def test_role_restricted_send_button_survives_busy_round_trip(self):
        dialog = PacsDialog(allow_send=False)
        try:
            self.assertFalse(dialog._action_buttons[-1].isEnabled())
            dialog._set_busy(True, "çalışıyor")
            self.assertTrue(all(not button.isEnabled() for button in dialog._action_buttons))
            dialog._set_busy(False, "hazır")
            self.assertTrue(all(button.isEnabled() for button in dialog._action_buttons[:-1]))
            self.assertFalse(dialog._action_buttons[-1].isEnabled())
        finally:
            dialog.close()
            self.qt_app.processEvents()


if __name__ == "__main__":
    unittest.main()

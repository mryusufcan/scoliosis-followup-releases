"""Small Qt-thread-pool adapter for non-GUI application work."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject, QRunnable, Signal, Slot


class TaskSignals(QObject):
    finished = Signal(object)
    failed = Signal(object)


class FunctionTask(QRunnable):
    """Run a callable off the GUI thread and return only plain Python values."""

    def __init__(self, function: Callable[[], Any]) -> None:
        super().__init__()
        self.function = function
        self.signals = TaskSignals()
        self.setAutoDelete(True)

    @Slot()
    def run(self) -> None:
        try:
            self.signals.finished.emit(self.function())
        except Exception as exc:  # worker boundary: report, never crash the GUI
            self.signals.failed.emit(exc)


__all__ = ["FunctionTask", "TaskSignals"]

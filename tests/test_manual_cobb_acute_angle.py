from __future__ import annotations

import math
import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QPointF

from modular_app.ui.workspace_actions import calculate_acute_cobb_angle


class ManualCobbAcuteAngleTests(unittest.TestCase):
    def test_supplementary_161_9_degrees_is_reported_as_18_1_degrees(self):
        degrees = 161.9
        fourth = QPointF(math.cos(math.radians(degrees)), math.sin(math.radians(degrees)))
        result = calculate_acute_cobb_angle(QPointF(0, 0), QPointF(1, 0), QPointF(0, 0), fourth)
        self.assertAlmostEqual(result, 18.1, places=1)

    def test_right_angle_is_preserved(self):
        result = calculate_acute_cobb_angle(QPointF(0, 0), QPointF(1, 0), QPointF(0, 0), QPointF(0, 1))
        self.assertAlmostEqual(result, 90.0, places=4)

    def test_zero_length_line_is_rejected(self):
        with self.assertRaises(ValueError):
            calculate_acute_cobb_angle(QPointF(1, 1), QPointF(1, 1), QPointF(0, 0), QPointF(1, 0))


if __name__ == "__main__":
    unittest.main()

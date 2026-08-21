from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from roadmap_fixtures import manual_cobb_record  # noqa: E402
from modular_app.domain.contracts import MeasurementStatus  # noqa: E402
from modular_app.timeline.longitudinal_center import (  # noqa: E402
    build_longitudinal_series,
    build_snapshot,
    curve_label,
)


class LongitudinalCenterTests(unittest.TestCase):
    def record(self, date: str, angle: float, *, upper="T5", lower="T11", direction="right", locked=False):
        record = manual_cobb_record(angle=angle)
        return record.__class__(
            **{
                **record.__dict__,
                "exam_date": date,
                "upper_vertebra": upper,
                "lower_vertebra": lower,
                "curve_direction": direction,
                "status": MeasurementStatus.VERIFIED if locked else MeasurementStatus.DRAFT,
                "verified_by": "Hekim" if locked else "",
            }
        )

    def test_curves_are_kept_separate(self):
        rows = [
            self.record("20240101", 30.0, upper="T5", lower="T11", direction="right"),
            self.record("20250101", 34.0, upper="T5", lower="T11", direction="right"),
            self.record("20240101", 18.0, upper="T12", lower="L4", direction="left"),
        ]
        series = build_longitudinal_series(rows)
        self.assertEqual(len(series), 2)
        labels = {item.label for item in series}
        self.assertIn("T5–T11 | right", labels)
        self.assertIn("T12–L4 | left", labels)

    def test_same_exam_date_collapses_to_one_record_and_prefers_locked(self):
        rows = [
            self.record("20240101", 30.0, locked=False),
            self.record("20240101", 31.5, locked=True),
            self.record("20250101", 35.0, locked=False),
        ]
        series = build_longitudinal_series(rows)
        self.assertEqual(len(series), 1)
        self.assertEqual([row.value for row in series[0].records], [31.5, 35.0])
        self.assertEqual(series[0].hidden_repeat_count, 1)

    def test_delta_and_annualized_rate_are_numeric_only(self):
        rows = [self.record("20240101", 30.0), self.record("20250101", 34.0)]
        item = build_longitudinal_series(rows)[0]
        self.assertAlmostEqual(item.delta, 4.0)
        self.assertGreater(item.annualized_delta or 0.0, 3.9)
        self.assertEqual(item.date_span_days, 366)

    def test_locked_only_excludes_draft_measurements(self):
        rows = [
            self.record("20240101", 30.0, locked=True),
            self.record("20250101", 34.0, locked=False),
        ]
        item = build_snapshot("FIXTURE-P001", rows, locked_only=True).series[0]
        self.assertEqual(len(item.records), 1)
        self.assertEqual(item.records[0].value, 30.0)

    def test_missing_curve_label_is_explicit(self):
        self.assertIn("belirtilmemiş", curve_label(("", "", "")).lower())


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "modular_app"), str(ROOT)]

from modular_app.ui.dicom_viewer_components import process_dicom_array


class DicomRenderPipelineTests(unittest.TestCase):
    def test_window_level_is_tonemapped_without_mutating_source_array(self):
        source = np.array([[0, 1000], [2000, 3000]], dtype=np.uint16)
        original = source.copy()
        dataset = SimpleNamespace(
            RescaleSlope=1.0,
            RescaleIntercept=0.0,
            PhotometricInterpretation="MONOCHROME2",
            WindowCenter=1500.0,
            WindowWidth=3000.0,
        )
        result = process_dicom_array(dataset, source_array=source)
        self.assertEqual(result.dtype, np.uint8)
        self.assertEqual(result.shape, source.shape)
        self.assertTrue(np.array_equal(source, original))
        self.assertEqual(int(result[0, 0]), 0)
        self.assertEqual(int(result[1, 1]), 255)

    def test_rescale_monochrome1_and_brightness_keep_uint8_contract(self):
        source = np.array([[0, 1], [2, 3]], dtype=np.int16)
        original = source.copy()
        dataset = SimpleNamespace(
            RescaleSlope=2.0,
            RescaleIntercept=10.0,
            PhotometricInterpretation="MONOCHROME1",
            WindowCenter=None,
            WindowWidth=None,
        )
        result = process_dicom_array(dataset, brightness_val=10, source_array=source)
        self.assertEqual(result.dtype, np.uint8)
        self.assertEqual(result.shape, source.shape)
        self.assertTrue(np.array_equal(source, original))
        self.assertGreaterEqual(int(result.min()), 0)
        self.assertLessEqual(int(result.max()), 255)
        self.assertFalse(np.array_equal(result, np.zeros_like(result)))


if __name__ == "__main__":
    unittest.main()

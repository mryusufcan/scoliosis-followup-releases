import sys
import unittest
from pathlib import Path

import numpy as np
import pydicom

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from modular_app.ui.dicom_codec import codec_status, decode_pixel_array  # noqa: E402


class DicomCodecTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.samples = [
            path
            for path in sorted((ROOT / "dev_data" / "dicom_samples").rglob("*"))
            if path.is_file()
        ]

    def test_real_fixture_selects_available_pylibjpeg_route(self):
        if not self.samples:
            self.skipTest("Gerçek DICOM örneği bulunamadı")
        ds = pydicom.dcmread(str(self.samples[0]), stop_before_pixels=True)
        status = codec_status(str(ds.file_meta.TransferSyntaxUID))
        self.assertEqual(status.transfer_syntax_uid, "1.2.840.10008.1.2.4.70")
        self.assertTrue(status.compressed)
        self.assertIn("pylibjpeg", status.available_plugins)
        self.assertEqual(status.selected_plugin, "pylibjpeg")

    def test_jpeg2000_and_jpegls_preferred_routes_are_reported(self):
        jpeg2000 = codec_status("1.2.840.10008.1.2.4.90")
        jpegls = codec_status("1.2.840.10008.1.2.4.80")
        self.assertTrue(jpeg2000.compressed)
        self.assertTrue(jpegls.compressed)
        self.assertEqual(jpeg2000.selected_plugin, "pylibjpeg")
        self.assertEqual(jpegls.selected_plugin, "pyjpegls")

    def test_real_fixture_decode_helper_returns_array_without_metadata_write(self):
        if not self.samples:
            self.skipTest("Gerçek DICOM örneği bulunamadı")
        path = self.samples[0]
        before = path.read_bytes()
        ds = pydicom.dcmread(str(path), stop_before_pixels=True)
        array = decode_pixel_array(
            str(path),
            index=0,
            transfer_syntax_uid=str(ds.file_meta.TransferSyntaxUID),
        )
        self.assertIsInstance(array, np.ndarray)
        self.assertEqual(array.ndim, 2)
        self.assertEqual(path.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()

import json
import tempfile
import unittest
from pathlib import Path

from tools.benchmark_iteration2 import (
    ROOT,
    _summary,
    benchmark_pacs,
    build_ephemeral_db_from_real_dicoms,
    discover_real_dicoms,
)


class Iteration2BenchmarkTests(unittest.TestCase):
    def test_summary_contains_stable_latency_statistics(self):
        result = _summary([10.0, 20.0, 30.0])
        self.assertEqual(result["repetitions"], 3)
        self.assertEqual(result["median_ms"], 20.0)
        self.assertEqual(result["min_ms"], 10.0)
        self.assertEqual(result["max_ms"], 30.0)
        self.assertEqual(result["p95_ms"], 30.0)

    def test_pacs_is_not_called_without_explicit_config(self):
        result = benchmark_pacs(None, 2, live=False, patient_id="", patient_name="", study_date="", retrieve_uid="", retrieve_destination=None)
        self.assertEqual(result["status"], "not_run")

    def test_real_dicom_headers_can_build_ephemeral_database(self):
        paths = discover_real_dicoms(ROOT / "dev_data" / "dicom_samples", limit=4)
        self.assertTrue(paths)
        with tempfile.TemporaryDirectory() as folder:
            db_path, patient_id = build_ephemeral_db_from_real_dicoms(paths, Path(folder))
            self.assertTrue(db_path.is_file())
            self.assertTrue(patient_id)
            self.assertGreater(db_path.stat().st_size, 0)

    def test_benchmark_json_contract_is_serializable(self):
        payload = {
            "kind": "scoliosis_follow_up_iteration2_benchmark",
            "measurement_policy": {"pacs_live_calls_opt_in": True},
        }
        self.assertEqual(json.loads(json.dumps(payload))["kind"], payload["kind"])


if __name__ == "__main__":
    unittest.main()

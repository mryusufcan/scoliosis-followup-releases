from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import unittest

from modular_app.services.license_policy import evaluate_license_gate


class FakeRepository:
    def __init__(self):
        self.values = {}

    def get_setting(self, key, default=None):
        return self.values.get(key, default)

    def set_setting(self, key, value):
        self.values[key] = str(value)


def status(active, online):
    return SimpleNamespace(active=active, online=online, message="test")


class LicensePolicyTests(unittest.TestCase):
    def setUp(self):
        self.repo = FakeRepository()
        self.start = datetime(2026, 8, 13, 9, 0, tzinfo=timezone.utc)

    def test_active_license_records_online_validation(self):
        result = evaluate_license_gate(
            self.repo,
            checker=lambda: SimpleNamespace(active=True, online=True, message="test", expires_at="2027-08-13"),
            now=self.start,
        )
        self.assertTrue(result.allowed)
        self.assertEqual(result.mode, "licensed")
        self.assertIn("license/last_online_validation_at", self.repo.values)
        self.assertEqual(result.expires_at, "2027-08-13")
        self.assertEqual(self.repo.values["license/expires_at"], "2027-08-13")

    def test_offline_license_is_limited_to_six_hours_after_validation(self):
        evaluate_license_gate(self.repo, checker=lambda: status(True, True), now=self.start)
        allowed = evaluate_license_gate(self.repo, checker=lambda: status(False, False), now=self.start + timedelta(hours=5, minutes=59))
        expired = evaluate_license_gate(self.repo, checker=lambda: status(False, False), now=self.start + timedelta(hours=6, seconds=1))
        self.assertTrue(allowed.allowed)
        self.assertEqual(allowed.mode, "offline_grace")
        self.assertFalse(expired.allowed)
        self.assertEqual(expired.mode, "offline_expired")

    def test_unlicensed_trial_is_six_hours_and_is_not_reset(self):
        allowed = evaluate_license_gate(self.repo, checker=lambda: status(False, True), now=self.start)
        expired = evaluate_license_gate(self.repo, checker=lambda: status(False, True), now=self.start + timedelta(hours=6, seconds=1))
        self.assertTrue(allowed.allowed)
        self.assertEqual(allowed.mode, "trial")
        self.assertFalse(expired.allowed)
        self.assertEqual(expired.mode, "trial_expired")

    def test_clock_rollback_is_rejected(self):
        evaluate_license_gate(self.repo, checker=lambda: status(False, True), now=self.start)
        result = evaluate_license_gate(self.repo, checker=lambda: status(False, True), now=self.start - timedelta(hours=1))
        self.assertFalse(result.allowed)
        self.assertEqual(result.mode, "clock_changed")


if __name__ == "__main__":
    unittest.main()

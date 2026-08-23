from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

import modular_app.services.license_policy as policy
from modular_app.services.license_policy import evaluate_license_gate


class FakeRepository:
    def __init__(self):
        self.values = {}

    def get_setting(self, key, default=None):
        return self.values.get(key, default)

    def set_setting(self, key, value):
        self.values[key] = str(value)


def license_status(active, online):
    return SimpleNamespace(
        active=active,
        online=online,
        message="test",
    )


def trial_status(started, now, online=True, ok=True):
    return SimpleNamespace(
        online=online,
        ok=ok,
        message="test",
        trial_started_at=started.isoformat() if started else None,
        server_now=now.isoformat() if now else None,
    )


class LicensePolicyTests(unittest.TestCase):
    def setUp(self):
        self.repo = FakeRepository()
        self.start = datetime(
            2026, 8, 13, 9, 0, tzinfo=timezone.utc
        )
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)

        self.patches = [
            patch.object(policy, "MACHINE_STATE_DIR", root),
                        patch.object(
                policy,
                "MACHINE_STATE_FILE",
                root / ".license_state.json",
            ),
            patch.object(policy, "LOCAL_LICENSE_DIR", root),
            patch.object(
                policy,
                "OFFLINE_LICENSE_FILE",
                root / "offline_license.json",
            ),
            patch.object(
                policy,
                "_get_hwid",

                return_value="TEST-HWID-1234567890",
            ),
        ]
        for item in self.patches:
            item.start()

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()
        self.temp.cleanup()

    def test_active_license_records_online_validation(self):
        result = evaluate_license_gate(
            self.repo,
            checker=lambda: SimpleNamespace(
                active=True,
                online=True,
                message="test",
                expires_at="2027-08-13",
            ),
            now=self.start,
        )
        self.assertTrue(result.allowed)
        self.assertEqual(result.mode, "licensed")

    def test_trial_requires_server_on_first_use(self):
        result = evaluate_license_gate(
            self.repo,
            checker=lambda: license_status(False, False),
            trial_checker=lambda: SimpleNamespace(
                online=False, ok=False, message="offline"
            ),
            now=self.start,
        )
        self.assertFalse(result.allowed)
        self.assertEqual(result.mode, "trial_online_required")

    def test_online_unlicensed_response_clears_stale_license_cache(self):
        self.repo.values["license/expires_at"] = "2027-08-16T23:59:59+03:00"
        self.repo.values["license/last_online_validation_at"] = self.start.isoformat()

        result = evaluate_license_gate(
            self.repo,
            checker=lambda: license_status(False, True),
            trial_checker=lambda: trial_status(self.start, self.start),
            now=self.start,
        )

        self.assertTrue(result.allowed)
        self.assertEqual(result.mode, "trial")
        self.assertIsNone(result.expires_at)
        self.assertEqual(self.repo.values["license/expires_at"], "")
        self.assertEqual(self.repo.values["license/last_online_validation_at"], "")

    def test_server_starts_trial_and_preserves_start_date(self):
        result = evaluate_license_gate(
            self.repo,
            checker=lambda: license_status(False, True),
            trial_checker=lambda: trial_status(
                self.start,
                self.start,
            ),
            now=self.start,
        )
        self.assertTrue(result.allowed)
        self.assertEqual(result.mode, "trial")
        self.assertEqual(
            self.repo.values["license/unlicensed_started_at"],
            self.start.isoformat(),
        )

    def test_database_deletion_cannot_reset_server_trial(self):
        first = evaluate_license_gate(
            self.repo,
            checker=lambda: license_status(False, True),
            trial_checker=lambda: trial_status(
                self.start,
                self.start,
            ),
            now=self.start,
        )
        self.assertTrue(first.allowed)

        fresh_repo = FakeRepository()
        expired_time = self.start + timedelta(days=14, seconds=1)

        result = evaluate_license_gate(
            fresh_repo,
            checker=lambda: license_status(False, True),
            trial_checker=lambda: trial_status(
                self.start,
                expired_time,
            ),
            now=expired_time,
        )
        self.assertFalse(result.allowed)
        self.assertEqual(result.mode, "trial_expired")

    def test_reinstall_and_local_state_deletion_cannot_reset_online_trial(self):
        evaluate_license_gate(
            self.repo,
            checker=lambda: license_status(False, True),
            trial_checker=lambda: trial_status(
                self.start,
                self.start,
            ),
            now=self.start,
        )

        policy.MACHINE_STATE_FILE.unlink()
        fresh_repo = FakeRepository()
        later = self.start + timedelta(days=10)

        result = evaluate_license_gate(
            fresh_repo,
            checker=lambda: license_status(False, True),
            trial_checker=lambda: trial_status(
                self.start,
                later,
            ),
            now=later,
        )

        self.assertTrue(result.allowed)
        self.assertEqual(result.mode, "trial")
        self.assertLess(
            result.remaining,
            timedelta(days=5),
        )

    def test_tampered_local_state_is_repaired_from_server_trial(self):
        evaluate_license_gate(
            self.repo,
            checker=lambda: license_status(False, True),
            trial_checker=lambda: trial_status(
                self.start,
                self.start,
            ),
            now=self.start,
        )

        text = policy.MACHINE_STATE_FILE.read_text(
            encoding="utf-8"
        )
        policy.MACHINE_STATE_FILE.write_text(
            text.replace(
                "TEST-HWID-1234567890",
                "OTHER-HWID-123456789",
            ),
            encoding="utf-8",
        )

        result = evaluate_license_gate(
            self.repo,
            checker=lambda: license_status(False, True),
            trial_checker=lambda: trial_status(
                self.start,
                self.start + timedelta(hours=1),
            ),
            now=self.start + timedelta(hours=1),
        )

        self.assertTrue(result.allowed)
        self.assertEqual(result.mode, "trial")
        self.assertIsNone(result.expires_at)
        repaired, error = policy._read_machine_state()
        self.assertIsNone(error)
        self.assertIsNotNone(repaired)

    def test_tampered_local_state_stays_closed_when_offline(self):
        evaluate_license_gate(
            self.repo,
            checker=lambda: license_status(False, True),
            trial_checker=lambda: trial_status(
                self.start,
                self.start,
            ),
            now=self.start,
        )

        text = policy.MACHINE_STATE_FILE.read_text(encoding="utf-8")
        policy.MACHINE_STATE_FILE.write_text(
            text.replace(
                "TEST-HWID-1234567890",
                "OTHER-HWID-123456789",
            ),
            encoding="utf-8",
        )

        result = evaluate_license_gate(
            self.repo,
            checker=lambda: license_status(False, False),
            trial_checker=lambda: SimpleNamespace(
                online=False,
                ok=False,
                message="offline",
            ),
            now=self.start + timedelta(hours=1),
        )

        self.assertFalse(result.allowed)
        self.assertEqual(result.mode, "license_state_invalid")

    def test_online_active_license_recovers_from_invalid_local_state(self):
        evaluate_license_gate(
            self.repo,
            checker=lambda: license_status(False, True),
            trial_checker=lambda: trial_status(
                self.start,
                self.start,
            ),
            now=self.start,
        )

        text = policy.MACHINE_STATE_FILE.read_text(encoding="utf-8")
        policy.MACHINE_STATE_FILE.write_text(
            text.replace(
                "TEST-HWID-1234567890",
                "OTHER-HWID-123456789",
            ),
            encoding="utf-8",
        )

        result = evaluate_license_gate(
            self.repo,
            checker=lambda: SimpleNamespace(
                active=True,
                online=True,
                message="test",
                expires_at="2027-08-16T23:59:59+03:00",
            ),
            now=self.start + timedelta(hours=1),
        )

        self.assertTrue(result.allowed)
        self.assertEqual(result.mode, "licensed")
        self.assertEqual(
            result.expires_at,
            "2027-08-16T23:59:59+03:00",
        )

    def test_clock_rollback_is_rejected(self):
        evaluate_license_gate(
            self.repo,
            checker=lambda: license_status(False, True),
            trial_checker=lambda: trial_status(
                self.start,
                self.start,
            ),
            now=self.start,
        )

        result = evaluate_license_gate(
            self.repo,
            checker=lambda: license_status(False, False),
            trial_checker=lambda: SimpleNamespace(
                online=False,
                ok=False,
                message="offline",
            ),
            now=self.start - timedelta(hours=1),
        )

        self.assertFalse(result.allowed)
        self.assertEqual(result.mode, "clock_changed")


if __name__ == "__main__":
    unittest.main()

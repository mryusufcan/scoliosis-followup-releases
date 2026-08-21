import hashlib
import unittest
from unittest.mock import patch

import license_app


class LicenseAppTests(unittest.TestCase):
    def test_get_hwid_uses_absolute_windows_wmic_path(self):
        completed = type(
            "Completed",
            (),
            {"stdout": "SerialNumber\nBOARD-SERIAL-123\n"},
        )()

        with (
            patch.dict("os.environ", {"WINDIR": r"D:\Windows"}),
            patch.object(license_app.os.path, "isfile", return_value=True),
            patch.object(
                license_app.subprocess,
                "run",
                return_value=completed,
            ) as run,
        ):
            result = license_app.get_hwid()

        self.assertEqual(
            result,
            hashlib.sha256(b"BOARD-SERIAL-123").hexdigest(),
        )
        self.assertEqual(
            run.call_args.args[0][0],
            r"D:\Windows\System32\wbem\WMIC.exe",
        )


if __name__ == "__main__":
    unittest.main()

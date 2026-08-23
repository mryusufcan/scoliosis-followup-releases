from __future__ import annotations

import hashlib
import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "release" / "GitHub_Yayinla.py"


def load_module():
    spec = importlib.util.spec_from_file_location("github_yayinla", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class GitHubReleaseAutomationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = load_module()

    def test_asset_match_requires_size_and_sha256(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "asset.bin"
            path.write_bytes(b"scoliosis-follow-up")
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            asset = {
                "name": path.name,
                "size": path.stat().st_size,
                "digest": f"sha256:{digest}",
            }
            self.assertTrue(self.module.asset_matches(asset, path))
            self.assertFalse(self.module.asset_matches({**asset, "size": 1}, path))
            self.assertFalse(self.module.asset_matches({**asset, "digest": "sha256:bad"}, path))

    def test_release_notes_body_removes_only_main_heading(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "notes.md"
            path.write_text("# Scoliosis Follow-Up 9.9.9\n\n## Düzeltmeler\n\n- Örnek\n", encoding="utf-8")
            self.assertEqual(
                self.module.release_notes_body(path),
                "## Düzeltmeler\n\n- Örnek",
            )

    def test_update_json_launcher_uses_versioned_github_url_and_python_fallback(self):
        launcher = (
            ROOT / "scripts" / "release" / "Guncelleme_JSON_Olustur.bat"
        ).read_text(encoding="utf-8-sig")
        self.assertIn(".venv-build\\Scripts\\python.exe", launcher)
        self.assertIn(".venv\\Scripts\\python.exe", launcher)
        self.assertIn("releases/download/%APP_VERSION%/", launcher)
        self.assertIn("ScoliosisFollowUp_Setup_%APP_VERSION%.exe", launcher)
        self.assertNotIn("releases/download/v%APP_VERSION%/ScoliosisFollowUp_Setup.exe", launcher)


if __name__ == "__main__":
    unittest.main()

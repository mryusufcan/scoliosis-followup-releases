"""Keep application, build and installer versions aligned before release."""
from __future__ import annotations

import re
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "modular_app"), str(ROOT)]


class ReleaseMetadataTests(unittest.TestCase):
    def test_frozen_application_reads_version_from_pyinstaller_data_root(self):
        paths_file = ROOT / "modular_app" / "config" / "paths.py"
        with tempfile.TemporaryDirectory() as folder:
            bundle_root = Path(folder)
            expected_version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
            (bundle_root / "VERSION").write_text(expected_version + "\n", encoding="utf-8")
            old_frozen = getattr(sys, "frozen", None)
            old_meipass = getattr(sys, "_MEIPASS", None)
            try:
                sys.frozen = True
                sys._MEIPASS = str(bundle_root)
                spec = importlib.util.spec_from_file_location("frozen_paths_test", paths_file)
                module = importlib.util.module_from_spec(spec)
                assert spec.loader is not None
                spec.loader.exec_module(module)
                self.assertEqual(module.PROJECT_ROOT, bundle_root)
                self.assertEqual(module.VERSION_FILE.read_text(encoding="utf-8").strip(), expected_version)
            finally:
                if old_frozen is None:
                    delattr(sys, "frozen")
                else:
                    sys.frozen = old_frozen
                if old_meipass is None:
                    delattr(sys, "_MEIPASS")
                else:
                    sys._MEIPASS = old_meipass

    @staticmethod
    def _release_module():
        spec = importlib.util.spec_from_file_location(
            "scoliosis_verify_release",
            ROOT / "packaging" / "verify_release.py",
        )
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        return module

    @staticmethod
    def _minimal_distribution(root: Path) -> Path:
        module = ReleaseMetadataTests._release_module()

        distribution = root / "dist" / "ScoliosisFollowUp"
        for pattern in module.REQUIRED_DISTRIBUTION_PATTERNS.values():
            concrete = pattern.replace("*", "")
            path = distribution / concrete
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"acceptance-fixture")
        return distribution

    def test_distribution_content_gate_accepts_required_runtime_without_known_bloat(self):
        module = self._release_module()

        with tempfile.TemporaryDirectory() as folder:
            module.verify_distribution_contents(self._minimal_distribution(Path(folder)))

    def test_distribution_content_gate_rejects_missing_codec_and_known_bloat(self):
        module = self._release_module()

        with tempfile.TemporaryDirectory() as folder:
            distribution = self._minimal_distribution(Path(folder))
            next(distribution.glob("_internal/_openjpeg*.pyd")).unlink()
            with self.assertRaisesRegex(module.ReleaseVerificationError, "JPEG 2000"):
                module.verify_distribution_contents(distribution)

            distribution = self._minimal_distribution(Path(folder))
            bloat = distribution / "_internal" / "PySide6" / "qml"
            bloat.mkdir(parents=True, exist_ok=True)
            with self.assertRaisesRegex(module.ReleaseVerificationError, "gereksiz büyük"):
                module.verify_distribution_contents(distribution)

    def test_release_version_is_consistent_across_runtime_and_packaging(self):
        from modular_app.services.system_services import APP_VERSION

        version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
        self.assertRegex(version, r"^\d+\.\d+\.\d+$")
        self.assertEqual(APP_VERSION, version)
        build_script = (ROOT / "packaging" / "build_windows.ps1").read_text(encoding="utf-8")
        ci_release_script = (ROOT / "packaging" / "ci_release.ps1").read_text(encoding="utf-8")
        installer_script = (ROOT / "packaging" / "build_installer.ps1").read_text(encoding="utf-8")
        installer_definition = (ROOT / "packaging" / "ScoliosisFollowUp.iss").read_text(encoding="utf-8")
        requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8")
        acceptance_script = (ROOT / "packaging" / "verify_release.py").read_text(encoding="utf-8")
        acceptance_wrapper = (ROOT / "tools" / "release_acceptance.ps1").read_text(encoding="utf-8")
        security_audit = (ROOT / "tools" / "audit_distribution_security.py").read_text(encoding="utf-8")
        beginner_guide = (ROOT / "docs" / "ACEMI_KULLANICI_REHBERI.md").read_text(encoding="utf-8")
        in_app_guide = (ROOT / "modular_app" / "ui" / "user_guide_dialog.py").read_text(encoding="utf-8")
        integration = (ROOT / "modular_app" / "run_modular.py").read_text(encoding="utf-8")
        self.assertIn("Get-Content -LiteralPath (Join-Path $root 'VERSION')", build_script)
        self.assertIn("--version \"$releaseVersion\"", build_script)
        self.assertIn("/DAppVersion=$releaseVersion", installer_script)
        self.assertIn("pylibjpeg>=", requirements)
        self.assertIn("pylibjpeg-libjpeg>=", requirements)
        self.assertIn("pylibjpeg-openjpeg>=", requirements)
        self.assertIn("pylibjpeg-rle>=", requirements)
        self.assertIn("pyjpegls>=", requirements)
        self.assertIn("Pillow>=", requirements)
        self.assertIn("--hidden-import pylibjpeg", build_script)
        for codec_package in ("libjpeg", "openjpeg", "rle", "jpeg_ls"):
            self.assertIn(f"--collect-binaries {codec_package}", build_script)
            self.assertNotIn(f"--collect-all {codec_package}", build_script)
        self.assertNotIn("--collect-all pylibjpeg", build_script)
        for excluded_module in (
            "libjpeg.tests", "openjpeg.tests", "rle.tests", "rle.benchmarks",
            "pylibjpeg.tests", "pylibjpeg.tools.tests", "jpeg_ls.tests", "jpeg_ls.example",
        ):
            self.assertIn(f"--exclude-module {excluded_module}", build_script)
        self.assertIn("--collect-submodules ai", build_script)
        self.assertIn('--add-data "$root\\VERSION;."', build_script)
        for package in (
            "PySide6", "pydicom", "pynetdicom", "reportlab", "PIL",
            "pyqtgraph", "onnxruntime", "requests", "cryptography",
        ):
            self.assertNotIn(
                f"--collect-all {package}",
                build_script,
                f"{package} collect-all paket boyutunu gereksiz buyutur",
            )
        self.assertIn("--hidden-import cv2", build_script)
        self.assertIn('"application version metadata": "_internal/VERSION"', acceptance_script)
        self.assertIn("test-results.txt", build_script)
        self.assertIn("audit_distribution_security.py", ci_release_script)
        self.assertIn("distribution_security_audit.json", ci_release_script)
        self.assertIn("ScoliosisFollowUpDistributionSecurityAuditV1", security_audit)
        self.assertIn("Start-Process -FilePath $venvPython", build_script)
        self.assertIn("verify_distribution_integrity", acceptance_script)
        self.assertIn("verify_update_feed", acceptance_script)
        self.assertIn("verify_release.py", acceptance_wrapper)
        self.assertIn("$PublishGitHubRelease -and -not $CertificateThumbprint.Trim()", ci_release_script)
        self.assertIn("release imzasız yayımlanacak", ci_release_script)
        self.assertIn("GitHub Releases", beginner_guide)
        self.assertIn("release_acceptance.ps1", beginner_guide)
        for heading in (
            "Görüntüleyici", "Görüntü Birleştirme", "Skolyoz Takip",
            "Hasta Takibi", "PACS", "Yapay Zekâ", "Lisans", "Yedekleme",
        ):
            self.assertIn(heading, in_app_guide)
        self.assertRegex(
            integration,
            r'help_menu\.addAction\("Kullanım Rehberi",\s*self\.show_user_guide\)',
        )
        self.assertIn('IconFilename: "{app}\\ScoliosisFollowUp.ico"', installer_definition)
        self.assertNotIn("AppUserModelID=", installer_definition)
        self.assertNotIn("QTimer.singleShot(1500", integration)
        self.assertIn(
            '#define AppVersion Trim(FileRead(FileOpen(AddBackslash(SourcePath) + "..\\VERSION")))',
            installer_definition,
        )

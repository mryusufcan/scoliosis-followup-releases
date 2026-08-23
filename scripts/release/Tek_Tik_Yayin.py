from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import zipfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VERSION_FILE = ROOT / "VERSION"
UPDATE_FILE = ROOT / "update.json"
INSTALLER = ROOT / "installer" / "ScoliosisFollowUp_Setup.exe"
SECURITY_KEY_DIR = Path(
    os.environ.get("SCOLIOSIS_FOLLOWUP_SECURITY_DIR")
    or Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    / "ScoliosisFollowUp"
    / "security_keys"
)
PRIVATE_KEY = SECURITY_KEY_DIR / "integrity_private.pem"
BUILD_PS1 = ROOT / "packaging" / "build_windows.ps1"
INSTALLER_PS1 = ROOT / "packaging" / "build_installer.ps1"
GENERATE_FEED = ROOT / "packaging" / "generate_update_feed.py"
LOCAL_VERIFY_BAT = ROOT / "scripts" / "release" / "Yayin_Paketini_Dogrula.bat"
RELEASES_DIR = ROOT / "releases"
LOG_DIR = ROOT / "artifacts" / "release_logs"


def banner(text: str) -> None:
    line = "=" * 64
    print(f"\n{line}\n{text.center(64)}\n{line}\n")


def fail(message: str, code: int = 1) -> None:
    print(f"\n[HATA] {message}")
    raise SystemExit(code)


def run(cmd, title: str, *, shell: bool = False) -> None:
    banner(title)
    result = subprocess.run(cmd, cwd=ROOT, shell=shell)
    if result.returncode != 0:
        fail(f"{title} basarisiz oldu. Kod: {result.returncode}", result.returncode)


def read_version() -> str:
    if not VERSION_FILE.is_file():
        fail("VERSION dosyasi bulunamadi.")
    version = VERSION_FILE.read_text(encoding="utf-8-sig").strip()
    if not version:
        fail("VERSION dosyasi bos.")
    return version


def choose_python() -> Path:
    for environment in (".venv", ".venv-build"):
        venv_python = ROOT / environment / "Scripts" / "python.exe"
        if venv_python.is_file():
            return venv_python
    return Path(sys.executable)


def current_download_url(version: str) -> str:
    if UPDATE_FILE.is_file():
        try:
            data = json.loads(UPDATE_FILE.read_text(encoding="utf-8-sig"))
            url = str(data.get("url") or "").strip()
            if url:
                # GitHub release etiketi ve sürümlü installer adı birlikte
                # güncellenir; update.json gerçek yüklenen varlığı göstermeli.
                import re
                updated = re.sub(
                    r"/releases/download/v?[^/]+/ScoliosisFollowUp_Setup(?:_[^/]+)?\.exe$",
                    f"/releases/download/{version}/ScoliosisFollowUp_Setup_{version}.exe",
                    url,
                )
                if updated != url:
                    return updated
        except Exception:
            pass
    return (
        "https://github.com/mryusufcan/scoliosis-followup-releases/"
        f"releases/download/{version}/ScoliosisFollowUp_Setup_{version}.exe"
    )


def generate_update_feed(version: str, python_exe: Path) -> None:
    if not INSTALLER.is_file():
        fail("Installer olusturulmamis.")
    if not PRIVATE_KEY.is_file():
        fail(f"Butunluk ozel anahtari bulunamadi: {PRIVATE_KEY}")
    if not GENERATE_FEED.is_file():
        fail("packaging/generate_update_feed.py bulunamadi.")

    url = current_download_url(version)
    run(
        [
            str(python_exe),
            str(GENERATE_FEED),
            "--version", version,
            "--url", url,
            "--installer", str(INSTALLER),
            "--private-key", str(PRIVATE_KEY),
            "--output", str(UPDATE_FILE),
        ],
        "4/6 - IMZALI UPDATE.JSON",
    )


def collect_release(version: str) -> Path:
    release_dir = RELEASES_DIR / version
    release_dir.mkdir(parents=True, exist_ok=True)

    files = [
        (INSTALLER, release_dir / f"ScoliosisFollowUp_Setup_{version}.exe"),
        (UPDATE_FILE, release_dir / "update.json"),
        (VERSION_FILE, release_dir / "VERSION"),
    ]
    for src, dst in files:
        if not src.is_file():
            fail(f"Yayin dosyasi bulunamadi: {src}")
        shutil.copy2(src, dst)

    zip_path = release_dir / f"ScoliosisFollowUp_{version}_release.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for _, dst in files:
            zf.write(dst, dst.name)

    return release_dir


def write_log(version: str, release_dir: Path) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    (LOG_DIR / f"release_{version}_{stamp}.txt").write_text(
        "\n".join([
            f"Version: {version}",
            f"Created: {datetime.now().isoformat(timespec='seconds')}",
            f"Release: {release_dir}",
            "Tests: OK",
            "Build: OK",
            "Installer: OK",
            "Local verification: OK",
        ]) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    banner("SCOLIOSIS FOLLOW-UP - TEK TIK TAM YAYIN")
    version = read_version()
    python_exe = choose_python()
    print(f"Surum: {version}")

    run([str(python_exe), "-m", "pytest", "-q"], "1/6 - TESTLER")

    run(
        ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
         "-File", str(BUILD_PS1), "-Clean"],
        "2/6 - TAM EXE PAKETI",
    )

    run(
        ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
         "-File", str(INSTALLER_PS1)],
        "3/6 - INSTALLER",
    )

    generate_update_feed(version, python_exe)

    if not LOCAL_VERIFY_BAT.is_file():
        fail("Yerel yayin dogrulama BAT dosyasi bulunamadi.")

    run(
        ["cmd.exe", "/d", "/c", "call", str(LOCAL_VERIFY_BAT)],
        "5/6 - YEREL YAYIN DOGRULAMA",
    )

    release_dir = collect_release(version)
    write_log(version, release_dir)

    banner("6/6 - YAYIN PAKETI HAZIR")
    print(f"Surum: {version}")
    print(f"Klasor: {release_dir}")
    print()
    print("GitHub'a yuklenecek ana dosyalar:")
    print(f"  {release_dir / f'ScoliosisFollowUp_Setup_{version}.exe'}")
    print(f"  {release_dir / 'update.json'}")
    print()
    print("GitHub'a yukledikten SONRA GitHub_Yayinini_Dogrula.bat kullanilabilir.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

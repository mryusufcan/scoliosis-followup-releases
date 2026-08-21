from __future__ import annotations

import argparse
import ctypes
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
HIDDEN = 0x2
INVALID_ATTRIBUTES = 0xFFFFFFFF

TECHNICAL_NAMES = {
    ".git",
    ".github",
    ".gitignore",
    ".quarantine",
    ".pytest_cache",
    ".restore_points",
    ".venv",
    ".venv-build",
    "__pycache__",
    "ai",
    "anonymization",
    "artifacts",
    "build",
    "dev_data",
    "dicom",
    "guncel_proje_zip.bat",
    "license_app.py",
    "main.py",
    "modular_app",
    "packaging",
    "pacs",
    "Proje_Temizlik_Merkezi_v2.bat",
    "project_control_center.py",
    "requirements-dev.txt",
    "requirements.txt",
    "resources",
    "scripts",
    "security_keys",
    "ScoliosisFollowUp.spec",
    "tests",
    "todo.md",
    "tools",
    "update.json",
    "VERSION",
}


def set_hidden(path: Path, hidden: bool) -> None:
    kernel32 = ctypes.windll.kernel32
    attributes = kernel32.GetFileAttributesW(str(path))
    if attributes == INVALID_ATTRIBUTES:
        raise OSError(f"Dosya özellikleri okunamadı: {path}")
    updated = attributes | HIDDEN if hidden else attributes & ~HIDDEN
    if not kernel32.SetFileAttributesW(str(path), updated):
        raise ctypes.WinError()


def main() -> int:
    parser = argparse.ArgumentParser(description="Proje kökündeki teknik dosyaların görünürlüğünü yönetir.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--hide", action="store_true", help="Teknik dosyaları gizle")
    group.add_argument("--show", action="store_true", help="Teknik dosyaları göster")
    args = parser.parse_args()

    if not (ROOT / "main.py").is_file() or not (ROOT / "VERSION").is_file():
        print("[HATA] Proje kökü doğrulanamadı.", file=sys.stderr)
        return 1

    changed = 0
    for name in sorted(TECHNICAL_NAMES, key=str.lower):
        path = ROOT / name
        if not path.exists():
            continue
        set_hidden(path, args.hide)
        changed += 1

    state = "gizlendi" if args.hide else "yeniden görünür yapıldı"
    print(f"[OK] {changed} teknik kök öğesi {state}.")
    print("[KORUNDU] Dosyaların yeri ve içeriği değiştirilmedi.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

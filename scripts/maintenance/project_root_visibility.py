from __future__ import annotations

import argparse
import ctypes
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
HIDDEN = 0x2
INVALID_ATTRIBUTES = 0xFFFFFFFF

# Yalnızca yerel, yeniden üretilebilir veya güvenlik nedeniyle gizli tutulması
# gereken alanlar saklanır. Kaynak kodu ve Proje Kontrol Merkezi görünür kalır.
TECHNICAL_NAMES = {
    ".git",
    ".github",
    ".gitignore",
    ".pytest_cache",
    ".quarantine",
    ".restore_points",
    ".venv",
    ".venv-build",
    "__pycache__",
    "artifacts",
    "build",
    "dev_data",
    "dist",
    "installer",
    "project_archives",
    "releases",
    "security_keys",
    "requirements-dev.txt",
}

# Önceden gizlenmiş olabilecek çekirdek öğeler show modunda daima açılır.
# Böylece eski geniş gizleme listesinden kalan Hidden attribute'ları temizlenir.
VISIBLE_CORE_NAMES = {
    "README.md",
    "Uygulamayi_Baslat.bat",
    "main.py",
    "project_control_center.py",
    "license_app.py",
    "requirements.txt",
    "VERSION",
    "update.json",
    "modular_app",
    "ai",
    "dicom",
    "pacs",
    "anonymization",
    "resources",
    "tests",
    "scripts",
    "tools",
    "packaging",
    "docs",
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
    names = TECHNICAL_NAMES if args.hide else TECHNICAL_NAMES | VISIBLE_CORE_NAMES
    for name in sorted(names, key=str.lower):
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

from __future__ import annotations

import argparse
import sys
import zipfile
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

SOURCE_DIRS = {
    ".github",
    "ai",
    "anonymization",
    "dicom",
    "docs",
    "modular_app",
    "packaging",
    "pacs",
    "resources",
    "scripts",
    "tests",
    "tools",
}

SOURCE_FILES = {
    ".gitignore",
    "license_app.py",
    "main.py",
    "project_control_center.py",
    "Proje_Araclari.bat",
    "Proje_Temizlik_Merkezi_v2.bat",
    "guncel_proje_zip.bat",
    "requirements.txt",
    "requirements-dev.txt",
    "ScoliosisFollowUp.spec",
    "update.json",
    "VERSION",
}

EXCLUDED_PARTS = {
    ".git",
    ".pytest_cache",
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
    "quarantine",
    "releases",
    "security_keys",
}

EXCLUDED_SUFFIXES = {
    ".dcm",
    ".dicom",
    ".key",
    ".log",
    ".p12",
    ".pfx",
    ".pyc",
    ".pyo",
    ".sqlite",
    ".sqlite3",
}

ALLOWED_PEM = Path("resources/security/integrity_public_key.pem")


def is_safe(relative: Path) -> bool:
    if any(part.lower() in EXCLUDED_PARTS for part in relative.parts):
        return False
    if relative.suffix.lower() in EXCLUDED_SUFFIXES:
        return False
    if relative.suffix.lower() == ".pem" and relative.as_posix().lower() != ALLOWED_PEM.as_posix().lower():
        return False
    return True


def source_files(root: Path = ROOT) -> list[Path]:
    selected: list[Path] = []
    for name in sorted(SOURCE_FILES):
        path = root / name
        if path.is_file() and is_safe(path.relative_to(root)):
            selected.append(path)
    for name in sorted(SOURCE_DIRS):
        folder = root / name
        if not folder.is_dir():
            continue
        for path in folder.rglob("*"):
            if path.is_file() and is_safe(path.relative_to(root)):
                selected.append(path)
    return sorted(set(selected), key=lambda path: path.relative_to(root).as_posix().lower())


def create_archive(output: Path | None = None, root: Path = ROOT) -> Path:
    version_file = root / "VERSION"
    version = version_file.read_text(encoding="utf-8-sig").strip() if version_file.exists() else "unknown"
    safe_version = "".join(ch for ch in version if ch.isalnum() or ch in "._-") or "unknown"
    if output is None:
        archive_dir = root / "project_archives"
        archive_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output = archive_dir / f"ScoliosisFollowUp_Source_v{safe_version}_{stamp}.zip"
    else:
        output = output.resolve()
        output.parent.mkdir(parents=True, exist_ok=True)

    files = source_files(root)
    if not files:
        raise RuntimeError("Arşivlenecek kaynak dosyası bulunamadı.")

    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in files:
            archive.write(path, path.relative_to(root).as_posix())

    with zipfile.ZipFile(output, "r") as archive:
        bad = [name for name in archive.namelist() if not is_safe(Path(name))]
        if bad:
            output.unlink(missing_ok=True)
            raise RuntimeError(f"Güvenlik doğrulaması başarısız: {bad[0]}")
        corrupt = archive.testzip()
        if corrupt:
            output.unlink(missing_ok=True)
            raise RuntimeError(f"ZIP doğrulaması başarısız: {corrupt}")

    return output


def main() -> int:
    parser = argparse.ArgumentParser(description="Güvenli paylaşılabilir proje kaynak ZIP'i oluşturur.")
    parser.add_argument("--output", type=Path, help="İsteğe bağlı çıktı ZIP yolu")
    args = parser.parse_args()
    try:
        output = create_archive(args.output)
    except Exception as exc:
        print(f"[HATA] {exc}", file=sys.stderr)
        return 1
    size_mb = output.stat().st_size / 1024 / 1024
    print(f"[OK] Güvenli proje ZIP'i oluşturuldu: {output}")
    print(f"[OK] Boyut: {size_mb:.2f} MB")
    print("[GÜVENLİK] Özel anahtarlar, DICOM/hasta verileri, sanal ortamlar ve derleme çıktıları dahil edilmedi.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

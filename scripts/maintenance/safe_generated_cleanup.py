from __future__ import annotations

import argparse
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROTECTED_PARTS = {
    ".git", ".quarantine", ".restore_points", ".venv", ".venv-build", "dist", "installer",
    "releases", "security_keys", "dev_data", "project_archives",
}


def targets(root: Path = ROOT) -> list[Path]:
    found: set[Path] = set()
    for relative in ("build", ".pytest_cache"):
        candidate = root / relative
        if candidate.exists():
            found.add(candidate)
    for directory in root.rglob("__pycache__"):
        relative = directory.relative_to(root)
        if directory.is_dir() and not any(part.lower() in PROTECTED_PARTS for part in relative.parts):
            found.add(directory)
    for suffix in ("*.pyc", "*.pyo"):
        for file in root.rglob(suffix):
            relative = file.relative_to(root)
            if file.is_file() and not any(part.lower() in PROTECTED_PARTS for part in relative.parts):
                found.add(file)
    return sorted(found, key=lambda path: (len(path.parts), str(path).lower()), reverse=True)


def size_of(path: Path) -> int:
    if path.is_file():
        return path.stat().st_size
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())


def main() -> int:
    parser = argparse.ArgumentParser(description="Yalnızca yeniden üretilebilir build/cache kalıntılarını temizler.")
    parser.add_argument("--apply", action="store_true", help="Listelenen hedefleri gerçekten kaldır")
    args = parser.parse_args()
    found = targets()
    total = sum(size_of(path) for path in found if path.exists())
    print("Güvenli temizlik hedefleri:")
    for path in found:
        print(f"  - {path.relative_to(ROOT)}")
    print(f"Toplam: {len(found)} hedef, yaklaşık {total / 1024 / 1024:.2f} MB")
    print("Korunur: kaynak kod, .venv, .venv-build, dist, installer, releases, restore noktaları, arşivler ve tüm hasta verileri.")
    if not args.apply:
        print("[DRY-RUN] Hiçbir dosya silinmedi.")
        return 0
    removed = 0
    for path in found:
        if not path.exists():
            continue
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
        removed += 1
    print(f"[OK] {removed} yeniden üretilebilir hedef kaldırıldı.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

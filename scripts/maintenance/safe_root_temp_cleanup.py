from __future__ import annotations

import argparse
import json
import shutil
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONFIRM_WORD = "CLEAN_ROOT_TEMP"

# Bu klasörler ayrı bakım politikalarına sahiptir; bu araç bunlara dokunmaz.
PROTECTED_DIRS = {
    ".git",
    ".github",
    ".quarantine",
    ".restore_points",
    ".venv",
    ".venv-build",
    "ai",
    "anonymization",
    "dicom",
    "modular_app",
    "pacs",
    "resources",
    "security_keys",
    "tests",
    "tools",
    "packaging",
    "scripts",
    "docs",
    "project_archives",
    "dev_data",
}

# Build/release klasörleri bu araçta silinmez; ayrı release cleanup akışına bırakılır.
GENERATED_DIRS = {
    "artifacts",
    "build",
    "dist",
    "installer",
    "releases",
}

# Kök düzeyinde yalnızca açıkça geçici olduğu bilinen yardımcı dosyalar adaydır.
ROOT_TEMP_FILES = {
    "project_size_inventory.json",
    "project_size_inventory_after_cleanup.json",
    "generated_cleanup_dry_run_20260822.json",
    "generated_cleanup_applied_20260822.json",
}


@dataclass(frozen=True)
class Candidate:
    path: str
    kind: str
    bytes: int
    modified_at: str
    reason: str


def relative(path: Path) -> str:
    return str(path.relative_to(ROOT))


def add_file(rows: list[Candidate], path: Path, kind: str, reason: str) -> None:
    if not path.is_file():
        return
    stat = path.stat()
    rows.append(
        Candidate(
            path=relative(path),
            kind=kind,
            bytes=stat.st_size,
            modified_at=datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
            reason=reason,
        )
    )


def collect(root: Path) -> list[Candidate]:
    rows: list[Candidate] = []
    for name in sorted(ROOT_TEMP_FILES):
        add_file(rows, root / name, "root_temp_file", "Bilinen geçici envanter/cleanup çıktısı.")
    # Kök __pycache__ yalnızca bu araç tarafından ayrıca görülebilir; alt kaynak cache'leri
    # safe_cache_log_cleanup.py tarafından yönetilir.
    cache = root / "__pycache__"
    if cache.is_dir():
        total = sum(p.stat().st_size for p in cache.rglob("*") if p.is_file())
        rows.append(
            Candidate(
                path=relative(cache),
                kind="root_cache_directory",
                bytes=total,
                modified_at=datetime.fromtimestamp(cache.stat().st_mtime).isoformat(timespec="seconds"),
                reason="Kök Python bytecode önbelleği; yeniden üretilebilir.",
            )
        )
    return sorted(rows, key=lambda row: row.bytes, reverse=True)


def write_report(path: Path, rows: list[Candidate], applied: bool) -> None:
    total = sum(row.bytes for row in rows)
    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "root": str(ROOT),
        "dry_run": not applied,
        "summary": {
            "candidate_count": len(rows),
            "candidate_bytes": total,
            "candidate_mib": round(total / 1024 / 1024, 2),
        },
        "protected_directories": sorted(PROTECTED_DIRS),
        "separate_generated_directories": sorted(GENERATED_DIRS),
        "entries": [asdict(row) for row in rows],
        "note": "Bu araç kaynak, veri, yedek, sanal ortam veya release klasörlerini taramaz/silmez.",
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Kök geçici proje dosyalarını güvenli temizleme aracı")
    parser.add_argument("--report", type=Path, default=None)
    parser.add_argument("--apply", action="store_true", help="Adayları sil")
    parser.add_argument("--confirm", default="", help=f"Yıkıcı işlem onayı: {CONFIRM_WORD}")
    args = parser.parse_args()

    rows = collect(ROOT)
    applied = False
    if args.apply:
        if args.confirm != CONFIRM_WORD:
            raise SystemExit(f"Silme durduruldu: --confirm {CONFIRM_WORD} gerekli.")
        for row in rows:
            path = ROOT / row.path
            if row.kind == "root_cache_directory":
                shutil.rmtree(path, ignore_errors=False)
            elif path.is_file():
                path.unlink()
        applied = True

    report_path = args.report or ROOT / "docs" / f"root_temp_cleanup_{datetime.now():%Y%m%d_%H%M%S}.json"
    write_report(report_path, rows, applied=applied)
    total = sum(row.bytes for row in rows)
    print(f"ROOT_TEMP_CLEANUP_{'APPLIED' if applied else 'DRY_RUN'}")
    print(f"Adaylar: {len(rows)} / {total / 1024 / 1024:.2f} MiB")
    for row in rows:
        print(f"{row.kind:22} {row.bytes / 1024 / 1024:10.2f} MiB {row.path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

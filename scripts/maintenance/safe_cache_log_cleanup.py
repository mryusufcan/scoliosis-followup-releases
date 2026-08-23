from __future__ import annotations

import argparse
import json
import os
import shutil
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONFIRM_WORD = "CLEAN_GENERATED_OUTPUTS"
CACHE_NAMES = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
SKIP_DIRS = {
    ".git",
    ".venv",
    ".venv-build",
    ".quarantine",
    ".restore_points",
    "project_archives",
    "dist",
    "build",
    "installer",
    "releases",
    "security_keys",
}
LOG_MARKERS = ("test", "pytest", "smoke", "validation", "benchmark", "acceptance")
LOG_SUFFIXES = {".log", ".txt", ".out"}


@dataclass(frozen=True)
class Candidate:
    path: str
    kind: str
    bytes: int
    modified_at: str
    action: str
    reason: str


def relative(path: Path) -> str:
    return str(path.relative_to(ROOT))


def candidate_for_file(path: Path, kind: str, reason: str) -> Candidate:
    stat = path.stat()
    return Candidate(
        path=relative(path),
        kind=kind,
        bytes=stat.st_size,
        modified_at=datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
        action="delete_candidate",
        reason=reason,
    )


def collect(root: Path, cutoff: datetime) -> list[Candidate]:
    rows: list[Candidate] = []
    for current, dirnames, filenames in os.walk(root):
        current_path = Path(current)
        dirnames[:] = [name for name in dirnames if name not in SKIP_DIRS]
        for dirname in list(dirnames):
            if dirname not in CACHE_NAMES:
                continue
            cache_path = current_path / dirname
            total = 0
            for cache_current, _, cache_files in os.walk(cache_path):
                for filename in cache_files:
                    try:
                        total += (Path(cache_current) / filename).stat().st_size
                    except OSError:
                        pass
            rows.append(
                Candidate(
                    path=relative(cache_path),
                    kind="cache_directory",
                    bytes=total,
                    modified_at=datetime.fromtimestamp(cache_path.stat().st_mtime).isoformat(timespec="seconds"),
                    action="delete_candidate",
                    reason="Yeniden üretilebilir Python/test önbelleği.",
                )
            )
            dirnames.remove(dirname)
        for filename in filenames:
            path = current_path / filename
            if path.suffix.lower() not in LOG_SUFFIXES:
                continue
            lower = path.name.lower()
            if not any(marker in lower for marker in LOG_MARKERS):
                continue
            try:
                modified = datetime.fromtimestamp(path.stat().st_mtime)
            except OSError:
                continue
            if modified >= cutoff:
                continue
            rows.append(
                candidate_for_file(
                    path,
                    "old_test_log",
                    f"{cutoff.date().isoformat()} tarihinden eski test/validation logu.",
                )
            )
    return sorted(rows, key=lambda row: row.bytes, reverse=True)


def write_report(path: Path, root: Path, rows: list[Candidate], args: argparse.Namespace, applied: bool) -> None:
    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "root": str(root),
        "dry_run": not applied,
        "older_than_days": args.older_than_days,
        "protected_directories": sorted(SKIP_DIRS),
        "summary": {
            "candidate_count": len(rows),
            "candidate_bytes": sum(row.bytes for row in rows),
            "candidate_mib": round(sum(row.bytes for row in rows) / 1024 / 1024, 2),
            "cache_count": sum(row.kind == "cache_directory" for row in rows),
            "old_test_log_count": sum(row.kind == "old_test_log" for row in rows),
        },
        "entries": [asdict(row) for row in rows],
        "note": "Varsayılan çalışma dry-run'dır; korunan alanlar taranmadı.",
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="__pycache__ ve eski test loglarını güvenli temizleme aracı")
    p.add_argument("--root", type=Path, default=ROOT)
    p.add_argument("--report", type=Path, default=None)
    p.add_argument("--older-than-days", type=int, default=14)
    p.add_argument("--apply", action="store_true", help="Dry-run yerine adayları sil")
    p.add_argument("--confirm", default="", help=f"Yıkıcı işlem onayı: {CONFIRM_WORD}")
    return p


def main() -> int:
    args = parser().parse_args()
    root = args.root.resolve()
    cutoff = datetime.now() - timedelta(days=max(0, args.older_than_days))
    rows = collect(root, cutoff)
    applied = False
    if args.apply:
        if args.confirm != CONFIRM_WORD:
            raise SystemExit(f"Silme durduruldu: --confirm {CONFIRM_WORD} gerekli.")
        for row in rows:
            path = root / row.path
            if not path.exists():
                continue
            if row.kind == "cache_directory":
                shutil.rmtree(path)
            else:
                path.unlink()
        applied = True
    report_path = args.report or root / "docs" / f"generated_cleanup_{datetime.now():%Y%m%d_%H%M%S}.json"
    write_report(report_path, root, rows, args, applied=applied)
    print(f"GENERATED_CLEANUP_{'APPLIED' if applied else 'DRY_RUN'}")
    print(f"Adaylar: {len(rows)} / {sum(row.bytes for row in rows) / 1024 / 1024:.2f} MiB")
    print(f"Cache klasörü: {sum(row.kind == 'cache_directory' for row in rows)}")
    print(f"Eski test logu: {sum(row.kind == 'old_test_log' for row in rows)}")
    for row in rows:
        print(f"{row.kind:18} {row.bytes / 1024 / 1024:10.2f} MiB {row.path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

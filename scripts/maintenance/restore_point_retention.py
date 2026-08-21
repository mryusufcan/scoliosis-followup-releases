"""Güvenli restore point retention bakımı.

Varsayılan davranış dry-run'dır: hiçbir dosya silmez, yalnızca JSON raporu üretir.
Silme için ayrıca --apply ve --confirm RETENTION_SIL gerekir.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable

STAMP_RE = re.compile(r"(?P<stamp>20\d{6}_\d{6})")
CONFIRM_WORD = "RETENTION_SIL"
DEFAULT_KEEP_DAYS = 7
DEFAULT_KEEP_LAST = 10
DEFAULT_MAX_AUTO_DELETE_MIB = 500.0


@dataclass(frozen=True)
class RestorePoint:
    path: str
    name: str
    modified: str
    age_days: float
    bytes: int
    files: int
    classification: str
    reason: str

    @property
    def mib(self) -> float:
        return round(self.bytes / 1024 / 1024, 2)


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def parse_timestamp(path: Path) -> datetime:
    match = STAMP_RE.search(path.name)
    if match:
        try:
            return datetime.strptime(match.group("stamp"), "%Y%m%d_%H%M%S")
        except ValueError:
            pass
    return datetime.fromtimestamp(path.stat().st_mtime)


def size_of(path: Path) -> tuple[int, int]:
    total = 0
    count = 0
    for item in path.rglob("*"):
        if item.is_file():
            try:
                total += item.stat().st_size
                count += 1
            except OSError:
                continue
    return total, count


def iter_restore_points(root: Path) -> Iterable[RestorePoint]:
    now = datetime.now()
    if not root.exists():
        return []
    paths = sorted((path for path in root.iterdir() if path.is_dir()), key=parse_timestamp, reverse=True)
    rows: list[RestorePoint] = []
    for path in paths:
        modified = parse_timestamp(path)
        total, files = size_of(path)
        age_days = max(0.0, (now - modified).total_seconds() / 86400.0)
        rows.append(
            RestorePoint(
                path=str(path),
                name=path.name,
                modified=modified.isoformat(timespec="seconds"),
                age_days=round(age_days, 3),
                bytes=total,
                files=files,
                classification="unclassified",
                reason="",
            )
        )
    return rows


def classify(
    points: list[RestorePoint],
    *,
    keep_days: int = DEFAULT_KEEP_DAYS,
    keep_last: int = DEFAULT_KEEP_LAST,
    max_auto_delete_mib: float = DEFAULT_MAX_AUTO_DELETE_MIB,
) -> list[RestorePoint]:
    ordered = sorted(points, key=lambda point: point.modified, reverse=True)
    recent_cutoff = float(keep_days)
    result: list[RestorePoint] = []
    for index, point in enumerate(ordered):
        if point.age_days <= recent_cutoff:
            result.append(point.__class__(**{**asdict(point), "classification": "keep_recent", "reason": f"Son {keep_days} gün içinde oluşturuldu."}))
        elif index < keep_last:
            result.append(point.__class__(**{**asdict(point), "classification": "keep_last", "reason": f"En yeni {keep_last} restore point içinde."}))
        elif point.bytes > int(max_auto_delete_mib * 1024 * 1024):
            result.append(point.__class__(**{**asdict(point), "classification": "large_protected", "reason": f"Boyutu {max_auto_delete_mib:.0f} MiB sınırını aşıyor; otomatik silme yok."}))
        else:
            result.append(point.__class__(**{**asdict(point), "classification": "candidate_delete", "reason": "Retention süresi dolmuş ve küçük restore point."}))
    return result


def write_report(path: Path, rows: list[RestorePoint], args: argparse.Namespace, *, applied: bool) -> None:
    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "root": str(args.root),
        "policy": {
            "keep_days": args.keep_days,
            "keep_last": args.keep_last,
            "max_auto_delete_mib": args.max_auto_delete_mib,
            "default_mode": "dry-run",
            "large_points_require_manual_review": True,
        },
        "mode": "apply" if applied else "dry-run",
        "summary": {
            "total_points": len(rows),
            "keep_recent": sum(row.classification == "keep_recent" for row in rows),
            "keep_last": sum(row.classification == "keep_last" for row in rows),
            "large_protected": sum(row.classification == "large_protected" for row in rows),
            "candidate_delete": sum(row.classification == "candidate_delete" for row in rows),
            "candidate_delete_mib": round(sum(row.bytes for row in rows if row.classification == "candidate_delete") / 1024 / 1024, 2),
        },
        "restore_points": [
            {**asdict(row), "mib": row.mib}
            for row in rows
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Restore point retention dry-run/apply aracı")
    parser.add_argument("--root", type=Path, default=project_root(), help="Proje kökü")
    parser.add_argument("--keep-days", type=int, default=DEFAULT_KEEP_DAYS)
    parser.add_argument("--keep-last", type=int, default=DEFAULT_KEEP_LAST)
    parser.add_argument("--max-auto-delete-mib", type=float, default=DEFAULT_MAX_AUTO_DELETE_MIB)
    parser.add_argument("--report", type=Path, default=None)
    parser.add_argument("--apply", action="store_true", help="candidate_delete sınıfını sil")
    parser.add_argument("--confirm", default="", help=f"Silme onayı: {CONFIRM_WORD}")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    args.root = args.root.resolve()
    restore_root = args.root / ".restore_points"
    rows = classify(
        list(iter_restore_points(restore_root)),
        keep_days=max(0, args.keep_days),
        keep_last=max(0, args.keep_last),
        max_auto_delete_mib=max(0.0, args.max_auto_delete_mib),
    )
    candidates = [row for row in rows if row.classification == "candidate_delete"]
    applied = False
    if args.apply:
        if args.confirm != CONFIRM_WORD:
            raise SystemExit(f"Silme durduruldu: --confirm {CONFIRM_WORD} gerekli.")
        for row in candidates:
            path = Path(row.path)
            if path.exists():
                shutil.rmtree(path)
        applied = True
    report_path = args.report or (args.root / "docs" / f"restore_point_retention_{datetime.now():%Y%m%d_%H%M%S}.json")
    write_report(report_path, rows, args, applied=applied)
    print(f"RESTORE_RETENTION_{'APPLIED' if applied else 'DRY_RUN'}")
    print(f"Toplam: {len(rows)} | Korunan: {len(rows) - len(candidates)} | Aday silme: {len(candidates)} | Aday alan: {sum(row.mib for row in candidates):.2f} MiB")
    for row in rows:
        print(f"{row.classification:16} {row.mib:10.2f} MiB {row.name} — {row.reason}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

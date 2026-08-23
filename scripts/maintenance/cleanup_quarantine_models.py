"""Karantina model/venv bakım aracı.

Varsayılan davranış yalnızca rapor üretir. Aktif resources altındaki dosyalar
asla hedeflenmez. Model silmek için --apply-model-duplicates ve --confirm
QUARANTINE_MODEL_SIL; venv silmek için ayrıca --apply-venvs gerekir.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

MODEL_SUFFIXES = {".onnx", ".pth", ".pt", ".ckpt", ".zip"}
CONFIRM_WORD = "QUARANTINE_MODEL_SIL"
DEFAULT_ROOT = Path(__file__).resolve().parents[2]


@dataclass
class Candidate:
    path: str
    kind: str
    bytes: int
    mib: float
    sha256: str | None
    action: str
    reason: str


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def size_of(path: Path) -> tuple[int, int]:
    total = 0
    files = 0
    for item in path.rglob("*"):
        if item.is_file():
            try:
                total += item.stat().st_size
                files += 1
            except OSError:
                pass
    return total, files


def relative(path: Path, root: Path) -> str:
    return str(path.resolve().relative_to(root.resolve()))


def model_files(root: Path) -> list[Path]:
    quarantine = root / ".quarantine"
    if not quarantine.exists():
        return []
    paths: list[Path] = []
    for path in quarantine.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in MODEL_SUFFIXES:
            continue
        if any(part in {".venv", ".git", "__pycache__"} for part in path.parts):
            continue
        paths.append(path)
    return sorted(paths, key=lambda path: str(path).lower())


def active_hashes(root: Path) -> dict[str, list[str]]:
    active_root = root / "resources" / "ai"
    result: dict[str, list[str]] = {}
    if not active_root.exists():
        return result
    for path in active_root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in MODEL_SUFFIXES:
            continue
        digest = sha256(path)
        result.setdefault(digest, []).append(relative(path, root))
    return result


def collect(root: Path) -> list[Candidate]:
    active = active_hashes(root)
    files = model_files(root)
    digest_groups: dict[str, list[Path]] = {}
    result: list[Candidate] = []
    for path in files:
        digest = sha256(path)
        digest_groups.setdefault(digest, []).append(path)
        size = path.stat().st_size
        result.append(
            Candidate(
                path=relative(path, root),
                kind="model_file",
                bytes=size,
                mib=round(size / 1024 / 1024, 2),
                sha256=digest,
                action="protected",
                reason="Aktif resources modeliyle eşleşip eşleşmediği ve quarantine içi kopyalar tamamlanmadan karar verilmez.",
            )
        )

    by_path = {row.path: row for row in result}
    for digest, group in digest_groups.items():
        active_paths = active.get(digest, [])
        ordered = sorted(group, key=lambda path: str(path).lower())
        for index, path in enumerate(ordered):
            row = by_path[relative(path, root)]
            if active_paths:
                row.action = "delete_model_duplicate"
                row.reason = "Aktif resources modeliyle SHA-256 birebir aynı; aktif dosya quarantine dışında korunuyor."
            elif index > 0:
                row.action = "delete_model_duplicate"
                row.reason = "Quarantine içinde aynı SHA-256 içeriğinin ikinci veya sonraki kopyası."
            else:
                row.action = "protected"
                row.reason = "Bu hash grubunda korunacak quarantine kopyası."

    # All venv folders are protected unless the caller explicitly enables them.
    for venv in sorted((path for path in (root / ".quarantine").rglob(".venv") if path.is_dir()), key=lambda path: str(path).lower()):
        total, files_count = size_of(venv)
        result.append(
            Candidate(
                path=relative(venv, root),
                kind="venv",
                bytes=total,
                mib=round(total / 1024 / 1024, 2),
                sha256=None,
                action="protected_venv",
                reason=(
                    "Yeniden kurulum smoke testi, --venv-tested, --apply-venvs ve "
                    f"açık onay olmadan silinmez ({files_count} dosya)."
                ),
            )
        )
    return sorted(result, key=lambda row: row.bytes, reverse=True)


def write_report(path: Path, root: Path, rows: list[Candidate], args: argparse.Namespace, applied: bool) -> None:
    deletable = [row for row in rows if row.action == "delete_model_duplicate"]
    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "root": str(root),
        "mode": "apply" if applied else "dry-run",
        "policy": {
            "active_resources_are_never_deleted": True,
            "venvs_require_explicit_apply_venvs": True,
            "model_confirmation": CONFIRM_WORD,
        },
        "summary": {
            "total_entries": len(rows),
            "model_duplicate_candidates": len(deletable),
            "model_duplicate_candidate_mib": round(sum(row.bytes for row in deletable) / 1024 / 1024, 2),
            "protected_model_entries": sum(row.action == "protected" for row in rows),
            "protected_venvs": sum(row.kind == "venv" for row in rows),
            "protected_venv_mib": round(sum(row.bytes for row in rows if row.kind == "venv") / 1024 / 1024, 2),
        },
        "entries": [asdict(row) for row in rows],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Karantina model ve venv dry-run/temizlik aracı")
    p.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    p.add_argument("--report", type=Path, default=None)
    p.add_argument("--apply-model-duplicates", action="store_true", help="Yalnızca aktif veya quarantine içi birebir model kopyalarını sil")
    p.add_argument("--apply-venvs", action="store_true", help="Karantina altındaki .venv klasörlerini de silmeye izin ver")
    p.add_argument("--venv-tested", action="store_true", help="Geçici ortamda yeniden kurulum smoke testinin başarıyla tamamlandığını beyan eder")
    p.add_argument("--confirm", default="", help=f"Yıkıcı işlem onayı: {CONFIRM_WORD}")
    return p


def main() -> int:
    args = parser().parse_args()
    root = args.root.resolve()
    rows = collect(root)
    model_candidates = [row for row in rows if row.action == "delete_model_duplicate"]
    venvs = [row for row in rows if row.kind == "venv"]
    delete_rows: list[Candidate] = []
    if args.apply_model_duplicates or args.apply_venvs:
        if args.confirm != CONFIRM_WORD:
            raise SystemExit(f"Silme durduruldu: --confirm {CONFIRM_WORD} gerekli.")
        if args.apply_venvs and not args.venv_tested:
            raise SystemExit("Venv silme durduruldu: önce yeniden kurulum smoke testi yapın ve --venv-tested verin.")
        if args.apply_model_duplicates:
            delete_rows.extend(model_candidates)
        if args.apply_venvs:
            delete_rows.extend(venvs)
        for row in delete_rows:
            path = root / row.path
            if path.exists():
                if row.kind == "venv":
                    shutil.rmtree(path)
                else:
                    path.unlink()
    applied = bool(delete_rows)
    report_path = args.report or root / "docs" / f"quarantine_model_cleanup_{datetime.now():%Y%m%d_%H%M%S}.json"
    write_report(report_path, root, rows, args, applied=applied)
    print(f"QUARANTINE_MODEL_CLEANUP_{'APPLIED' if applied else 'DRY_RUN'}")
    print(f"Model duplicate adayları: {len(model_candidates)} / {sum(row.mib for row in model_candidates):.2f} MiB")
    print(f"Korunan venv: {len(venvs)} / {sum(row.mib for row in venvs):.2f} MiB")
    for row in rows:
        print(f"{row.action:24} {row.mib:10.2f} MiB {row.path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Second-iteration performance benchmark for Scoliosis Follow-Up.

The DICOM cases are discovered from a real dataset directory. Report and
longitudinal benchmarks require an explicitly supplied local SQLite database;
PACS network operations are opt-in and never run without ``--live-pacs``.
The JSON output intentionally omits patient identifiers and full source paths.
"""
from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
import platform
import statistics
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Callable, Iterable

import pydicom

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modular_app.database.exam_repository import ExamRepository
from modular_app.reporting.follow_up_csv import export_follow_up_csv
from modular_app.reporting.follow_up_pdf import generate_follow_up_report
from modular_app.timeline.longitudinal_models import FilterState
from modular_app.timeline.longitudinal_service import LongitudinalService
from pacs.client import (
    PacsConfig,
    query_studies,
    retrieve_study,
    test_connection,
    validate_config,
)


class BenchmarkError(RuntimeError):
    """Raised for an invalid benchmark setup, not for a clinical result."""


def _timed(fn: Callable[[], Any], repeats: int) -> tuple[list[float], Any]:
    repeat_count = max(1, int(repeats))
    fn()
    durations: list[float] = []
    result: Any = None
    for _ in range(repeat_count):
        started = time.perf_counter()
        result = fn()
        durations.append((time.perf_counter() - started) * 1000.0)
    return durations, result


def _summary(durations: Iterable[float]) -> dict[str, float | int]:
    values = [float(item) for item in durations]
    if not values:
        return {"repetitions": 0, "mean_ms": 0.0, "median_ms": 0.0, "min_ms": 0.0, "max_ms": 0.0, "p95_ms": 0.0}
    ordered = sorted(values)
    p95_index = min(len(ordered) - 1, max(0, int(round(0.95 * len(ordered))) - 1))
    return {
        "repetitions": len(values),
        "mean_ms": round(statistics.mean(values), 3),
        "median_ms": round(statistics.median(values), 3),
        "min_ms": round(min(values), 3),
        "max_ms": round(max(values), 3),
        "p95_ms": round(ordered[p95_index], 3),
    }


def discover_real_dicoms(dataset_root: Path, limit: int = 0) -> list[Path]:
    """Return only files with readable DICOM image geometry."""
    if not dataset_root.is_dir():
        raise BenchmarkError(f"DICOM veri dizini bulunamadı: {dataset_root}")
    paths: list[Path] = []
    for path in sorted(dataset_root.rglob("*")):
        if not path.is_file():
            continue
        try:
            metadata = pydicom.dcmread(str(path), stop_before_pixels=True, force=True)
        except Exception:
            continue
        if hasattr(metadata, "Rows") and hasattr(metadata, "Columns"):
            paths.append(path)
    return paths[:limit] if limit > 0 else paths


def benchmark_dicom_metadata(paths: list[Path], repeats: int) -> dict[str, Any]:
    def scan() -> int:
        readable = 0
        for path in paths:
            metadata = pydicom.dcmread(str(path), stop_before_pixels=True, force=True)
            readable += int(hasattr(metadata, "Rows") and hasattr(metadata, "Columns"))
        return readable

    durations, readable = _timed(scan, repeats)
    return {
        "status": "ok",
        "files": len(paths),
        "readable_images": int(readable),
        "total": _summary(durations),
        "per_file_mean_ms": round(statistics.mean(durations) / max(1, len(paths)), 3),
    }


def benchmark_dicom_decode(paths: list[Path], repeats: int) -> dict[str, Any]:
    from modular_app.ui.dicom_preload_worker import DecodeLimits, decode_dicom_frame
    from threading import Event

    def decode() -> int:
        pixels = 0
        for path in paths:
            decoded = decode_dicom_frame(str(path), 0, Event(), limits=DecodeLimits())
            pixels += int(decoded.array.size)
        return pixels

    durations, pixels = _timed(decode, repeats)
    return {
        "status": "ok",
        "files": len(paths),
        "decoded_pixels_last_run": int(pixels),
        "total": _summary(durations),
        "per_file_mean_ms": round(statistics.mean(durations) / max(1, len(paths)), 3),
    }


def build_ephemeral_db_from_real_dicoms(paths: list[Path], root: Path) -> tuple[Path, str]:
    """Create a temporary exam index from real DICOM headers only."""
    repository = ExamRepository(root / "real_dicom_fixture.db")
    rows: list[dict[str, str]] = []
    selected_patient_id = ""
    selected_patient_name = ""
    for path in paths:
        try:
            metadata = pydicom.dcmread(str(path), stop_before_pixels=True, force=True)
        except Exception:
            continue
        source_patient_id = str(getattr(metadata, "PatientID", "") or "").strip()
        if not selected_patient_id:
            selected_patient_id = source_patient_id or "BENCHMARK-LOCAL"
            selected_patient_name = str(getattr(metadata, "PatientName", "") or "Benchmark")
        if source_patient_id and source_patient_id != selected_patient_id:
            continue
        rows.append(
            {
                "patient_id": selected_patient_id,
                "patient_name": selected_patient_name,
                "exam_date": str(getattr(metadata, "StudyDate", "") or "UNKNOWN"),
                "body_part": str(getattr(metadata, "BodyPartExamined", "") or ""),
                "modality": str(getattr(metadata, "Modality", "DX") or "DX"),
                "study_description": str(getattr(metadata, "StudyDescription", "") or ""),
                "dicom_path": str(path),
            }
        )
    if not rows:
        raise BenchmarkError("Gerçek DICOM başlıklarından benchmark fixture üretilemedi.")
    repository.add_many(rows)
    return repository.db_path, selected_patient_id


def _require_db_patient(db_path: Path, patient_id: str) -> tuple[ExamRepository, str]:
    if not db_path.is_file():
        raise BenchmarkError(f"SQLite benchmark veritabanı bulunamadı: {db_path}")
    normalized = str(patient_id or "").strip()
    if not normalized:
        raise BenchmarkError("Longitudinal/rapor benchmarkı için --patient-id zorunludur.")
    return ExamRepository(db_path), normalized


def benchmark_longitudinal(db_path: Path, patient_id: str, repeats: int) -> dict[str, Any]:
    repository, normalized = _require_db_patient(db_path, patient_id)
    service = LongitudinalService(repository)
    filters = FilterState(patient_id=normalized)

    durations, snapshot = _timed(lambda: service.load_snapshot(filters), repeats)
    return {
        "status": "ok",
        "patient_id_recorded": True,
        "snapshot": {
            "total_exams": int(snapshot.total_exams),
            "total_measurements": int(snapshot.total_measurements),
            "total_hidden_repeats": int(snapshot.total_hidden_repeats),
            "curve_count": len(snapshot.curves),
        },
        "load_snapshot": _summary(durations),
    }


def benchmark_reports(db_path: Path, patient_id: str, repeats: int) -> dict[str, Any]:
    repository, normalized = _require_db_patient(db_path, patient_id)
    patient_options = repository.list_patients(normalized)
    patient_name = ""
    if patient_options:
        patient_name = str(patient_options[0].get("patient_name", "") or "")

    with tempfile.TemporaryDirectory(prefix="scoliosis-report-bench-") as folder:
        output_dir = Path(folder)

        def make_csv() -> int:
            output, exams, measurements = export_follow_up_csv(
                repository,
                normalized,
                patient_name,
                output_dir / "follow_up.csv",
            )
            return int(output.stat().st_size + exams + measurements)

        def make_pdf() -> int:
            output = generate_follow_up_report(
                repository,
                normalized,
                patient_name,
                output_dir / "follow_up.pdf",
                prepared_by="benchmark",
                prepared_role="benchmark",
            )
            return int(output.stat().st_size)

        csv_durations, csv_size = _timed(make_csv, repeats)
        pdf_durations, pdf_size = _timed(make_pdf, repeats)

    return {
        "status": "ok",
        "patient_id_recorded": True,
        "last_output_bytes": {"csv": int(csv_size), "pdf": int(pdf_size)},
        "csv_export": _summary(csv_durations),
        "pdf_export": _summary(pdf_durations),
    }


def _load_pacs_config(path: Path) -> PacsConfig:
    if not path.is_file():
        raise BenchmarkError(f"PACS config dosyası bulunamadı: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return PacsConfig(
            host=str(payload["host"]),
            port=int(payload["port"]),
            called_ae_title=str(payload["called_ae_title"]),
            calling_ae_title=str(payload.get("calling_ae_title", "SCOLIOSIS_APP")),
            timeout_seconds=float(payload.get("timeout_seconds", 15.0)),
        )
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise BenchmarkError(f"PACS config geçersiz: {exc}") from exc


def benchmark_pacs(
    config_path: Path | None,
    repeats: int,
    *,
    live: bool,
    patient_id: str,
    patient_name: str,
    study_date: str,
    retrieve_uid: str,
    retrieve_destination: Path | None,
) -> dict[str, Any]:
    if config_path is None:
        return {"status": "not_run", "reason": "--pacs-config verilmedi; ağ işlemi çalıştırılmadı."}
    config = _load_pacs_config(config_path)
    validate_durations, _ = _timed(lambda: validate_config(config), repeats)
    result: dict[str, Any] = {
        "status": "validation_only" if not live else "ok",
        "config": {
            "host_recorded": True,
            "port": int(config.port),
            "timeout_seconds": float(config.timeout_seconds),
        },
        "validate_config": _summary(validate_durations),
    }
    if not live:
        result["reason"] = "Güvenlik nedeniyle canlı PACS çağrısı için ayrıca --live-pacs gerekir."
        return result

    connection_durations, _ = _timed(lambda: test_connection(config), repeats)
    query_durations, rows = _timed(
        lambda: query_studies(config, patient_id, patient_name, study_date),
        repeats,
    )
    result["test_connection"] = _summary(connection_durations)
    result["query_studies"] = {
        **_summary(query_durations),
        "rows_last_run": len(rows),
    }

    if retrieve_uid:
        if retrieve_destination is None:
            raise BenchmarkError("C-GET benchmarkı için --retrieve-destination zorunludur.")
        retrieve_durations, files = _timed(
            lambda: retrieve_study(config, retrieve_uid, retrieve_destination),
            1,
        )
        result["retrieve_study"] = {
            **_summary(retrieve_durations),
            "files_last_run": len(files),
            "destination_recorded": True,
        }
    else:
        result["retrieve_study"] = {"status": "not_run", "reason": "--retrieve-study-uid verilmedi."}
    return result


def _package_version(name: str) -> str | None:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    dataset_root = Path(args.dataset_root).resolve()
    dicom_paths = discover_real_dicoms(dataset_root, args.dicom_limit)
    if not dicom_paths:
        raise BenchmarkError("Gerçek DICOM görüntü dosyası bulunamadı.")

    payload: dict[str, Any] = {
        "kind": "scoliosis_follow_up_iteration2_benchmark",
        "schema_version": 1,
        "measurement_policy": {
            "real_dicom_dataset_required": True,
            "warmup_runs": 1,
            "reported_repetitions": max(1, int(args.repeats)),
            "patient_identifiers_omitted_from_output": True,
            "pacs_live_calls_opt_in": True,
        },
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
            "processor": platform.processor(),
            "cpu_count": os.cpu_count(),
            "pydicom": _package_version("pydicom"),
            "numpy": _package_version("numpy"),
            "pynetdicom": _package_version("pynetdicom"),
            "reportlab": _package_version("reportlab"),
        },
        "dataset": {
            "root_name": dataset_root.name,
            "files_selected": len(dicom_paths),
            "total_bytes": sum(path.stat().st_size for path in dicom_paths),
            "file_names": [path.name for path in dicom_paths],
        },
        "benchmarks": {
            "dicom_metadata_scan": benchmark_dicom_metadata(dicom_paths, args.repeats),
        },
    }
    if args.decode:
        payload["benchmarks"]["dicom_decode"] = benchmark_dicom_decode(dicom_paths, args.repeats)
    else:
        payload["benchmarks"]["dicom_decode"] = {
            "status": "not_run",
            "reason": "Süreyi sınırlamak için --decode verilmedi; worker benchmarkı ayrı çalıştırılabilir.",
        }

    derived_temp = None
    benchmark_db = Path(args.db).resolve() if args.db else None
    benchmark_patient_id = str(args.patient_id or "")
    if args.derive_db_from_dicom:
        derived_temp = tempfile.TemporaryDirectory(prefix="scoliosis-benchmark-db-")
        benchmark_db, benchmark_patient_id = build_ephemeral_db_from_real_dicoms(
            dicom_paths,
            Path(derived_temp.name),
        )
    try:
        if benchmark_db is not None and benchmark_patient_id:
            payload["benchmarks"]["longitudinal"] = benchmark_longitudinal(
                benchmark_db,
                benchmark_patient_id,
                args.repeats,
            )
            payload["benchmarks"]["reports"] = benchmark_reports(
                benchmark_db,
                benchmark_patient_id,
                args.repeats,
            )
            payload["benchmarks"]["database_source"] = {
                "kind": "explicit_db" if args.db else "temporary_db_derived_from_real_dicom_headers",
                "patient_id_recorded": True,
            }
        else:
            reason = "--db/--patient-id veya --derive-db-from-dicom verilmedi; veritabanı benchmarkları çalıştırılmadı."
            payload["benchmarks"]["longitudinal"] = {"status": "not_run", "reason": reason}
            payload["benchmarks"]["reports"] = {"status": "not_run", "reason": reason}
    finally:
        if derived_temp is not None:
            derived_temp.cleanup()

    pacs_config = Path(args.pacs_config).resolve() if args.pacs_config else None
    payload["benchmarks"]["pacs"] = benchmark_pacs(
        pacs_config,
        args.repeats,
        live=bool(args.live_pacs),
        patient_id=args.pacs_patient_id,
        patient_name=args.pacs_patient_name,
        study_date=args.pacs_study_date,
        retrieve_uid=args.retrieve_study_uid,
        retrieve_destination=Path(args.retrieve_destination).resolve() if args.retrieve_destination else None,
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-root", default=str(ROOT / "dev_data" / "dicom_samples"))
    parser.add_argument("--dicom-limit", type=int, default=0, help="0 tüm gerçek DICOM dosyalarını kullanır")
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--decode", action="store_true", help="Gerçek piksel decode ölçümünü de çalıştırır")
    parser.add_argument("--db", help="Açıkça seçilmiş benchmark SQLite kopyası")
    parser.add_argument("--patient-id", default="")
    parser.add_argument("--derive-db-from-dicom", action="store_true", help="Gerçek DICOM header'larından geçici SQLite fixture oluşturur")
    parser.add_argument("--pacs-config", help="host/port/AE alanlarını içeren JSON")
    parser.add_argument("--live-pacs", action="store_true", help="PACS association/query çağrılarını açıkça etkinleştirir")
    parser.add_argument("--pacs-patient-id", default="")
    parser.add_argument("--pacs-patient-name", default="")
    parser.add_argument("--pacs-study-date", default="")
    parser.add_argument("--retrieve-study-uid", default="")
    parser.add_argument("--retrieve-destination")
    parser.add_argument("--output", help="JSON çıktı yolu")
    args = parser.parse_args()

    try:
        payload = build_payload(args)
    except BenchmarkError as exc:
        parser.error(str(exc))

    output = Path(args.output).resolve() if args.output else ROOT / "docs" / "roadmap" / "iteration2_benchmark_latest.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    print(f"Benchmark JSON: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

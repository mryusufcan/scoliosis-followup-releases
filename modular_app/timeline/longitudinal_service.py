"""İlerleme ve takip paneli için Qt-bağımsız servis facade'ı.

Servis, mevcut ExamRepository ve LegacyCobbRepositoryAdapter üzerine oturur.
UI katmanı SQL satırlarıyla değil, longitudinal_models içindeki DTO'larla
çalışır. Bu modül ham DICOM verisini değiştirmez; yalnızca yerel kayıtları
okur, filtreler ve panel snapshot'ı üretir.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping

from modular_app.database.exam_repository import ExamRepository
from modular_app.domain.contracts import MeasurementRecord, MeasurementStatus
from modular_app.domain.measurement_adapter import LegacyCobbRepositoryAdapter
from modular_app.timeline.longitudinal_center import (
    CurveKey,
    CurveSeries,
    build_snapshot,
    curve_key,
)
from modular_app.timeline.longitudinal_models import (
    CurveOption,
    ExamTimelineItem,
    FilterState,
    MeasurementDetail,
    PanelSnapshot,
    PatientOption,
    SourceReference,
)


class LongitudinalServiceError(Exception):
    """UI veya ilerideki REST adaptörünün çevirebileceği servis hatası."""

    def __init__(self, code: str, message: str, details: Mapping[str, Any] | None = None):
        super().__init__(message)
        self.code = str(code)
        self.message = str(message)
        self.details = dict(details or {})

    def to_dict(self) -> dict[str, Any]:
        return {
            "error": {
                "code": self.code,
                "message": self.message,
                "details": self.details,
            }
        }


class LongitudinalService:
    """Hasta/eğri filtrelerini ve panel snapshot'ını yöneten facade.

    Bu sınıf Qt widget'larına bağımlı değildir. Aynı servis daha sonra CSV/PDF
    rapor üreticisi veya yerel REST adaptörü tarafından da kullanılabilir.
    """

    def __init__(
        self,
        repository: ExamRepository,
        *,
        adapter: LegacyCobbRepositoryAdapter | None = None,
    ) -> None:
        self.repository = repository
        self.adapter = adapter or LegacyCobbRepositoryAdapter(repository)

    def list_patients(self, query: str = "") -> list[PatientOption]:
        """Hasta seçiminde gösterilecek lokal hasta özetlerini döndür."""
        rows = self.repository.list_patients(str(query or ""))
        return [
            PatientOption(
                patient_id=str(row.get("patient_id", "") or ""),
                display_name=str(row.get("patient_name", "") or ""),
                exam_count=_as_int(row.get("exam_count")),
                latest_exam_date=str(row.get("latest_exam_date", "") or ""),
            )
            for row in rows
            if str(row.get("patient_id", "") or "").strip()
        ]

    def list_curves(
        self,
        patient_id: str,
        *,
        locked_only: bool = False,
    ) -> tuple[CurveOption, ...]:
        """Hastanın ölçüm kayıtlarından kararlı eğri seçenekleri üret."""
        patient_id = _require_patient_id(patient_id)
        records = self.adapter.list_measurements(patient_id)
        snapshot = build_snapshot(patient_id, records, locked_only=bool(locked_only))
        return tuple(
            CurveOption(
                key=series.key,
                count=len(series.records),
                latest_date=str(series.latest.exam_date if series.latest else ""),
                latest_value=float(series.latest.value) if series.latest else None,
                hidden_repeat_count=series.hidden_repeat_count,
            )
            for series in snapshot.series
        )

    def load_snapshot(self, filters: FilterState) -> PanelSnapshot:
        """Filtre durumuna göre grafik ve zaman çizelgesinin ortak snapshot'ını üret."""
        patient_id = _require_patient_id(filters.patient_id)
        normalized_filters = self._normalize_filters(filters)

        records = self.adapter.list_measurements(patient_id)
        exam_rows = self.repository.list_patient_exams(patient_id)
        exam_rows = _filter_exam_rows(exam_rows, normalized_filters)
        visible_paths = {str(row.get("dicom_path", "") or "") for row in exam_rows}

        # Tetkik filtresi aktifse ölçüm tarafında da aynı kaynak bağlamı uygulanır.
        # Hiç tetkik satırı yoksa, tarih/search/modality filtresi nedeniyle grafik
        # de boş kalmalıdır; bu durum kullanıcıya uyarı olarak aktarılır.
        filtered_records = [
            record
            for record in records
            if _record_visible(record, normalized_filters, visible_paths)
        ]

        domain_snapshot = build_snapshot(
            patient_id,
            filtered_records,
            locked_only=normalized_filters.locked_only,
        )
        curves = tuple(domain_snapshot.series)
        selected_series = _select_series(curves, normalized_filters.curve_key)
        warnings = list(self._build_warnings(exam_rows, filtered_records, selected_series))

        timeline_records = (
            [record for record in filtered_records if record.status == MeasurementStatus.VERIFIED]
            if normalized_filters.locked_only
            else filtered_records
        )
        patient_name = self._patient_name(patient_id)
        overlay_sessions = self.repository.list_comparison_sessions(patient_id)
        exams = tuple(
            _exam_timeline_item(
                row,
                records=timeline_records,
                selected_curve=normalized_filters.curve_key,
                overlay_sessions=overlay_sessions,
            )
            for row in exam_rows
        )

        return PanelSnapshot(
            patient_id=patient_id,
            patient_name=patient_name,
            filter_state=normalized_filters,
            selected_series=selected_series,
            curves=curves,
            exams=exams,
            total_exams=len(exams),
            total_measurements=domain_snapshot.total_measurements,
            total_hidden_repeats=domain_snapshot.total_hidden_repeats,
            warnings=tuple(warnings),
        )

    def get_measurement_detail(
        self,
        patient_id: str,
        measurement_id: int,
    ) -> MeasurementDetail:
        """Tek ölçümü hasta bağlamını doğrulayarak DTO'ya dönüştür."""
        patient_id = _require_patient_id(patient_id)
        record = self.adapter.get_measurement(int(measurement_id))
        if record is None:
            raise LongitudinalServiceError(
                "measurement_not_found",
                "Cobb ölçüm kaydı bulunamadı.",
                {"measurement_id": int(measurement_id)},
            )
        if str(record.patient_id) != patient_id:
            raise LongitudinalServiceError(
                "measurement_patient_mismatch",
                "Ölçüm seçili hastaya ait değil.",
                {
                    "measurement_id": int(measurement_id),
                    "requested_patient_id": patient_id,
                },
            )
        if record.measurement_id is None:
            raise LongitudinalServiceError(
                "measurement_id_missing",
                "Ölçüm kaydının kararlı kimliği bulunamadı.",
            )
        return MeasurementDetail.from_record(record)

    def get_exam_detail(self, patient_id: str, exam_id: int) -> ExamTimelineItem:
        """Tek tetkiki hasta bağlamını doğrulayarak timeline DTO'suna dönüştür."""
        patient_id = _require_patient_id(patient_id)
        row = self.repository.get_exam(int(exam_id))
        if row is None:
            raise LongitudinalServiceError(
                "exam_not_found",
                "Tetkik kaydı bulunamadı.",
                {"exam_id": int(exam_id)},
            )
        if str(row.get("patient_id", "")) != patient_id:
            raise LongitudinalServiceError(
                "exam_patient_mismatch",
                "Tetkik seçili hastaya ait değil.",
                {"exam_id": int(exam_id), "requested_patient_id": patient_id},
            )

        records = self.adapter.list_measurements(patient_id)
        sessions = self.repository.list_comparison_sessions(patient_id)
        return _exam_timeline_item(
            row,
            records=records,
            selected_curve=None,
            overlay_sessions=sessions,
        )

    def openable_source(self, patient_id: str, exam_id: int) -> SourceReference:
        """Tetkik kaydını görüntüleyiciye açılabilirlik bilgisiyle döndür."""
        exam = self.get_exam_detail(patient_id, exam_id)
        return SourceReference(
            patient_id=exam.patient_id,
            exam_id=exam.exam_id,
            dicom_path=exam.dicom_path,
            source_exists=exam.source_exists,
            exam_date=exam.exam_date,
            study_description=exam.study_description,
        )

    def build_csv_rows(self, snapshot: PanelSnapshot) -> list[dict[str, Any]]:
        """CSV üreticisinin kullanacağı düzleştirilmiş, filtreli satırları hazırla."""
        rows: list[dict[str, Any]] = []
        for item in snapshot.exams:
            rows.append(
                {
                    "patient_id": snapshot.patient_id,
                    "patient_name": snapshot.patient_name,
                    "exam_id": item.exam_id,
                    "exam_date": item.exam_date,
                    "body_part": item.body_part,
                    "modality": item.modality,
                    "study_description": item.study_description,
                    "latest_cobb": item.latest_cobb,
                    "latest_cobb_unit": item.latest_cobb_unit,
                    "latest_measurement_id": item.latest_measurement_id,
                    "status": item.status_label,
                    "source_exists": item.source_exists,
                    "measurement_count": item.measurement_count,
                    "overlay_session_count": item.overlay_session_count,
                }
            )
        return rows

    def _normalize_filters(self, filters: FilterState) -> FilterState:
        date_from = _normalize_date_filter(filters.date_from, "date_from")
        date_to = _normalize_date_filter(filters.date_to, "date_to")
        if date_from and date_to and date_from > date_to:
            raise LongitudinalServiceError(
                "invalid_date_filter",
                "Başlangıç tarihi bitiş tarihinden sonra olamaz.",
                {"date_from": filters.date_from, "date_to": filters.date_to},
            )
        return FilterState(
            patient_id=_require_patient_id(filters.patient_id),
            curve_key=_normalize_curve_key(filters.curve_key),
            locked_only=bool(filters.locked_only),
            date_from=date_from,
            date_to=date_to,
            search_text=str(filters.search_text or "").strip(),
            modality=str(filters.modality or "").strip(),
        )

    def _patient_name(self, patient_id: str) -> str:
        for option in self.list_patients():
            if option.patient_id == patient_id:
                return option.display_name
        return ""

    @staticmethod
    def _build_warnings(
        exam_rows: Iterable[Mapping[str, Any]],
        records: Iterable[MeasurementRecord],
        selected_series: CurveSeries | None,
    ) -> tuple[str, ...]:
        warnings: list[str] = []
        exam_rows = list(exam_rows)
        records = list(records)
        if not exam_rows and records:
            warnings.append("Ölçüm kaydı var ancak eşleşen tetkik satırı bulunamadı.")
        missing_sources = sum(
            1
            for row in exam_rows
            if (str(row.get("dicom_path", "") or "") and not Path(str(row.get("dicom_path"))).is_file())
        )
        if missing_sources:
            warnings.append(f"{missing_sources} tetkik kaydının kaynak DICOM dosyası bulunamadı.")
        if selected_series is not None and len(selected_series.records) == 1:
            warnings.append("Trend için en az iki farklı tetkik tarihi gerekir.")
        if selected_series is not None and selected_series.hidden_repeat_count:
            warnings.append(
                f"{selected_series.hidden_repeat_count} aynı tarihli tekrar ölçüm trendde temsilciyle gösterildi."
            )
        return tuple(dict.fromkeys(warnings))


def _require_patient_id(patient_id: str) -> str:
    value = str(patient_id or "").strip()
    if not value:
        raise LongitudinalServiceError("patient_id_required", "Hasta kimliği gereklidir.")
    return value


def _normalize_curve_key(value: CurveKey | None) -> CurveKey | None:
    if value is None:
        return None
    if len(value) != 3:
        raise LongitudinalServiceError(
            "invalid_curve_key",
            "Eğri anahtarı üst vertebra, alt vertebra ve yön olmak üzere üç alan içermelidir.",
        )
    return tuple(str(item or "").strip() for item in value)  # type: ignore[return-value]


def _normalize_date_filter(value: str, field_name: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    normalized = raw.replace("-", "")
    if len(normalized) != 8 or not normalized.isdigit():
        raise LongitudinalServiceError(
            "invalid_date_filter",
            f"{field_name} YYYYMMDD veya YYYY-MM-DD biçiminde olmalıdır.",
            {field_name: raw},
        )
    try:
        datetime.strptime(normalized, "%Y%m%d")
    except ValueError as exc:
        raise LongitudinalServiceError(
            "invalid_date_filter",
            f"{field_name} geçerli bir tarih değil.",
            {field_name: raw},
        ) from exc
    return normalized


def _normalize_date(value: object) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    normalized = raw.replace("-", "")
    if len(normalized) == 8 and normalized.isdigit():
        return normalized
    return raw


def _filter_exam_rows(rows: Iterable[Mapping[str, Any]], filters: FilterState) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    search = filters.search_text.casefold()
    modality = filters.modality.casefold()
    for source in rows:
        row = dict(source)
        exam_date = _normalize_date(row.get("exam_date"))
        if filters.date_from and (not exam_date or exam_date < filters.date_from):
            continue
        if filters.date_to and (not exam_date or exam_date > filters.date_to):
            continue
        if modality and modality != str(row.get("modality", "") or "").casefold():
            continue
        if search:
            searchable = " ".join(
                str(row.get(key, "") or "")
                for key in (
                    "exam_date",
                    "body_part",
                    "modality",
                    "study_description",
                    "dicom_path",
                    "notes",
                )
            ).casefold()
            if search not in searchable:
                continue
        result.append(row)
    return result


def _record_visible(
    record: MeasurementRecord,
    filters: FilterState,
    visible_paths: set[str],
) -> bool:
    path = str(record.source_context.dicom_path or "")
    if visible_paths and path not in visible_paths:
        return False
    if not visible_paths and (filters.date_from or filters.date_to or filters.search_text or filters.modality):
        return False
    date = _normalize_date(record.exam_date)
    if filters.date_from and (not date or date < filters.date_from):
        return False
    if filters.date_to and (not date or date > filters.date_to):
        return False
    return True


def _select_series(
    curves: Iterable[CurveSeries],
    preferred_key: CurveKey | None,
) -> CurveSeries | None:
    curves = tuple(curves)
    if preferred_key is not None:
        return next((series for series in curves if series.key == preferred_key), None)
    return curves[0] if curves else None


def _exam_timeline_item(
    row: Mapping[str, Any],
    *,
    records: Iterable[MeasurementRecord],
    selected_curve: CurveKey | None,
    overlay_sessions: Iterable[Mapping[str, Any]],
) -> ExamTimelineItem:
    exam_id = _as_int(row.get("id"))
    patient_id = str(row.get("patient_id", "") or "")
    path = str(row.get("dicom_path", "") or "")
    matching = [
        record
        for record in records
        if str(record.source_context.dicom_path or "") == path
        and (selected_curve is None or curve_key(record) == selected_curve)
    ]
    matching.sort(key=_record_sort_key, reverse=True)
    latest = matching[0] if matching else None
    overlay_count = sum(
        1
        for session in overlay_sessions
        if path
        and path in {
            str(session.get("reference_path", "") or ""),
            str(session.get("comparison_path", "") or ""),
        }
    )
    return ExamTimelineItem(
        exam_id=exam_id,
        patient_id=patient_id,
        exam_date=str(row.get("exam_date", "") or ""),
        body_part=str(row.get("body_part", "") or ""),
        modality=str(row.get("modality", "") or ""),
        study_description=str(row.get("study_description", "") or ""),
        dicom_path=path,
        latest_cobb=float(latest.value) if latest is not None else None,
        latest_cobb_unit=str(latest.unit or "deg") if latest is not None else "deg",
        latest_measurement_id=latest.measurement_id if latest is not None else None,
        latest_cobb_locked=(latest.status == MeasurementStatus.VERIFIED) if latest is not None else False,
        measurement_count=len(matching),
        overlay_session_count=overlay_count,
        source_exists=Path(path).is_file() if path else False,
        notes=str(row.get("notes", "") or ""),
    )


def _record_sort_key(record: MeasurementRecord) -> tuple[str, int]:
    return (
        str(record.provenance.created_at or ""),
        int(record.measurement_id or 0),
    )


def _as_int(value: object, default: int = 0) -> int:
    try:
        return int(value or default)
    except (TypeError, ValueError):
        return default


__all__ = [
    "LongitudinalService",
    "LongitudinalServiceError",
]

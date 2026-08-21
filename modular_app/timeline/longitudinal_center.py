"""Curve-based longitudinal tracking services without Qt dependencies."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Iterable

from modular_app.domain.contracts import MeasurementRecord, MeasurementStatus, MeasurementType


CurveKey = tuple[str, str, str]


def curve_key(record: MeasurementRecord) -> CurveKey:
    return (
        str(record.upper_vertebra or "").strip(),
        str(record.lower_vertebra or "").strip(),
        str(record.curve_direction or "").strip(),
    )


def curve_label(key: CurveKey) -> str:
    upper, lower, direction = key
    if not upper or not lower:
        return "Vertebra çifti belirtilmemiş / eski kayıt"
    return f"{upper}–{lower}{(' | ' + direction) if direction else ''}"


def _record_sort_key(record: MeasurementRecord) -> tuple[str, str, int]:
    return (
        str(record.exam_date or ""),
        str(record.provenance.created_at or ""),
        int(record.measurement_id or 0),
    )


def _date_value(raw: str) -> date | None:
    value = str(raw or "").strip()
    for fmt in ("%Y%m%d", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            pass
    return None


def _one_record_per_exam_date(records: Iterable[MeasurementRecord]) -> tuple[tuple[MeasurementRecord, ...], int]:
    by_date: dict[str, list[MeasurementRecord]] = {}
    for record in records:
        key = str(record.exam_date or "").strip() or f"NO_DATE:{record.measurement_id or id(record)}"
        by_date.setdefault(key, []).append(record)

    selected: list[MeasurementRecord] = []
    hidden_repeats = 0
    for group in by_date.values():
        hidden_repeats += max(0, len(group) - 1)
        selected.append(max(
            group,
            key=lambda record: (
                record.status == MeasurementStatus.VERIFIED,
                str(record.provenance.created_at or ""),
                int(record.measurement_id or 0),
            ),
        ))
    selected.sort(key=_record_sort_key)
    return tuple(selected), hidden_repeats


@dataclass(frozen=True)
class CurveSeries:
    key: CurveKey
    records: tuple[MeasurementRecord, ...]
    hidden_repeat_count: int = 0

    @property
    def label(self) -> str:
        return curve_label(self.key)

    @property
    def first(self) -> MeasurementRecord | None:
        return self.records[0] if self.records else None

    @property
    def latest(self) -> MeasurementRecord | None:
        return self.records[-1] if self.records else None

    @property
    def delta(self) -> float | None:
        if len(self.records) < 2:
            return None
        return float(self.records[-1].value) - float(self.records[0].value)

    @property
    def annualized_delta(self) -> float | None:
        if len(self.records) < 2:
            return None
        first_date = _date_value(self.records[0].exam_date)
        last_date = _date_value(self.records[-1].exam_date)
        if first_date is None or last_date is None:
            return None
        days = (last_date - first_date).days
        if days <= 0:
            return None
        return (float(self.records[-1].value) - float(self.records[0].value)) / days * 365.25

    @property
    def date_span_days(self) -> int | None:
        if len(self.records) < 2:
            return None
        first_date = _date_value(self.records[0].exam_date)
        last_date = _date_value(self.records[-1].exam_date)
        if first_date is None or last_date is None:
            return None
        return (last_date - first_date).days


@dataclass(frozen=True)
class LongitudinalSnapshot:
    patient_id: str
    series: tuple[CurveSeries, ...]
    locked_only: bool = False

    @property
    def total_measurements(self) -> int:
        return sum(len(item.records) for item in self.series)

    @property
    def total_hidden_repeats(self) -> int:
        return sum(item.hidden_repeat_count for item in self.series)

    @property
    def latest_value(self) -> float | None:
        latest = [item.latest for item in self.series if item.latest is not None]
        return max((float(record.value) for record in latest), default=None)


def build_longitudinal_series(
    records: Iterable[MeasurementRecord],
    *,
    locked_only: bool = False,
) -> tuple[CurveSeries, ...]:
    groups: dict[CurveKey, list[MeasurementRecord]] = {}
    for record in records:
        if record.measurement_type != MeasurementType.COBB_ANGLE:
            continue
        if locked_only and record.status != MeasurementStatus.VERIFIED:
            continue
        groups.setdefault(curve_key(record), []).append(record)

    result: list[CurveSeries] = []
    for key, group in groups.items():
        selected, hidden_repeats = _one_record_per_exam_date(group)
        result.append(CurveSeries(key=key, records=selected, hidden_repeat_count=hidden_repeats))
    result.sort(key=lambda item: (item.label.casefold(), item.key))
    return tuple(result)


def build_snapshot(
    patient_id: str,
    records: Iterable[MeasurementRecord],
    *,
    locked_only: bool = False,
) -> LongitudinalSnapshot:
    return LongitudinalSnapshot(
        patient_id=str(patient_id or ""),
        series=build_longitudinal_series(records, locked_only=locked_only),
        locked_only=locked_only,
    )

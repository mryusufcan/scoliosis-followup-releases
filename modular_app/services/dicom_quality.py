from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from dicom.validation import validate_dicom_file


@dataclass(frozen=True)
class DicomQualityItem:
    source: Path
    valid: bool
    errors: tuple[str, ...]
    warnings: tuple[str, ...]
    modality: str = ""
    frames: int = 0
    bits_allocated: int = 0
    dimensions: str = ""
    transfer_syntax: str = ""
    compression_status: str = ""


def inspect_dicom_paths(paths: Iterable[str | Path]) -> list[DicomQualityItem]:
    """Run the existing validator over local files without importing or editing them."""
    items: list[DicomQualityItem] = []
    for raw_path in paths:
        source = Path(raw_path)
        result = validate_dicom_file(source)
        details = result.details
        rows, columns = details.get("rows", 0), details.get("columns", 0)
        items.append(DicomQualityItem(
            source=source,
            valid=bool(result.valid),
            errors=tuple(result.errors),
            warnings=tuple(result.warnings),
            modality=str(details.get("modality", "")),
            frames=int(details.get("frames", 0) or 0),
            bits_allocated=int(details.get("bits_allocated", 0) or 0),
            dimensions=f"{columns} × {rows}" if rows and columns else "",
            transfer_syntax=str(details.get("transfer_syntax_name", "")),
            compression_status=str(details.get("compression_status", "")),
        ))
    return items


def quality_summary(items: Iterable[DicomQualityItem]) -> tuple[int, int, int]:
    rows = list(items)
    valid = sum(1 for item in rows if item.valid)
    warnings = sum(1 for item in rows if item.warnings)
    return valid, len(rows) - valid, warnings


def export_dicom_quality_csv(items: Iterable[DicomQualityItem], destination: str | Path) -> Path:
    """Write a technical report that contains file names, never patient tags."""
    output = Path(destination)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=[
            "Dosya", "Durum", "Modalite", "Boyut", "Kare", "Bit", "Aktarım Türü", "Sıkıştırma", "Hatalar", "Uyarılar",
        ])
        writer.writeheader()
        for item in items:
            writer.writerow({
                "Dosya": item.source.name,
                "Durum": "Geçerli" if item.valid else "Geçersiz",
                "Modalite": item.modality,
                "Boyut": item.dimensions,
                "Kare": item.frames,
                "Bit": item.bits_allocated,
                "Aktarım Türü": item.transfer_syntax,
                "Sıkıştırma": item.compression_status,
                "Hatalar": " | ".join(item.errors),
                "Uyarılar": " | ".join(item.warnings),
            })
    return output

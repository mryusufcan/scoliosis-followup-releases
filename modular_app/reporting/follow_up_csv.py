from __future__ import annotations

import csv
from pathlib import Path

from modular_app.database.exam_repository import ExamRepository
from modular_app.services.measurement_labels import display_measurement_source


CSV_HEADERS = [
    "Kayıt türü", "Hasta ID", "Hasta adı", "Tetkik tarihi", "Görüntü dosyası", "Bölge", "Modalite",
    "Tetkik açıklaması", "Cobb tarafı", "Cobb açısı (°)", "Doğrulama durumu", "Doğrulayan", "Kayıt zamanı",
]


def export_follow_up_csv(
    repository: ExamRepository,
    patient_id: str,
    patient_name: str,
    destination: str | Path,
) -> tuple[Path, int, int]:
    """Export the selected patient's local follow-up records as Excel-friendly CSV.

    Internal source paths and pixel data are deliberately never written to the
    CSV.  The recipient still receives patient identifiers, so this is limited
    to clinician/administrator roles by the UI.
    """
    output = Path(destination)
    output.parent.mkdir(parents=True, exist_ok=True)
    exams = repository.list_patient_follow_up(patient_id)
    measurements = list(reversed(repository.list_cobb_measurements(patient_id)))
    image_notes = list(reversed(repository.list_image_notes(patient_id)))
    with output.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_HEADERS)
        writer.writeheader()
        for exam in exams:
            latest = exam.get("latest_cobb")
            writer.writerow({
                "Kayıt türü": "Tetkik", "Hasta ID": patient_id, "Hasta adı": patient_name,
                "Tetkik tarihi": exam.get("exam_date", ""), "Görüntü dosyası": Path(str(exam.get("dicom_path", ""))).name,
                "Bölge": exam.get("body_part", ""), "Modalite": exam.get("modality", ""),
                "Tetkik açıklaması": exam.get("study_description", ""),
                "Cobb açısı (°)": "" if latest is None else f"{float(latest):.2f}",
                "Doğrulama durumu": "Kilitli" if bool(exam.get("latest_cobb_locked")) else ("Taslak" if latest is not None else ""),
            })
        for measurement in measurements:
            writer.writerow({
                "Kayıt türü": "Cobb ölçümü", "Hasta ID": patient_id, "Hasta adı": patient_name,
                "Tetkik tarihi": measurement.get("exam_date", ""),
                "Görüntü dosyası": Path(str(measurement.get("dicom_path", ""))).name,
                "Cobb tarafı": display_measurement_source(measurement.get("side", "")),
                "Cobb açısı (°)": f"{float(measurement.get('angle_degrees', 0.0)):.2f}",
                "Doğrulama durumu": "Kilitli" if bool(measurement.get("is_locked")) else "Taslak",
                "Doğrulayan": measurement.get("verified_by", ""), "Kayıt zamanı": measurement.get("created_at", ""),
            })
        for note in image_notes:
            writer.writerow({
                "Kayıt türü": "Görüntü notu", "Hasta ID": patient_id, "Hasta adı": patient_name,
                "Görüntü dosyası": Path(str(note.get("dicom_path", ""))).name,
                "Tetkik açıklaması": note.get("note", ""),
                "Doğrulayan": note.get("created_by", ""), "Kayıt zamanı": note.get("created_at", ""),
            })
    return output, len(exams), len(measurements)

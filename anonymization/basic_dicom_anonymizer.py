from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


class AnonymizationError(RuntimeError):
    """Raised when a local, non-destructive anonymized copy cannot be made."""


@dataclass(frozen=True)
class AnonymizedDicom:
    source: Path
    output: Path
    pseudonym: str


# These are direct identifiers or direct contact/clinical-account references.
# The list is intentionally explicit: it must not accidentally remove useful
# acquisition tags such as PatientPosition or ImageOrientationPatient.
_REMOVE_KEYWORDS = {
    "AccessionNumber", "AdditionalPatientHistory", "AdmissionID", "AdmittingDiagnosesDescription",
    "CurrentPatientLocation", "InstitutionAddress", "InstitutionName", "InstitutionalDepartmentName",
    "MedicalRecordLocator", "MilitaryRank", "Occupation", "OtherPatientIDs", "OtherPatientIDsSequence",
    "OtherPatientNames", "PatientAddress", "PatientBirthDate", "PatientBirthTime", "PatientComments",
    "PatientMotherBirthName", "PatientSex", "PatientTelephoneNumbers", "PatientWeight", "PatientSize",
    "PatientAge", "PatientInsurancePlanCodeSequence", "PatientPrimaryLanguageCodeSequence",
    "PatientReligiousPreference", "PerformingPhysicianName", "PerformingPhysicianIdentificationSequence",
    "PhysiciansOfRecord", "PhysiciansOfRecordIdentificationSequence", "ReferringPhysicianName",
    "ReferringPhysicianIdentificationSequence", "RequestingPhysician", "RequestingService",
    "ScheduledPerformingPhysicianName", "ScheduledProcedureStepDescription", "ScheduledStationName",
    "StationName", "StudyID", "StudyComments", "StudyDescription", "OperatorsName", "ProtocolName",
    "DeviceSerialNumber", "IssuerOfPatientID", "IssuerOfPatientIDQualifiersSequence",
}

_CLEAR_DATE_TIME_KEYWORDS = {
    "AcquisitionDate", "AcquisitionDateTime", "AcquisitionTime", "ContentDate", "ContentTime",
    "InstanceCreationDate", "InstanceCreationTime", "SeriesDate", "SeriesTime", "StudyDate", "StudyTime",
    "PerformedProcedureStepStartDate", "PerformedProcedureStepStartTime",
    "PerformedProcedureStepEndDate", "PerformedProcedureStepEndTime",
}

_REMAP_UID_KEYWORDS = {
    "StudyInstanceUID", "SeriesInstanceUID", "SOPInstanceUID", "FrameOfReferenceUID",
    "ReferencedSOPInstanceUID", "ReferencedSeriesInstanceUID", "ReferencedFrameOfReferenceUID",
}


def _anonymize_dataset(dataset, pseudonym: str, uid_map: dict[str, str]) -> None:
    from pydicom.uid import generate_uid

    for element in list(dataset):
        if element.VR == "SQ":
            for item in element.value:
                _anonymize_dataset(item, pseudonym, uid_map)
        keyword = element.keyword
        if element.tag.is_private or keyword in _REMOVE_KEYWORDS:
            del dataset[element.tag]
            continue
        if keyword in _CLEAR_DATE_TIME_KEYWORDS:
            element.value = ""
            continue
        if keyword in _REMAP_UID_KEYWORDS and str(element.value).strip():
            original = str(element.value)
            element.value = uid_map.setdefault(original, generate_uid())

    dataset.PatientName = pseudonym.replace("-", "^")
    dataset.PatientID = pseudonym
    dataset.PatientIdentityRemoved = "YES"
    # DeidentificationMethod, DICOM'da LO (en fazla 64 karakter) tipindedir.
    # Kısa tutmak pydicom uyarısını ve standart dışı çıktı oluşmasını engeller.
    dataset.DeidentificationMethod = "Local de-identification; identifiers and private tags removed"
    # Pixel data is retained verbatim. Never state that possible burned-in text
    # has been removed when this utility has not analysed pixels.
    dataset.BurnedInAnnotation = "UNSPECIFIED"

    # File meta has a second copy of the SOP Instance UID and must agree with
    # the dataset when it is present.
    if getattr(dataset, "SOPInstanceUID", None):
        dataset.file_meta.MediaStorageSOPInstanceUID = dataset.SOPInstanceUID


def anonymize_dicom_files(
    paths: Iterable[str | Path],
    destination_dir: str | Path,
) -> list[AnonymizedDicom]:
    """Write de-identified copies without altering any original DICOM.

    Each source patient gets a neutral, sequential pseudonym within this one
    export.  Study/series/instance UIDs are regenerated consistently across
    the supplied batch, so selected images continue to belong together.
    """
    try:
        import pydicom
    except ImportError as exc:
        raise AnonymizationError("Anonimleştirme için pydicom paketi kurulu olmalıdır.") from exc

    sources = [Path(path) for path in paths if Path(path).is_file()]
    if not sources:
        raise AnonymizationError("Anonimleştirilecek geçerli DICOM dosyası seçilmedi.")
    target = Path(destination_dir)
    target.mkdir(parents=True, exist_ok=True)
    expected_outputs = [target / f"anonim_{index:03d}.dcm" for index, _source in enumerate(sources, start=1)]
    existing = [path.name for path in expected_outputs if path.exists()]
    if existing:
        raise AnonymizationError(
            "Hedef klasörde aynı adlı anonim kopya zaten var (" + ", ".join(existing[:3]) + "). "
            "Yeni veya boş bir klasör seçin; mevcut dosyalar asla üzerine yazılmaz."
        )
    patient_map: dict[str, str] = {}
    uid_map: dict[str, str] = {}
    results: list[AnonymizedDicom] = []

    for index, source in enumerate(sources, start=1):
        try:
            dataset = pydicom.dcmread(str(source), force=False)
        except Exception as exc:
            raise AnonymizationError(f"{source.name} okunamadı: {exc}") from exc
        original_patient = str(getattr(dataset, "PatientID", "") or getattr(dataset, "PatientName", "") or "UNKNOWN")
        pseudonym = patient_map.setdefault(original_patient, f"ANON-{len(patient_map) + 1:03d}")
        _anonymize_dataset(dataset, pseudonym, uid_map)
        output = expected_outputs[index - 1]
        try:
            dataset.save_as(str(output), enforce_file_format=True)
        except Exception as exc:
            raise AnonymizationError(f"{source.name} için anonim kopya yazılamadı: {exc}") from exc
        results.append(AnonymizedDicom(source=source, output=output, pseudonym=pseudonym))
    return results


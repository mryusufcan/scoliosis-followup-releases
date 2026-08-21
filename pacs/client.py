from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PacsConfig:
    host: str
    port: int
    called_ae_title: str
    calling_ae_title: str = "SCOLIOSIS_APP"
    timeout_seconds: float = 15.0


class PacsError(RuntimeError):
    pass


def validate_config(config: PacsConfig) -> None:
    """Reject malformed association settings before opening a network socket."""
    if not str(config.host).strip():
        raise PacsError("PACS IP/sunucu bilgisi zorunludur.")
    try:
        port = int(config.port)
        timeout = float(config.timeout_seconds)
    except (TypeError, ValueError):
        raise PacsError("PACS portu ve zaman aşımı sayısal olmalıdır.") from None
    if not 1 <= port <= 65535:
        raise PacsError("PACS portu 1 ile 65535 arasında olmalıdır.")
    if not 1 <= len(str(config.called_ae_title).strip()) <= 16:
        raise PacsError("Called AE Title 1-16 karakter olmalıdır.")
    if not 1 <= len(str(config.calling_ae_title).strip()) <= 16:
        raise PacsError("Calling AE Title 1-16 karakter olmalıdır.")
    if not 1 <= timeout <= 120:
        raise PacsError("PACS zaman aşımı 1-120 saniye arasında olmalıdır.")


def _dependencies():
    try:
        from pynetdicom import AE, StoragePresentationContexts, evt
        from pynetdicom.sop_class import StudyRootQueryRetrieveInformationModelFind, StudyRootQueryRetrieveInformationModelGet
        return AE, StoragePresentationContexts, evt, StudyRootQueryRetrieveInformationModelFind, StudyRootQueryRetrieveInformationModelGet
    except ImportError as exc:
        raise PacsError("pynetdicom kurulu değil. requirements.txt bağımlılıklarını yükleyin.") from exc


def test_connection(config: PacsConfig) -> None:
    """DICOM association ile ağ/AE Title ayarını hasta verisi sorgulamadan doğrular."""
    validate_config(config)
    AE, _, _, _, _ = _dependencies()
    ae = AE(ae_title=config.calling_ae_title)
    ae.acse_timeout = float(config.timeout_seconds)
    ae.dimse_timeout = float(config.timeout_seconds)
    ae.network_timeout = float(config.timeout_seconds)
    association = ae.associate(config.host, int(config.port), ae_title=config.called_ae_title)
    if not association.is_established:
        raise PacsError("PACS bağlantısı kurulamadı. IP, port ve AE Title bilgilerini kontrol edin.")
    association.release()


def query_studies(config: PacsConfig, patient_id: str = "", patient_name: str = "", study_date: str = "") -> list[dict[str, str]]:
    validate_config(config)
    AE, _, _, FindModel, _ = _dependencies()
    from pydicom.dataset import Dataset
    ae = AE(ae_title=config.calling_ae_title)
    ae.add_requested_context(FindModel)
    association = ae.associate(config.host, int(config.port), ae_title=config.called_ae_title)
    if not association.is_established:
        raise PacsError("PACS bağlantısı kurulamadı. IP, port ve AE Title bilgilerini kontrol edin.")
    request = Dataset()
    request.QueryRetrieveLevel = "STUDY"
    request.PatientID = patient_id
    request.PatientName = patient_name
    request.StudyDate = study_date
    for field in ("StudyInstanceUID", "StudyDescription", "ModalitiesInStudy", "StudyDate", "AccessionNumber"):
        setattr(request, field, "")
    rows = []
    try:
        for status, identifier in association.send_c_find(request, FindModel):
            if status and status.Status in (0xFF00, 0xFF01) and identifier:
                rows.append({field: str(getattr(identifier, field, "")) for field in (
                    "PatientID", "PatientName", "StudyDate", "StudyDescription", "ModalitiesInStudy", "StudyInstanceUID",
                )})
    finally:
        association.release()
    return rows


def retrieve_study(config: PacsConfig, study_instance_uid: str, destination: str | Path) -> list[Path]:
    validate_config(config)
    if not str(study_instance_uid).strip():
        raise PacsError("Alınacak tetkik için Study Instance UID eksik.")
    AE, StorageContexts, evt, _, GetModel = _dependencies()
    from pydicom.dataset import Dataset
    target = Path(destination); target.mkdir(parents=True, exist_ok=True)
    saved: list[Path] = []

    def handle_store(event):
        dataset = event.dataset; dataset.file_meta = event.file_meta
        path = target / f"{getattr(dataset, 'SOPInstanceUID', 'image')}.dcm"
        dataset.save_as(str(path), enforce_file_format=True)
        saved.append(path)
        return 0x0000

    ae = AE(ae_title=config.calling_ae_title)
    ae.add_requested_context(GetModel)
    for context in StorageContexts:
        ae.add_supported_context(context.abstract_syntax, context.transfer_syntax)
    association = ae.associate(config.host, int(config.port), ae_title=config.called_ae_title, evt_handlers=[(evt.EVT_C_STORE, handle_store)])
    if not association.is_established:
        raise PacsError("PACS bağlantısı kurulamadı. IP, port ve AE Title bilgilerini kontrol edin.")
    request = Dataset(); request.QueryRetrieveLevel = "STUDY"; request.StudyInstanceUID = study_instance_uid
    try:
        statuses = list(association.send_c_get(request, GetModel))
        if not statuses or not any(status and status.Status in (0x0000, 0xB000) for status, _ in statuses):
            raise PacsError("PACS tetkiki gönderemedi veya C-GET desteklemiyor.")
    finally:
        association.release()
    return saved


def send_dicom(config: PacsConfig, path: str | Path) -> None:
    validate_config(config)
    try:
        import pydicom
    except ImportError as exc:
        raise PacsError("pydicom kurulu değil.") from exc
    AE, _, _, _, _ = _dependencies()
    dataset = pydicom.dcmread(str(path))
    ae = AE(ae_title=config.calling_ae_title)
    ae.add_requested_context(dataset.SOPClassUID, getattr(dataset.file_meta, "TransferSyntaxUID", None))
    association = ae.associate(config.host, int(config.port), ae_title=config.called_ae_title)
    if not association.is_established:
        raise PacsError("PACS bağlantısı kurulamadı. IP, port ve AE Title bilgilerini kontrol edin.")
    try:
        status = association.send_c_store(dataset)
        if not status or status.Status != 0x0000:
            raise PacsError(f"PACS C-STORE başarısız: {getattr(status, 'Status', 'bilinmiyor')}")
    finally:
        association.release()


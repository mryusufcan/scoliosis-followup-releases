"""Describe DICOM pixel transfer syntax support without decoding an image.

The viewer itself relies on pydicom's current ``pixels`` backend.  This module
only gives the import/quality layers a stable, Turkish explanation before an
unsupported compressed image reaches the viewer.
"""

from __future__ import annotations

import importlib.util
from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class TransferSyntaxSupport:
    uid: str
    name: str
    known: bool
    compressed: bool
    lossy: bool
    supported: bool
    required_modules: tuple[tuple[str, ...], ...] = ()
    present_modules: tuple[str, ...] = ()

    @property
    def status(self) -> str:
        if not self.known:
            return "Bilinmeyen"
        if not self.compressed:
            return "Sıkıştırılmamış"
        if self.supported:
            return "Çözücü hazır"
        return "Çözücü eksik"

    @property
    def explanation(self) -> str:
        if not self.known:
            return "Aktarım türü tanınmıyor; pydicom piksel verisini çözmeyi deneyecek."
        if not self.compressed:
            return "Sıkıştırılmamış DICOM piksel verisi."
        if self.supported:
            text = "Sıkıştırılmış DICOM için uygun çözücü hazır."
            if self.lossy:
                text += " Kayıplı sıkıştırılmış kaynak görüntü; klinik yorumu kaynak kaliteyle birlikte değerlendirin."
            return text
        alternatives = []
        for group in self.required_modules:
            alternatives.append(" + ".join(group))
        requirement = " veya ".join(alternatives) or "uygun pydicom çözücüsü"
        return f"Bu DICOM aktarım türü için çözücü eksik ({requirement}). Uygulamayı güncel paketle yeniden kurun."


@dataclass(frozen=True)
class _SyntaxSpec:
    name: str
    compressed: bool
    lossy: bool = False
    # A module group represents one valid decoder choice.  Any complete group
    # allows pydicom to decode the syntax.
    decoder_groups: tuple[tuple[str, ...], ...] = ()


_SPECS: dict[str, _SyntaxSpec] = {
    "1.2.840.10008.1.2": _SyntaxSpec("Implicit VR Little Endian", False),
    "1.2.840.10008.1.2.1": _SyntaxSpec("Explicit VR Little Endian", False),
    "1.2.840.10008.1.2.1.99": _SyntaxSpec("Deflated Explicit VR Little Endian", False),
    "1.2.840.10008.1.2.2": _SyntaxSpec("Explicit VR Big Endian", False),
    "1.2.840.10008.1.2.5": _SyntaxSpec("RLE Lossless", True),
    "1.2.840.10008.1.2.4.50": _SyntaxSpec("JPEG Baseline 8-bit", True, True, (("libjpeg",),)),
    "1.2.840.10008.1.2.4.51": _SyntaxSpec("JPEG Extended 12-bit", True, True, (("libjpeg",),)),
    "1.2.840.10008.1.2.4.57": _SyntaxSpec("JPEG Lossless Process 14", True, False, (("libjpeg",),)),
    "1.2.840.10008.1.2.4.70": _SyntaxSpec("JPEG Lossless Process 14 SV1", True, False, (("libjpeg",),)),
    "1.2.840.10008.1.2.4.80": _SyntaxSpec("JPEG-LS Lossless", True, False, (("libjpeg",), ("jpeg_ls",))),
    "1.2.840.10008.1.2.4.81": _SyntaxSpec("JPEG-LS Near Lossless", True, True, (("libjpeg",), ("jpeg_ls",))),
    "1.2.840.10008.1.2.4.90": _SyntaxSpec("JPEG 2000 Lossless", True, False, (("openjpeg",),)),
    "1.2.840.10008.1.2.4.91": _SyntaxSpec("JPEG 2000", True, True, (("openjpeg",),)),
    "1.2.840.10008.1.2.4.201": _SyntaxSpec("HTJ2K Lossless", True, False, (("openjpeg",),)),
    "1.2.840.10008.1.2.4.202": _SyntaxSpec("HTJ2K Lossless RPCL", True, False, (("openjpeg",),)),
    "1.2.840.10008.1.2.4.203": _SyntaxSpec("HTJ2K", True, True, (("openjpeg",),)),
}


def _available_modules(modules: Iterable[str] | None = None) -> set[str]:
    if modules is not None:
        return {str(item) for item in modules}
    candidates = {module for spec in _SPECS.values() for group in spec.decoder_groups for module in group}
    return {module for module in candidates if importlib.util.find_spec(module) is not None}


def get_transfer_syntax_support(uid: object, *, available_modules: Iterable[str] | None = None) -> TransferSyntaxSupport:
    """Return codec availability for a DICOM Transfer Syntax UID.

    Unknown transfer syntaxes are not rejected here: pydicom may support a
    future syntax natively. Pixel decoding remains the final authority.
    """
    value = str(uid or "").strip()
    spec = _SPECS.get(value)
    if spec is None:
        return TransferSyntaxSupport(
            uid=value or "Bilinmiyor",
            name="Bilinmeyen aktarım türü",
            known=False,
            compressed=False,
            lossy=False,
            supported=True,
        )
    available = _available_modules(available_modules)
    present = tuple(sorted(available))
    supported = not spec.compressed or not spec.decoder_groups or any(
        all(module in available for module in group) for group in spec.decoder_groups
    )
    return TransferSyntaxSupport(
        uid=value,
        name=spec.name,
        known=True,
        compressed=spec.compressed,
        lossy=spec.lossy,
        supported=supported,
        required_modules=spec.decoder_groups,
        present_modules=present,
    )


def dataset_transfer_syntax_support(dataset, *, available_modules: Iterable[str] | None = None) -> TransferSyntaxSupport:
    file_meta = getattr(dataset, "file_meta", None)
    return get_transfer_syntax_support(getattr(file_meta, "TransferSyntaxUID", ""), available_modules=available_modules)

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import pydicom
from pydicom.pixels import get_decoder, pixel_array
from pydicom.uid import UID


# pydicom plugin names are logical decoder plugins. The pylibjpeg entry selects
# the appropriate installed backend, such as libjpeg or OpenJPEG.
PREFERRED_PLUGINS: dict[str, tuple[str, ...]] = {
    "1.2.840.10008.1.2.4.50": ("pylibjpeg", "pillow"),
    "1.2.840.10008.1.2.4.51": ("pylibjpeg", "pillow"),
    "1.2.840.10008.1.2.4.57": ("pylibjpeg", "pillow"),
    "1.2.840.10008.1.2.4.70": ("pylibjpeg", "pillow"),
    "1.2.840.10008.1.2.4.80": ("pyjpegls", "pylibjpeg", "gdcm"),
    "1.2.840.10008.1.2.4.81": ("pyjpegls", "pylibjpeg", "gdcm"),
    "1.2.840.10008.1.2.4.90": ("pylibjpeg", "pillow", "gdcm"),
    "1.2.840.10008.1.2.4.91": ("pylibjpeg", "pillow", "gdcm"),
    "1.2.840.10008.1.2.4.201": ("pylibjpeg", "gdcm"),
    "1.2.840.10008.1.2.4.202": ("pylibjpeg", "gdcm"),
    "1.2.840.10008.1.2.4.203": ("pylibjpeg", "gdcm"),
    "1.2.840.10008.1.2.5": ("pylibjpeg", "gdcm"),
}


@dataclass(frozen=True)
class CodecStatus:
    transfer_syntax_uid: str
    transfer_syntax_name: str
    compressed: bool
    available_plugins: tuple[str, ...]
    missing_dependencies: tuple[str, ...]
    selected_plugin: str | None


def codec_status(transfer_syntax_uid: str) -> CodecStatus:
    uid = str(transfer_syntax_uid or "")
    try:
        transfer = UID(uid)
        name = str(getattr(transfer, "name", "") or uid)
        compressed = bool(transfer.is_compressed)
    except Exception:
        name = uid
        compressed = False
    try:
        decoder = get_decoder(uid)
        available = tuple(str(item) for item in decoder.available_plugins)
        missing = tuple(str(item) for item in decoder.missing_dependencies)
    except Exception as exc:
        available = ()
        missing = (str(exc),)
    return CodecStatus(
        transfer_syntax_uid=uid,
        transfer_syntax_name=name,
        compressed=compressed,
        available_plugins=available,
        missing_dependencies=missing,
        selected_plugin=_select_from_available(uid, available),
    )


def _select_from_available(uid: str, available: tuple[str, ...]) -> str | None:
    if not available:
        return None
    for candidate in PREFERRED_PLUGINS.get(str(uid), ("pylibjpeg", "pyjpegls", "gdcm", "pillow")):
        if candidate in available:
            return candidate
    return available[0]


def preferred_decoding_plugin(transfer_syntax_uid: str) -> str | None:
    """Return a known installed native/plugin route, or None for auto selection."""
    return codec_status(transfer_syntax_uid).selected_plugin


def decode_pixel_array(path: str, *, index: int, transfer_syntax_uid: str = "") -> Any:
    """Decode one frame with a preferred plugin and a pydicom fallback.

    The fallback is intentionally automatic rather than a second hard-coded
    codec. It preserves pydicom's compatibility behavior for unusual samples,
    while the first attempt makes the installed native route deterministic.
    """
    plugin = preferred_decoding_plugin(transfer_syntax_uid) if transfer_syntax_uid else None
    kwargs: dict[str, Any] = {"index": int(index)}
    if plugin:
        kwargs["decoding_plugin"] = plugin
    try:
        return pixel_array(path, **kwargs)
    except Exception as preferred_error:
        if not plugin:
            raise
        try:
            return pixel_array(path, index=int(index))
        except Exception as fallback_error:
            raise preferred_error from fallback_error


def codec_status_dict(transfer_syntax_uid: str) -> dict[str, Any]:
    return asdict(codec_status(transfer_syntax_uid))


__all__ = [
    "CodecStatus",
    "PREFERRED_PLUGINS",
    "codec_status",
    "codec_status_dict",
    "decode_pixel_array",
    "preferred_decoding_plugin",
]

"""Verify a built release before it is sent to another computer.

The check is read-only: it never starts the installer, changes user data, or
contacts a PACS.  It verifies the frozen distribution, installer hash and the
locally generated signed update feed.  A public HTTPS feed can optionally be
checked against the same release information.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from urllib.request import Request, urlopen


class ReleaseVerificationError(RuntimeError):
    pass


REQUIRED_DISTRIBUTION_PATTERNS = {
    "application version metadata": "_internal/VERSION",
    "JPEG Lossless decoder": "_internal/_libjpeg*.pyd",
    "JPEG 2000 decoder": "_internal/_openjpeg*.pyd",
    "JPEG-LS decoder": "_internal/_CharLS*.pyd",
    "RLE decoder": "_internal/rle/rle*.pyd",
    "ONNX Runtime": "_internal/onnxruntime/capi/onnxruntime.dll",
    "experimental landmark model": "_internal/resources/ai/vertebra_landmarks_experimental/vertebra_landmarks_68.onnx",
}

FORBIDDEN_DISTRIBUTION_PATHS = (
    "_internal/PySide6/Qt6WebEngineCore.dll",
    "_internal/PySide6/Qt63DCore.dll",
    "_internal/PySide6/qml",
    "_internal/pyqtgraph/examples",
    "_internal/pynetdicom/tests",
    "_internal/onnxruntime/tools",
)


def verify_distribution_contents(distribution: Path) -> None:
    """Reject a package that lost clinical codecs or regained known bloat."""
    missing = [
        label
        for label, pattern in REQUIRED_DISTRIBUTION_PATTERNS.items()
        if not any(distribution.glob(pattern))
    ]
    if missing:
        raise ReleaseVerificationError(
            "Dağıtımda zorunlu çalışma bileşenleri eksik: " + ", ".join(missing)
        )
    unexpected = [relative for relative in FORBIDDEN_DISTRIBUTION_PATHS if (distribution / relative).exists()]
    if unexpected:
        raise ReleaseVerificationError(
            "Dağıtıma gereksiz büyük geliştirme bileşenleri yeniden eklenmiş: " + ", ".join(unexpected)
        )


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReleaseVerificationError(f"JSON dosyası okunamadı: {path}") from exc
    if not isinstance(payload, dict):
        raise ReleaseVerificationError(f"JSON nesnesi geçersiz: {path}")
    return payload


def verify_feed(payload: dict, expected_version: str, installer: Path) -> tuple[str, str, str]:
    from modular_app.services.system_services import verify_update_feed

    version, download_url, expected_hash = verify_update_feed(payload)
    if version != expected_version:
        raise ReleaseVerificationError(
            f"Güncelleme bildirimi sürümü ({version}), uygulama sürümüyle ({expected_version}) eşleşmiyor."
        )
    actual_hash = sha256(installer)
    if expected_hash.lower() != actual_hash.lower():
        raise ReleaseVerificationError("Güncelleme bildirimindeki SHA-256 özeti kurulum dosyasıyla eşleşmiyor.")
    return version, download_url, expected_hash


def fetch_json(url: str) -> dict:
    if not url.lower().startswith("https://"):
        raise ReleaseVerificationError("Uzak güncelleme adresi HTTPS ile başlamalıdır.")
    request = Request(url, headers={"User-Agent": "ScoliosisFollowUp-ReleaseCheck/1"})
    try:
        with urlopen(request, timeout=15) as response:
            raw = response.read()
    except OSError as exc:
        raise ReleaseVerificationError(f"Uzak güncelleme bildirimi alınamadı: {exc}") from exc
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReleaseVerificationError("Uzak adres imzalı update.json içeriği döndürmüyor.") from exc
    if not isinstance(payload, dict):
        raise ReleaseVerificationError("Uzak update.json içeriği geçersiz.")
    return payload


def verify_release(root: Path, installer: Path, feed: Path, feed_url: str = "") -> None:
    source_root = root.resolve()
    sys.path[:0] = [str(source_root / "modular_app"), str(source_root)]
    from modular_app.security.integrity import verify_distribution_integrity
    from modular_app.services.system_services import APP_VERSION

    version = (source_root / "VERSION").read_text(encoding="utf-8").strip()
    if APP_VERSION != version:
        raise ReleaseVerificationError("Uygulama sürümü ile VERSION dosyası eşleşmiyor.")
    distribution = source_root / "dist" / "ScoliosisFollowUp"
    executable = distribution / "ScoliosisFollowUp.exe"
    if not executable.is_file():
        raise ReleaseVerificationError("Dağıtım EXE dosyası bulunamadı; önce EXE paketini oluşturun.")
    if not installer.is_file():
        raise ReleaseVerificationError("Kurulum dosyası bulunamadı; önce kurulum paketini oluşturun.")
    if not feed.is_file():
        raise ReleaseVerificationError("Yerel update.json bulunamadı; önce imzalı güncelleme bildirimi oluşturun.")

    verify_distribution_contents(distribution)

    # Yayın kabul denetiminde performans önbelleği kullanılmaz; dağıtımın tüm
    # dosyaları her zaman yeniden özetlenir.
    integrity = verify_distribution_integrity(distribution, frozen=True, force_full=True)
    if not integrity.allowed:
        raise ReleaseVerificationError(f"Dağıtım bütünlüğü doğrulanamadı: {integrity.message}")
    manifest = read_json(distribution / "runtime_integrity.json")
    if str(manifest.get("version", "")) != version:
        raise ReleaseVerificationError("Dağıtım bütünlük manifest'i uygulama sürümüyle eşleşmiyor.")

    local = verify_feed(read_json(feed), version, installer)
    print(f"Bütünlük doğrulandı: {executable.name}")
    print(f"Kurulum özeti doğrulandı: {installer.name}")
    print(f"Yerel güncelleme bildirimi doğrulandı: {local[0]}")

    if feed_url.strip():
        remote = verify_feed(fetch_json(feed_url.strip()), version, installer)
        if remote != local:
            raise ReleaseVerificationError("Yayınlanan update.json yerel imzalı bildirimle eşleşmiyor.")
        print("Yayınlanan HTTPS güncelleme bildirimi doğrulandı.")


def main() -> int:
    default_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="Scoliosis Follow-Up dağıtım kabul denetimi")
    parser.add_argument("--root", type=Path, default=default_root)
    parser.add_argument("--installer", type=Path, default=None)
    parser.add_argument("--feed", type=Path, default=None)
    parser.add_argument("--feed-url", default="", help="İsteğe bağlı, yayınlanmış HTTPS update.json adresi")
    args = parser.parse_args()
    root = args.root.resolve()
    installer = (args.installer or root / "installer" / "ScoliosisFollowUp_Setup.exe").resolve()
    feed = (args.feed or root / "update.json").resolve()
    try:
        verify_release(root, installer, feed, args.feed_url)
    except (OSError, ReleaseVerificationError) as exc:
        print(f"KABUL DENETİMİ BAŞARISIZ: {exc}", file=sys.stderr)
        return 2
    print("KABUL DENETİMİ BAŞARILI: Dağıtım göndermeye hazır.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Açılışta uygulanan lisans, çevrimdışı süre ve cihaz-bağlı trial politikası."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
import os
from pathlib import Path
from typing import Callable

OFFLINE_GRACE_PERIOD = timedelta(hours=6)
TRIAL_PERIOD = timedelta(days=14)
CLOCK_TOLERANCE = timedelta(minutes=5)

MACHINE_STATE_DIR = Path(
    os.environ.get("PROGRAMDATA")
    or os.environ.get("LOCALAPPDATA")
    or str(Path.home())
) / "ScoliosisFollowUp"

MACHINE_STATE_FILE = MACHINE_STATE_DIR / ".license_state.json"


@dataclass(frozen=True)
class LicenseGateResult:
    allowed: bool
    mode: str
    message: str
    remaining: timedelta | None = None
    expires_at: str | None = None


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def _format_remaining(value: timedelta) -> str:
    seconds = max(0, int(value.total_seconds()))
    hours, remainder = divmod(seconds, 3600)
    minutes = remainder // 60
    return f"{hours} saat {minutes} dk"


def _store_now(repository, key: str, now: datetime) -> None:
    repository.set_setting(key, now.isoformat())


def _get_hwid() -> str:
    from license_app import get_hwid
    return str(get_hwid())


def _signature(payload: dict, hwid: str) -> str:
    body = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    key = hashlib.sha256(
        ("ScoliosisFollowUp|trial-state|" + hwid).encode("utf-8")
    ).digest()
    return hmac.new(key, body, hashlib.sha256).hexdigest()


def _read_machine_state() -> tuple[dict | None, str | None]:
    if not MACHINE_STATE_FILE.exists():
        return None, None
    try:
        envelope = json.loads(
            MACHINE_STATE_FILE.read_text(encoding="utf-8")
        )
        payload = envelope.get("payload")
        sig = str(envelope.get("signature", ""))

        if not isinstance(payload, dict):
            return None, "invalid"

        hwid = _get_hwid()
        if not hwid or payload.get("hwid") != hwid:
            return None, "machine_mismatch"

        if not hmac.compare_digest(sig, _signature(payload, hwid)):
            return None, "tampered"

        return payload, None
    except Exception:
        return None, "invalid"


def _write_machine_state(
    trial_started: datetime,
    last_seen: datetime,
    *,
    server_synced: bool,
) -> None:
    hwid = _get_hwid()
    payload = {
        "schema": 2,
        "hwid": hwid,
        "trial_started_at": trial_started.isoformat(),
        "last_seen_at": last_seen.isoformat(),
        "server_synced": bool(server_synced),
    }
    envelope = {
        "payload": payload,
        "signature": _signature(payload, hwid),
    }

    MACHINE_STATE_DIR.mkdir(parents=True, exist_ok=True)
    temp = MACHINE_STATE_FILE.with_suffix(".tmp")
    temp.write_text(
        json.dumps(envelope, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temp.replace(MACHINE_STATE_FILE)


def _clock_is_valid(repository, now: datetime, machine_state: dict | None) -> bool:
    candidates = [
        _parse_timestamp(repository.get_setting("license/last_seen_at", "")),
        _parse_timestamp((machine_state or {}).get("last_seen_at")),
    ]
    last_seen = max(
        (item for item in candidates if item is not None),
        default=None,
    )
    if last_seen is not None and now + CLOCK_TOLERANCE < last_seen:
        return False

    if last_seen is None or now > last_seen:
        _store_now(repository, "license/last_seen_at", now)

    return True


def _server_trial_status(trial_checker=None):
    if trial_checker is None:
        from license_app import check_or_create_device_trial
        trial_checker = check_or_create_device_trial
    try:
        return trial_checker()
    except Exception:
        return None


def evaluate_license_gate(
    repository,
    checker: Callable[[], object] | None = None,
    now: datetime | None = None,
    trial_checker: Callable[[], object] | None = None,
) -> LicenseGateResult:
    """Fail-closed lisans kapısı.

    - Etkin lisans: normal kullanım.
    - Daha önce çevrimiçi doğrulanmış lisans: en fazla 6 saat offline grace.
    - Lisanssız cihaz: trial ilk kez MUTLAKA sunucudan başlar.
    - DB/AppData silinse bile sunucudaki HWID trial tarihi esas alınır.
    - Yerel state manipülasyonu veya saat geri alma erişimi kapatır.
    """
    local_now = now or _utc_now()
    stored_expiry = repository.get_setting("license/expires_at", "") or None

    machine_state, state_error = _read_machine_state()
    if state_error:
        return LicenseGateResult(
            False,
            "license_state_invalid",
            "Yerel lisans/deneme kaydı değiştirilmiş veya başka cihaza ait görünüyor. "
            "Devam etmek için internet bağlantısıyla etkin lisans doğrulayın.",
            expires_at=stored_expiry,
        )

    if not _clock_is_valid(repository, local_now, machine_state):
        return LicenseGateResult(
            False,
            "clock_changed",
            "Sistem tarihi önceki lisans denetiminden geriye alınmış görünüyor. "
            "Devam etmek için internet bağlantısıyla lisansı doğrulayın.",
            expires_at=stored_expiry,
        )

    if checker is None:
        from license_app import check_license_status
        checker = check_license_status

    try:
        status = checker()
        active = bool(getattr(status, "active", status is True))
        online = bool(getattr(status, "online", active))
        expires_at = getattr(status, "expires_at", None) or stored_expiry
    except Exception:
        active, online, expires_at = False, False, stored_expiry

    if active:
        _store_now(repository, "license/last_online_validation_at", local_now)
        if expires_at:
            repository.set_setting("license/expires_at", str(expires_at))
        repository.set_setting("license/last_status", "active")
        return LicenseGateResult(
            True,
            "licensed",
            "Etkin lisans doğrulandı.",
            expires_at=expires_at,
        )

    repository.set_setting(
        "license/last_status",
        "unlicensed" if online else "offline",
    )

    last_valid = _parse_timestamp(
        repository.get_setting(
            "license/last_online_validation_at",
            "",
        )
    )

    if not online and last_valid is not None:
        remaining = OFFLINE_GRACE_PERIOD - (local_now - last_valid)
        if remaining > timedelta(0):
            return LicenseGateResult(
                True,
                "offline_grace",
                f"Çevrimdışı kullanım izni: {_format_remaining(remaining)} kaldı. "
                "İnternete bağlanıp lisansı doğrulayın.",
                remaining,
                expires_at,
            )

        return LicenseGateResult(
            False,
            "offline_expired",
            "Çevrimdışı kullanım süresi doldu. Etkin lisansı internet üzerinden "
            "doğrulamadan uygulama açılamaz.",
            expires_at=expires_at,
        )

    # ------------------------------------------------------------------
    # TRIAL: online olduğumuz sürece sunucu HWID kaydı tek kaynak kabul edilir.
    # ------------------------------------------------------------------
    server = _server_trial_status(trial_checker)

    if server is not None and bool(getattr(server, "online", False)):
        if not bool(getattr(server, "ok", False)):
            return LicenseGateResult(
                False,
                "trial_server_rejected",
                str(
                    getattr(
                        server,
                        "message",
                        "Deneme lisansı doğrulanamadı.",
                    )
                ),
                expires_at=expires_at,
            )

        server_start = _parse_timestamp(
            getattr(server, "trial_started_at", None)
        )
        server_now = _parse_timestamp(
            getattr(server, "server_now", None)
        )

        if server_start is None or server_now is None:
            return LicenseGateResult(
                False,
                "trial_server_invalid",
                "Deneme lisansı sunucusundan geçerli zaman bilgisi alınamadı.",
                expires_at=expires_at,
            )

        # Sunucu zamanı esas alınır. Böylece istemci saatini ileri/geri oynatmak
        # trial hesaplamasını değiştirmez.
        repository.set_setting(
            "license/unlicensed_started_at",
            server_start.isoformat(),
        )
        repository.set_setting(
            "license/last_seen_at",
            server_now.isoformat(),
        )

        try:
            _write_machine_state(
                server_start,
                server_now,
                server_synced=True,
            )
        except Exception:
            return LicenseGateResult(
                False,
                "license_state_unavailable",
                "Deneme lisansı cihazda güvenli şekilde kaydedilemedi. "
                "Etkin lisans olmadan devam edilemez.",
                expires_at=expires_at,
            )

        remaining = TRIAL_PERIOD - (server_now - server_start)

        if remaining > timedelta(0):
            return LicenseGateResult(
                True,
                "trial",
                f"Lisanssız kullanım izni: {_format_remaining(remaining)} kaldı. "
                "Süre sonunda etkin lisans gerekir.",
                remaining,
                expires_at,
            )

        return LicenseGateResult(
            False,
            "trial_expired",
            "14 günlük lisanssız deneme süresi doldu. "
            "Devam etmek için etkin lisansı internet üzerinden doğrulayın.",
            expires_at=expires_at,
        )

    # ------------------------------------------------------------------
    # SUNUCU YOK: yalnız daha önce sunucuyla senkronize edilmiş imzalı state varsa
    # trial devam edebilir. İlk trial offline başlatılmaz.
    # ------------------------------------------------------------------
    if machine_state and bool(machine_state.get("server_synced")):
        trial_started = _parse_timestamp(
            machine_state.get("trial_started_at")
        )
        if trial_started is None:
            return LicenseGateResult(
                False,
                "license_state_invalid",
                "Yerel deneme lisansı kaydı okunamadı.",
                expires_at=expires_at,
            )

        remaining = TRIAL_PERIOD - (local_now - trial_started)

        if remaining > timedelta(0):
            try:
                _write_machine_state(
                    trial_started,
                    local_now,
                    server_synced=True,
                )
            except Exception:
                return LicenseGateResult(
                    False,
                    "license_state_unavailable",
                    "Deneme lisansı cihazda doğrulanamadı.",
                    expires_at=expires_at,
                )

            return LicenseGateResult(
                True,
                "trial",
                f"Çevrimdışı deneme kullanımı: {_format_remaining(remaining)} kaldı. "
                "İnternete bağlanarak lisans durumunu doğrulayın.",
                remaining,
                expires_at,
            )

        return LicenseGateResult(
            False,
            "trial_expired",
            "14 günlük lisanssız deneme süresi doldu. "
            "Etkin lisans doğrulanmadan uygulama açılamaz.",
            expires_at=expires_at,
        )

    return LicenseGateResult(
        False,
        "trial_online_required",
        "Bu cihazda deneme süresini başlatmak veya yeniden doğrulamak için "
        "internet bağlantısı gereklidir.",
        expires_at=expires_at,
    )

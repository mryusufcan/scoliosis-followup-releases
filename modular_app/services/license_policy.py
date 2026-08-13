"""Açılışta uygulanan yerel lisans ve çevrimdışı süre politikası."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable


GRACE_PERIOD = timedelta(hours=6)
CLOCK_TOLERANCE = timedelta(minutes=5)


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


def _clock_is_valid(repository, now: datetime) -> bool:
    last_seen = _parse_timestamp(repository.get_setting("license/last_seen_at", ""))
    if last_seen is not None and now + CLOCK_TOLERANCE < last_seen:
        return False
    if last_seen is None or now > last_seen:
        _store_now(repository, "license/last_seen_at", now)
    return True


def evaluate_license_gate(repository, checker: Callable[[], object] | None = None, now: datetime | None = None) -> LicenseGateResult:
    """Uygulamanın açılıp açılmayacağını belirler.

    Etkin lisans çevrimiçiyken kaydedilir. İnternet erişimi yokken son başarılı
    denetimden itibaren yalnızca 6 saat kullanım verilir. Hiç etkin lisans
    doğrulanmamış cihazlar için de ilk açılıştan itibaren tek seferlik 6 saatlik
    deneme süresi uygulanır.
    """
    now = now or _utc_now()
    stored_expiry = repository.get_setting("license/expires_at", "") or None
    if not _clock_is_valid(repository, now):
        return LicenseGateResult(
            False,
            "clock_changed",
            "Sistem tarihi önceki lisans denetiminden geriye alınmış görünüyor. İnternet bağlantısıyla lisansı tekrar doğrulayın.",
            expires_at=stored_expiry,
        )

    if checker is None:
        from license_app import check_license_status

        checker = check_license_status

    try:
        status = checker()
        active = bool(getattr(status, "active", status is True))
        online = bool(getattr(status, "online", active))
        detail = str(getattr(status, "message", ""))
        expires_at = getattr(status, "expires_at", None) or stored_expiry
    except Exception as exc:
        active, online, detail = False, False, f"Lisans denetimi yapılamadı: {exc}"
        expires_at = stored_expiry

    if active:
        _store_now(repository, "license/last_online_validation_at", now)
        if expires_at:
            repository.set_setting("license/expires_at", str(expires_at))
        repository.set_setting("license/last_status", "active")
        return LicenseGateResult(True, "licensed", "Etkin lisans doğrulandı.", expires_at=expires_at)

    repository.set_setting("license/last_status", "unlicensed" if online else "offline")
    last_valid = _parse_timestamp(repository.get_setting("license/last_online_validation_at", ""))

    if not online and last_valid is not None:
        remaining = GRACE_PERIOD - (now - last_valid)
        if remaining > timedelta(0):
            return LicenseGateResult(
                True,
                "offline_grace",
                f"Çevrimdışı kullanım izni: {_format_remaining(remaining)} kaldı. İnternete bağlanıp lisansı doğrulayın.",
                remaining,
                expires_at,
            )
        return LicenseGateResult(
            False,
            "offline_expired",
            "Çevrimdışı kullanım süresi doldu. Uygulamayı açmak için internete bağlanıp etkin lisansı doğrulayın.",
            expires_at=expires_at,
        )

    # Etkin lisans geçmişi olmayan cihazlarda veya sunucunun lisanssız
    # yanıt verdiği durumda tek seferlik altı saatlik deneme uygulanır.
    trial_started = _parse_timestamp(repository.get_setting("license/unlicensed_started_at", ""))
    if trial_started is None:
        _store_now(repository, "license/unlicensed_started_at", now)
        trial_started = now
    remaining = GRACE_PERIOD - (now - trial_started)
    if remaining > timedelta(0):
        source = "Çevrimdışı" if not online else "Lisanssız"
        return LicenseGateResult(
            True,
            "trial",
            f"{source} kullanım izni: {_format_remaining(remaining)} kaldı. Süre sonunda etkin lisans doğrulaması gerekir.",
            remaining,
            expires_at,
        )
    return LicenseGateResult(
        False,
        "trial_expired",
        "Lisanssız/çevrimdışı kullanım için verilen 6 saatlik süre doldu. Devam etmek için etkin lisansı internet üzerinden doğrulayın.",
        expires_at=expires_at,
    )

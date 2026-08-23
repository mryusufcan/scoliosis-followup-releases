from __future__ import annotations

import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

SOURCE_EXTS = {
    ".py", ".ps1", ".bat", ".cmd", ".spec", ".iss",
    ".json", ".toml", ".ini", ".cfg", ".txt", ".md",
}

PACKAGING_TARGETS = [
    ROOT / "packaging",
    ROOT / "packaging" / "ScoliosisFollowUp.spec",
    ROOT / "scripts" / "build",
    ROOT / "scripts" / "release",
]

OUTPUT_TARGETS = [
    ROOT / "dist",
    ROOT / "build",
    ROOT / "installer",
    ROOT / "releases",
    ROOT / "artifacts",
]

FORBIDDEN_PATH_PARTS = (
    "tools/license_admin.py",
    "tools\\license_admin.py",
    "scripts/admin",
    "scripts\\admin",
    "license_admin_v2.py",
    "license_admin_v3.py",
    "17_lisans_yonetim",
    "18_lisans_panel",
    "19_lisans_panel",
)

SECRET_MARKERS = (
    "SUPABASE_SECRET_KEY",
    "SUPABASE_SERVICE_ROLE_KEY",
    "sb_secret_",
    "service_role",
)

# Bu dosyaların kendilerinde marker bulunması normaldir; bunlar dağıtıma
# girmemesi gereken yönetici kaynaklarıdır.
ADMIN_SOURCE_ALLOWLIST = {
    str((ROOT / "tools" / "license_admin.py").resolve()).lower(),
    str((ROOT / "scripts" / "admin" / "Lisans_Yonetimi_Anahtar_Kaydet.ps1").resolve()).lower(),
    str((ROOT / "scripts" / "admin" / "Lisans_Yonetimi_Ac.bat").resolve()).lower(),
    str((ROOT / "license_admin_tool.py").resolve()).lower(),
    str((ROOT / "license_admin_v2.py").resolve()).lower(),
    str((ROOT / "license_admin_v3.py").resolve()).lower(),
    str((ROOT / "17_Lisans_Yonetim_Araci_Kur.py").resolve()).lower(),
    str((ROOT / "18_Lisans_Paneli_V2_Kur.py").resolve()).lower(),
    str((ROOT / "19_Lisans_Paneli_V3_Kur.py").resolve()).lower(),
    str(Path(__file__).resolve()).lower(),
    str((ROOT / "20_Dagitim_Guvenlik_Denetimi.py").resolve()).lower(),
    str((ROOT / "20B_Dagitim_Guvenlik_Denetimi_Duzeltilmis.py").resolve()).lower(),
    str((ROOT / "20C_Dagitim_Guvenlik_Denetimi_Final.py").resolve()).lower(),
}


def norm(path: Path) -> str:
    return str(path.resolve()).replace("\\", "/").lower()


def iter_files(target: Path):
    if not target.exists():
        return
    if target.is_file():
        yield target
        return
    for path in target.rglob("*"):
        if path.is_file():
            yield path


def read_text_safe(path: Path) -> str | None:
    if path.suffix.lower() not in SOURCE_EXTS:
        return None
    try:
        return path.read_text(encoding="utf-8-sig", errors="ignore")
    except Exception:
        return None


def packaging_audit():
    findings = []
    audit_script = Path(__file__).resolve()

    for target in PACKAGING_TARGETS:
        for path in iter_files(target) or []:
            # Denetim aracının kendi yasaklı imzaları bulgu değildir.
            if path.resolve() == audit_script:
                continue
            text = read_text_safe(path)
            if text is None:
                continue

            low = text.lower()

            for marker in FORBIDDEN_PATH_PARTS:
                if marker.lower() in low:
                    findings.append(
                        ("PACKAGING_ADMIN_REFERENCE", path, marker)
                    )

            for marker in SECRET_MARKERS:
                if marker.lower() in low:
                    findings.append(
                        ("PACKAGING_SECRET_REFERENCE", path, marker)
                    )

            # Tehlikeli geniş paketleme desenlerini ayrıca işaretle.
            dangerous_patterns = [
                # Yalnız proje KÖKÜNÜN tamamı add-data ile paketleniyorsa alarm ver.
                # Örn. --add-data "$root;." veya --add-data "$root\;."
                # $root\resources gibi kontrollü alt klasörler güvenlidir ve
                # burada yanlış pozitif üretmemelidir.
                r"--add-data\s+['\"]?\$root(?:[\\/])?;[.'\"]",
                r"collect_data_files\([^)]*['\"]\.['\"]",
            ]
            for pattern in dangerous_patterns:
                if re.search(pattern, text, flags=re.IGNORECASE):
                    findings.append(
                        ("BROAD_PACKAGING_PATTERN", path, pattern)
                    )

    return findings


def source_secret_audit():
    findings = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue

        pnorm = norm(path)
        if (
            "/.venv-build/" in pnorm
            or "/.restore_points/" in pnorm
            or "/.git/" in pnorm
            or "/dev_data/" in pnorm
        ):
            continue

        text = read_text_safe(path)
        if text is None:
            continue

        if str(path.resolve()).lower() in ADMIN_SOURCE_ALLOWLIST:
            continue

        # Anon key son kullanıcı tarafında olabilir; burada yalnız secret/admin
        # anahtar sınıflarını arıyoruz.
        for marker in SECRET_MARKERS:
            if marker.lower() in text.lower():
                findings.append(
                    ("SECRET_MARKER_IN_SOURCE", path, marker)
                )

    return findings


def output_audit():
    findings = []

    for target in OUTPUT_TARGETS:
        if not target.exists():
            continue

        for path in iter_files(target) or []:
            pnorm = norm(path)

            for forbidden in FORBIDDEN_PATH_PARTS:
                clean = forbidden.replace("\\", "/").lower()
                if clean in pnorm:
                    findings.append(
                        ("ADMIN_FILE_IN_OUTPUT", path, forbidden)
                    )

            # Metin çıktılarında secret marker ara.
            text = read_text_safe(path)
            if text is not None:
                low = text.lower()
                for marker in SECRET_MARKERS:
                    if marker.lower() in low:
                        findings.append(
                            ("SECRET_MARKER_IN_OUTPUT", path, marker)
                        )

                for marker in FORBIDDEN_PATH_PARTS:
                    if marker.lower() in low:
                        findings.append(
                            ("ADMIN_REFERENCE_IN_OUTPUT", path, marker)
                        )

    return findings


def print_findings(title, findings):
    print()
    print(title)
    print("-" * len(title))
    if not findings:
        print("[OK] Bulgu yok.")
        return

    for kind, path, detail in findings:
        try:
            rel = path.relative_to(ROOT)
        except Exception:
            rel = path
        print(f"[!] {kind}")
        print(f"    Dosya : {rel}")
        print(f"    Bulgu : {detail}")


def main():
    print()
    print("=" * 66)
    print("     SCOLIOSIS FOLLOW-UP | DAGITIM GUVENLIK DENETIMI")
    print("=" * 66)
    print("Proje:", ROOT)

    pkg = packaging_audit()
    src = source_secret_audit()
    out = output_audit()

    print_findings("1) Paketleme scriptleri", pkg)
    print_findings("2) Kaynak kod secret taramasi", src)
    print_findings("3) Build / installer / release ciktilari", out)

    critical = pkg + src + out

    print()
    print("=" * 66)
    if critical:
        print("SONUC: DAGITIM GUVENLIK DENETIMI BASARISIZ")
        print()
        print(
            "Bu bulgular duzeltilmeden son kullanici EXE/installer "
            "yayinlanmamali."
        )
        print("=" * 66)
        return 1

    print("SONUC: DAGITIM GUVENLIK DENETIMI BASARILI")
    print()
    print("Yonetici lisans araci ve secret-key markerlari")
    print("paketleme zincirinde veya mevcut dagitim ciktilarinda bulunmadi.")
    print("=" * 66)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

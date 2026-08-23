from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REPO = "mryusufcan/scoliosis-followup-releases"
VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def fail(message: str, code: int = 1) -> None:
    print(f"\n[HATA] {message}", file=sys.stderr)
    raise SystemExit(code)


def run(
    command: list[str],
    *,
    cwd: Path = ROOT,
    capture: bool = False,
    check: bool = True,
    show_capture: bool = True,
) -> subprocess.CompletedProcess[str]:
    print("[KOMUT]", " ".join(command))
    result = subprocess.run(
        command,
        cwd=cwd,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=capture,
    )
    if capture and show_capture and result.stdout:
        print(result.stdout.rstrip())
    if capture and show_capture and result.stderr and result.returncode != 0:
        print(result.stderr.rstrip(), file=sys.stderr)
    if check and result.returncode != 0:
        fail(f"Komut başarısız oldu (kod {result.returncode}).", result.returncode)
    return result


def read_version() -> str:
    path = ROOT / "VERSION"
    if not path.is_file():
        fail("VERSION dosyası bulunamadı.")
    version = path.read_text(encoding="utf-8-sig").strip()
    if not VERSION_RE.fullmatch(version):
        fail(f"Geçersiz sürüm: {version!r}")
    return version


def release_files(version: str) -> tuple[Path, Path, Path]:
    release_dir = ROOT / "releases" / version
    installer = release_dir / f"ScoliosisFollowUp_Setup_{version}.exe"
    feed = release_dir / "update.json"
    notes = ROOT / "docs" / f"RELEASE_NOTES_{version}.md"
    missing = [path for path in (installer, feed, notes) if not path.is_file()]
    if missing:
        fail("Eksik yayın dosyaları:\n" + "\n".join(f"  {path}" for path in missing))
    return installer, feed, notes


def validate_release(version: str, installer: Path, feed: Path, repo: str) -> dict:
    try:
        payload = json.loads(feed.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"update.json okunamadı: {exc}")

    expected_url = (
        f"https://github.com/{repo}/releases/download/{version}/"
        f"ScoliosisFollowUp_Setup_{version}.exe"
    )
    actual_hash = hashlib.sha256(installer.read_bytes()).hexdigest()
    checks = {
        "version": payload.get("version") == version,
        "url": payload.get("url") == expected_url,
        "sha256": str(payload.get("sha256", "")).lower() == actual_hash,
        "signature": bool(payload.get("signature")),
    }
    failed = [name for name, valid in checks.items() if not valid]
    if failed:
        fail("Yayın doğrulaması başarısız: " + ", ".join(failed))

    print(f"[OK] Sürüm: {version}")
    print(f"[OK] Installer SHA-256: {actual_hash}")
    print(f"[OK] İndirme adresi: {expected_url}")
    return payload


def require_gh() -> None:
    if not shutil.which("gh"):
        fail("GitHub CLI (gh) bulunamadı.")
    run(["gh", "auth", "status", "-h", "github.com"], capture=True)


def asset_matches(asset: dict | None, path: Path) -> bool:
    if not asset or int(asset.get("size", -1)) != path.stat().st_size:
        return False
    digest = str(asset.get("digest") or "")
    if not digest.startswith("sha256:"):
        return False
    return digest.removeprefix("sha256:").lower() == hashlib.sha256(path.read_bytes()).hexdigest()


def publish_release(version: str, installer: Path, feed: Path, notes: Path, repo: str) -> None:
    current = run(
        ["gh", "release", "view", version, "--repo", repo, "--json", "assets"],
        capture=True,
        check=False,
        show_capture=False,
    )
    exists = current.returncode == 0

    if exists:
        print(f"[BİLGİ] {version} mevcut; açıklama ve dosyalar güvenli biçimde güncellenecek.")
        run([
            "gh", "release", "edit", version, "--repo", repo,
            "--title", f"Scoliosis Follow-Up {version}",
            "--notes-file", str(notes), "--latest",
        ])
        assets = {
            asset.get("name"): asset
            for asset in json.loads(current.stdout).get("assets", [])
        }
        if asset_matches(assets.get(installer.name), installer) and asset_matches(assets.get(feed.name), feed):
            print("[BİLGİ] GitHub asset dosyaları yerel paketle zaten aynı; yeniden yüklenmedi.")
        else:
            run([
                "gh", "release", "upload", version, str(installer), str(feed),
                "--repo", repo, "--clobber",
            ])
    else:
        run([
            "gh", "release", "create", version, str(installer), str(feed),
            "--repo", repo,
            "--title", f"Scoliosis Follow-Up {version}",
            "--notes-file", str(notes), "--latest",
        ])


def release_notes_body(notes: Path) -> str:
    lines = notes.read_text(encoding="utf-8-sig").strip().splitlines()
    if lines and lines[0].startswith("# "):
        lines = lines[1:]
    return "\n".join(lines).strip()


def update_pages(version: str, notes: Path, repo: str) -> None:
    def read_remote(path: str) -> tuple[str, str]:
        result = run(
            ["gh", "api", f"repos/{repo}/contents/{path}?ref=main"],
            capture=True,
            show_capture=False,
        )
        payload = json.loads(result.stdout)
        try:
            content = base64.b64decode(payload["content"]).decode("utf-8-sig")
            sha = str(payload["sha"])
        except (KeyError, ValueError, UnicodeDecodeError) as exc:
            fail(f"GitHub'daki {path} okunamadı: {exc}")
        return content, sha

    def write_remote(path: str, content: str, sha: str) -> None:
        payload = {
            "message": f"docs: publish {version} release information",
            "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
            "sha": sha,
            "branch": "main",
        }
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", suffix=".json", delete=False
        ) as handle:
            json.dump(payload, handle, ensure_ascii=False)
            request_file = Path(handle.name)
        try:
            run([
                "gh", "api", "--method", "PUT",
                f"repos/{repo}/contents/{path}", "--input", str(request_file),
            ])
        finally:
            request_file.unlink(missing_ok=True)

    readme_original, readme_sha = read_remote("README.md")
    index_original, index_sha = read_remote("index.html")
    readme_text = readme_original
    match = re.search(r"Sürüm-(\d+\.\d+\.\d+)-blue", readme_text)
    if not match:
        fail("README içindeki mevcut sürüm rozeti bulunamadı.")
    previous = match.group(1)
    readme_text = readme_text.replace(previous, version)

    section = (
        f"# 🆕 Sürüm {version}\n\n"
        f"{release_notes_body(notes)}\n\n"
        "[GitHub sürümünü ve indirme dosyalarını görüntüle]"
        f"(https://github.com/{repo}/releases/tag/{version})\n\n---"
    )
    readme_text, count = re.subn(
        r"(?ms)^# 🆕 Sürüm \d+\.\d+\.\d+\s*$.*?^---\s*$",
        section,
        readme_text,
        count=1,
    )
    if count != 1:
        fail("README sürüm bölümü güncellenemedi.")

    html = index_original.replace(previous, version)
    release_url = f"https://github.com/{repo}/releases/tag/{version}"
    html_section = (
        '<section id="surum"><div class="wrap"><div class="section-head">'
        f'<h2>{version} sürümü</h2><p>Güncel bakım sürümünün ayrıntılı değişiklikleri '
        'GitHub sürüm notlarında yayımlanmıştır.</p></div><div class="grid">'
        '<div class="card"><h3>Ayrıntılı Sürüm Notları</h3>'
        f'<p><a href="{release_url}" target="_blank" rel="noopener">'
        'Tüm değişiklikleri görüntüleyin.</a></p></div>'
        '<div class="card"><h3>Güvenli İndirme</h3><p>Kurulum dosyası yalnız resmi '
        'GitHub Releases alanından sunulur.</p></div>'
        '<div class="card"><h3>İmzalı Güncelleme</h3><p>Installer SHA-256 özeti '
        'imzalı update.json ile doğrulanır.</p></div>'
        '<div class="card"><h3>Uzman Kontrollü Kullanım</h3><p>Otomatik ve AI '
        'sonuçları uzman doğrulaması olmadan klinik karar değildir.</p></div>'
        '</div></div></section>'
    )
    html, count = re.subn(
        r'<section id="surum">.*?</section>',
        html_section,
        html,
        count=1,
        flags=re.DOTALL,
    )
    if count != 1:
        fail("Pages sürüm bölümü güncellenemedi.")

    changed = False
    if readme_text != readme_original:
        write_remote("README.md", readme_text, readme_sha)
        changed = True
    if html != index_original:
        write_remote("index.html", html, index_sha)
        changed = True
    if not changed:
        print("[BİLGİ] README ve Pages zaten güncel; Git kurulumu gerekmedi.")


def verify_remote(version: str, feed: Path, repo: str, *, wait_pages: bool) -> None:
    result = run([
        "gh", "release", "view", version, "--repo", repo,
        "--json", "tagName,isDraft,isPrerelease,assets,url",
    ], capture=True, show_capture=False)
    data = json.loads(result.stdout)
    assets = {asset["name"]: asset for asset in data.get("assets", [])}
    expected = {f"ScoliosisFollowUp_Setup_{version}.exe", "update.json"}
    if not expected.issubset(assets):
        fail("GitHub release asset doğrulaması başarısız.")
    if data.get("isDraft") or data.get("isPrerelease") or data.get("tagName") != version:
        fail("GitHub release kararlı/latest yayın koşullarını karşılamıyor.")

    with tempfile.TemporaryDirectory(prefix="sfu-feed-") as temp:
        run([
            "gh", "release", "download", version, "--repo", repo,
            "--pattern", "update.json", "--dir", temp,
        ])
        remote_feed = Path(temp) / "update.json"
        if remote_feed.read_bytes() != feed.read_bytes():
            fail("GitHub'daki update.json yerel dosyayla eşleşmiyor.")

    if wait_pages:
        for _ in range(18):
            build = run(
                ["gh", "api", f"repos/{repo}/pages/builds/latest"],
                capture=True,
                show_capture=False,
            )
            status = json.loads(build.stdout).get("status")
            print(f"[PAGES] {status}")
            if status == "built":
                break
            if status == "errored":
                fail("GitHub Pages oluşturması başarısız.")
            time.sleep(5)
        else:
            fail("GitHub Pages doğrulaması zaman aşımına uğradı.")

    print(f"\n[OK] GitHub yayını doğrulandı: https://github.com/{repo}/releases/tag/{version}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Hazır Scoliosis Follow-Up paketini GitHub'da yayımla.")
    parser.add_argument("--repo", default=DEFAULT_REPO, help="owner/repository")
    parser.add_argument("--dry-run", action="store_true", help="Yalnız yerel kontrolleri yap")
    parser.add_argument("--yes", action="store_true", help="Etkileşimli onayı atla")
    parser.add_argument("--skip-pages", action="store_true", help="README ve Pages güncellemesini atla")
    args = parser.parse_args()

    version = read_version()
    installer, feed, notes = release_files(version)
    validate_release(version, installer, feed, args.repo)
    print(f"[OK] Sürüm notları: {notes}")

    if args.dry_run:
        print("\n[DRY-RUN] GitHub üzerinde hiçbir değişiklik yapılmadı.")
        return 0

    if not args.yes:
        answer = input(f"\n{version} GitHub'da yayımlansın mı? Devam etmek için EVET yazın: ").strip()
        if answer.upper() != "EVET":
            print("[İPTAL] GitHub yayını değiştirilmedi.")
            return 0

    require_gh()
    publish_release(version, installer, feed, notes, args.repo)
    if not args.skip_pages:
        update_pages(version, notes, args.repo)
    verify_remote(version, feed, args.repo, wait_pages=not args.skip_pages)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

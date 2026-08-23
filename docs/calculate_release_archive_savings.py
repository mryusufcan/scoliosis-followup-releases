from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RELEASES = ROOT / 'releases'


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def size(path: Path) -> int:
    if path.is_file():
        return path.stat().st_size
    return sum(item.stat().st_size for item in path.rglob('*') if item.is_file())

versions = []
for path in sorted((p for p in RELEASES.iterdir() if p.is_dir()), key=lambda p: p.name):
    versions.append({'version': path.name, 'path': str(path.relative_to(ROOT)), 'bytes': size(path), 'mib': round(size(path) / 1024 / 1024, 2)})

versions_desc = sorted(versions, key=lambda row: row['version'], reverse=True)
scenarios = []
for keep_count in (1, 2, 3):
    keep = {row['version'] for row in versions_desc[:keep_count]}
    archive = [row for row in versions if row['version'] not in keep]
    scenarios.append({
        'name': f'En yeni {keep_count} sürüm yerelde tutulur',
        'keep_versions': sorted(keep),
        'archive_versions': [row['version'] for row in archive],
        'reclaim_mib': round(sum(row['mib'] for row in archive), 2),
        'reclaim_gib': round(sum(row['bytes'] for row in archive) / 1024 / 1024 / 1024, 3),
    })

installer_rows = []
installer_dir = ROOT / 'installer'
if installer_dir.exists():
    for path in installer_dir.iterdir():
        if path.is_file() and path.suffix.lower() in {'.exe', '.msi'}:
            installer_rows.append({'path': str(path.relative_to(ROOT)), 'bytes': path.stat().st_size, 'mib': round(path.stat().st_size / 1024 / 1024, 2), 'sha256': sha256(path)})

current_release = RELEASES / '1.7.5' / 'ScoliosisFollowUp_Setup_1.7.5.exe'
for row in installer_rows:
    row['same_as_current_1_7_5_release'] = current_release.is_file() and row['sha256'] == sha256(current_release)

root_duplicate = [row for row in installer_rows if row['same_as_current_1_7_5_release']]
result = {
    'generated_at': datetime.now().isoformat(timespec='seconds'),
    'releases': versions,
    'scenarios': scenarios,
    'installer_files': installer_rows,
    'root_installer_duplicates_of_release_1_7_5': {
        'files': [row['path'] for row in root_duplicate],
        'mib': round(sum(row['mib'] for row in root_duplicate), 2),
    },
    'note': 'Arşivleme senaryoları yalnızca hesaplandı; hiçbir dosya taşınmadı veya silinmedi.',
}
output = ROOT / 'docs' / 'release_archive_savings_20260822.json'
output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'scenarios': scenarios, 'installer_files': installer_rows, 'root_duplicate': result['root_installer_duplicates_of_release_1_7_5']}, ensure_ascii=False, indent=2))

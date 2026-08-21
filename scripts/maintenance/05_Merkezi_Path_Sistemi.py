from __future__ import annotations

import re
import shutil
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RUN_MODULAR = ROOT / "modular_app" / "run_modular.py"
CONFIG_DIR = ROOT / "modular_app" / "config"
PATHS_FILE = CONFIG_DIR / "paths.py"
INIT_FILE = CONFIG_DIR / "__init__.py"
RESTORE_ROOT = ROOT / ".restore_points"

if not RUN_MODULAR.is_file():
    raise SystemExit(f"Bulunamadı: {RUN_MODULAR}")

stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
backup_dir = RESTORE_ROOT / f"central_paths_{stamp}"
backup_dir.mkdir(parents=True, exist_ok=True)
shutil.copy2(RUN_MODULAR, backup_dir / "run_modular.py")

CONFIG_DIR.mkdir(parents=True, exist_ok=True)
INIT_FILE.write_text('"""Uygulama genelindeki merkezi yapılandırma yardımcıları."""\n', encoding='utf-8')

paths_code = r'''"""Scoliosis Follow-Up merkezi dosya ve klasör yolları."""

from __future__ import annotations

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MODULAR_APP_DIR = PROJECT_ROOT / "modular_app"

RESOURCES_DIR = PROJECT_ROOT / "resources"
BRANDING_DIR = RESOURCES_DIR / "branding"
AI_RESOURCES_DIR = RESOURCES_DIR / "ai"

PACKAGING_DIR = PROJECT_ROOT / "packaging"
RELEASES_DIR = PROJECT_ROOT / "releases"
ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"

VERSION_FILE = PROJECT_ROOT / "VERSION"
UPDATE_FEED_FILE = PROJECT_ROOT / "update.json"

def application_data_dir() -> Path:
    if getattr(sys, "frozen", False):
        local_data = os.environ.get("LOCALAPPDATA")
        base = Path(local_data) if local_data else Path.home() / "AppData" / "Local"
        return base / "ScoliosisFollowUp"
    return MODULAR_APP_DIR / "data"

DATA_DIR = application_data_dir()
DB_PATH = DATA_DIR / "scoliosis.db"
LOG_DIR = DATA_DIR / "logs"
LOG_PATH = LOG_DIR / "application.log"

def application_icon_path() -> Path:
    return BRANDING_DIR / "ScoliosisFollowUp.ico"

def startup_logo_path() -> Path:
    candidates = (
        BRANDING_DIR / "ScoliosisFollowUp.png",
        BRANDING_DIR / "logo.png",
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return candidates[0]
'''
PATHS_FILE.write_text(paths_code, encoding='utf-8')

text = RUN_MODULAR.read_text(encoding='utf-8')
original = text

text = text.replace(
'''PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    # Keep modular_app first so the integration's database/timeline modules win.
    # The project root remains available for optional dicom and pacs packages.
    sys.path.append(str(PROJECT_ROOT))
''',
'''_BOOTSTRAP_ROOT = Path(__file__).resolve().parent.parent
if str(_BOOTSTRAP_ROOT) not in sys.path:
    sys.path.append(str(_BOOTSTRAP_ROOT))
''',
1
)

anchor = "from modular_app.database.exam_repository import ExamRepository\n"
path_import = (
    "from modular_app.config.paths import (\n"
    "    AI_RESOURCES_DIR, DATA_DIR, DB_PATH, LOG_PATH, PROJECT_ROOT,\n"
    "    application_icon_path, startup_logo_path,\n"
    ")\n"
)
if path_import not in text:
    if anchor not in text:
        raise RuntimeError("ExamRepository import noktası bulunamadı.")
    text = text.replace(anchor, path_import + anchor, 1)

pattern = re.compile(
    r'\ndef application_data_dir\(\) -> Path:\n.*?\ndef application_icon_path\(\) -> Path:\n.*?(?=\n\ndef create_startup_splash)',
    re.DOTALL,
)
text, count = pattern.subn("\n", text, count=1)
if count != 1:
    raise RuntimeError("Eski path bloğu bulunamadı; dosya beklenenden farklı.")

for old_splash in (
'''    branding_logo = PROJECT_ROOT / "resources" / "branding" / "ScoliosisFollowUp.png"
    legacy_logo = PROJECT_ROOT / "resources" / "branding" / "logo.png"
    artwork_path = branding_logo if branding_logo.is_file() else legacy_logo
''',
'''    branding_logo = PROJECT_ROOT / "resources" / "branding" / "ScoliosisFollowUp.png"
    legacy_logo = PROJECT_ROOT / "logo.png"
    artwork_path = branding_logo if branding_logo.is_file() else legacy_logo
'''
):
    if old_splash in text:
        text = text.replace(old_splash, "    artwork_path = startup_logo_path()\n", 1)
        break

text = text.replace(
    'PROJECT_ROOT / "resources" / "ai" / "vertebra_cobb"',
    'AI_RESOURCES_DIR / "vertebra_cobb"'
)

text = text.replace(
    'log_path = Path(DB_PATH).parent / "logs" / "application.log"',
    'log_path = LOG_PATH'
)

RUN_MODULAR.write_text(text, encoding='utf-8')

print("Merkezi path sistemi oluşturuldu.")
print("  modular_app/config/paths.py")
print("  modular_app/config/__init__.py")
print("Güncellendi: modular_app/run_modular.py")
print("Yedek:", backup_dir)
print()
print("Şimdi çalıştırın:")
print("  python -m unittest discover -s tests")

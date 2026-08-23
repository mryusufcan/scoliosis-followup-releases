"""Scoliosis Follow-Up merkezi dosya ve klasör yolları."""

from __future__ import annotations

import os
import sys
from pathlib import Path

if getattr(sys, "frozen", False):
    # PyInstaller onedir paketinde veri dosyalari sys._MEIPASS (_internal)
    # altina acilir. Kaynak dosyanin __file__ yolundan yukariya cikmak kurulu
    # uygulamada VERSION dosyasini kurulum klasorunun disinda aratiyordu.
    PROJECT_ROOT = Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
else:
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
    override = os.environ.get("SCOLIOSIS_FOLLOWUP_DATA_DIR", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    local_data = os.environ.get("LOCALAPPDATA")
    base = Path(local_data) if local_data else Path.home() / "AppData" / "Local"
    return base / "ScoliosisFollowUp"

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

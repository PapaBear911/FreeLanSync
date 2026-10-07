"""Configuration settings for FreeLanSync Desktop Server."""
from pathlib import Path
import os
import socket
import json

# Base Directories
BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_FILE = BASE_DIR / "freelansync_config.json"
LEGACY_CONFIG_FILE = BASE_DIR / "photosync_config.json"

def load_settings() -> dict:
    default_storage = str((BASE_DIR / "storage").resolve())
    target_cfg = CONFIG_FILE if CONFIG_FILE.exists() else LEGACY_CONFIG_FILE
    if target_cfg.exists():
        try:
            with open(target_cfg, "r", encoding="utf-8") as f:
                data = json.load(f)
                return {
                    "storage_dir": data.get("storage_dir", default_storage)
                }
        except Exception:
            pass
    return {"storage_dir": default_storage}

def save_settings(settings: dict):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2)

def get_storage_dir() -> Path:
    settings = load_settings()
    custom_dir = os.getenv("FREELANSYNC_STORAGE_DIR", os.getenv("PHOTOSYNC_STORAGE_DIR", settings.get("storage_dir")))
    p = Path(custom_dir)
    p.mkdir(parents=True, exist_ok=True)
    return p

def get_backup_dir() -> Path:
    p = get_storage_dir() / "Backups"
    p.mkdir(parents=True, exist_ok=True)
    return p

def get_quickdrop_dir() -> Path:
    p = get_storage_dir() / "QuickDrop"
    p.mkdir(parents=True, exist_ok=True)
    return p

def get_transfers_dir() -> Path:
    p = get_storage_dir() / "Transfers"
    p.mkdir(parents=True, exist_ok=True)
    return p

def get_database_path() -> Path:
    legacy_db = BASE_DIR / "photosync.db"
    new_db = BASE_DIR / "freelansync.db"
    if legacy_db.exists() and not new_db.exists():
        return legacy_db
    return new_db

STORAGE_DIR = get_storage_dir()
DATABASE_PATH = get_database_path()
BACKUP_DIR = get_backup_dir()
QUICKDROP_DIR = get_quickdrop_dir()
TRANSFERS_DIR = get_transfers_dir()

# Server Network Settings
SERVER_HOST = os.getenv("FREELANSYNC_HOST", os.getenv("PHOTOSYNC_HOST", "0.0.0.0"))
SERVER_PORT = int(os.getenv("FREELANSYNC_PORT", os.getenv("PHOTOSYNC_PORT", "8080")))
SERVICE_NAME = "FreeLanSync Desktop Server"
MDNS_SERVICE_TYPE = "_freelansync._tcp.local."
LEGACY_MDNS_SERVICE_TYPE = "_photosync._tcp.local."

def get_local_ip() -> str:
    """Detect the local primary IP address on Wi-Fi/LAN."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.5)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

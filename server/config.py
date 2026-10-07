"""Configuration settings for PhotoSync Desktop Server."""
from pathlib import Path
import os
import socket
import json

# Base Directories
BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_FILE = BASE_DIR / "photosync_config.json"

def load_settings() -> dict:
    default_storage = str((BASE_DIR / "storage").resolve())
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
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
    custom_dir = os.getenv("PHOTOSYNC_STORAGE_DIR", settings.get("storage_dir"))
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

def get_database_path() -> Path:
    return BASE_DIR / "photosync.db"

STORAGE_DIR = get_storage_dir()
DATABASE_PATH = get_database_path()
BACKUP_DIR = get_backup_dir()
QUICKDROP_DIR = get_quickdrop_dir()

# Server Network Settings
SERVER_HOST = os.getenv("PHOTOSYNC_HOST", "0.0.0.0")
SERVER_PORT = int(os.getenv("PHOTOSYNC_PORT", "8080"))
SERVICE_NAME = "PhotoSync Desktop Server"
MDNS_SERVICE_TYPE = "_photosync._tcp.local."

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

"""Configuration settings for PhotoSync Desktop Server."""
from pathlib import Path
import os
import socket

# Base Directories
BASE_DIR = Path(__file__).resolve().parent.parent
STORAGE_DIR = Path(os.getenv("PHOTOSYNC_STORAGE_DIR", BASE_DIR / "storage"))
BACKUP_DIR = STORAGE_DIR / "Backups"
DATABASE_PATH = STORAGE_DIR / "photosync.db"

# Server Network Settings
SERVER_HOST = os.getenv("PHOTOSYNC_HOST", "0.0.0.0")
SERVER_PORT = int(os.getenv("PHOTOSYNC_PORT", "8080"))
SERVICE_NAME = "PhotoSync Desktop Server"
MDNS_SERVICE_TYPE = "_photosync._tcp.local."

# Ensure required directories exist
STORAGE_DIR.mkdir(parents=True, exist_ok=True)
BACKUP_DIR.mkdir(parents=True, exist_ok=True)

def get_local_ip() -> str:
    """Detect the local primary IP address on Wi-Fi/LAN."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.5)
        # Doesn't have to be reachable, just triggers OS routing selection
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

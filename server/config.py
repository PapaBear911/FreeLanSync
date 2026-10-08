"""Configuration settings for FreeLanSync Desktop Server."""
from pathlib import Path
import os
import socket
import json

# Base Directories
BASE_DIR = Path(__file__).resolve().parent.parent

def get_app_data_dir() -> Path:
    """Return a guaranteed writable application data directory for database and config."""
    # 1. Environment variable override
    env_dir = os.getenv("FREELANSYNC_DATA_DIR")
    if env_dir:
        p = Path(env_dir)
        try:
            p.mkdir(parents=True, exist_ok=True)
            return p
        except Exception:
            pass

    # 2. Check if BASE_DIR is writable AND not inside system directories (e.g. dev workspace)
    base_str = str(BASE_DIR).lower()
    in_system_dir = any(s in base_str for s in ["program files", "program files (x86)", "windows\\system32", "/usr/", "/opt/"])
    if not in_system_dir:
        try:
            writable, _ = test_writable(BASE_DIR)
            if writable:
                return BASE_DIR
        except Exception:
            pass

    # 3. Standard OS user application data folder
    if os.name == "nt":
        app_data = os.getenv("APPDATA")
        base = Path(app_data) if app_data else Path.home() / "AppData" / "Roaming"
        data_dir = base / "FreeLanSync"
    else:
        data_dir = Path.home() / ".freelansync"

    try:
        data_dir.mkdir(parents=True, exist_ok=True)
        return data_dir
    except Exception:
        import tempfile
        temp_dir = Path(tempfile.gettempdir()) / "FreeLanSync"
        temp_dir.mkdir(parents=True, exist_ok=True)
        return temp_dir

DATA_DIR = get_app_data_dir()
CONFIG_FILE = DATA_DIR / "freelansync_config.json"
LEGACY_CONFIG_FILE = DATA_DIR / "photosync_config.json"

def get_config_file_path() -> Path:
    data_dir = get_app_data_dir()
    new_cfg = data_dir / "freelansync_config.json"
    if new_cfg.exists():
        return new_cfg
    legacy_cfg = data_dir / "photosync_config.json"
    if legacy_cfg.exists():
        return legacy_cfg
    base_cfg = BASE_DIR / "freelansync_config.json"
    if base_cfg.exists():
        return base_cfg
    base_legacy = BASE_DIR / "photosync_config.json"
    if base_legacy.exists():
        return base_legacy
    return new_cfg

def load_settings() -> dict:
    default_storage = str(get_default_recommended_storage().resolve())
    cfg_file = get_config_file_path()
    if cfg_file.exists():
        try:
            with open(cfg_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                custom_storage = data.get("storage_dir")
                if custom_storage:
                    lowered = custom_storage.lower()
                    if not any(s in lowered for s in ["program files", "system32"]):
                        return {"storage_dir": custom_storage}
        except Exception:
            pass
    return {"storage_dir": default_storage}

def save_settings(settings: dict):
    data_dir = get_app_data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
    target_file = data_dir / "freelansync_config.json"
    # TD-018: stage to tmp then atomically replace; a torn direct write would
    # be silently discarded by load_settings on the next start.
    tmp_file = target_file.with_name(f".tmp_{os.getpid()}_freelansync_config.json")
    try:
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2)
        os.replace(tmp_file, target_file)
    except Exception:
        if tmp_file.exists():
            try:
                tmp_file.unlink(missing_ok=True)
            except OSError:
                pass
        raise

def format_bytes(size: int) -> str:
    """Format bytes into human-readable string."""
    if size < 0:
        return "0 B"
    units = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']
    unit_idx = 0
    val = float(size)
    while val >= 1024.0 and unit_idx < len(units) - 1:
        val /= 1024.0
        unit_idx += 1
    return f"{val:.1f} {units[unit_idx]}" if unit_idx > 0 else f"{int(val)} B"

def get_drive_stats(p: Path) -> dict:
    """Compute volume capacity and free space for a directory."""
    import shutil
    try:
        if not p.exists():
            target = p.parent if p.parent.exists() else Path.home()
        else:
            target = p
        usage = shutil.disk_usage(target)
        total = usage.total
        free = usage.free
        used = usage.used
        percent_used = round((used / total) * 100, 1) if total > 0 else 0.0
        return {
            "total_bytes": total,
            "free_bytes": free,
            "used_bytes": used,
            "total_human": format_bytes(total),
            "free_human": format_bytes(free),
            "used_human": format_bytes(used),
            "percent_used": percent_used
        }
    except Exception as e:
        return {
            "total_bytes": 0,
            "free_bytes": 0,
            "used_bytes": 0,
            "total_human": "Unknown",
            "free_human": "Unknown",
            "used_human": "Unknown",
            "percent_used": 0.0,
            "error": str(e)
        }

def test_writable(p: Path) -> tuple[bool, str]:
    """Test if a path is writable by creating and deleting a temporary marker."""
    try:
        p.mkdir(parents=True, exist_ok=True)
        test_file = p / ".freelansync_perm_test.tmp"
        test_file.write_text("ok", encoding="utf-8")
        test_file.unlink(missing_ok=True)
        return True, "Writable and verified"
    except Exception as e:
        return False, str(e)

def get_default_recommended_storage() -> Path:
    """Default recommended user storage in Pictures/FreeLanSync."""
    return Path.home() / "Pictures" / "FreeLanSync"

def get_storage_presets() -> list[dict]:
    """Return auto-detected storage folder suggestions with live space statistics."""
    import shutil
    presets = []

    # 1. Pictures
    pics = get_default_recommended_storage()
    pics_stats = get_drive_stats(pics)
    presets.append({
        "id": "pictures",
        "title": "Pictures Library",
        "subtitle": "Recommended for photos & videos",
        "path": str(pics.resolve()),
        "free_human": pics_stats["free_human"],
        "percent_used": pics_stats["percent_used"],
        "icon": "image",
        "is_recommended": True
    })

    # 2. Documents
    docs = Path.home() / "Documents" / "FreeLanSync"
    docs_stats = get_drive_stats(docs)
    presets.append({
        "id": "documents",
        "title": "Documents Folder",
        "subtitle": "Standard personal files vault",
        "path": str(docs.resolve()),
        "free_human": docs_stats["free_human"],
        "percent_used": docs_stats["percent_used"],
        "icon": "folder",
        "is_recommended": False
    })

    # 3. Available drive roots on Windows
    if os.name == "nt":
        import string
        try:
            from ctypes import windll
            bitmask = windll.kernel32.GetLogicalDrives()
            for letter in string.ascii_uppercase:
                if bitmask & 1:
                    drive_root = Path(f"{letter}:\\")
                    try:
                        d_stats = get_drive_stats(drive_root)
                        if d_stats["total_bytes"] > 0:
                            target_dir = Path(f"{letter}:\\FreeLanSync_Storage")
                            presets.append({
                                "id": f"drive_{letter.lower()}",
                                "title": f"Drive {letter}: Dedicated",
                                "subtitle": f"Direct high-speed root on {letter}:",
                                "path": str(target_dir),
                                "free_human": d_stats["free_human"],
                                "percent_used": d_stats["percent_used"],
                                "icon": "hard-drive",
                                "is_recommended": False
                            })
                    except Exception:
                        pass
                bitmask >>= 1
        except Exception:
            pass

    return presets

def get_storage_dir() -> Path:
    settings = load_settings()
    custom_dir = os.getenv("FREELANSYNC_STORAGE_DIR", os.getenv("PHOTOSYNC_STORAGE_DIR", settings.get("storage_dir")))
    p = Path(custom_dir) if custom_dir else get_default_recommended_storage()
    try:
        p.mkdir(parents=True, exist_ok=True)
        writable, _ = test_writable(p)
        if not writable:
            fallback = get_default_recommended_storage()
            fallback.mkdir(parents=True, exist_ok=True)
            return fallback
        return p
    except Exception:
        fallback = get_default_recommended_storage()
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback

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
    data_dir = get_app_data_dir()
    new_db = data_dir / "freelansync.db"
    legacy_db = data_dir / "photosync.db"
    if legacy_db.exists() and not new_db.exists():
        return legacy_db
    if data_dir != BASE_DIR and not new_db.exists():
        base_db = BASE_DIR / "freelansync.db"
        if base_db.exists():
            try:
                import shutil
                shutil.copy2(base_db, new_db)
            except Exception:
                pass
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

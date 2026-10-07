"""Database models and management for PhotoSync metadata."""
import sqlite3
import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
from .config import DATABASE_PATH, get_database_path

def init_db(db_path: Optional[Path] = None):
    """Initialize database schema with WAL mode for high concurrency."""
    target_path = db_path if db_path is not None else get_database_path()
    target_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(target_path) as conn:
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA foreign_keys = ON;")
        
        # Paired devices table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS devices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_name TEXT NOT NULL,
                device_id TEXT UNIQUE NOT NULL,
                auth_token TEXT UNIQUE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active INTEGER DEFAULT 1
            );
        """)
        
        # Backed up media files table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS media_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id TEXT NOT NULL,
                sha256 TEXT NOT NULL,
                original_filename TEXT NOT NULL,
                relative_path TEXT NOT NULL,
                file_size INTEGER NOT NULL,
                mime_type TEXT,
                taken_at TIMESTAMP,
                backed_up_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (device_id) REFERENCES devices(device_id),
                UNIQUE (device_id, sha256)
            );
        """)
        
        # Fast index on sha256 and device_id
        conn.execute("CREATE INDEX IF NOT EXISTS idx_media_sha256 ON media_files(sha256);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_media_device ON media_files(device_id);")

def get_connection(db_path: Optional[Path] = None) -> sqlite3.Connection:
    target_path = db_path if db_path is not None else get_database_path()
    init_db(target_path)
    conn = sqlite3.connect(target_path)
    conn.row_factory = sqlite3.Row
    return conn

def register_device(device_name: str, device_id: str, auth_token: str, db_path: Optional[Path] = None):
    with get_connection(db_path) as conn:
        conn.execute("""
            INSERT INTO devices (device_name, device_id, auth_token, last_seen_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(device_id) DO UPDATE SET
                device_name = excluded.device_name,
                auth_token = excluded.auth_token,
                last_seen_at = CURRENT_TIMESTAMP,
                is_active = 1;
        """, (device_name, device_id, auth_token))

def get_device_by_token(auth_token: str, db_path: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    with get_connection(db_path) as conn:
        cur = conn.execute("SELECT * FROM devices WHERE auth_token = ? AND is_active = 1", (auth_token,))
        row = cur.fetchone()
        if row:
            conn.execute("UPDATE devices SET last_seen_at = CURRENT_TIMESTAMP WHERE id = ?", (row["id"],))
            return dict(row)
        return None

def check_existing_hashes(device_id: str, hashes: List[str], db_path: Optional[Path] = None) -> List[str]:
    """Return hashes already backed up for THIS device (UNIQUE is (device_id, sha256))."""
    if not hashes:
        return []
    with get_connection(db_path) as conn:
        placeholders = ",".join(["?"] * len(hashes))
        cur = conn.execute(
            f"SELECT sha256 FROM media_files WHERE device_id = ? AND sha256 IN ({placeholders})",
            [device_id, *hashes],
        )
        return [r["sha256"] for r in cur.fetchall()]

def record_media_backup(
    device_id: str,
    sha256: str,
    original_filename: str,
    relative_path: str,
    file_size: int,
    mime_type: Optional[str],
    taken_at: Optional[str],
    db_path: Optional[Path] = None
):
    with get_connection(db_path) as conn:
        conn.execute("""
            INSERT INTO media_files (device_id, sha256, original_filename, relative_path, file_size, mime_type, taken_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(device_id, sha256) DO NOTHING;
        """, (device_id, sha256, original_filename, relative_path, file_size, mime_type, taken_at))

def get_all_devices(db_path: Optional[Path] = None) -> List[Dict[str, Any]]:
    with get_connection(db_path) as conn:
        # TD-013: never expose auth_token to dashboard/list consumers.
        cur = conn.execute("""
            SELECT d.id, d.device_name, d.device_id, d.created_at, d.last_seen_at, d.is_active,
                   COUNT(m.id) as total_files,
                   COALESCE(SUM(m.file_size), 0) as total_bytes
            FROM devices d
            LEFT JOIN media_files m ON d.device_id = m.device_id
            GROUP BY d.id
            ORDER BY d.last_seen_at DESC;
        """)
        return [dict(r) for r in cur.fetchall()]

def get_recent_media(limit: int = 50, db_path: Optional[Path] = None) -> List[Dict[str, Any]]:
    with get_connection(db_path) as conn:
        cur = conn.execute("""
            SELECT m.*, COALESCE(d.device_name, 'Unknown Device') as device_name 
            FROM media_files m
            LEFT JOIN devices d ON m.device_id = d.device_id
            ORDER BY m.backed_up_at DESC
            LIMIT ?;
        """, (limit,))
        return [dict(r) for r in cur.fetchall()]

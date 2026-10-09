"""Concurrency and lock-resilience tests for SQLite database management (TD-019)."""
import concurrent.futures
import sqlite3
import pytest
from pathlib import Path
from server.database import (
    init_db,
    get_connection,
    register_device,
    record_media_backup,
    check_existing_hashes,
    _initialized_dbs,
)

def test_database_busy_timeout_configured(tmp_path: Path):
    db_file = tmp_path / "test_busy.db"
    conn = get_connection(db_file)
    cur = conn.execute("PRAGMA busy_timeout;")
    row = cur.fetchone()
    conn.close()
    assert row[0] >= 5000, "TD-019: busy_timeout must be configured to at least 5000ms"

def test_init_db_runs_once_per_path(tmp_path: Path):
    db_file = tmp_path / "test_init_once.db"
    path_key = str(db_file.resolve())
    _initialized_dbs.discard(path_key)

    assert path_key not in _initialized_dbs
    conn1 = get_connection(db_file)
    conn1.close()
    assert path_key in _initialized_dbs

    # Second connection must reuse initialized state without re-running DDL
    conn2 = get_connection(db_file)
    conn2.close()
    assert path_key in _initialized_dbs

def test_concurrent_writes_do_not_throw_database_locked(tmp_path: Path):
    """TD-019 challenge test: 20 concurrent threads writing simultaneously."""
    db_file = tmp_path / "concurrent_stress.db"
    register_device("TestDevice", "dev_1", "tok_1", db_path=db_file)

    def write_worker(idx: int):
        record_media_backup(
            device_id="dev_1",
            sha256=f"hash_{idx:04d}",
            original_filename=f"photo_{idx}.jpg",
            relative_path=f"2026/10/photo_{idx}.jpg",
            file_size=1024 * (idx + 1),
            mime_type="image/jpeg",
            taken_at="2026-10-09T12:00:00Z",
            db_path=db_file
        )
        return idx

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(write_worker, i) for i in range(25)]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]

    assert len(results) == 25
    hashes = [f"hash_{i:04d}" for i in range(25)]
    existing = check_existing_hashes("dev_1", hashes, db_path=db_file)
    assert len(existing) == 25

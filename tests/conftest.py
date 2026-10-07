"""Pytest configuration and global environment isolation fixture."""
import pytest
from pathlib import Path

@pytest.fixture(autouse=True)
def isolate_test_environment(tmp_path, monkeypatch):
    """Ensure all tests run against an isolated sandbox and never pollute live user storage or database."""
    test_storage = tmp_path / "sandbox_storage"
    test_backups = test_storage / "Backups"
    test_transfers = test_storage / "Transfers"
    test_quickdrop = test_storage / "QuickDrop"
    test_db = test_storage / "sandbox_freelansync.db"

    for d in (test_storage, test_backups, test_transfers, test_quickdrop):
        d.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr("server.config.get_storage_dir", lambda: test_storage)
    monkeypatch.setattr("server.config.get_backup_dir", lambda: test_backups)
    monkeypatch.setattr("server.config.get_transfers_dir", lambda: test_transfers)
    monkeypatch.setattr("server.config.get_quickdrop_dir", lambda: test_quickdrop)
    monkeypatch.setattr("server.config.get_database_path", lambda: test_db)
    monkeypatch.setattr("server.config.STORAGE_DIR", test_storage)
    monkeypatch.setattr("server.config.BACKUP_DIR", test_backups)
    monkeypatch.setattr("server.config.TRANSFERS_DIR", test_transfers)
    monkeypatch.setattr("server.config.QUICKDROP_DIR", test_quickdrop)
    monkeypatch.setattr("server.config.DATABASE_PATH", test_db)
    monkeypatch.setattr("server.database.get_database_path", lambda: test_db)

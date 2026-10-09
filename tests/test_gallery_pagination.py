"""Feature #1 — Gallery Pagination: server-side limit/offset on /api/v1/photos/recent."""
import secrets
import pytest
from fastapi.testclient import TestClient

from server.main import app
from server.database import init_db, register_device, record_media_backup

client = TestClient(app)


@pytest.fixture()
def seeded_db(tmp_path, monkeypatch):
    """Isolated storage/DB with one paired device registered."""
    test_storage = tmp_path / "test_storage"
    test_backup = test_storage / "Backups"
    test_db = test_storage / "test_pagination.db"
    test_storage.mkdir(parents=True, exist_ok=True)
    test_backup.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr("server.config.STORAGE_DIR", test_storage)
    monkeypatch.setattr("server.config.BACKUP_DIR", test_backup)
    monkeypatch.setattr("server.database.get_database_path", lambda: test_db)
    init_db(test_db)

    register_device("Pixel 8", f"pixel-{secrets.token_hex(4)}", f"tok-{secrets.token_hex(8)}", test_db)

    return test_db


@pytest.fixture()
def five_media(seeded_db):
    """Five media rows. `backed_up_at` ties within the same second (CURRENT_TIMESTAMP
    has 1s resolution), so a deterministic total order needs the id tiebreak —
    this exercises pagination correctness under timestamp ties."""
    import sqlite3

    test_db = seeded_db
    with sqlite3.connect(test_db) as conn:
        device_id = conn.execute("SELECT device_id FROM devices LIMIT 1").fetchone()[0]
    for i in range(5):
        record_media_backup(
            device_id=device_id,
            sha256=secrets.token_hex(32),
            original_filename=f"IMG_{i:04d}.jpg",
            relative_path=f"Pixel_8/IMG_{i:04d}.jpg",
            file_size=1000 + i,
            mime_type="image/jpeg",
            taken_at="2026-10-07T12:00:00Z",
            db_path=test_db,
        )
    return test_db


def _ids(payload):
    return [m["id"] for m in payload["recent_media"]]


def test_page_walk_covers_all_rows_once(five_media):
    """limit/offset walk must return every row exactly once, newest first."""
    seen = []
    offset = 0
    while True:
        resp = client.get("/api/v1/photos/recent", params={"limit": 2, "offset": offset})
        assert resp.status_code == 200
        body = resp.json()
        page_ids = _ids(body)
        if not page_ids:
            break
        seen.extend(page_ids)
        assert body["pagination"]["has_more"] is (len(page_ids) == 2)
        if not body["pagination"]["has_more"]:
            break
        offset += 2
    assert len(seen) == 5
    assert len(set(seen)) == 5  # no duplicates across pages
    assert seen == sorted(seen, reverse=True)  # newest (highest id) first


def test_has_more_false_on_short_page(five_media):
    resp = client.get("/api/v1/photos/recent", params={"limit": 2, "offset": 4})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["recent_media"]) == 1
    assert body["pagination"] == {"limit": 2, "offset": 4, "returned": 1, "has_more": False}


def test_empty_past_end(five_media):
    resp = client.get("/api/v1/photos/recent", params={"limit": 10, "offset": 100})
    assert resp.status_code == 200
    body = resp.json()
    assert body["recent_media"] == []
    assert body["pagination"]["has_more"] is False


def test_defaults_preserve_behavior(five_media):
    """No params must work like before: all 5 rows, default page size, contract key intact."""
    resp = client.get("/api/v1/photos/recent")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["recent_media"]) == 5
    assert body["pagination"]["limit"] == 60 and body["pagination"]["offset"] == 0
    assert body["pagination"]["has_more"] is False
    assert "recent_media" in body  # backward-compatible payload key


def test_invalid_pagination_params_rejected(five_media):
    assert client.get("/api/v1/photos/recent", params={"limit": 0}).status_code == 422
    assert client.get("/api/v1/photos/recent", params={"limit": 501}).status_code == 422
    assert client.get("/api/v1/photos/recent", params={"limit": 2, "offset": -1}).status_code == 422


def test_response_carries_device_name_join(five_media):
    resp = client.get("/api/v1/photos/recent", params={"limit": 1})
    row = resp.json()["recent_media"][0]
    assert row["device_name"] == "Pixel 8"
    assert row["original_filename"].startswith("IMG_")

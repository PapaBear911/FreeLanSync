"""Comprehensive tests for PhotoSync Desktop Server."""
import pytest
import hashlib
import tempfile
import shutil
import secrets
from pathlib import Path
from fastapi.testclient import TestClient

from server.main import app
from server.database import init_db
from server.auth import pairing_manager
from server.storage import storage_manager

@pytest.fixture(autouse=True)
def setup_test_env(tmp_path, monkeypatch):
    """Isolate database and storage to a temporary directory during tests."""
    test_storage = tmp_path / "test_storage"
    test_backup = test_storage / "Backups"
    test_db = test_storage / "test_photosync.db"

    test_storage.mkdir(parents=True, exist_ok=True)
    test_backup.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr("server.config.STORAGE_DIR", test_storage)
    monkeypatch.setattr("server.config.BACKUP_DIR", test_backup)
    monkeypatch.setattr("server.config.DATABASE_PATH", test_db)
    monkeypatch.setattr(storage_manager, "backup_dir", test_backup)

    init_db(test_db)
    yield

client = TestClient(app)

def test_ping():
    response = client.get("/api/v1/ping")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "online"
    assert "version" in data

def test_pairing_flow():
    # 1. Get pairing info
    info_resp = client.get("/api/v1/pairing/info")
    assert info_resp.status_code == 200
    info_data = info_resp.json()
    active_pin = info_data["pin"]
    assert len(active_pin) == 6
    assert "qr_svg" in info_data

    # 2. Pair with invalid PIN
    bad_pair = client.post("/api/v1/pairing/verify", json={
        "pin": "000000",
        "device_name": "Test Phone",
        "device_id": "phone-uuid-123"
    })
    assert bad_pair.status_code == 200
    assert bad_pair.json()["success"] is False

    # 3. Pair with valid PIN
    good_pair = client.post("/api/v1/pairing/verify", json={
        "pin": active_pin,
        "device_name": "Test Phone",
        "device_id": "phone-uuid-123"
    })
    assert good_pair.status_code == 200
    res_data = good_pair.json()
    assert res_data["success"] is True
    assert res_data["auth_token"] is not None
    token = res_data["auth_token"]

    # 4. Verify auth token allows batch check
    h1 = secrets.token_hex(32)
    h2 = secrets.token_hex(32)
    batch_resp = client.post(
        "/api/v1/photos/check-batch",
        headers={"Authorization": f"Bearer {token}"},
        json={"hashes": [h1, h2]}
    )
    assert batch_resp.status_code == 200
    batch_data = batch_resp.json()
    assert len(batch_data["existing_hashes"]) == 0
    assert len(batch_data["missing_hashes"]) == 2

def test_photo_upload_and_deduplication():
    # Setup paired device
    pin = pairing_manager.generate_pin()
    dev_id = f"pixel-8-{secrets.token_hex(4)}"
    pair_resp = client.post("/api/v1/pairing/verify", json={
        "pin": pin,
        "device_name": "Pixel 8",
        "device_id": dev_id
    })
    token = pair_resp.json()["auth_token"]

    # Create unique dummy photo bytes
    photo_content = b"\xFF\xD8\xFF\xE0\x00\x10JFIF" + secrets.token_bytes(64)
    photo_hash = hashlib.sha256(photo_content).hexdigest()

    # 1. Pre-flight check: hash should be missing
    check_resp = client.post(
        "/api/v1/photos/check-batch",
        headers={"Authorization": f"Bearer {token}"},
        json={"hashes": [photo_hash]}
    )
    assert photo_hash in check_resp.json()["missing_hashes"]

    # 2. Upload file
    upload_resp = client.post(
        "/api/v1/photos/upload",
        headers={"Authorization": f"Bearer {token}"},
        data={"sha256": photo_hash, "taken_at": "2026-10-07T12:00:00Z"},
        files={"file": ("photo_vacation.jpg", photo_content, "image/jpeg")}
    )
    assert upload_resp.status_code == 200
    upload_data = upload_resp.json()
    assert upload_data["success"] is True
    assert "Pixel_8" in upload_data["relative_path"] or "Pixel 8" in upload_data["relative_path"]

    # 3. Post-upload check: hash should now be existing!
    check_resp2 = client.post(
        "/api/v1/photos/check-batch",
        headers={"Authorization": f"Bearer {token}"},
        json={"hashes": [photo_hash]}
    )
    assert photo_hash in check_resp2.json()["existing_hashes"]
    assert len(check_resp2.json()["missing_hashes"]) == 0

    # 4. Re-uploading same file should succeed without corrupting or duplicating
    re_upload = client.post(
        "/api/v1/photos/upload",
        headers={"Authorization": f"Bearer {token}"},
        data={"sha256": photo_hash, "taken_at": "2026-10-07T12:00:00Z"},
        files={"file": ("photo_vacation.jpg", photo_content, "image/jpeg")}
    )
    assert re_upload.status_code == 200

def test_tampered_hash_rejection():
    # Setup paired device
    pin = pairing_manager.generate_pin()
    pair_resp = client.post("/api/v1/pairing/verify", json={
        "pin": pin,
        "device_name": "Galaxy S24",
        "device_id": f"galaxy-s24-{secrets.token_hex(4)}"
    })
    token = pair_resp.json()["auth_token"]

    photo_content = b"sample_real_image_payload"
    wrong_hash = "0" * 64

    # Upload with tampered/wrong SHA-256
    upload_resp = client.post(
        "/api/v1/photos/upload",
        headers={"Authorization": f"Bearer {token}"},
        data={"sha256": wrong_hash, "taken_at": "2026-10-07T12:00:00Z"},
        files={"file": ("tampered.jpg", photo_content, "image/jpeg")}
    )
    assert upload_resp.status_code == 400
    assert "mismatch" in upload_resp.json()["detail"].lower()

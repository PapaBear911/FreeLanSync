import pytest
import secrets
from fastapi.testclient import TestClient
from server.main import app
from server.database import register_device, init_db

def test_space_checker_success_and_rejection(tmp_path, monkeypatch):
    init_db()
    token = "test_token_" + secrets.token_hex(8)
    register_device("Test Laptop", "test-device-id", token)
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {token}"}
    
    # 1. Normal requirement (e.g. 10 MB) -> should be allowed
    res = client.post(
        "/api/v1/transfer/check-space",
        json={"required_bytes": 10 * 1024 * 1024},
        headers=headers
    )
    assert res.status_code == 200
    data = res.json()
    assert data["allowed"] is True
    assert data["free_bytes"] > 0
    assert "free_human" in data

    # 2. Impossible requirement (e.g. 50 Petabytes) -> should be rejected
    res = client.post(
        "/api/v1/transfer/check-space",
        json={"required_bytes": 50 * 1024 * 1024 * 1024 * 1024 * 1024},
        headers=headers
    )
    assert res.status_code == 200
    data = res.json()
    assert data["allowed"] is False
    assert "Insufficient disk space" in data["message"]

    # 3. GET storage info status
    info_res = client.get("/api/v1/transfer/storage-info", headers=headers)
    assert info_res.status_code == 200
    info_data = info_res.json()
    assert "free_bytes" in info_data
    assert "total_bytes" in info_data
    assert "used_bytes" in info_data

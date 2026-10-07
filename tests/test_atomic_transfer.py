import io
import uuid
import pytest
import secrets
from fastapi.testclient import TestClient
from server.main import app
from server.database import register_device, init_db
from server.config import get_transfers_dir

def test_atomic_upload_and_cancellation():
    init_db()
    token = "test_token_" + secrets.token_hex(8)
    register_device("Test Laptop", "test-device-id", token)
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {token}"}
    
    # 1. Normal upload -> atomic rename to final file
    tid1 = str(uuid.uuid4())
    content = b"GIGABIT_LAN_STREAMING_DATA" * 1000
    res = client.post(
        "/api/v1/transfer/upload-chunked",
        data={"transfer_id": tid1, "filename": "test_large.dat", "total_size": len(content)},
        files={"file": ("test_large.dat", io.BytesIO(content), "application/octet-stream")},
        headers=headers
    )
    assert res.status_code == 200
    assert res.json()["success"] is True
    dest_path = get_transfers_dir() / "test_large.dat"
    assert dest_path.exists()
    assert dest_path.read_bytes() == content

    # Check status endpoint
    status_res = client.get(f"/api/v1/transfer/status/{tid1}", headers=headers)
    assert status_res.status_code == 200
    assert status_res.json()["status"] == "COMPLETED"

    # 2. Cancelled transfer -> unlinks .tmp file immediately
    tid2 = str(uuid.uuid4())
    # Stage a mock temp transfer
    from server.transfer_manager import transfer_manager
    tmp_file = get_transfers_dir() / f".tmp_{tid2}_test_cancel.dat"
    tmp_file.write_bytes(b"PARTIAL_UNFINISHED_DATA" * 50)
    assert tmp_file.exists()

    transfer_manager.register_transfer(tid2, "test_cancel.dat", tmp_file, 1000000)

    cancel_res = client.post(f"/api/v1/transfer/cancel/{tid2}", headers=headers)
    assert cancel_res.status_code == 200
    assert cancel_res.json()["success"] is True
    # Verify .tmp file was deleted by rollback!
    assert not tmp_file.exists()

    # Check status endpoint reflects CANCELLED
    stat2 = client.get(f"/api/v1/transfer/status/{tid2}", headers=headers)
    assert stat2.status_code == 200
    assert stat2.json()["status"] == "CANCELLED"

def test_web_client_unauthenticated_transfer():
    """Verify that local web dashboard clients can perform transfers without device bearer tokens."""
    init_db()
    client = TestClient(app)
    
    # Pre-flight space check without Authorization header
    space_res = client.post("/api/v1/transfer/check-space", json={"required_bytes": 1024 * 1024})
    assert space_res.status_code == 200
    assert space_res.json()["allowed"] is True

    # Web client direct file upload
    tid = str(uuid.uuid4())
    content = b"WEB_DASHBOARD_DRAG_AND_DROP_PAYLOAD"
    upload_res = client.post(
        "/api/v1/transfer/upload-chunked",
        data={"transfer_id": tid, "filename": "web_upload.txt", "total_size": len(content)},
        files={"file": ("web_upload.txt", io.BytesIO(content), "text/plain")}
    )
    assert upload_res.status_code == 200
    assert upload_res.json()["success"] is True

    # Check status without auth header
    status_res = client.get(f"/api/v1/transfer/status/{tid}")
    assert status_res.status_code == 200
    assert status_res.json()["status"] == "COMPLETED"

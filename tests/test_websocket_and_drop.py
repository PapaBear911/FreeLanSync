"""Unit tests for WebSocket device bridge and Quick-Drop endpoints."""
import pytest
import io
import json
from fastapi.testclient import TestClient
from server.main import app
from server.database import init_db, register_device
from server.websocket_manager import ws_manager

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_db():
    init_db()

def test_continuity_status_initial():
    response = client.get("/api/v1/continuity/status")
    assert response.status_code == 200
    data = response.json()
    assert "battery" in data
    assert "media" in data
    assert "notifications" in data

def test_quick_drop_lifecycle():
    # 1. Upload a file to Quick-Drop
    file_content = b"Hello from PC to Android via Quick-Drop!"
    file_obj = io.BytesIO(file_content)
    
    response = client.post(
        "/api/v1/drop/upload",
        files={"file": ("test_doc.txt", file_obj, "text/plain")}
    )
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["success"] is True
    file_id = res_data["drop"]["file_id"]
    assert res_data["drop"]["filename"] == "test_doc.txt"
    assert res_data["drop"]["size"] == len(file_content)

    # 2. Check pending drops
    pending_resp = client.get("/api/v1/drop/pending")
    assert pending_resp.status_code == 200
    pending_list = pending_resp.json()["pending"]
    assert any(item["file_id"] == file_id for item in pending_list)

    # 3. Download the file
    download_resp = client.get(f"/api/v1/drop/download/{file_id}")
    assert download_resp.status_code == 200
    assert download_resp.content == file_content

    # 4. Delete the drop
    del_resp = client.delete(f"/api/v1/drop/{file_id}")
    assert del_resp.status_code == 200
    assert del_resp.json()["success"] is True

    # 5. Verify it's no longer pending
    download_fail = client.get(f"/api/v1/drop/download/{file_id}")
    assert download_fail.status_code == 404

def test_clipboard_endpoint():
    payload = {"text": "Copied link: https://getsynco.vercel.app/", "source": "desktop"}
    resp = client.post("/api/v1/clipboard", json=payload)
    assert resp.status_code == 200
    assert resp.json()["success"] is True

    get_resp = client.get("/api/v1/clipboard")
    assert get_resp.status_code == 200
    assert get_resp.json()["clipboard"]["text"] == "Copied link: https://getsynco.vercel.app/"

def test_websocket_ui_connection():
    with client.websocket_connect("/api/v1/ws/device-bridge?client_type=ui") as ws:
        # First message should be STATE_SNAPSHOT
        msg = ws.receive_json()
        assert msg["event"] == "STATE_SNAPSHOT"
        assert "data" in msg

def test_websocket_device_authentication():
    # 1. Unauthenticated connection should be closed
    with pytest.raises(Exception):
        with client.websocket_connect("/api/v1/ws/device-bridge?client_type=device") as ws:
            ws.receive_json()

    # 2. Create a mock registered device
    token = "mock_token_123"
    register_device(device_name="Galaxy S24", device_id="test_phone_999", auth_token=token)

    # 3. Authenticated connection
    with client.websocket_connect(f"/api/v1/ws/device-bridge?client_type=device&token={token}") as ws:
        # Send battery telemetry from device
        ws.send_json({
            "event": "BATTERY_STATUS",
            "data": {"level": 88, "is_charging": True, "health": "GOOD"}
        })
        
        # Send notification from device
        ws.send_json({
            "event": "NOTIFICATION_POSTED",
            "data": {
                "id": "notif_123",
                "package": "com.whatsapp",
                "app_name": "WhatsApp",
                "title": "Alice",
                "text": "See you soon!",
                "can_reply": True
            }
        })

    # Verify server stored state
    status_resp = client.get("/api/v1/continuity/status")
    data = status_resp.json()
    assert data["battery"]["level"] == 88
    assert data["battery"]["is_charging"] is True
    assert len(data["notifications"]) >= 1
    assert data["notifications"][0]["title"] == "Alice"

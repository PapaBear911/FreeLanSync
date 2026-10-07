"""End-to-End Simulation Test: Complete PhotoSync & Synco Device Continuity Suite.
Tests WebSocket bridge, Battery telemetry, Notification mirroring, Media playback control,
Incoming call alert, Clipboard sync, Quick-Drop file transfer, and Photo archival.
"""
import time
import json
import hashlib
import io
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient
from server.main import app
from server.database import init_db, get_device_by_token
from server.config import SERVER_PORT, BACKUP_DIR, get_local_ip

client = TestClient(app)

def run_simulation():
    print("=" * 65)
    print("  PhotoSync & Synco Full Continuity Suite: E2E Simulation")
    print("=" * 65)

    # 1. Ping Server
    print("\n[1] Pinging server...")
    ping_res = client.get("/api/v1/ping")
    assert ping_res.status_code == 200
    ping_data = ping_res.json()
    print(f"    Server online! Status: {ping_data['status']} | Host: {ping_data['host']}:{ping_data['port']}")

    # 2. Fetch Pairing PIN & QR
    print("\n[2] Fetching active Desktop 6-digit PIN and QR info...")
    pair_info_res = client.get("/api/v1/pairing/info")
    assert pair_info_res.status_code == 200
    pair_info = pair_info_res.json()
    pin = pair_info["pin"]
    print(f"    Active Desktop PIN: {pin} (Expires in {pair_info['expires_in']}s)")

    # 3. Simulate Android Phone pairing
    print("\n[3] Android phone pairing with 6-digit PIN...")
    pair_post_res = client.post("/api/v1/pairing/verify", json={
        "pin": pin,
        "device_name": "Pixel 8 Pro (Simulated)",
        "device_id": "device_pixel_8_pro_simulation"
    })
    assert pair_post_res.status_code == 200
    pair_data = pair_post_res.json()
    assert pair_data["success"] is True
    auth_token = pair_data["auth_token"]
    print(f"    Pairing SUCCESS! Received auth token: {auth_token[:16]}...")

    # 4. Open Dual WebSocket Connections: Android Phone Socket & Desktop UI Socket
    print("\n[4] Establishing duplex WebSocket channels (Android Device & Web Dashboard)...")
    with client.websocket_connect(f"/api/v1/ws/device-bridge?client_type=device&token={auth_token}") as phone_ws:
        print("    -> Android Phone WebSocket connected.")

        with client.websocket_connect("/api/v1/ws/device-bridge?client_type=ui") as ui_ws:
            print("    -> Desktop Web Dashboard WebSocket connected.")

            # Dashboard receives initial STATE_SNAPSHOT
            snapshot = ui_ws.receive_json()
            assert snapshot["event"] == "STATE_SNAPSHOT"
            print("    -> Desktop received initial STATE_SNAPSHOT.")

            # 5. Battery Telemetry (Phone -> Server -> Desktop UI)
            print("\n[5] Transmitting phone battery telemetry over WebSocket...")
            phone_ws.send_json({
                "event": "BATTERY_STATUS",
                "data": {"level": 89, "is_charging": True, "health": "GOOD"}
            })
            ui_battery = ui_ws.receive_json()
            assert ui_battery["event"] == "BATTERY_STATUS"
            assert ui_battery["data"]["level"] == 89
            assert ui_battery["data"]["is_charging"] is True
            print(f"    -> Desktop UI received: Battery {ui_battery['data']['level']}% (Charging: {ui_battery['data']['is_charging']})")

            # 6. Notification Mirroring (Phone -> Server -> Desktop UI)
            print("\n[6] Simulating incoming WhatsApp notification mirroring (Synco Protocol)...")
            phone_ws.send_json({
                "event": "NOTIFICATION_POSTED",
                "data": {
                    "id": "notif_msg_001",
                    "package": "com.whatsapp",
                    "app_name": "WhatsApp",
                    "title": "Alex Vance",
                    "text": "Hey! Are you ready for the deployment test?",
                    "can_reply": True
                }
            })
            ui_notif = ui_ws.receive_json()
            assert ui_notif["event"] == "NOTIFICATION_POSTED"
            assert ui_notif["data"]["app_name"] == "WhatsApp"
            assert ui_notif["data"]["title"] == "Alex Vance"
            print(f"    -> Desktop UI received Notification Toast: [{ui_notif['data']['app_name']}] {ui_notif['data']['title']}: \"{ui_notif['data']['text']}\"")

            # 7. Incoming Phone Call Alert (Phone -> Server -> Desktop UI)
            print("\n[7] Simulating incoming phone call alert...")
            phone_ws.send_json({
                "event": "CALL_INCOMING",
                "data": {
                    "caller_name": "Sarah Connor",
                    "phone_number": "+1 (555) 019-2834"
                }
            })
            ui_call = ui_ws.receive_json()
            assert ui_call["event"] == "CALL_INCOMING"
            assert ui_call["data"]["caller_name"] == "Sarah Connor"
            print(f"    -> Desktop UI received Incoming Call Banner: \"{ui_call['data']['caller_name']}\" ({ui_call['data']['phone_number']})")

            # 8. Media Telemetry & Remote Playback Control (Phone <-> Desktop)
            print("\n[8] Testing Media Telemetry and Remote Playback Controller...")
            # Phone sends now playing
            phone_ws.send_json({
                "event": "MEDIA_PLAYBACK_STATUS",
                "data": {
                    "title": "Blinding Lights",
                    "artist": "The Weeknd",
                    "album": "After Hours",
                    "is_playing": True
                }
            })
            ui_media = ui_ws.receive_json()
            assert ui_media["event"] == "MEDIA_PLAYBACK_STATUS"
            assert ui_media["data"]["title"] == "Blinding Lights"
            print(f"    -> Desktop UI received Now Playing: \"{ui_media['data']['title']}\" by {ui_media['data']['artist']}")

            # Desktop sends Pause command to phone
            print("    Desktop UI clicks 'Pause'...")
            ui_ws.send_json({
                "event": "MEDIA_CONTROL_COMMAND",
                "data": {"action": "PAUSE"}
            })
            phone_cmd = phone_ws.receive_json()
            assert phone_cmd["event"] == "MEDIA_CONTROL_COMMAND"
            assert phone_cmd["data"]["action"] == "PAUSE"
            print(f"    -> Android phone received remote media command: {phone_cmd['data']['action']}")

            # 9. Bidirectional Shared Clipboard
            print("\n[9] Testing Bidirectional Clipboard Synchronization...")
            # Phone -> Desktop
            phone_ws.send_json({
                "event": "CLIPBOARD_UPDATE",
                "data": {"text": "https://github.com/dhruvesh07/Synco", "source": "phone"}
            })
            ui_clip = ui_ws.receive_json()
            assert ui_clip["event"] == "CLIPBOARD_UPDATE"
            assert ui_clip["data"]["text"] == "https://github.com/dhruvesh07/Synco"
            print(f"    -> Desktop UI received phone clipboard text: \"{ui_clip['data']['text']}\"")

            # Desktop -> Phone
            print("    Desktop sending text to phone clipboard...")
            ui_ws.send_json({
                "event": "CLIPBOARD_UPDATE",
                "data": {"text": "SECURE_WIFI_KEY_98765", "source": "desktop"}
            })
            phone_clip = phone_ws.receive_json()
            assert phone_clip["event"] == "CLIPBOARD_UPDATE"
            assert phone_clip["data"]["text"] == "SECURE_WIFI_KEY_98765"
            print(f"    -> Android phone received PC clipboard text: \"{phone_clip['data']['text']}\"")

            # 10. Universal Quick-Drop (PC -> Phone)
            print("\n[10] Testing Universal Quick-Drop (PC file drop -> Android download)...")
            file_payload = b"Sample configuration & test firmware file transmitted wirelessly over LAN!"
            upload_resp = client.post(
                "/api/v1/drop/upload",
                files={"file": ("firmware_config.bin", io.BytesIO(file_payload), "application/octet-stream")}
            )
            assert upload_resp.status_code == 200
            drop_info = upload_resp.json()["drop"]
            file_id = drop_info["file_id"]
            print(f"    PC uploaded Quick-Drop file: '{drop_info['filename']}' ({drop_info['size']} bytes, ID: {file_id})")

            # Phone WebSocket receives QUICK_DROP_AVAILABLE
            phone_drop_ev = phone_ws.receive_json()
            assert phone_drop_ev["event"] == "QUICK_DROP_AVAILABLE"
            assert phone_drop_ev["data"]["file_id"] == file_id
            print(f"    -> Android phone received real-time QUICK_DROP_AVAILABLE event for '{phone_drop_ev['data']['filename']}'")

            # Phone downloads the drop
            dl_resp = client.get(f"/api/v1/drop/download/{file_id}")
            assert dl_resp.status_code == 200
            assert dl_resp.content == file_payload
            dl_hash = hashlib.sha256(dl_resp.content).hexdigest().lower()
            assert dl_hash == drop_info["sha256"]
            print(f"    -> Android phone downloaded file and verified SHA-256 checksum ({dl_hash[:12]}...)!")

            # Clean up drop
            del_resp = client.delete(f"/api/v1/drop/{file_id}")
            assert del_resp.status_code == 200
            print("    -> Quick-Drop item acknowledged and cleared.")

    # 11. Verify Camera Roll Archival & Deduplication remains intact
    print("\n[11] Verifying Core Camera Roll Backup & Deduplication...")
    import secrets
    mock_img_bytes = f"JPEG_DATA_SIMULATION_IMAGE_{time.time()}_{secrets.token_hex(4)}".encode()
    img_hash = hashlib.sha256(mock_img_bytes).hexdigest().lower()

    # Preflight batch check
    batch_res = client.post(
        "/api/v1/photos/check-batch",
        json={"hashes": [img_hash]},
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert batch_res.status_code == 200
    missing = batch_res.json()["missing_hashes"]
    assert img_hash in missing

    # Upload photo
    up_res = client.post(
        "/api/v1/photos/upload",
        files={"file": ("IMG_CONTINUITY_TEST.jpg", io.BytesIO(mock_img_bytes), "image/jpeg")},
        data={"sha256": img_hash, "taken_at": "2026-10-07T12:00:00Z"},
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert up_res.status_code == 200
    assert up_res.json()["success"] is True
    print(f"    -> Uploaded test photo to archive: {up_res.json()['relative_path']}")

    # Deduplication check
    batch_res2 = client.post(
        "/api/v1/photos/check-batch",
        json={"hashes": [img_hash]},
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert batch_res2.status_code == 200
    assert img_hash in batch_res2.json()["existing_hashes"]
    print("    -> 100% Deduplication verified on secondary check!")

    # Cleanup test photo from backup dir
    try:
        backed_up = BACKUP_DIR / up_res.json()["relative_path"]
        if backed_up.exists():
            backed_up.unlink(missing_ok=True)
    except Exception:
        pass

    print("\n" + "=" * 65)
    print("  ALL 11/11 CONTINUITY & SYNCO VERIFICATION STEPS PASSED 100%!")
    print("=" * 65)

if __name__ == "__main__":
    run_simulation()

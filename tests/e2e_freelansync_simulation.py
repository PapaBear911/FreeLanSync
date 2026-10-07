"""End-to-End Comprehensive Simulation Test for FreeLanSync & LANSync Gigabit Transfer Engine.

Covers:
1. FreeLanSync Branding & Service Ping
2. 6-Digit PIN Pairing & Auth Token Issuance
3. Duplex WebSockets (Android Phone + Desktop UI)
4. Pre-Flight Smart Disk Space Validation (Allowed & Rejected)
5. Gigabit Chunked Atomic Transfer Streaming & Progress Tracking
6. Cancellation Rollback (Purging unverified .tmp staging files)
7. Recursive Folder Tree Upload (Preserving directory structure & subfolders)
8. Streaming Zip Archive Download (Zero intermediate disk bloat)
9. Phone Battery Telemetry & Remote Control HUD
10. Synco Notification Mirroring & Call Alerting
11. Universal Clipboard Synchronization
"""
import io
import time
import json
import uuid
import zipfile
import secrets
import hashlib
from fastapi.testclient import TestClient
from server.main import app
from server.database import init_db
from server.config import SERVICE_NAME, MDNS_SERVICE_TYPE, get_transfers_dir
from server.transfer_manager import transfer_manager

def wait_for_ui_event(ws, expected_event, timeout_iterations=15):
    for _ in range(timeout_iterations):
        raw = ws.receive_text()
        msg = json.loads(raw)
        if msg.get("event") == expected_event:
            return msg
    raise TimeoutError(f"Did not receive expected event '{expected_event}'")

def run_freelansync_simulation():
    print("=" * 70)
    print("   FreeLanSync & LANSync Gigabit Transfer Engine: Full E2E Simulation")
    print("=" * 70)

    init_db()
    client = TestClient(app)

    # 1. Branding & Ping
    print("\n[1] Verifying FreeLanSync Server Branding & Health Ping...")
    res = client.get("/api/v1/ping")
    assert res.status_code == 200
    ping_data = res.json()
    assert ping_data["status"] == "online"
    assert "FreeLanSync" in ping_data["service"]
    assert "FreeLanSync" in SERVICE_NAME
    assert "freelansync" in MDNS_SERVICE_TYPE.lower()
    print(f"    Server online! Service: '{ping_data['service']}' (v{ping_data['version']}) on {ping_data['host']}:{ping_data['port']}")

    # 2. 6-Digit PIN Pairing
    print("\n[2] Pairing Android Device via 6-digit PIN...")
    pair_info = client.get("/api/v1/pairing/info").json()
    pin = pair_info["pin"]
    assert len(pin) == 6
    assert "FreeLanSync.apk" in pair_info["apk_download_url"]

    phone_device_id = "device_pixel_gigabit_" + secrets.token_hex(4)
    verify_res = client.post("/api/v1/pairing/verify", json={
        "pin": pin,
        "device_name": "Google Pixel 9 Pro (Gigabit)",
        "device_id": phone_device_id
    })
    assert verify_res.status_code == 200
    auth_token = verify_res.json()["auth_token"]
    assert auth_token is not None
    headers = {"Authorization": f"Bearer {auth_token}"}
    print(f"    Pairing SUCCESS! Issued bearer token: {auth_token[:16]}...")

    # 3. Duplex WebSockets
    print("\n[3] Establishing Duplex WebSockets for Real-Time Streaming & Control...")
    with client.websocket_connect(f"/api/v1/ws/device-bridge?client_type=device&token={auth_token}") as phone_ws:
        with client.websocket_connect("/api/v1/ws/device-bridge?client_type=ui") as desktop_ws:
            init_msg = json.loads(desktop_ws.receive_text())
            assert init_msg["event"] == "STATE_SNAPSHOT"
            print("    -> Phone & Desktop WebSockets connected with STATE_SNAPSHOT received.")

            # 4. Smart Pre-Flight Disk Space Validation
            print("\n[4] Testing Smart Pre-Flight Storage Space Validation...")
            # Normal file: 50 MB
            check_normal = client.post(
                "/api/v1/transfer/check-space",
                json={"required_bytes": 50 * 1024 * 1024},
                headers=headers
            ).json()
            assert check_normal["allowed"] is True
            print(f"    -> 50 MB Transfer Check: ALLOWED ({check_normal['free_human']} available)")

            # Gigantic impossible file: 100 Petabytes
            check_oversize = client.post(
                "/api/v1/transfer/check-space",
                json={"required_bytes": 100 * 1024 * 1024 * 1024 * 1024 * 1024},
                headers=headers
            ).json()
            assert check_oversize["allowed"] is False
            assert "Insufficient disk space" in check_oversize["message"]
            print(f"    -> 100 PB Transfer Check: REJECTED SAFELY ({check_oversize['message']})")

            # 5. Gigabit Atomic Transfer Streaming
            print("\n[5] Testing Gigabit Atomic Streaming Transfer with Progress HUD...")
            transfer_id = "tx_" + secrets.token_hex(8)
            payload_data = b"GIGABIT_LAN_TRANSFER_PAYLOAD_BLOCK_" * 5000  # ~175 KB
            
            upload_res = client.post(
                "/api/v1/transfer/upload-chunked",
                data={
                    "transfer_id": transfer_id,
                    "filename": "render_project_4k.raw",
                    "total_size": len(payload_data)
                },
                files={"file": ("render_project_4k.raw", io.BytesIO(payload_data), "application/octet-stream")},
                headers=headers
            )
            assert upload_res.status_code == 200
            up_json = upload_res.json()
            assert up_json["success"] is True
            assert up_json["status"] == "COMPLETED"

            # Verify physical file existence
            target_file = get_transfers_dir() / "render_project_4k.raw"
            assert target_file.exists()
            assert target_file.read_bytes() == payload_data
            print(f"    -> Successfully streamed & atomically verified '{target_file.name}' ({len(payload_data)} bytes)!")

            # 6. Cancellation & Rollback
            print("\n[6] Testing Transfer Cancellation & Automatic Rollback...")
            cancel_tid = "tx_cancel_" + secrets.token_hex(8)
            tmp_rollback_file = get_transfers_dir() / f".tmp_{cancel_tid}_abandoned_large.bin"
            tmp_rollback_file.write_bytes(b"PARTIAL_INTERRUPTED_DATA_BLOCKS" * 100)
            assert tmp_rollback_file.exists()

            transfer_manager.register_transfer(cancel_tid, "abandoned_large.bin", tmp_rollback_file, 500000)
            cancel_res = client.post(f"/api/v1/transfer/cancel/{cancel_tid}", headers=headers)
            assert cancel_res.status_code == 200
            assert cancel_res.json()["success"] is True

            # Verify staging file was deleted to avoid disk pollution
            assert not tmp_rollback_file.exists()
            print("    -> Cancellation successful: Incomplete .tmp staging file automatically purged!")

            # 7. Recursive Folder Upload
            print("\n[7] Testing Recursive Folder Tree Transfer & Directory Preservation...")
            folder_name = "GigabitProject_" + secrets.token_hex(4)
            folder_files = [
                ("files", ("main.py", io.BytesIO(b"print('FreeLanSync Gigabit')"), "text/x-python")),
                ("files", ("config.json", io.BytesIO(b"{\"speed\": \"gigabit\"}"), "application/json")),
                ("files", ("asset.png", io.BytesIO(b"PNG_MOCK_IMAGE_DATA_12345"), "image/png"))
            ]
            folder_data = {
                "folder_name": folder_name,
                "relative_paths": [
                    "src/main.py",
                    "config/config.json",
                    "assets/brand/asset.png"
                ]
            }
            folder_res = client.post("/api/v1/transfer/folder", files=folder_files, data=folder_data, headers=headers)
            assert folder_res.status_code == 200
            f_json = folder_res.json()
            assert f_json["success"] is True
            assert f_json["files_count"] == 3

            # Check nested paths
            base_f = get_transfers_dir() / folder_name
            assert (base_f / "src" / "main.py").exists()
            assert (base_f / "config" / "config.json").exists()
            assert (base_f / "assets" / "brand" / "asset.png").exists()
            print(f"    -> Recursive folder tree preserved on disk in '{folder_name}/'!")

            # 8. Streaming Zip Archive Download
            print("\n[8] Testing Dynamic Streaming Zip Download of Transferred Folder...")
            zip_res = client.get(f"/api/v1/transfer/download-folder/{folder_name}", headers=headers)
            assert zip_res.status_code == 200
            assert zip_res.headers["content-type"] == "application/zip"
            
            zf = zipfile.ZipFile(io.BytesIO(zip_res.content))
            namelist = [n.replace("\\", "/") for n in zf.namelist()]
            assert "src/main.py" in namelist
            assert "config/config.json" in namelist
            assert "assets/brand/asset.png" in namelist
            print(f"    -> Received streaming zip with {len(namelist)} items preserved on-the-fly!")

            # 9. Phone Battery HUD & Telemetry
            print("\n[9] Transmitting Phone Battery Telemetry over Bridge...")
            phone_ws.send_text(json.dumps({
                "event": "BATTERY_STATUS",
                "data": {"level": 94, "is_charging": True, "device_name": "Pixel 9 Pro"}
            }))
            bat_msg = wait_for_ui_event(desktop_ws, "BATTERY_STATUS")
            assert bat_msg["data"]["level"] == 94
            print("    -> Desktop HUD received Battery Telemetry: 94% (Charging: True)")

            # 10. Synco Notification Mirroring
            print("\n[10] Mirroring Phone Notification to Desktop...")
            notif_id = "notif_" + secrets.token_hex(4)
            phone_ws.send_text(json.dumps({
                "event": "NOTIFICATION_POSTED",
                "data": {
                    "id": notif_id,
                    "app_name": "Signal",
                    "package_name": "org.thoughtcrime.securesms",
                    "title": "Elena Rostova",
                    "text": "The gigabit test build passed with zero errors!",
                    "timestamp": time.time(),
                    "actions": ["REPLY", "DISMISS"]
                }
            }))
            notif_msg = wait_for_ui_event(desktop_ws, "NOTIFICATION_POSTED")
            assert notif_msg["data"]["app_name"] == "Signal"
            print(f"    -> Desktop Toast received: [{notif_msg['data']['app_name']}] {notif_msg['data']['title']}: \"{notif_msg['data']['text']}\"")

            # 11. Bidirectional Clipboard Sync
            print("\n[11] Testing Bidirectional Clipboard Synchronization...")
            phone_ws.send_text(json.dumps({
                "event": "CLIPBOARD_UPDATE",
                "data": {"text": "GIGABIT_TOKEN_FREELANSYNC_2026", "source": "phone"}
            }))
            clip_msg = wait_for_ui_event(desktop_ws, "CLIPBOARD_UPDATE")
            assert clip_msg["data"]["text"] == "GIGABIT_TOKEN_FREELANSYNC_2026"
            print(f"    -> Desktop received shared clipboard: \"{clip_msg['data']['text']}\"")

            # 12. List Transfers
            print("\n[12] Verifying Completed Transfers List...")
            trans_list_res = client.get("/api/v1/transfer/list")
            assert trans_list_res.status_code == 200
            trans_items = trans_list_res.json()["transfers"]
            assert any(t["name"] == folder_name for t in trans_items)
            print(f"    -> Transfers directory catalog contains {len(trans_items)} verified items.")

    print("\n" + "=" * 70)
    print("  ALL 12/12 FREELANSYNC & LANSYNC GIGABIT TESTS PASSED 100%!")
    print("=" * 70)

if __name__ == "__main__":
    run_freelansync_simulation()

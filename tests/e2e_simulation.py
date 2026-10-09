import time
import hashlib
import json
import socket
import tempfile
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import httpx

from server.config import SERVER_PORT, BACKUP_DIR, get_local_ip
from server.auth import pairing_manager

def run_simulation():
    print("=" * 60)
    print("   FreeLanSync End-to-End Simulation: Phone -> PC Server")
    print("=" * 60)
    
    base_url = f"http://127.0.0.1:{SERVER_PORT}"
    client = httpx.Client(base_url=base_url, timeout=10.0)

    # Step 1: Health check / Ping
    print("\n[1] Pinging server...")
    ping_resp = client.get("/api/v1/ping")
    assert ping_resp.status_code == 200, f"Ping failed: {ping_resp.text}"
    print(f"    Server online! Details: {ping_resp.json()}")

    # Step 2: Fetch pairing info (simulate user looking at desktop screen)
    print("\n[2] Fetching active 6-digit PIN and QR info...")
    pair_info_resp = client.get("/api/v1/pairing/info")
    assert pair_info_resp.status_code == 200
    pair_info = pair_info_resp.json()
    active_pin = pair_info["pin"]
    print(f"    Active Desktop PIN: {active_pin} (Expires in {pair_info['expires_in']}s)")

    # Step 3: Simulate Android phone pairing
    device_id = "simulated-android-device-uuid-999"
    device_name = "Pixel 8 Pro (Simulated)"
    print(f"\n[3] Android phone attempting pairing with PIN {active_pin}...")
    pair_resp = client.post("/api/v1/pairing/verify", json={
        "pin": active_pin,
        "device_name": device_name,
        "device_id": device_id
    })
    assert pair_resp.status_code == 200
    pair_result = pair_resp.json()
    assert pair_result["success"] is True, f"Pairing rejected: {pair_result}"
    auth_token = pair_result["auth_token"]
    print(f"    Pairing SUCCESS! Received bearer token: {auth_token[:12]}...")

    headers = {"Authorization": f"Bearer {auth_token}"}

    # Step 4: Create simulated camera roll items (photos and video)
    run_epoch = str(time.time()).encode()
    print("\n[4] Generating simulated camera roll files...")
    media_items = [
        {
            "filename": f"IMG_20261007_143000_{int(time.time())}.jpg",
            "content": b"\xFF\xD8\xFF\xE0\x00\x10JFIF" + b"simulated_jpeg_photo_bytes_mountain_trip_" + run_epoch,
            "mime": "image/jpeg",
            "taken_at": "2026-10-07T14:30:00Z"
        },
        {
            "filename": f"IMG_20261007_150000_{int(time.time())}.jpg",
            "content": b"\xFF\xD8\xFF\xE0\x00\x10JFIF" + b"simulated_jpeg_photo_bytes_beach_sunset_" + run_epoch,
            "mime": "image/jpeg",
            "taken_at": "2026-10-07T15:00:00Z"
        },
        {
            "filename": f"VID_20261007_160000_{int(time.time())}.mp4",
            "content": b"\x00\x00\x00\x18ftypmp42" + b"simulated_mp4_video_bytes_family_dinner_" + run_epoch,
            "mime": "video/mp4",
            "taken_at": "2026-10-07T16:00:00Z"
        }
    ]

    for item in media_items:
        item["sha256"] = hashlib.sha256(item["content"]).hexdigest()

    hashes = [m["sha256"] for m in media_items]

    # Step 5: Pre-flight check (batch check)
    print(f"\n[5] Phone querying pre-flight batch check for {len(hashes)} files...")
    batch_resp = client.post("/api/v1/photos/check-batch", headers=headers, json={"hashes": hashes})
    assert batch_resp.status_code == 200
    batch_data = batch_resp.json()
    print(f"    Missing hashes on PC: {len(batch_data['missing_hashes'])} / {len(hashes)}")
    assert len(batch_data["missing_hashes"]) == 3

    # Step 6: Upload missing media files
    print("\n[6] Uploading missing files to PC Server...")
    for item in media_items:
        print(f"    Streaming upload: {item['filename']} ({len(item['content'])} bytes, hash: {item['sha256'][:8]}...)")
        upload_resp = client.post(
            "/api/v1/photos/upload",
            headers=headers,
            data={"sha256": item["sha256"], "taken_at": item["taken_at"]},
            files={"file": (item["filename"], item["content"], item["mime"])}
        )
        assert upload_resp.status_code == 200
        up_json = upload_resp.json()
        print(f"    -> Saved on PC at: {up_json['relative_path']}")

    # Step 7: Verify Deduplication on subsequent sync
    print("\n[7] Re-running batch check (verifying 100% deduplication)...")
    re_batch = client.post("/api/v1/photos/check-batch", headers=headers, json={"hashes": hashes})
    assert re_batch.status_code == 200
    re_batch_data = re_batch.json()
    print(f"    Existing on server: {len(re_batch_data['existing_hashes'])}")
    print(f"    Missing on server: {len(re_batch_data['missing_hashes'])}")
    assert len(re_batch_data["missing_hashes"]) == 0
    assert len(re_batch_data["existing_hashes"]) == 3

    # Step 8: Verify Dashboard endpoints
    print("\n[8] Querying PC Server Dashboard API...")
    devices_resp = client.get("/api/v1/devices")
    assert devices_resp.status_code == 200
    devices = devices_resp.json()["devices"]
    print(f"    Total registered devices: {len(devices)}")
    target_dev = next((d for d in devices if d["device_id"] == device_id), None)
    assert target_dev is not None
    print(f"    Device '{target_dev['device_name']}' backed up {target_dev['total_files']} files ({target_dev['total_bytes']} bytes)")

    recent_resp = client.get("/api/v1/photos/recent")
    assert recent_resp.status_code == 200
    recent = recent_resp.json()["recent_media"]
    print(f"    Recent media entries in PC index: {len(recent)}")
    assert len(recent) >= 3

    # Step 9: Verify Physical File System Existence
    print("\n[9] Verifying files on Windows PC File System...")
    for item in media_items:
        expected_file = BACKUP_DIR / "Pixel 8 Pro (Simulated)" / "2026" / "10" / item["filename"]
        assert expected_file.exists(), f"File missing on PC disk: {expected_file}"
        with open(expected_file, "rb") as f:
            disk_bytes = f.read()
        assert disk_bytes == item["content"], f"File content corrupted on disk for {item['filename']}"
        print(f"    Confirmed on disk: {expected_file} ({len(disk_bytes)} bytes)")

    print("\n" + "=" * 60)
    print("   ALL END-TO-END TESTS PASSED WITH 100% SUCCESS!")
    print("=" * 60)

if __name__ == "__main__":
    run_simulation()

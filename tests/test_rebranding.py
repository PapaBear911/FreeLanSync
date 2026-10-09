import json
from server.config import SERVICE_NAME, MDNS_SERVICE_TYPE
from server.main import app
from fastapi.testclient import TestClient

def test_freelansync_branding():
    client = TestClient(app)
    # 1. Configuration branding
    assert "FreeLanSync" in SERVICE_NAME
    assert "freelansync" in MDNS_SERVICE_TYPE.lower()
    
    # 2. Auth QR endpoint
    res = client.get("/api/v1/pairing/info")
    assert res.status_code == 200
    assert "FreeLanSync.apk" in res.json()["apk_download_url"]
    payload = json.loads(res.json()["qr_payload"])
    assert payload["service"] == "freelansync"

    # 3. Root health endpoint
    root_res = client.get("/")
    assert root_res.status_code == 200
    assert "FreeLanSync" in root_res.text


def test_android_canonical_file_and_class_naming():
    """Architecture check: Android source files use canonical FreeLanSync naming."""
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    android_src = root / "android" / "app" / "src" / "main" / "java" / "com" / "photosync" / "app"

    assert (android_src / "FreeLanSyncApplication.kt").exists()
    assert (android_src / "network" / "FreeLanSyncApiClient.kt").exists()
    assert (android_src / "service" / "FreeLanSyncNotificationListener.kt").exists()
    assert (android_src / "sync" / "FreeLanSyncWorker.kt").exists()

    manifest = (root / "android" / "app" / "src" / "main" / "AndroidManifest.xml").read_text(encoding="utf-8")
    assert 'android:name=".FreeLanSyncApplication"' in manifest
    assert 'android:name=".service.FreeLanSyncNotificationListener"' in manifest

    legacy_files = list(android_src.rglob("PhotoSync*.kt"))
    assert not legacy_files, f"Legacy PhotoSync files found: {legacy_files}"



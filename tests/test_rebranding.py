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


def test_unified_mobius_hyperlink_logo_parity():
    """Verify Desktop web dashboard and Android adaptive vector share the Mobius HyperLink mark."""
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    index_html = (root / "server" / "static" / "index.html").read_text(encoding="utf-8")
    android_fg = (root / "android" / "app" / "src" / "main" / "res" / "drawable" / "ic_launcher_foreground.xml").read_text(encoding="utf-8")
    preview_svg = (root / "android" / "tools" / "ic_launcher_foreground_preview.svg").read_text(encoding="utf-8")

    # 1. Desktop dashboard has the modern Mobius HyperLink gradients & paths
    assert "flsCyan" in index_html
    assert "flsIndigo" in index_html
    assert "FreeLanSync Mobius HyperLink" in index_html
    assert "M 38,38 A 8.485,8.485" in index_html
    assert "M 26,38 A 8.485,8.485" in index_html

    # 2. Desktop favicon uses the updated Mobius HyperLink
    assert "FreeLanSync Mobius HyperLink Favicon" in index_html

    # 3. Android adaptive icon foreground has the matching Mobius knot geometry
    assert "14.142,14.142" in android_fg
    assert "14.142,14.142" in preview_svg
    assert "#38BDF8" in android_fg  # Cyan mobile link
    assert "#6366F1" in android_fg  # Indigo desktop vault




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

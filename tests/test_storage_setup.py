import pytest
from fastapi.testclient import TestClient
from pathlib import Path
import tempfile
import shutil

from server.main import app
from server.config import get_storage_dir, get_storage_presets

client = TestClient(app)

def test_storage_settings_and_suggestions():
    # 1. Fetch storage settings
    res = client.get("/api/v1/settings")
    assert res.status_code == 200
    data = res.json()
    assert "storage_dir" in data
    assert "stats" in data
    assert data["writable"] is True
    assert "free_human" in data["stats"]
    assert "total_human" in data["stats"]

    # 2. Fetch storage suggestions
    s_res = client.get("/api/v1/settings/storage-suggestions")
    assert s_res.status_code == 200
    s_data = s_res.json()
    assert "recommended_path" in s_data
    assert "suggestions" in s_data
    assert len(s_data["suggestions"]) >= 2
    rec = [s for s in s_data["suggestions"] if s.get("is_recommended")]
    assert len(rec) >= 1
    assert "free_human" in rec[0]

def test_validate_storage_path():
    with tempfile.TemporaryDirectory() as tmpdir:
        test_path = Path(tmpdir) / "TestStorage"
        res = client.post("/api/v1/settings/validate-path", json={"path": str(test_path)})
        assert res.status_code == 200
        data = res.json()
        assert data["valid"] is True
        assert data["writable"] is True
        assert "stats" in data
        assert "free_human" in data["stats"]

    # Test invalid path
    res_bad = client.post("/api/v1/settings/validate-path", json={"path": ""})
    assert res_bad.status_code == 200
    assert res_bad.json()["valid"] is False

def test_update_storage_settings():
    original_settings = client.get("/api/v1/settings").json()
    original_storage = original_settings["storage_dir"]

    with tempfile.TemporaryDirectory() as tmpdir:
        new_storage = Path(tmpdir) / "NewFreeLanSyncVault"
        res = client.post("/api/v1/settings", json={"storage_dir": str(new_storage)})
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert (new_storage / "Backups").exists()
        assert (new_storage / "Transfers").exists()
        assert (new_storage / "QuickDrop").exists()

        # Re-fetch settings
        verify_res = client.get("/api/v1/settings")
        assert verify_res.json()["storage_dir"] == str(new_storage.resolve())

    # Restore original setting
    client.post("/api/v1/settings", json={"storage_dir": original_storage})

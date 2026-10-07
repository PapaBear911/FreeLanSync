import io
import zipfile
import pytest
import secrets
from fastapi.testclient import TestClient
from server.main import app
from server.database import register_device, init_db
from server.config import get_transfers_dir

def test_recursive_folder_upload_and_download():
    init_db()
    token = "test_token_" + secrets.token_hex(8)
    register_device("Test Laptop", "test-device-id", token)
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {token}"}
    
    # 1. Upload nested directory structure:
    # TestFolder/Docs/readme.txt
    # TestFolder/Docs/src/main.py
    files = [
        ("files", ("readme.txt", io.BytesIO(b"Hello Docs from FreeLanSync"), "text/plain")),
        ("files", ("main.py", io.BytesIO(b"print('Gigabit P2P')"), "text/x-python"))
    ]
    data = {
        "folder_name": "TestFolder",
        "relative_paths": ["Docs/readme.txt", "Docs/src/main.py"]
    }
    
    res = client.post("/api/v1/transfer/folder", files=files, data=data, headers=headers)
    assert res.status_code == 200
    res_json = res.json()
    assert res_json["success"] is True
    assert res_json["files_count"] == 2

    # Verify physical file structure on disk
    base_folder = get_transfers_dir() / "TestFolder"
    readme_path = base_folder / "Docs" / "readme.txt"
    main_path = base_folder / "Docs" / "src" / "main.py"
    assert readme_path.exists()
    assert readme_path.read_text(encoding="utf-8") == "Hello Docs from FreeLanSync"
    assert main_path.exists()
    assert main_path.read_text(encoding="utf-8") == "print('Gigabit P2P')"

    # 2. Download folder as streaming zip archive
    dl_res = client.get("/api/v1/transfer/download-folder/TestFolder", headers=headers)
    assert dl_res.status_code == 200
    assert dl_res.headers["content-type"] == "application/zip"
    
    # Verify contents of zip file
    zf = zipfile.ZipFile(io.BytesIO(dl_res.content))
    namelist = zf.namelist()
    assert any("Docs/readme.txt" in name.replace("\\", "/") for name in namelist)
    assert any("Docs/src/main.py" in name.replace("\\", "/") for name in namelist)

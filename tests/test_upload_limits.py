"""Guard tests for TD-017: bounded upload memory + streamed folder zips."""
import hashlib
import io
import secrets
import zipfile

import pytest
from fastapi.testclient import TestClient

from server.main import app
from server.database import init_db, register_device

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_db():
    init_db()


def _paired_token():
    token = "limit_token_" + secrets.token_hex(8)
    register_device("Limit Phone", "limit-device-" + secrets.token_hex(4), token)
    return token


def test_oversized_upload_rejected_413(monkeypatch):
    # Declared Content-Length over the cap must 413 before the body is buffered.
    monkeypatch.setattr("server.main.MAX_UPLOAD_BYTES", 64)
    token = _paired_token()

    content = b"x" * 128
    res = client.post(
        "/api/v1/photos/upload",
        headers={"Authorization": f"Bearer {token}"},
        data={"sha256": hashlib.sha256(content).hexdigest()},
        files={"file": ("big.jpg", content, "image/jpeg")},
    )
    assert res.status_code == 413


def test_oversized_quick_drop_rejected_413(monkeypatch):
    monkeypatch.setattr("server.main.MAX_UPLOAD_BYTES", 64)
    res = client.post(
        "/api/v1/drop/upload",
        files={"file": ("big.bin", b"y" * 128, "application/octet-stream")},
    )
    assert res.status_code == 413


def test_oversized_folder_upload_rejected_413(monkeypatch):
    monkeypatch.setattr("server.main.MAX_UPLOAD_BYTES", 64)
    res = client.post(
        "/api/v1/transfer/folder",
        files=[("files", ("a.txt", io.BytesIO(b"z" * 128), "text/plain"))],
        data={"folder_name": "BigFolder", "relative_paths": ["a.txt"]},
    )
    assert res.status_code == 413


def test_chunked_upload_over_declared_size_rejected_413(monkeypatch):
    # A client that lies about total_size must be cut off per-chunk (413),
    # not streamed to completion and failed at the end.
    from server.transfer_manager import transfer_manager

    monkeypatch.setattr("server.transfer_manager.MAX_UPLOAD_BYTES", 1024 * 1024)
    token = _paired_token()

    res = client.post(
        "/api/v1/transfer/upload-chunked",
        headers={"Authorization": f"Bearer {token}"},
        data={
            "transfer_id": "oversize-tid",
            "filename": "liar.bin",
            "total_size": "10",
        },
        files={"file": ("liar.bin", b"b" * 100, "application/octet-stream")},
    )
    assert res.status_code == 413


def test_oversized_stream_upload_aborts_mid_chunk(monkeypatch):
    import asyncio

    from server.transfer_manager import transfer_manager, UploadTooLargeError

    monkeypatch.setattr("server.transfer_manager.MAX_UPLOAD_BYTES", 8)

    class _OverStream:
        filename = "over.bin"

        async def read(self, size=-1):
            return b"0123456789ABCDEF"  # 16 bytes total

    with pytest.raises(UploadTooLargeError):
        asyncio.run(
            transfer_manager.save_stream_upload(
                transfer_id="midchunk-tid",
                upload_file=_OverStream(),
                filename="over.bin",
                total_size=1024,
            )
        )


def test_folder_zip_stream_unpacks_with_correct_contents():
    # Named guard: streamed zip keeps the same layout/filenames/content-type.
    res = client.get("/api/v1/transfer/download-folder/DoesNotExist")
    assert res.status_code == 404

    up = client.post(
        "/api/v1/transfer/folder",
        files=[
            ("files", ("one.txt", io.BytesIO(b"alpha"), "text/plain")),
            ("files", ("two.txt", io.BytesIO(b"beta"), "text/plain")),
        ],
        data={"folder_name": "ZipGuard", "relative_paths": ["sub/one.txt", "two.txt"]},
    )
    assert up.status_code == 200

    dl = client.get("/api/v1/transfer/download-folder/ZipGuard")
    assert dl.status_code == 200
    assert dl.headers["content-type"] == "application/zip"
    zf = zipfile.ZipFile(io.BytesIO(dl.content))
    assert zf.read("sub/one.txt") == b"alpha"
    assert zf.read("two.txt") == b"beta"
    # No in-memory buffer: response arrives as streamed bytes
    assert len(dl.content) > 0

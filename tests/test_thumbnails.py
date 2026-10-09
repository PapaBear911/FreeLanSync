"""TD-038: dashboard thumbnail endpoint.

Guards the fix for user-reported laggy gallery rendering:
- tiles must be served as small (<=256px) JPEGs with cache headers, not originals;
- the cache must live under the sandbox storage dir and survive repeat requests;
- traversal must stay rejected (same TD-005 containment as view_photo);
- non-image media (videos) must 404 instead of crashing PIL;
- view_photo must now send Cache-Control so the lightbox stops revalidating.
"""
import asyncio
import io
import os

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from server import config as config_mod
from server import main as main_mod


def _make_jpeg(path, size=(1200, 800)):
    """Deterministic, non-trivial JPEG so the original is clearly bigger than a thumb."""
    path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", size, (18, 24, 48))
    draw = ImageDraw.Draw(img)
    draw.rectangle([40, 40, size[0] - 40, size[1] - 40], outline=(99, 102, 241), width=12)
    draw.ellipse([200, 150, 700, 600], fill=(56, 189, 248))
    img.save(path, "JPEG", quality=92)
    return path


def test_thumbnail_endpoint_serves_small_cached_image(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient as TC
    from server.main import app

    backup = tmp_path / "Backups"
    monkeypatch.setattr("server.main.get_backup_dir", lambda: backup)

    original = _make_jpeg(backup / "Phone" / "2026" / "10" / "IMG_1.jpg")
    original_bytes = original.stat().st_size
    rel = "Phone/2026/10/IMG_1.jpg"

    client = TC(app)
    res = client.get(f"/api/v1/photos/thumb/{rel}")
    assert res.status_code == 200, res.text
    assert res.headers["content-type"].startswith("image/jpeg")
    assert "cache-control" in res.headers and "max-age" in res.headers["cache-control"], (
        "TD-038: thumbnails must be cacheable or the 12s refresh tick re-downloads them"
    )
    assert len(res.content) < original_bytes, (
        f"TD-038: thumb ({len(res.content)} B) must be smaller than the original ({original_bytes} B)"
    )
    thumb_img = Image.open(io.BytesIO(res.content))
    assert max(thumb_img.size) <= 256, f"TD-038: thumb {thumb_img.size} exceeds 256px"

    # Cache file landed in the (sandboxed) storage dir and a repeat hit is served from it.
    cache_root = config_mod.get_storage_dir() / "thumbnails"
    cached = list(cache_root.glob("*.jpg"))
    assert cached, "TD-038: thumbnail was not written to storage/thumbnails cache"

    res2 = client.get(f"/api/v1/photos/thumb/{rel}")
    assert res2.status_code == 200
    assert res2.content == res.content, "TD-038: repeat request must serve identical cached bytes"


def test_thumbnail_rejects_traversal(tmp_path, monkeypatch):
    backup = tmp_path / "Backups"
    backup.mkdir()
    secret = tmp_path / "SECRET.jpg"
    _make_jpeg(secret)
    monkeypatch.setattr("server.main.get_backup_dir", lambda: backup)

    traversal = os.path.relpath(secret, backup).replace("\\", "/")
    with pytest.raises(HTTPException) as exc:
        asyncio.run(main_mod.photo_thumbnail(traversal))
    assert exc.value.status_code == 404, "TD-038/TD-005: traversal escaped the backup root"
    # Nothing was generated for the escaped path either.
    cache_root = config_mod.get_storage_dir() / "thumbnails"
    assert not list(cache_root.glob("*.jpg")) if cache_root.exists() else True


def test_thumbnail_returns_404_for_video(tmp_path, monkeypatch):
    from server.main import app

    backup = tmp_path / "Backups"
    monkeypatch.setattr("server.main.get_backup_dir", lambda: backup)

    video = backup / "Phone" / "VID_0001.mp4"
    video.parent.mkdir(parents=True, exist_ok=True)
    video.write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 1024)

    client = TestClient(app)
    res = client.get("/api/v1/photos/thumb/Phone/VID_0001.mp4")
    assert res.status_code == 404, (
        "TD-038: non-image media must 404 cleanly, not surface a PIL traceback"
    )


def test_view_photo_sets_cache_control(tmp_path, monkeypatch):
    from server.main import app

    backup = tmp_path / "Backups"
    monkeypatch.setattr("server.main.get_backup_dir", lambda: backup)

    original = _make_jpeg(backup / "Phone" / "IMG_2.jpg")

    client = TestClient(app)
    res = client.get(f"/api/v1/photos/view/{original.relative_to(backup).as_posix()}")
    assert res.status_code == 200
    assert "cache-control" in res.headers and "max-age" in res.headers["cache-control"], (
        "TD-038: view_photo must send Cache-Control so the lightbox stops revalidating"
    )

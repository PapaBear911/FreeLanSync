"""On-demand thumbnail generation for the dashboard gallery (TD-038).

The web dashboard used to render gallery tiles from the ORIGINAL multi-megabyte
photos served by /api/v1/photos/view, which made the Vault tab laggy. These
helpers generate <=256px JPEG thumbnails under ``storage/thumbnails/`` so tiles
load in kilobytes.

Cache keys include the absolute path, mtime and size, so a replaced original
regenerates its thumbnail automatically. Anything PIL cannot decode (videos,
corrupt files) returns None and callers serve a 404 — the dashboard already
renders video tiles with a placeholder instead of an image.
"""
from hashlib import sha1
from pathlib import Path
from typing import Optional

from PIL import Image, ImageOps, UnidentifiedImageError

from . import config

THUMBNAIL_SIZE = (256, 256)
JPEG_QUALITY = 82


def thumbnail_cache_root() -> Path:
    return config.get_storage_dir() / "thumbnails"


def get_or_create_thumbnail(file_path: Path) -> Optional[Path]:
    """Return a cached thumbnail path for ``file_path``, generating it if needed.

    Returns None when the file is missing or is not a decodable image (e.g.
    videos); callers translate that into an HTTP 404 with no side effects.
    """
    try:
        stat = file_path.stat()
    except OSError:
        return None

    key = sha1(
        f"{file_path.resolve()}|{stat.st_mtime_ns}|{stat.st_size}".encode("utf-8")
    ).hexdigest()[:32]
    thumb_path = thumbnail_cache_root() / f"{key}.jpg"
    if thumb_path.is_file():
        return thumb_path

    try:
        with Image.open(file_path) as img:
            img = ImageOps.exif_transpose(img)
            img.thumbnail(THUMBNAIL_SIZE, Image.Resampling.LANCZOS)
            if img.mode not in ("RGB", "L"):
                img = img.convert("RGB")
            thumb_path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path = thumb_path.with_suffix(".tmp")
            img.save(tmp_path, format="JPEG", quality=JPEG_QUALITY, optimize=True)
            tmp_path.replace(thumb_path)  # atomic: never a half-written cache entry
    except (UnidentifiedImageError, OSError, ValueError):
        # Videos and unsupported/corrupt media simply have no thumbnail.
        return None
    return thumb_path

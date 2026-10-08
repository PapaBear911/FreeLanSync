"""File system storage manager with SHA-256 deduplication and date hierarchy."""
import os
import hashlib
import datetime
import re
import uuid
from pathlib import Path
from typing import Tuple, Optional
from .config import get_backup_dir, get_quickdrop_dir
from .database import record_media_backup

# TD-016: server-issued Quick-Drop ids are uuid4hex[:12]; anything else reaching
# the glob is a probe and must be rejected before filesystem access.
FILE_ID_RE = re.compile(r"^[0-9a-f]{12}$")

def sanitize_filename(filename: str) -> str:
    """Sanitize filename to prevent directory traversal or invalid characters."""
    clean = Path(filename).name
    for ch in '<>:"/\\|?*':
        clean = clean.replace(ch, '_')
    return clean.strip() or "unnamed_media"

def parse_date_hierarchy(taken_at_iso: Optional[str]) -> Tuple[str, str]:
    """Extract (YYYY, MM) folder path from ISO timestamp or fallback to current date."""
    if taken_at_iso:
        try:
            # Handle timestamps with or without Z/offset
            dt = datetime.datetime.fromisoformat(taken_at_iso.replace('Z', '+00:00'))
            return f"{dt.year:04d}", f"{dt.month:02d}"
        except Exception:
            pass
    now = datetime.datetime.now()
    return f"{now.year:04d}", f"{now.month:02d}"

class StorageManager:
    def __init__(self, backup_dir: Optional[Path] = None):
        self._custom_backup_dir = backup_dir

    @property
    def backup_dir(self) -> Path:
        if self._custom_backup_dir is not None:
            self._custom_backup_dir.mkdir(parents=True, exist_ok=True)
            return self._custom_backup_dir
        return get_backup_dir()

    @backup_dir.setter
    def backup_dir(self, val: Path):
        self._custom_backup_dir = val

    def save_media(
        self,
        device_id: str,
        device_name: str,
        original_filename: str,
        file_bytes: bytes,
        expected_sha256: str,
        taken_at_iso: Optional[str] = None,
        mime_type: Optional[str] = None
    ) -> Tuple[bool, str, str]:
        """
        Verify SHA-256, deduplicate, and write file atomically.
        Returns: (success: bool, relative_path: str, message: str)
        """
        # 1. Compute and verify actual SHA-256
        hasher = hashlib.sha256()
        hasher.update(file_bytes)
        actual_sha256 = hasher.hexdigest().lower()

        if expected_sha256 and expected_sha256.lower() != actual_sha256:
            return False, "", f"SHA-256 mismatch. Expected {expected_sha256}, got {actual_sha256}"

        # 2. Determine target path: Backups/<DeviceName>/<YYYY>/<MM>/<filename>
        clean_device = sanitize_filename(device_name)
        year_str, month_str = parse_date_hierarchy(taken_at_iso)
        clean_file = sanitize_filename(original_filename)

        current_backup_dir = self.backup_dir
        target_dir = current_backup_dir / clean_device / year_str / month_str
        target_dir.mkdir(parents=True, exist_ok=True)

        target_path = target_dir / clean_file
        
        # If file with same name exists, check if identical hash or append counter
        if target_path.exists():
            with open(target_path, "rb") as existing_file:
                existing_hash = hashlib.sha256(existing_file.read()).hexdigest().lower()
            if existing_hash == actual_sha256:
                # Already exists and content is identical
                rel_path = str(target_path.relative_to(current_backup_dir))
                record_media_backup(
                    device_id=device_id,
                    sha256=actual_sha256,
                    original_filename=clean_file,
                    relative_path=rel_path,
                    file_size=len(file_bytes),
                    mime_type=mime_type,
                    taken_at=taken_at_iso
                )
                return True, rel_path, "File already archived (deduplicated)."
            else:
                # Collision with different file: append short hash
                stem = target_path.stem
                suffix = target_path.suffix
                target_path = target_dir / f"{stem}_{actual_sha256[:8]}{suffix}"

        # 3. Atomic write: write to temp file then rename
        temp_path = target_path.with_suffix(f"{target_path.suffix}.tmp_{os.getpid()}")
        try:
            with open(temp_path, "wb") as f:
                f.write(file_bytes)
            temp_path.replace(target_path)
        except Exception as e:
            if temp_path.exists():
                temp_path.unlink()
            raise e

        # 4. Record in database
        rel_path = str(target_path.relative_to(current_backup_dir))
        record_media_backup(
            device_id=device_id,
            sha256=actual_sha256,
            original_filename=clean_file,
            relative_path=rel_path,
            file_size=len(file_bytes),
            mime_type=mime_type,
            taken_at=taken_at_iso
        )

        return True, rel_path, "File successfully saved and indexed."

    def save_quick_drop(
        self,
        original_filename: str,
        file_bytes: bytes,
        mime_type: Optional[str] = None
    ) -> dict:
        drop_dir = get_quickdrop_dir()
        file_id = uuid.uuid4().hex[:12]
        clean_file = sanitize_filename(original_filename)
        hasher = hashlib.sha256(file_bytes)
        sha256 = hasher.hexdigest().lower()
        
        target_path = drop_dir / f"{file_id}_{clean_file}"
        # TD-006: stage to .tmp then atomically replace; crash/ENOSPC must never
        # leave a truncated file that list_pending_drops advertises as complete.
        tmp_path = drop_dir / f".tmp_{file_id}_{clean_file}.tmp"
        try:
            with open(tmp_path, "wb") as f:
                f.write(file_bytes)
            os.replace(tmp_path, target_path)
        except Exception:
            if tmp_path.exists():
                try:
                    tmp_path.unlink()
                except OSError:
                    pass
            raise
            
        return {
            "file_id": file_id,
            "filename": clean_file,
            "size": len(file_bytes),
            "sha256": sha256,
            "mime_type": mime_type or "application/octet-stream",
            "path": str(target_path),
            "timestamp": datetime.datetime.now().isoformat()
        }

    def list_pending_drops(self) -> list:
        drop_dir = get_quickdrop_dir()
        results = []
        for p in drop_dir.glob("*_*"):
            if p.is_file():
                # TD-006: never advertise staging tmp files; crash/ENOSPC mid-write
                # must not surface a truncated file as complete.
                # Staging names always start with ".tmp_"; final names are
                # "{hex12}_{clean}" so they never start with ".".
                if p.name.startswith(".tmp_"):
                    continue
                parts = p.name.split("_", 1)
                file_id = parts[0]
                orig_name = parts[1] if len(parts) > 1 else p.name
                stat = p.stat()
                results.append({
                    "file_id": file_id,
                    "filename": orig_name,
                    "size": stat.st_size,
                    "created_at": datetime.datetime.fromtimestamp(stat.st_ctime).isoformat()
                })
        # Sort newest first
        results.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return results

    def get_drop_file_path(self, file_id: str) -> Optional[Path]:
        # TD-016: never interpolate an unvalidated id into a glob ("*" would
        # match every pending drop). Callers in main.py also pre-validate.
        if not self.is_valid_file_id(file_id):
            return None
        drop_dir = get_quickdrop_dir()
        for p in drop_dir.glob(f"{file_id}_*"):
            if p.is_file():
                return p
        return None

    @staticmethod
    def is_valid_file_id(file_id: str) -> bool:
        return bool(FILE_ID_RE.match(file_id or ""))

    def delete_drop_file(self, file_id: str) -> bool:
        if not self.is_valid_file_id(file_id):
            return False
        path = self.get_drop_file_path(file_id)
        if path and path.exists():
            path.unlink()
            return True
        return False

storage_manager = StorageManager()

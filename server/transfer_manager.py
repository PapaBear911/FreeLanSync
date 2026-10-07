"""LANSync Gigabit Transfer Engine for FreeLanSync.
Handles pre-flight space checking, atomic streaming, chunked staging, cancellation rollback, and recursive folder transfers.
"""
import os
import io
import zipfile
import shutil
import time
import uuid
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List, Callable
from .config import get_storage_dir, get_transfers_dir

logger = logging.getLogger("freelansync.transfer")

def format_bytes(size: int) -> str:
    """Format bytes into human-readable string."""
    if size < 0:
        return "0 B"
    units = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']
    unit_idx = 0
    val = float(size)
    while val >= 1024.0 and unit_idx < len(units) - 1:
        val /= 1024.0
        unit_idx += 1
    return f"{val:.1f} {units[unit_idx]}" if unit_idx > 0 else f"{int(val)} B"

class TransferManager:
    # 250 MB safety margin buffer for disk space
    SAFETY_MARGIN_BYTES = 250 * 1024 * 1024
    CHUNK_SIZE = 1024 * 1024  # 1 MB chunk buffer for gigabit Wi-Fi / Ethernet streaming

    def __init__(self):
        self.active_transfers: Dict[str, Dict[str, Any]] = {}

    def get_storage_info(self) -> Dict[str, Any]:
        """Return disk usage statistics for the storage volume."""
        storage_dir = get_storage_dir()
        usage = shutil.disk_usage(storage_dir)
        total = usage.total
        free = usage.free
        used = usage.used
        percent_used = round((used / total) * 100, 1) if total > 0 else 0.0

        return {
            "total_bytes": total,
            "used_bytes": used,
            "free_bytes": free,
            "free_human": format_bytes(free),
            "total_human": format_bytes(total),
            "used_human": format_bytes(used),
            "percent_used": percent_used,
            "storage_path": str(storage_dir)
        }

    def check_space(self, required_bytes: int) -> Dict[str, Any]:
        """Smart Pre-Flight Storage Validation."""
        info = self.get_storage_info()
        free_bytes = info["free_bytes"]
        total_needed = required_bytes + self.SAFETY_MARGIN_BYTES
        allowed = free_bytes >= total_needed

        if allowed:
            message = f"Storage space verified. Available: {format_bytes(free_bytes)}"
        else:
            message = f"Insufficient disk space. Required {format_bytes(total_needed)} (including 250MB buffer), but only {format_bytes(free_bytes)} free."

        return {
            "allowed": allowed,
            "free_bytes": free_bytes,
            "required_bytes": required_bytes,
            "safety_margin_bytes": self.SAFETY_MARGIN_BYTES,
            "total_bytes": info["total_bytes"],
            "used_bytes": info["used_bytes"],
            "free_human": format_bytes(free_bytes),
            "required_human": format_bytes(required_bytes),
            "message": message
        }

    def register_transfer(self, transfer_id: str, filename: str, tmp_path: Path, total_size: int, relative_path: Optional[str] = None):
        """Register a new transfer in the tracking registry."""
        self.active_transfers[transfer_id] = {
            "transfer_id": transfer_id,
            "filename": filename,
            "relative_path": relative_path or filename,
            "tmp_path": str(tmp_path),
            "final_path": None,
            "total_size": total_size,
            "bytes_transferred": 0,
            "status": "STAGING",
            "start_time": time.time(),
            "last_update": time.time(),
            "speed_bps": 0.0,
            "speed_human": "0 B/s",
            "eta_seconds": 0
        }

    def update_progress(self, transfer_id: str, bytes_written: int):
        """Update transfer progress and calculate real-time speed / ETA."""
        record = self.active_transfers.get(transfer_id)
        if not record or record["status"] != "STAGING":
            return
        
        now = time.time()
        elapsed = now - record["start_time"]
        record["bytes_transferred"] = bytes_written
        record["last_update"] = now

        if elapsed > 0.1:
            speed = bytes_written / elapsed
            record["speed_bps"] = speed
            record["speed_human"] = f"{format_bytes(int(speed))}/s"
            remaining_bytes = max(0, record["total_size"] - bytes_written)
            record["eta_seconds"] = int(remaining_bytes / speed) if speed > 0 else 0

    def complete_transfer(self, transfer_id: str, final_path: Path):
        """Mark transfer as completed and record final path."""
        record = self.active_transfers.get(transfer_id)
        if record:
            record["status"] = "COMPLETED"
            record["final_path"] = str(final_path)
            record["bytes_transferred"] = record["total_size"]

    def cancel_transfer(self, transfer_id: str) -> bool:
        """Cancel an in-progress transfer and purge its staging temporary file."""
        record = self.active_transfers.get(transfer_id)
        if not record:
            return False

        record["status"] = "CANCELLED"
        tmp_str = record.get("tmp_path")
        if tmp_str:
            p = Path(tmp_str)
            if p.exists():
                try:
                    p.unlink(missing_ok=True)
                    logger.info(f"Purged partial temp file for cancelled transfer: {tmp_str}")
                except Exception as e:
                    logger.error(f"Error purging temp file {tmp_str}: {e}")
        return True

    def get_status(self, transfer_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve progress metrics for a given transfer."""
        record = self.active_transfers.get(transfer_id)
        if not record:
            return None
        
        total = record["total_size"]
        transferred = record["bytes_transferred"]
        pct = round((transferred / total) * 100, 1) if total > 0 else 100.0

        return {
            "transfer_id": transfer_id,
            "filename": record["filename"],
            "relative_path": record.get("relative_path"),
            "status": record["status"],
            "bytes_transferred": transferred,
            "total_size": total,
            "percent": pct,
            "speed_human": record.get("speed_human", "0 B/s"),
            "eta_seconds": record.get("eta_seconds", 0),
            "final_path": record.get("final_path")
        }

    async def save_stream_upload(
        self,
        transfer_id: str,
        upload_file,
        filename: str,
        total_size: int,
        relative_path: Optional[str] = None,
        progress_cb: Optional[Callable[[Dict[str, Any]], Any]] = None
    ) -> Dict[str, Any]:
        """Atomically stream an upload to temporary staging file, then rename upon success."""
        safe_name = os.path.basename(filename)
        transfers_dir = get_transfers_dir()

        # Handle nested relative paths safely
        if relative_path:
            clean_rel = os.path.normpath(relative_path).lstrip(r"\/.")
            target_path = transfers_dir / clean_rel
        else:
            target_path = transfers_dir / safe_name

        target_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = target_path.parent / f".tmp_{transfer_id}_{safe_name}"

        self.register_transfer(transfer_id, safe_name, tmp_path, total_size, relative_path)

        written = 0
        try:
            with open(tmp_path, "wb") as f:
                while True:
                    # Check if user cancelled mid-stream
                    rec = self.active_transfers.get(transfer_id)
                    if rec and rec["status"] == "CANCELLED":
                        raise RuntimeError("Transfer cancelled by user")

                    chunk = await upload_file.read(self.CHUNK_SIZE)
                    if not chunk:
                        break
                    f.write(chunk)
                    written += len(chunk)
                    self.update_progress(transfer_id, written)
                    if progress_cb:
                        await progress_cb(self.get_status(transfer_id))

            # Atomic rename from staging .tmp to target path
            os.replace(tmp_path, target_path)
            self.complete_transfer(transfer_id, target_path)

            return {
                "success": True,
                "transfer_id": transfer_id,
                "filename": safe_name,
                "path": str(target_path),
                "size": written,
                "status": "COMPLETED"
            }

        except Exception as e:
            # Atomic rollback: purge partial .tmp file
            if tmp_path.exists():
                try:
                    tmp_path.unlink(missing_ok=True)
                except Exception:
                    pass
            rec = self.active_transfers.get(transfer_id)
            if rec and rec["status"] != "CANCELLED":
                rec["status"] = "FAILED"
            raise e

    async def save_folder_upload(
        self,
        folder_name: str,
        files: List[Any],
        relative_paths: List[str]
    ) -> Dict[str, Any]:
        """Save a recursive directory tree while preserving nested subfolder structures."""
        safe_folder = os.path.basename(folder_name).strip() or "TransferredFolder"
        base_dir = get_transfers_dir() / safe_folder
        base_dir.mkdir(parents=True, exist_ok=True)

        saved_files = []
        total_bytes = 0

        for idx, file_obj in enumerate(files):
            rel_path = relative_paths[idx] if idx < len(relative_paths) else (file_obj.filename or f"file_{idx}")
            clean_rel = os.path.normpath(rel_path).replace("\\", "/").lstrip("/")
            
            # Security verification: defend against path traversal outside folder
            if ".." in clean_rel.split("/"):
                clean_rel = os.path.basename(clean_rel)
            
            dest_file = base_dir / clean_rel
            dest_file.parent.mkdir(parents=True, exist_ok=True)

            content = await file_obj.read()
            with open(dest_file, "wb") as f:
                f.write(content)
            
            size = len(content)
            total_bytes += size
            saved_files.append({
                "path": clean_rel,
                "size": size
            })

        return {
            "success": True,
            "folder_name": safe_folder,
            "folder_path": str(base_dir),
            "files_count": len(saved_files),
            "total_bytes": total_bytes,
            "files": saved_files
        }

    def create_folder_zip(self, folder_name: str) -> io.BytesIO:
        """Package a transferred folder into a zip archive buffer on-the-fly."""
        safe_folder = os.path.basename(folder_name).strip()
        folder_path = get_transfers_dir() / safe_folder
        if not folder_path.exists() or not folder_path.is_dir():
            raise FileNotFoundError(f"Folder '{folder_name}' not found")

        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for root, _, files in os.walk(folder_path):
                for file in files:
                    full_p = Path(root) / file
                    rel_p = full_p.relative_to(folder_path)
                    zf.write(full_p, arcname=str(rel_p).replace("\\", "/"))
        
        buffer.seek(0)
        return buffer

transfer_manager = TransferManager()

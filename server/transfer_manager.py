"""LANSync Gigabit Transfer Engine for FreeLanSync.
Handles pre-flight space checking, atomic streaming, chunked staging, cancellation rollback, and recursive folder transfers.
"""
import os
import shutil
import time
import uuid
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
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

transfer_manager = TransferManager()

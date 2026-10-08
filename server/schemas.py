"""Request/response schemas for the FreeLanSync server (TD-009).

Pydantic models live here so route modules keep a single responsibility:
`main.py` wires routes and delegates to managers. These are data schemas,
not business-logic classes, and the SRP checker excludes BaseModel
subclasses for that reason.
"""
from typing import List, Optional

from pydantic import BaseModel


class PairRequest(BaseModel):
    pin: str
    device_name: str
    device_id: str


class PairResponse(BaseModel):
    success: bool
    auth_token: Optional[str] = None
    message: str


class BatchCheckRequest(BaseModel):
    hashes: List[str]


class BatchCheckResponse(BaseModel):
    existing_hashes: List[str]
    missing_hashes: List[str]


class SpaceCheckRequest(BaseModel):
    required_bytes: int


class SettingsRequest(BaseModel):
    storage_dir: str


class ValidatePathRequest(BaseModel):
    path: str


class OpenFolderRequest(BaseModel):
    path: Optional[str] = None


class ClipboardPayload(BaseModel):
    text: str
    source: Optional[str] = "desktop"

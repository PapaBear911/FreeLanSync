"""FastAPI application entrypoint for PhotoSync Server."""
from contextlib import asynccontextmanager
from typing import List, Optional
from fastapi import FastAPI, Depends, HTTPException, Header, UploadFile, File, Form, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from pathlib import Path

from .config import SERVICE_NAME, SERVER_HOST, SERVER_PORT, BACKUP_DIR, get_local_ip
from .database import (
    init_db,
    get_device_by_token,
    check_existing_hashes,
    get_all_devices,
    get_recent_media
)
from .auth import pairing_manager
from .discovery import mdns_advertiser
from .storage import storage_manager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize Database and mDNS
    init_db()
    mdns_advertiser.start()
    print(f"[{SERVICE_NAME}] Ready at http://{get_local_ip()}:{SERVER_PORT}")
    yield
    # Shutdown: Clean up mDNS
    mdns_advertiser.stop()

app = FastAPI(
    title=SERVICE_NAME,
    version="1.0.0",
    description="High-speed local Wi-Fi photo & video backup server for Android",
    lifespan=lifespan
)

# CORS middleware for local web dashboard and client access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
static_dir = Path(__file__).resolve().parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Models
class PairRequest(BaseModel):
    pin: str
    device_name: str
    device_id: str

class PairResponse(BaseModel):
    success: bool
    auth_token: Optional[str] = None
    message: str

class HashCheckItem(BaseModel):
    sha256: str
    filename: Optional[str] = None
    size: Optional[int] = None

class BatchCheckRequest(BaseModel):
    hashes: List[str]

class BatchCheckResponse(BaseModel):
    existing_hashes: List[str]
    missing_hashes: List[str]

# Authentication dependency
async def verify_auth(authorization: Optional[str] = Header(None)) -> dict:
    if not authorization:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing Authorization header")
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token format")
    token = parts[1]
    device = get_device_by_token(token)
    if not device:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired device token")
    return device

# --- Public Endpoints ---

@app.get("/api/v1/ping")
async def ping():
    return {
        "status": "online",
        "service": SERVICE_NAME,
        "version": "1.0.0",
        "host": get_local_ip(),
        "port": SERVER_PORT
    }

@app.get("/api/v1/pairing/info")
async def get_pairing_info():
    info = pairing_manager.get_pairing_info()
    qr_svg = pairing_manager.generate_qr_svg()
    return {
        **info,
        "qr_svg": qr_svg
    }

@app.post("/api/v1/pairing/verify", response_model=PairResponse)
async def verify_pair(req: PairRequest):
    token = pairing_manager.verify_pin_and_pair(
        pin=req.pin,
        device_name=req.device_name,
        device_id=req.device_id
    )
    if not token:
        return PairResponse(success=False, message="Invalid or expired 6-digit PIN")
    return PairResponse(
        success=True,
        auth_token=token,
        message="Device paired successfully"
    )

# --- Authenticated Endpoints for Android Client ---

@app.post("/api/v1/photos/check-batch", response_model=BatchCheckResponse)
async def check_batch_hashes(req: BatchCheckRequest, device: dict = Depends(verify_auth)):
    requested_hashes = [h.lower() for h in req.hashes]
    existing = check_existing_hashes(device_id=device["device_id"], hashes=requested_hashes)
    existing_set = set(existing)
    missing = [h for h in requested_hashes if h not in existing_set]
    return BatchCheckResponse(
        existing_hashes=existing,
        missing_hashes=missing
    )

@app.post("/api/v1/photos/upload")
async def upload_photo(
    file: UploadFile = File(...),
    sha256: str = Form(...),
    taken_at: Optional[str] = Form(None),
    device: dict = Depends(verify_auth)
):
    contents = await file.read()
    success, rel_path, message = storage_manager.save_media(
        device_id=device["device_id"],
        device_name=device["device_name"],
        original_filename=file.filename or "media_upload",
        file_bytes=contents,
        expected_sha256=sha256,
        taken_at_iso=taken_at,
        mime_type=file.content_type
    )
    if not success:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)
    
    return {
        "success": True,
        "relative_path": rel_path,
        "sha256": sha256,
        "message": message
    }

# --- Dashboard & Monitoring Endpoints ---

@app.get("/api/v1/devices")
async def list_devices():
    return {"devices": get_all_devices()}

@app.get("/api/v1/photos/recent")
async def list_recent_media():
    return {"recent_media": get_recent_media(limit=60)}

@app.get("/api/v1/photos/view/{relative_path:path}")
async def view_photo(relative_path: str):
    file_path = BACKUP_DIR / relative_path
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="Photo not found")
    return FileResponse(file_path)

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    html_file = static_dir / "index.html"
    if html_file.exists():
        return html_file.read_text(encoding="utf-8")
    return "<h1>PhotoSync Server is running</h1>"

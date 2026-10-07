"""FastAPI application entrypoint for PhotoSync Server."""
from contextlib import asynccontextmanager
from typing import List, Optional
from fastapi import FastAPI, Depends, HTTPException, Header, UploadFile, File, Form, status, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from pathlib import Path
import json

from .config import (
    SERVICE_NAME,
    SERVER_HOST,
    SERVER_PORT,
    get_backup_dir,
    get_storage_dir,
    load_settings,
    save_settings,
    get_local_ip
)
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
from .websocket_manager import ws_manager
from .transfer_manager import transfer_manager

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
    version="1.1.0",
    description="High-speed gigabit local Wi-Fi transfer, backup, and continuity server for Android & Desktop",
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

class BatchCheckRequest(BaseModel):
    hashes: List[str]

class BatchCheckResponse(BaseModel):
    existing_hashes: List[str]
    missing_hashes: List[str]

class SpaceCheckRequest(BaseModel):
    required_bytes: int

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
        "version": "1.1.0",
        "host": get_local_ip(),
        "port": SERVER_PORT
    }

@app.get("/api/v1/pairing/info")
async def get_pairing_info():
    info = pairing_manager.get_pairing_info()
    qr_svg = pairing_manager.generate_qr_svg()
    apk_qr_svg = pairing_manager.generate_apk_download_qr_svg()
    local_ip = get_local_ip()
    return {
        **info,
        "qr_svg": qr_svg,
        "apk_qr_svg": apk_qr_svg,
        "apk_download_url": f"http://{local_ip}:{SERVER_PORT}/static/FreeLanSync.apk"
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

class SettingsRequest(BaseModel):
    storage_dir: str

@app.get("/api/v1/settings")
async def get_settings():
    return {
        "storage_dir": str(get_storage_dir().resolve()),
        "backup_dir": str(get_backup_dir().resolve())
    }

@app.post("/api/v1/settings")
async def update_settings(req: SettingsRequest):
    new_path = Path(req.storage_dir.strip())
    try:
        new_path.mkdir(parents=True, exist_ok=True)
        save_settings({"storage_dir": str(new_path.resolve())})
        return {
            "success": True,
            "message": "Storage directory updated successfully",
            "storage_dir": str(new_path.resolve())
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Cannot create or access directory: {str(e)}")

@app.get("/api/v1/photos/view/{relative_path:path}")
async def view_photo(relative_path: str):
    file_path = get_backup_dir() / relative_path
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="Photo not found")
    return FileResponse(file_path)

# --- Real-Time Device Continuity WebSocket Bridge ---

@app.websocket("/api/v1/ws/device-bridge")
async def device_bridge_ws(
    websocket: WebSocket,
    token: Optional[str] = Query(None),
    client_type: str = Query("device")
):
    """
    Duplex WebSocket connection for Real-Time Continuity:
    - UI Clients (web dashboard / electron app) connect with client_type="ui"
    - Android Devices connect with client_type="device" and bearer auth token
    """
    if client_type == "ui":
        await ws_manager.connect_ui(websocket)
        try:
            while True:
                msg_text = await websocket.receive_text()
                try:
                    payload = json.loads(msg_text)
                    event_type = payload.get("event")
                    event_data = payload.get("data", {})
                    await ws_manager.handle_ui_event(websocket, event_type, event_data)
                except Exception as e:
                    print(f"Error handling UI event: {e}")
        except WebSocketDisconnect:
            ws_manager.disconnect_ui(websocket)
        except Exception:
            ws_manager.disconnect_ui(websocket)
    else:
        # Authenticate Device
        if not token:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
        device = get_device_by_token(token)
        if not device:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
        
        device_id = device["device_id"]
        device_name = device.get("device_name", "Android Phone")
        await ws_manager.connect_device(device_id, websocket, device_name)
        try:
            while True:
                msg_text = await websocket.receive_text()
                try:
                    payload = json.loads(msg_text)
                    event_type = payload.get("event")
                    event_data = payload.get("data", {})
                    await ws_manager.handle_device_event(device_id, event_type, event_data)
                except Exception as e:
                    print(f"Error handling device event: {e}")
        except WebSocketDisconnect:
            ws_manager.disconnect_device(device_id, websocket)
        except Exception:
            ws_manager.disconnect_device(device_id, websocket)

# --- Quick-Drop (Bidirectional File Transfer) Endpoints ---

@app.post("/api/v1/drop/upload")
async def upload_quick_drop(file: UploadFile = File(...)):
    """Upload a file from PC to send directly to paired Android devices."""
    contents = await file.read()
    orig_name = file.filename or "dropped_file"
    drop_info = storage_manager.save_quick_drop(
        original_filename=orig_name,
        file_bytes=contents,
        mime_type=file.content_type
    )
    # Broadcast QUICK_DROP_AVAILABLE to all connected phones
    await ws_manager.broadcast_to_devices("QUICK_DROP_AVAILABLE", {
        "file_id": drop_info["file_id"],
        "filename": drop_info["filename"],
        "size": drop_info["size"],
        "sha256": drop_info["sha256"],
        "download_url": f"/api/v1/drop/download/{drop_info['file_id']}"
    })
    # Also notify UI
    await ws_manager.broadcast_to_ui("QUICK_DROP_SENT", drop_info)
    return {"success": True, "drop": drop_info}

@app.get("/api/v1/drop/pending")
async def list_pending_quick_drops():
    """List pending Quick-Drop files waiting for phone download."""
    return {"pending": storage_manager.list_pending_drops()}

@app.get("/api/v1/drop/download/{file_id}")
async def download_quick_drop(file_id: str):
    """Download a pending Quick-Drop file to the Android device."""
    file_path = storage_manager.get_drop_file_path(file_id)
    if not file_path or not file_path.exists():
        raise HTTPException(status_code=404, detail="Quick-Drop file not found or already downloaded")
    parts = file_path.name.split("_", 1)
    orig_name = parts[1] if len(parts) > 1 else file_path.name
    return FileResponse(file_path, filename=orig_name)

@app.delete("/api/v1/drop/{file_id}")
async def delete_quick_drop(file_id: str):
    """Delete a quick drop file after download or cancel."""
    success = storage_manager.delete_drop_file(file_id)
    if not success:
        raise HTTPException(status_code=404, detail="File not found")
    await ws_manager.broadcast_to_ui("QUICK_DROP_CLEARED", {"file_id": file_id})
    return {"success": True, "message": "Quick-Drop file removed"}

# --- Clipboard Sharing Endpoints ---

class ClipboardPayload(BaseModel):
    text: str
    source: Optional[str] = "desktop"

@app.post("/api/v1/clipboard")
async def update_clipboard(payload: ClipboardPayload):
    """Update shared clipboard from PC or REST client."""
    import datetime
    data = {
        "text": payload.text,
        "source": payload.source,
        "timestamp": datetime.datetime.now().isoformat()
    }
    ws_manager.latest_state["clipboard"] = data
    await ws_manager.broadcast_to_devices("CLIPBOARD_UPDATE", data)
    await ws_manager.broadcast_to_ui("CLIPBOARD_UPDATE", data)
    return {"success": True, "clipboard": data}

@app.get("/api/v1/clipboard")
async def get_clipboard():
    """Get current shared clipboard content."""
    return {"clipboard": ws_manager.latest_state.get("clipboard")}

@app.get("/api/v1/continuity/status")
async def get_continuity_status():
    """Get snapshot of current device continuity status."""
    return ws_manager.latest_state

# --- LANSync Gigabit Transfer Endpoints ---

@app.post("/api/v1/transfer/check-space")
async def check_transfer_space(payload: SpaceCheckRequest, device: dict = Depends(verify_auth)):
    """Pre-flight check to verify target storage has sufficient capacity."""
    return transfer_manager.check_space(payload.required_bytes)

@app.get("/api/v1/transfer/storage-info")
async def get_transfer_storage_info():
    """Return storage volume statistics for UI dashboard and clients."""
    return transfer_manager.get_storage_info()

@app.post("/api/v1/transfer/upload-chunked")
async def upload_chunked_transfer(
    file: UploadFile = File(...),
    transfer_id: str = Form(...),
    filename: str = Form(...),
    total_size: int = Form(...),
    relative_path: Optional[str] = Form(None),
    device: dict = Depends(verify_auth)
):
    """Gigabit streaming upload with atomic staging and rollback on cancellation."""
    async def on_progress(status_dict):
        if status_dict:
            await ws_manager.broadcast_to_ui("TRANSFER_PROGRESS", status_dict)

    try:
        result = await transfer_manager.save_stream_upload(
            transfer_id=transfer_id,
            upload_file=file,
            filename=filename,
            total_size=total_size,
            relative_path=relative_path,
            progress_cb=on_progress
        )
        await ws_manager.broadcast_to_ui("TRANSFER_COMPLETED", result)
        return result
    except Exception as e:
        await ws_manager.broadcast_to_ui("TRANSFER_FAILED", {"transfer_id": transfer_id, "error": str(e)})
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/v1/transfer/cancel/{transfer_id}")
async def cancel_transfer(transfer_id: str, device: dict = Depends(verify_auth)):
    """Cancel an ongoing transfer and immediately delete temporary partial data."""
    success = transfer_manager.cancel_transfer(transfer_id)
    await ws_manager.broadcast_to_ui("TRANSFER_CANCELLED", {"transfer_id": transfer_id})
    return {
        "success": success,
        "transfer_id": transfer_id,
        "message": "Transfer cancelled and staging data rolled back."
    }

@app.get("/api/v1/transfer/status/{transfer_id}")
async def get_transfer_status(transfer_id: str, device: dict = Depends(verify_auth)):
    """Retrieve current transfer progress, throughput, and state."""
    status_dict = transfer_manager.get_status(transfer_id)
    if not status_dict:
        raise HTTPException(status_code=404, detail="Transfer not found")
    return status_dict

@app.post("/api/v1/transfer/folder")
async def upload_folder_transfer(
    files: List[UploadFile] = File(...),
    folder_name: str = Form(...),
    relative_paths: List[str] = Form(...),
    device: dict = Depends(verify_auth)
):
    """Recursive folder upload with directory hierarchy preservation."""
    cleaned_rel_paths = []
    for r in relative_paths:
        if r.startswith("[") and r.endswith("]"):
            try:
                cleaned_rel_paths.extend(json.loads(r))
            except Exception:
                cleaned_rel_paths.append(r)
        else:
            cleaned_rel_paths.append(r)

    try:
        result = await transfer_manager.save_folder_upload(
            folder_name=folder_name,
            files=files,
            relative_paths=cleaned_rel_paths
        )
        await ws_manager.broadcast_to_ui("FOLDER_TRANSFER_COMPLETED", result)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/v1/transfer/download-folder/{folder_name}")
async def download_folder_zip(folder_name: str, device: dict = Depends(verify_auth)):
    """Package and stream an entire directory tree as a zip archive."""
    try:
        buf = transfer_manager.create_folder_zip(folder_name)
        return StreamingResponse(
            iter([buf.getvalue()]),
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{folder_name}.zip"'}
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Folder '{folder_name}' not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/transfer/list")
async def list_transfers():
    """List all completed gigabit files and folders in the Transfers directory."""
    transfers_dir = get_transfers_dir()
    items = []
    if transfers_dir.exists():
        for p in transfers_dir.iterdir():
            if p.name.startswith(".tmp_"):
                continue
            is_dir = p.is_dir()
            try:
                if is_dir:
                    size = sum(f.stat().st_size for f in p.glob("**/*") if f.is_file())
                else:
                    size = p.stat().st_size
                items.append({
                    "name": p.name,
                    "is_dir": is_dir,
                    "size": size,
                    "mtime": p.stat().st_mtime
                })
            except Exception:
                pass
    items.sort(key=lambda x: x["mtime"], reverse=True)
    return {"transfers": items}

@app.get("/api/v1/transfer/download-file/{file_name}")
async def download_transfer_file(file_name: str):
    """Download an individual file from the Transfers folder."""
    import os
    safe_name = os.path.basename(file_name)
    p = get_transfers_dir() / safe_name
    if not p.exists() or not p.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(p, filename=safe_name)

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    html_file = static_dir / "index.html"
    if html_file.exists():
        return html_file.read_text(encoding="utf-8")
    return "<h1>FreeLanSync Server is running</h1>"

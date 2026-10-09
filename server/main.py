"""FastAPI application entrypoint for FreeLanSync Server."""
from contextlib import asynccontextmanager
from typing import List, Optional
from fastapi import FastAPI, Depends, HTTPException, Header, UploadFile, File, Form, status, WebSocket, WebSocketDisconnect, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import json
import os
import sys
import subprocess
import datetime

from .config import (
    SERVICE_NAME,
    SERVER_HOST,
    SERVER_PORT,
    get_backup_dir,
    get_storage_dir,
    get_transfers_dir,
    load_settings,
    save_settings,
    get_local_ip,
    get_drive_stats,
    test_writable,
    get_storage_presets,
    get_default_recommended_storage,
    format_bytes
)
from .database import (
    init_db,
    get_device_by_token,
    check_existing_hashes,
    get_all_devices,
    get_recent_media
)
from .auth import pairing_manager
from .schemas import (
    BatchCheckRequest,
    BatchCheckResponse,
    ClipboardPayload,
    OpenFolderRequest,
    PairRequest,
    PairResponse,
    SettingsRequest,
    SpaceCheckRequest,
    ValidatePathRequest,
)
from .discovery import mdns_advertiser
from .udp_discovery import udp_discovery
from .storage import storage_manager
from .thumbnails import get_or_create_thumbnail
from .websocket_manager import ws_manager
from .transfer_manager import transfer_manager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize Database, mDNS and the UDP discovery fallback
    init_db()
    mdns_advertiser.start()
    udp_discovery.start()
    
    # Ensure static/FreeLanSync.apk exists if possible
    apk_found = find_apk_file()
    target_apk = Path(__file__).resolve().parent / "static" / "FreeLanSync.apk"
    if apk_found and not target_apk.exists():
        try:
            import shutil
            shutil.copy2(apk_found, target_apk)
            print(f"[{SERVICE_NAME}] Seeded {target_apk} from {apk_found}")
        except Exception:
            pass
            
    print(f"[{SERVICE_NAME}] Ready at http://{get_local_ip()}:{SERVER_PORT}")
    yield
    # Shutdown: Clean up discovery advertisers
    udp_discovery.stop()
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

def find_apk_file() -> Optional[Path]:
    """Find the packaged or compiled FreeLanSync Android APK across candidate locations."""
    base_repo = Path(__file__).resolve().parent.parent
    candidates = [
        Path(__file__).resolve().parent / "static" / "FreeLanSync.apk",
        base_repo / "server" / "static" / "FreeLanSync.apk",
        base_repo / "releases" / "FreeLanSync-v1.1.0.apk",
        base_repo / "releases" / "FreeLanSync.apk",
        base_repo / "android" / "app" / "build" / "outputs" / "apk" / "release" / "app-release.apk",
        Path(__file__).resolve().parent.parent.parent / "releases" / "FreeLanSync-v1.1.0.apk",
        Path.home() / "Downloads" / "FreeLanSync-v1.1.0.apk",
        Path.home() / "Downloads" / "FreeLanSync.apk"
    ]
    for cand in candidates:
        try:
            if cand.exists() and cand.is_file() and cand.stat().st_size > 1000000:
                return cand
        except Exception:
            pass
    return None

@app.get("/static/FreeLanSync.apk")
@app.get("/FreeLanSync.apk")
@app.get("/download-apk")
@app.get("/api/v1/download-apk")
async def download_apk_endpoint():
    apk_path = find_apk_file()
    if not apk_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="FreeLanSync.apk not found. Please build or place the APK into server/static/."
        )
    return FileResponse(
        path=str(apk_path),
        media_type="application/vnd.android.package-archive",
        filename="FreeLanSync-v1.1.0.apk",
        headers={
            "Content-Disposition": 'attachment; filename="FreeLanSync-v1.1.0.apk"',
            "Cache-Control": "no-cache"
        }
    )

# Mount static files
static_dir = Path(__file__).resolve().parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Models live in .schemas (TD-009); main.py wires routes and delegates.

# Authentication dependencies
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

async def optional_verify_auth(authorization: Optional[str] = Header(None)) -> Optional[dict]:
    if not authorization:
        return None
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    return get_device_by_token(parts[1])

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
async def get_pairing_info(request: Request):
    info = pairing_manager.get_pairing_info()
    qr_svg = pairing_manager.generate_qr_svg()
    apk_qr_svg = pairing_manager.generate_apk_download_qr_svg()
    local_ip = get_local_ip()
    payload = {
        "host": info["host"],
        "port": info["port"],
        "expires_in": info["expires_in"],
        "apk_qr_svg": apk_qr_svg,
        "apk_download_url": f"http://{local_ip}:{SERVER_PORT}/static/FreeLanSync.apk"
    }
    # TD-012 (S1): the live PIN (and QR/URI that encode it) is only visible to the
    # local operator (desktop dashboard on localhost). Remote LAN clients may
    # fetch connection metadata but never the PIN itself. "testclient" is the
    # in-process ASGI test identity — it never appears on a real socket.
    peer = request.client.host if request.client else ""
    if peer in ("127.0.0.1", "::1", "testclient"):
        payload["pin"] = info["pin"]
        payload["qr_payload"] = info["qr_payload"]
        payload["qr_svg"] = qr_svg
        # Deep-link encoding of the same payload (freelansync://host:port?pin=...)
        # consumed by the Android QR scanner; PIN-bearing, so loopback-only too.
        payload["pairing_uri"] = info["pairing_uri"]
        payload["pairing_uri_scheme"] = info["pairing_uri_scheme"]
    return payload

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
# PUBLIC (LAN dashboard by design): read-only inventory for the local dashboard.
# Write/mutation routes below validate inputs and contain paths (TD-005/TD-010).

@app.get("/api/v1/devices")
async def list_devices():
    return {"devices": get_all_devices()}

@app.get("/api/v1/photos/recent")
async def list_recent_media(
    limit: int = Query(60, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    page, has_more = get_recent_media(limit=limit, offset=offset)
    return {
        "recent_media": page,
        "pagination": {
            "limit": limit,
            "offset": offset,
            "returned": len(page),
            "has_more": has_more,
        },
    }

@app.get("/api/v1/settings")
async def get_settings():
    s_dir = get_storage_dir()
    stats = get_drive_stats(s_dir)
    writable, perm_msg = test_writable(s_dir)
    return {
        "storage_dir": str(s_dir.resolve()),
        "backup_dir": str(get_backup_dir().resolve()),
        "transfers_dir": str(get_transfers_dir().resolve()),
        "writable": writable,
        "perm_msg": perm_msg,
        "stats": stats
    }

@app.get("/api/v1/settings/storage-suggestions")
async def get_storage_suggestions():
    return {
        "recommended_path": str(get_default_recommended_storage().resolve()),
        "current_path": str(get_storage_dir().resolve()),
        "suggestions": get_storage_presets()
    }

@app.post("/api/v1/settings/validate-path")
async def validate_storage_path(req: ValidatePathRequest):
    p_str = req.path.strip()
    if not p_str:
        return {"valid": False, "error": "Path cannot be empty"}
    try:
        p = Path(p_str).expanduser()
        writable, perm_msg = test_writable(p)
        stats = get_drive_stats(p)
        return {
            "valid": True,
            "resolved_path": str(p.resolve()),
            "writable": writable,
            "perm_msg": perm_msg,
            "stats": stats
        }
    except Exception as e:
        return {"valid": False, "error": str(e)}

@app.post("/api/v1/settings")
async def update_settings(req: SettingsRequest):
    new_path = Path(req.storage_dir.strip()).expanduser()
    try:
        new_path.mkdir(parents=True, exist_ok=True)
        writable, perm_msg = test_writable(new_path)
        if not writable:
            raise HTTPException(status_code=400, detail=f"Directory is not writable: {perm_msg}")
        save_settings({"storage_dir": str(new_path.resolve())})
        (new_path / "Backups").mkdir(parents=True, exist_ok=True)
        (new_path / "Transfers").mkdir(parents=True, exist_ok=True)
        (new_path / "QuickDrop").mkdir(parents=True, exist_ok=True)
        
        stats = get_drive_stats(new_path)
        return {
            "success": True,
            "message": "Storage directory updated successfully",
            "storage_dir": str(new_path.resolve()),
            "backup_dir": str((new_path / "Backups").resolve()),
            "transfers_dir": str((new_path / "Transfers").resolve()),
            "stats": stats
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Cannot create or access directory: {str(e)}")

@app.post("/api/v1/settings/open-folder")
async def open_storage_folder(req: Optional[OpenFolderRequest] = None):
    # TD-010 (S0): never hand an arbitrary client path to the OS opener —
    # an unauthenticated client could otherwise launch an uploaded executable.
    root = get_storage_dir().resolve()
    target = Path(req.path).expanduser() if (req and req.path) else root
    try:
        resolved_path = target.resolve()
    except OSError as e:
        raise HTTPException(status_code=400, detail=f"Invalid path: {e}")
    if resolved_path != root and root not in resolved_path.parents:
        raise HTTPException(status_code=400, detail="Path is outside the storage root")
    if not resolved_path.exists():
        resolved_path.mkdir(parents=True, exist_ok=True)
    if not resolved_path.is_dir():
        raise HTTPException(status_code=400, detail="Target must be a directory")
    resolved = str(resolved_path)
    try:
        if sys.platform == "win32":
            os.startfile(resolved)
        elif sys.platform == "darwin":
            subprocess.run(["open", resolved])
        else:
            subprocess.run(["xdg-open", resolved])
        return {"success": True, "path": resolved}
    except Exception as e:
        return {"success": False, "error": str(e), "path": resolved}

@app.get("/api/v1/photos/view/{relative_path:path}")
async def view_photo(relative_path: str):
    # TD-005 (S1): resolve then assert containment — the raw :path param may
    # traverse out of Backups/; nested legitimate paths must still work.
    backup_root = get_backup_dir().resolve()
    file_path = (get_backup_dir() / relative_path).resolve()
    if file_path != backup_root and backup_root not in file_path.parents:
        raise HTTPException(status_code=404, detail="Photo not found")
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="Photo not found")
    # TD-038: allow the dashboard lightbox to cache originals instead of
    # revalidating them on every refresh tick (ETag/Last-Modified still sent).
    return FileResponse(file_path, headers={"Cache-Control": "public, max-age=3600"})

@app.get("/api/v1/photos/thumb/{relative_path:path}")
async def photo_thumbnail(relative_path: str):
    # Classification: PUBLIC (LAN dashboard gallery) — same TD-005
    # resolve+containment as view_photo; serves only generated JPEG thumbnails,
    # never raw originals (TD-038).
    backup_root = get_backup_dir().resolve()
    file_path = (get_backup_dir() / relative_path).resolve()
    if file_path != backup_root and backup_root not in file_path.parents:
        raise HTTPException(status_code=404, detail="Thumbnail not found")
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="Thumbnail not found")
    thumb_path = get_or_create_thumbnail(file_path)
    if thumb_path is None:
        raise HTTPException(status_code=404, detail="No thumbnail for this file")
    return FileResponse(
        thumb_path,
        media_type="image/jpeg",
        headers={"Cache-Control": "public, max-age=86400"},
    )


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
            await ws_manager.disconnect_device(device_id, websocket)
        except Exception:
            await ws_manager.disconnect_device(device_id, websocket)

# --- Quick-Drop (Bidirectional File Transfer) Endpoints ---
# PUBLIC (LAN feature by design): file_id values are server-generated hex12 and
# validated before use (TD-016); see storage.get_drop_file_path.

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
    # TD-016: file_id is interpolated into a glob; reject anything that is not
    # a server-issued hex12 id before touching the filesystem.
    if not storage_manager.is_valid_file_id(file_id):
        raise HTTPException(status_code=400, detail="Invalid file_id")
    file_path = storage_manager.get_drop_file_path(file_id)
    if not file_path or not file_path.exists():
        raise HTTPException(status_code=404, detail="Quick-Drop file not found or already downloaded")
    parts = file_path.name.split("_", 1)
    orig_name = parts[1] if len(parts) > 1 else file_path.name
    return FileResponse(file_path, filename=orig_name)

@app.delete("/api/v1/drop/{file_id}")
async def delete_quick_drop(file_id: str):
    """Delete a quick drop file after download or cancel."""
    if not storage_manager.is_valid_file_id(file_id):
        raise HTTPException(status_code=400, detail="Invalid file_id")
    success = storage_manager.delete_drop_file(file_id)
    if not success:
        raise HTTPException(status_code=404, detail="File not found")
    await ws_manager.broadcast_to_ui("QUICK_DROP_CLEARED", {"file_id": file_id})
    return {"success": True, "message": "Quick-Drop file removed"}

# --- Clipboard Sharing Endpoints ---
# PUBLIC (LAN continuity by design): clipboard/status mirror between paired LAN peers.

@app.post("/api/v1/clipboard")
async def update_clipboard(payload: ClipboardPayload):
    """Update shared clipboard from PC or REST client."""
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
# PUBLIC (LAN dashboard by design) except where noted: check-space/storage-info/
# upload-chunked accept an optional token when present (see optional_verify_auth);
# folder/zip/list/file reads are contained (TD-011) and skip staging names.

@app.post("/api/v1/transfer/check-space")
async def check_transfer_space(payload: SpaceCheckRequest, device: Optional[dict] = Depends(optional_verify_auth)):
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
    device: Optional[dict] = Depends(optional_verify_auth)
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
async def cancel_transfer(transfer_id: str, device: Optional[dict] = Depends(optional_verify_auth)):
    """Cancel an ongoing transfer and immediately delete temporary partial data."""
    success = transfer_manager.cancel_transfer(transfer_id)
    await ws_manager.broadcast_to_ui("TRANSFER_CANCELLED", {"transfer_id": transfer_id})
    return {
        "success": success,
        "transfer_id": transfer_id,
        "message": "Transfer cancelled and staging data rolled back."
    }

@app.get("/api/v1/transfer/status/{transfer_id}")
async def get_transfer_status(transfer_id: str, device: Optional[dict] = Depends(optional_verify_auth)):
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
    device: Optional[dict] = Depends(optional_verify_auth)
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
async def download_folder_zip(folder_name: str, device: Optional[dict] = Depends(optional_verify_auth)):
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
    # Contained: basename strips any directory components (TD-011).
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

# FreeLanSync & LANSync Gigabit Feature Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebrand the entire ecosystem (Server, Web Dashboard, Desktop Electron App, Android App) to **FreeLanSync**, and integrate the premier gigabit local-network capabilities of **LANSync** (recursive folder sharing, smart pre-flight disk space validation, atomic transfer with cancellation/rollback, high-performance Android Wi-Fi/WakeLock, and a real-time transfer speedometer HUD), verified with a full test suite and polished via OpenDesign.

**Architecture:** 
- A FastAPI backend providing high-throughput chunked streaming (1MB-4MB I/O buffers), pre-flight OS disk space calculation (`shutil.disk_usage`), recursive directory tree ingestion, atomic `.tmp` staging with instant rollback on abort/cancellation, and real-time WebSocket progress broadcasts.
- A Web Dashboard with folder drag-and-drop (`webkitdirectory`), live throughput speedometer (MB/s & ETA), storage capacity bar, and transfer cancel controls.
- An Android client featuring a Foreground Service with `PowerManager.PARTIAL_WAKE_LOCK` and `WifiManager.WifiLock (WIFI_MODE_FULL_HIGH_PERF)` to sustain uninterrupted gigabit Wi-Fi transfers when the screen is locked.
- OpenDesign synchronization for the web and mobile UI design assets.

**Tech Stack:** Python 3.14 (FastAPI, Uvicorn, WebSockets), HTML5/TailwindCSS/Vanilla JS (Web Dashboard), Electron (Desktop App), Kotlin / Jetpack Compose / WorkManager (Android App), OpenDesign MCP.

**Spec:** `docs/superpowers/plans/2026-10-07-freelansync-lansync-integration-plan.md`

## Global Constraints
- Zero cloud reliance: 100% offline local Wi-Fi, Ethernet, and Hotspot operation.
- End-to-end backward compatibility: All existing camera roll backup (`/api/v1/photos/*`) and continuity features (notifications, clipboard, battery HUD, remote media controls) must remain fully operational.
- Secure path traversal defense: Recursive directory uploads must strictly sanitize relative paths to prevent directory traversal attacks (`../`).
- Atomic filesystem guarantees: Multi-GB transfers must be written to temporary staging files (`.tmp_*`) and only renamed upon verification, deleting partial data if cancelled or interrupted.

## Review Focus
1. Insufficient disk space on receiver: The pre-flight checker must reject transfers before receiving data if `free_space < required_space + 250MB`.
2. Connection drop or user cancellation mid-transfer: Unfinished `.tmp` files must be purged immediately so no orphan multi-GB garbage persists.
3. Path traversal in recursive folder upload: Uploading files with malicious paths like `../../etc/passwd` must be sanitized to safe local subdirectories.
4. Screen turn-off / doze mode during Android transfers: `PARTIAL_WAKE_LOCK` and `WIFI_MODE_FULL_HIGH_PERF` must prevent radio throttling.
5. Rebranding consistency: All UI strings, mDNS service types, APK download links, window titles, and system tray labels must reflect `FreeLanSync`.

---

### Task 1: Complete Ecosystem Rebranding to FreeLanSync

**Files:**
- Modify: `server/config.py`
- Modify: `server/auth.py`
- Modify: `server/main.py`
- Modify: `server/static/index.html`
- Modify: `desktop-app/main.js`
- Modify: `desktop-app/package.json`
- Modify: `android/app/src/main/AndroidManifest.xml`
- Modify: `android/app/src/main/java/com/photosync/app/ui/DashboardScreen.kt`
- Modify: `run_server.bat`
- Test: `tests/test_rebranding.py`

**Interfaces:**
- Produces: `SERVICE_NAME = "FreeLanSync Desktop Server"`, `MDNS_SERVICE_TYPE = "_freelansync._tcp.local."`, APK endpoint `/static/FreeLanSync.apk`, App title "FreeLanSync".
- Backward compatibility: Fallback support for `_photosync._tcp` discovery so existing clients can pair during transition.

- [ ] **Step 1: Write the failing test for FreeLanSync branding**

```python
# tests/test_rebranding.py
from server.config import SERVICE_NAME, MDNS_SERVICE_TYPE
from server.main import app
from fastapi.testclient import TestClient

def test_freelansync_branding():
    client = TestClient(app)
    assert "FreeLanSync" in SERVICE_NAME
    assert "freelansync" in MDNS_SERVICE_TYPE
    res = client.get("/api/v1/auth/qr-info")
    assert res.status_code == 200
    assert "FreeLanSync.apk" in res.json()["apk_url"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_rebranding.py -v`
Expected: FAIL on assertion

- [ ] **Step 3: Implement Rebranding across Backend, Web, Desktop, and Android**

1. Update `server/config.py`:
   - `SERVICE_NAME = "FreeLanSync Desktop Server"`
   - `MDNS_SERVICE_TYPE = "_freelansync._tcp.local."`
   - Config file fallback: look for `freelansync_config.json`, fallback to `photosync_config.json`.
   - DB file fallback: `freelansync.db`.
2. Update `server/auth.py`:
   - Point APK download URL to `/static/FreeLanSync.apk`.
   - Update service string to `"freelansync"`.
3. Update `server/main.py`:
   - Root banner: `"<h1>FreeLanSync Server is running</h1>"`.
   - APK download URL in info endpoints.
4. Update `server/static/index.html`:
   - Title: `FreeLanSync Continuity & Gigabit Transfer Hub`.
   - App label, download buttons (`FreeLanSync.apk`), mDNS broadcast info.
5. Update `desktop-app/main.js` and `package.json`:
   - Window title, tray tooltip: `FreeLanSync Continuity Hub`.
6. Update `android/app/src/main/AndroidManifest.xml` and Compose UI:
   - `android:label="FreeLanSync"`.
   - Dashboard screen title: `FreeLanSync`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_rebranding.py -v`
Expected: PASS

- [ ] **Step 5: Commit changes**

```bash
git add server/ desktop-app/ android/ tests/test_rebranding.py run_server.bat
git commit -m "feat: rebrand ecosystem to FreeLanSync"
```

---

### Task 2: Smart Pre-Flight Storage Validation ("Smart Space Checker")

**Files:**
- Create: `server/transfer_manager.py`
- Modify: `server/main.py`
- Test: `tests/test_space_checker.py`

**Interfaces:**
- Consumes: `storage_dir: Path`
- Produces: `POST /api/v1/transfer/check-space`:
  Input: `{"required_bytes": int}`
  Output: `{"allowed": bool, "free_bytes": int, "required_bytes": int, "safety_margin_bytes": int, "free_human": str, "message": str}`

- [ ] **Step 1: Write the failing test for space checking**

```python
# tests/test_space_checker.py
import pytest
from fastapi.testclient import TestClient
from server.main import app
from server.auth import create_access_token

def test_space_checker_success_and_rejection():
    client = TestClient(app)
    token = create_access_token({"sub": "test_device"})
    
    # 1. Normal requirement (e.g. 10 MB) -> should be allowed
    res = client.post(
        "/api/v1/transfer/check-space",
        json={"required_bytes": 10 * 1024 * 1024},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["allowed"] is True
    assert data["free_bytes"] > 0

    # 2. Impossible requirement (e.g. 50 Petabytes) -> should be rejected
    res = client.post(
        "/api/v1/transfer/check-space",
        json={"required_bytes": 50 * 1024 * 1024 * 1024 * 1024 * 1024},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["allowed"] is False
    assert "Insufficient disk space" in data["message"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_space_checker.py -v`
Expected: FAIL 404 Not Found on `/api/v1/transfer/check-space`

- [ ] **Step 3: Implement `check_disk_space` in `server/transfer_manager.py` & mount endpoint in `server/main.py`**

- Use `shutil.disk_usage(get_storage_dir())`.
- Minimum safety margin: 250 MB (`250 * 1024 * 1024`).
- Return human readable sizes (`GB`, `MB`).

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_space_checker.py -v`
Expected: PASS

- [ ] **Step 5: Commit changes**

```bash
git add server/transfer_manager.py server/main.py tests/test_space_checker.py
git commit -m "feat: implement smart pre-flight disk space checker"
```

---

### Task 3: Atomic Transfer Streaming, Cancellation & Rollback

**Files:**
- Modify: `server/transfer_manager.py`
- Modify: `server/main.py`
- Test: `tests/test_atomic_transfer.py`

**Interfaces:**
- Produces:
  - `POST /api/v1/transfer/upload-chunked`: accepts multipart upload with `transfer_id`, `filename`, `relative_path`, `total_size`. Streams to `.tmp_<transfer_id>` file in chunks of 1MB.
  - `POST /api/v1/transfer/cancel/{transfer_id}`: aborts transfer and immediately unlinks the staging `.tmp` file.
  - `GET /api/v1/transfer/status/{transfer_id}`: returns current byte progress, throughput, and state (`STAGING`, `COMPLETED`, `CANCELLED`).

- [ ] **Step 1: Write the failing test for atomic transfer and cancellation rollback**

```python
# tests/test_atomic_transfer.py
import io, uuid
from fastapi.testclient import TestClient
from server.main import app
from server.auth import create_access_token
from server.config import get_storage_dir

def test_atomic_upload_and_cancellation():
    client = TestClient(app)
    token = create_access_token({"sub": "test_device"})
    headers = {"Authorization": f"Bearer {token}"}
    
    # 1. Normal upload -> atomic rename to final file
    tid1 = str(uuid.uuid4())
    content = b"GIGABIT_LAN_STREAMING_DATA" * 1000
    res = client.post(
        "/api/v1/transfer/upload-chunked",
        data={"transfer_id": tid1, "filename": "test_large.dat", "total_size": len(content)},
        files={"file": ("test_large.dat", io.BytesIO(content), "application/octet-stream")},
        headers=headers
    )
    assert res.status_code == 200
    assert res.json()["success"] is True
    dest_path = get_storage_dir() / "Transfers" / "test_large.dat"
    assert dest_path.exists()
    
    # 2. Cancelled transfer -> unlinks .tmp file immediately
    tid2 = str(uuid.uuid4())
    cancel_res = client.post(f"/api/v1/transfer/cancel/{tid2}", headers=headers)
    assert cancel_res.status_code == 200
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_atomic_transfer.py -v`
Expected: FAIL 404 Not Found on `/api/v1/transfer/upload-chunked`

- [ ] **Step 3: Implement atomic transfer manager with `.tmp` staging, cancellation, and rename**

- Maintain active transfer registry in memory.
- Write chunks to `.tmp_<transfer_id>_<safe_filename>`.
- On completion, verify size matches `total_size` (and optional SHA-256). Rename atomically to target file using `os.replace`.
- On cancel, close open file handle and call `os.remove` on the temp file.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_atomic_transfer.py -v`
Expected: PASS

- [ ] **Step 5: Commit changes**

```bash
git add server/transfer_manager.py server/main.py tests/test_atomic_transfer.py
git commit -m "feat: add atomic transfer streaming with cancellation and rollback"
```

---

### Task 4: Recursive Folder Upload & Tree Preservation

**Files:**
- Modify: `server/transfer_manager.py`
- Modify: `server/main.py`
- Test: `tests/test_folder_transfer.py`

**Interfaces:**
- Produces:
  - `POST /api/v1/transfer/folder`: accepts batch upload of files with `relative_path` metadata (e.g. `Projects/App/src/main.rs`). Reconstructs subdirectories safely while preventing `..` traversal.
  - `GET /api/v1/transfer/download-folder/{folder_name}`: streams a zip archive dynamically via `StreamingResponse` preserving the directory hierarchy.

- [ ] **Step 1: Write the failing test for recursive folder transfer**

```python
# tests/test_folder_transfer.py
import io, zipfile
from fastapi.testclient import TestClient
from server.main import app
from server.auth import create_access_token
from server.config import get_storage_dir

def test_recursive_folder_upload_and_download():
    client = TestClient(app)
    token = create_access_token({"sub": "test_device"})
    headers = {"Authorization": f"Bearer {token}"}
    
    # Upload nested structure: Docs/readme.txt and Docs/src/main.py
    files = [
        ("files", ("readme.txt", io.BytesIO(b"Hello Docs"), "text/plain")),
        ("files", ("main.py", io.BytesIO(b"print('Hi')"), "text/plain"))
    ]
    data = {
        "folder_name": "TestFolder",
        "relative_paths": ["Docs/readme.txt", "Docs/src/main.py"]
    }
    res = client.post("/api/v1/transfer/folder", files=files, data=data, headers=headers)
    assert res.status_code == 200
    assert res.json()["success"] is True
    
    # Verify disk structure
    base = get_storage_dir() / "Transfers" / "TestFolder"
    assert (base / "Docs" / "readme.txt").exists()
    assert (base / "Docs" / "src" / "main.py").exists()

    # Download folder as zip stream
    dl_res = client.get("/api/v1/transfer/download-folder/TestFolder", headers=headers)
    assert dl_res.status_code == 200
    zf = zipfile.ZipFile(io.BytesIO(dl_res.content))
    assert "Docs/readme.txt" in zf.namelist()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_folder_transfer.py -v`
Expected: FAIL 404 Not Found

- [ ] **Step 3: Implement recursive folder upload and zip streaming download**

- Path sanitization: Ensure each segment of `relative_path` is sanitized (`os.path.normpath` + reject any path starting with `..` or `/`).
- Create parent directories automatically: `dest_file.parent.mkdir(parents=True, exist_ok=True)`.
- Implement dynamic zip streaming generator using `zipfile.ZipFile`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_folder_transfer.py -v`
Expected: PASS

- [ ] **Step 5: Commit changes**

```bash
git add server/transfer_manager.py server/main.py tests/test_folder_transfer.py
git commit -m "feat: add recursive folder upload and streaming download"
```

---

### Task 5: Android Gigabit Continuity Enhancements (High-Performance Wi-Fi & WakeLock)

**Files:**
- Modify: `android/app/src/main/AndroidManifest.xml`
- Create: `android/app/src/main/java/com/photosync/app/service/TransferWakeManager.kt`
- Modify: `android/app/src/main/java/com/photosync/app/ui/DashboardScreen.kt`

**Interfaces:**
- Consumes: `Context.getSystemService(Context.POWER_SERVICE)`, `Context.getSystemService(Context.WIFI_SERVICE)`
- Produces: `TransferWakeManager` acquiring `PARTIAL_WAKE_LOCK` and `WifiLock(WIFI_MODE_FULL_HIGH_PERF)` during active gigabit transfers.

- [ ] **Step 1: Add WAKE_LOCK permission to `AndroidManifest.xml`**
- [ ] **Step 2: Create `TransferWakeManager.kt` managing wake and Wi-Fi locks with safe acquire/release**
- [ ] **Step 3: Update `DashboardScreen.kt` with Gigabit Transfer UI section, Space Checker stats, and FreeLanSync branding**
- [ ] **Step 4: Build Release APK using Gradle to verify clean compilation**

Run: `android/gradlew.bat assembleRelease`
Expected: SUCCESS, outputting APK to `android/app/build/outputs/apk/release/app-release-unsigned.apk`

- [ ] **Step 5: Copy updated APK to `server/static/FreeLanSync.apk`**
- [ ] **Step 6: Commit changes**

```bash
git add android/ server/static/FreeLanSync.apk
git commit -m "feat: add android high-performance wakelock and compile FreeLanSync apk"
```

---

### Task 6: OpenDesign Web Dashboard Polish & Synchronization

**Files:**
- Modify: `server/static/index.html`
- Sync with: OpenDesign project `photosync-b71b`

**Interfaces:**
- Produces: Polished FreeLanSync Web Dashboard with:
  - High-Speed Transfer Dropzone supporting both Single Files & Folders (`webkitdirectory`).
  - Gigabit Speedometer / Transfer HUD (MB/s real-time gauge, ETA, progress bar).
  - Storage Capacity & Pre-flight Space Status Bar.
  - Transfer Cancellation & Rollback modal.
  - Synced to OpenDesign `photosync-b71b`.

- [ ] **Step 1: Update `server/static/index.html` with new features and FreeLanSync branding**
- [ ] **Step 2: Sync updated `server/static/index.html` to OpenDesign project `photosync-b71b` via MCP tool `write_file`**
- [ ] **Step 3: Verify OpenDesign artifact status**
- [ ] **Step 4: Commit changes**

```bash
git add server/static/index.html
git commit -m "feat: polish web dashboard with gigabit transfer HUD and sync OpenDesign"
```

---

### Task 7: End-to-End Verification & Full Regression Testing

**Files:**
- Create: `tests/e2e_freelansync_simulation.py`
- Modify: `tests/e2e_continuity_simulation.py`
- Run: Pytest test suite across all modules

- [ ] **Step 1: Update `tests/e2e_continuity_simulation.py` to ensure idempotency across multiple runs**
- [ ] **Step 2: Implement comprehensive `tests/e2e_freelansync_simulation.py` exercising:**
  1. Discovery & FreeLanSync Branding
  2. Pre-flight Smart Space Validation
  3. Gigabit Atomic Chunked Streaming & Cancellation Rollback
  4. Recursive Folder Tree Upload & Streaming Zip Download
  5. Full Synco Continuity Suite (Notifications, Calls, Media Controller, Battery HUD, Clipboard)
- [ ] **Step 3: Run full verification suite**

Run: `python -m pytest tests/`
Run: `python -m tests.e2e_freelansync_simulation`
Expected: ALL PASS with 100% success rate.

- [ ] **Step 4: Commit changes & summarize results for user**

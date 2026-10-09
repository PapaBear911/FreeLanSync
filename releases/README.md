# FreeLanSync v1.2.0 Release Package

> **Zero-Cloud Gigabit P2P File Transfer, Backup & Device Continuity Suite**  
> Move GB files across local Wi-Fi / LAN in seconds without Internet or cloud accounts.

---

## 📦 Published Installers & Artifacts (v1.2.0)

| Binary | Target | Size | Description |
| :--- | :--- | :--- | :--- |
| **`FreeLanSync-Desktop-Setup-1.2.0.exe`** | Windows 10/11 | ~257 MB | Full NSIS Visual Wizard Installer with Start Menu, Desktop shortcut, and uninstaller. |
| **`FreeLanSync-Desktop-Portable-1.2.0.exe`** | Windows 10/11 | ~257 MB | Standalone portable executable. Zero installation required, runs directly from USB or drive. |
| **`FreeLanSync-v1.2.0.apk`** | Android 8.0+ | ~10.8 MB | Android Client with High-Performance Wi-Fi Lock, Camera Roll sync, and Synco notification mirroring. |
| **`SHA256SUMS.txt`** | All Platforms | < 1 KB | Cryptographic SHA-256 hashes for binary authenticity verification. |

---

## 📋 Changelog (v1.1.0 $\rightarrow$ v1.2.0)

### 🚀 Major Performance & Engine Enhancements

- **Zero-Copy Android Stream Upload**: Replaced disk temp-file buffer with direct `ContentResolver` streaming into OkHttp `BufferedSink` via `ContentUriRequestBody`. Eliminates local `cacheDir` disk churn and prevents ENOSPC crashes on large video files.
- **Gigabit Parallel Concurrency**: Upgraded Android upload engine to 4x parallel coroutines bounded by `Semaphore(permits = 4)` with `supervisorScope` and thread-safe atomics.
- **SQLite Database Lock Invariants (TD-019)**: Configured `PRAGMA busy_timeout = 5000;` on all database connections and cached DDL execution across sessions in `_initialized_dbs` to eliminate lock contention under write storms.
- **Collision-Free Upload Staging**: Added random UUID suffixes (`.tmp_{pid}_{uuid}`) to prevent temporary file collisions during concurrent multi-device uploads.

### 🛡️ Security & Resilience Hardening

- **HTTP Status Error Matrix**: Handled HTTP 400 (recompute SHA-256 and retry once), HTTP 413 (permanently skip oversized file with warning), and HTTP 401/403 (immediate batch abort with system & WebSocket push alerts).
- **Quick-Drop Path Traversal Defense (TD-030)**: Sanitized incoming drop filenames via `File(filename).name` and enforced strict canonical directory containment checks in Android `Downloads`.
- **Atomic Staged Downloads (TD-034)**: Drop files stage to temporary files (`.tmp_{fileId}_{ts}`) before atomic rename, cleaning up on network drops to prevent corrupted/truncated files.
- **Centralized Bearer Authentication (TD-031)**: Attached `Authorization: Bearer` token across all Quick-Drop retrieval endpoints.

### 🎨 Visual Branding & Icon Revamp ("The Mobius HyperLink")

- **Unified Identity**: Completely standardized branding from legacy PhotoSync to **FreeLanSync**.
- **Mobius HyperLink Mark**: Implemented a modern horizontal continuous-curvature 3D sync knot representing Mobile Link (Electric Cyan `#38BDF8`) and PC Vault (Hyper Indigo `#6366F1`) woven with a physical air-gap overpass.
- **Universal Parity**: Unified SVG favicon, Web Dashboard header mark, Welcome modal, and Android Adaptive Vector Icons.
- **Android 13+ Themed Icons**: Declared Material You monochrome icon support (`<monochrome>`).

### 📖 User Onboarding & In-App Documentation

- **In-App User Guides**: Added interactive User Guide sheet modal in Desktop Web Dashboard and `UserGuideDialog` in Android Client.
- **New Guide Endpoint**: Implemented `GET /api/v1/guide` route serving structured guide chapters.
- **Visual Onboarding Guide**: Published comprehensive `docs/USER_GUIDE.md` featuring ASCII network topology, step-by-step optical QR pairing, and troubleshooting matrix.

---

## 🔒 Verification (SHA-256 Checksums)

Verify your downloaded binary via PowerShell:

```powershell
Get-FileHash -Algorithm SHA256 <filename>
```

Checksums:

```text
cd3fc3dd6d04e99749c2c6a4b7940ff17e76a2ce4f431e56c367cf077414b16f  FreeLanSync-Desktop-Setup-1.2.0.exe
e79a6baa400518a533cf2a335e32f69e78ce3fea37953f3f8e6cb0f2b7452149  FreeLanSync-Desktop-Portable-1.2.0.exe
1f919c7292c1708f974e0262fc7640b40e5e4df1a963307f40eb9ce8026989d6  FreeLanSync-v1.2.0.apk
```

---

## 🚀 Quick Start Guide

### 1. Windows Desktop Host

1. Run **`FreeLanSync-Desktop-Setup-1.2.0.exe`** (or launch portable).
2. Choose installation folder or accept defaults.
3. Upon launch, FreeLanSync opens the Dashboard on `http://localhost:8080` and minimizes to the system tray.
4. Storage folder defaults to `Pictures/FreeLanSync` and can be adjusted anytime via the **Storage Vault Setup** modal.

### 2. Android Phone Client

1. Install **`FreeLanSync-v1.2.0.apk`** on your Android device (or scan the QR code displayed on the desktop dashboard).
2. Ensure both PC and Phone are on the same Wi-Fi / Local Area Network.
3. Launch app and scan the Desktop QR code or enter the 6-digit pairing PIN.
4. Camera Roll synchronization, Gigabit file transfer, notification mirroring, and clipboard sharing are instantly live.

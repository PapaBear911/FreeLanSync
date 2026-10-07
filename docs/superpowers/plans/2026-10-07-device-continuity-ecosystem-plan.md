# PhotoSync & Synco Device Continuity Ecosystem Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform PhotoSync from a photo backup utility into a full local device continuity ecosystem (Synco + PhotoSync), integrating real-time notification mirroring, media playback controls, phone battery HUD, call alerts, bidirectional Quick-Drop, and shared clipboard, powered by a persistent FastAPI WebSocket bridge and polished using OpenDesign.

**Architecture:** 
- A duplex WebSocket server on the desktop FastAPI backend (`/api/v1/ws/device-bridge`) handling real-time bi-directional streaming between Android and Desktop clients.
- An Android continuity service suite (`PhotoSyncNotificationListener`, `DeviceTelemetryManager`, `DeviceBridgeWebSocket`) streaming notification, media, battery, and clipboard events.
- An enhanced Electron & Web Dashboard featuring a 4-tab command center (Photo Vault, Notification Mirror, Quick-Drop & Clipboard, Device & Media HUD) with native OS notifications.

**Tech Stack:** Python 3.14 (FastAPI, WebSockets, Uvicorn, SQLite), Electron (Node.js), Kotlin (Android Jetpack Compose, OkHttp WebSocket, NotificationListenerService, MediaSessionManager, WorkManager), Tailwind CSS, Lucide Icons, OpenDesign.

**Spec Reference:** `docs/superpowers/specs/2026-10-07-photo-sync-design.md`

## Global Constraints
- Zero cloud dependence: 100% local Wi-Fi / Hotspot peer-to-peer communication.
- Backward compatibility: All existing photo & video backup endpoints (`/api/v1/photos/*`), mDNS discovery (`_photosync._tcp`), and 6-digit PIN pairing remain fully functional and unchanged.
- Battery conservation: WebSocket uses adaptive ping heartbeats (30s idle) and triggers only on events.
- Verification guarantee: All server tests, end-to-end simulation suites, and Android Gradle compilation must pass cleanly.

## Review Focus
1. **Network Disconnection & Reconnection**: When Wi-Fi drops or Android sleeps, WebSocket must reconnect automatically with exponential backoff without crashing.
2. **Notification Spam & Privacy**: Large notification bursts (e.g., group chats) must be throttled and deduplicated; private notifications must respect user settings.
3. **Quick-Drop Integrity**: PC-to-Phone uploads must verify SHA-256 and handle large binary streams safely in chunks.
4. **Clipboard Loop Prevention**: Syncing clipboard from PC -> Phone -> PC must not create an infinite echo loop (tracked via origin timestamp / ID).
5. **UI Responsiveness**: Media and notification events streamed at high frequencies must not freeze the Compose or Web UI.

---

### Task 1: Desktop Server WebSocket Bridge & Quick-Drop Backend
**Files:**
- Create: `server/websocket_manager.py`
- Modify: `server/main.py`
- Modify: `server/storage.py`
- Test: `tests/test_websocket_and_drop.py`

**Steps:**
- [ ] Implement `server/websocket_manager.py` with `ConnectionManager` handling client registration, device mapping, broadcast, and targeted messaging.
- [ ] Add endpoints to `server/main.py`:
  - `@app.websocket("/api/v1/ws/device-bridge")` authenticated with bearer token or query param token.
  - Quick-Drop endpoints: `POST /api/v1/drop/upload`, `GET /api/v1/drop/pending`, `GET /api/v1/drop/download/{file_id}`, `DELETE /api/v1/drop/{file_id}`.
- [ ] Add Quick-Drop storage handler in `server/storage.py` storing transient dropped files under `storage/QuickDrop/`.
- [ ] Write unit tests in `tests/test_websocket_and_drop.py` testing connection handshake, notification broadcast, clipboard exchange, and file dropping.
- [ ] Run `python -m pytest tests/` and verify tests pass.

---

### Task 2: Web Dashboard & OpenDesign UI Polish
**Files:**
- Modify: `server/static/index.html`
- Modify: `desktop-app/main.js`
- Test: Manual verification via browser & Electron tray

**Steps:**
- [ ] Refactor `server/static/index.html` with an executive multi-tab layout:
  - **Tab 1 (Vault)**: Photo & Video Backups, recent gallery preview, storage quota.
  - **Tab 2 (Notifications)**: Live notifications stream with app logos, dismiss action, and call incoming banner.
  - **Tab 3 (Quick-Drop & Clipboard)**: Drag-and-drop file target, pending transfer list, live clipboard mirror with 1-click copy.
  - **Tab 4 (Device HUD)**: Phone battery level with charging animation, Wi-Fi link status, and interactive Now-Playing media controller (Play/Pause, Next, Prev, Track Title, Artist).
- [ ] Connect WebSocket client in `server/static/index.html` to receive and display real-time events.
- [ ] Update `desktop-app/main.js` to hook into WebSocket events and display native Windows OS toast notifications when the window is minimized to the system tray.
- [ ] Ensure dark theme, fluid glassmorphism accents, and responsive layout across desktop and mobile browsers.

---

### Task 3: Android Device Bridge & Telemetry Services
**Files:**
- Create: `android/app/src/main/java/com/photosync/app/network/DeviceBridgeWebSocket.kt`
- Create: `android/app/src/main/java/com/photosync/app/service/DeviceTelemetryManager.kt`
- Create: `android/app/src/main/java/com/photosync/app/service/PhotoSyncNotificationListener.kt`
- Modify: `android/app/src/main/AndroidManifest.xml`
- Modify: `android/app/build.gradle.kts`

**Steps:**
- [ ] Add permissions in `AndroidManifest.xml` for `BIND_NOTIFICATION_LISTENER_SERVICE`, `READ_PHONE_STATE`, `BATTERY_STATS`.
- [ ] Implement `DeviceBridgeWebSocket.kt` using OkHttp `WebSocketListener` to connect to `ws://<server>/api/v1/ws/device-bridge`.
- [ ] Implement `PhotoSyncNotificationListener.kt` inheriting from `NotificationListenerService`:
  - Filters system noise, captures title, text, app name, and dispatches JSON payload via WebSocket.
- [ ] Implement `DeviceTelemetryManager.kt`:
  - Emits battery percentage and charging state (`ACTION_BATTERY_CHANGED`).
  - Emits clipboard updates (`ClipboardManager`) with loop prevention.
  - Emits telephony incoming call state (`TelephonyManager`).
  - Listens for media session playback changes.

---

### Task 4: Android Jetpack Compose UI Upgrades
**Files:**
- Modify: `android/app/src/main/java/com/photosync/app/ui/DashboardScreen.kt`
- Modify: `android/app/src/main/java/com/photosync/app/MainActivity.kt`
- Test: Gradle build verification

**Steps:**
- [ ] Add Continuity controls into `DashboardScreen.kt`:
  - Real-time connection badge for the WebSocket bridge.
  - Notification Mirroring toggle button + intent link to Android Notification Access settings.
  - Quick-Drop Received Files section with button to open or save received files.
  - Clipboard Sync switch.
  - Phone Battery / Bridge diagnostics card.
- [ ] Wire up lifecycle events in `MainActivity.kt` to bind services and maintain WebSocket connection when paired.
- [ ] Compile and verify via `gradle assembleRelease` or `gradle assembleDebug`.

---

### Task 5: End-to-End Simulation & Verification
**Files:**
- Create: `tests/e2e_continuity_simulation.py`
- Modify: `tests/e2e_simulation.py`

**Steps:**
- [ ] Write `tests/e2e_continuity_simulation.py`:
  - Simulates pairing handshake.
  - Establishes WebSocket client as an Android device.
  - Transmits battery telemetry (`BATTERY_STATUS`).
  - Transmits incoming notification (`NOTIFICATION_POSTED`) and incoming phone call alert (`CALL_INCOMING`).
  - Transmits clipboard text and verifies server broadcasts it.
  - Uploads a Quick-Drop file from PC and verifies phone can download and verify SHA-256.
  - Sends a remote media control command (`MEDIA_CONTROL_COMMAND`) from PC to phone.
- [ ] Run `python -m tests.e2e_continuity_simulation` and verify all tests pass.
- [ ] Run full test suite: `python -m pytest tests/`.
- [ ] Package final Android APK via Gradle.

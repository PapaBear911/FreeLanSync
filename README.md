# FreeLanSync

FreeLanSync synchronizes files and device state across devices on a local network. The repository contains a FastAPI server, an Electron desktop host, and an Android client.

> 📖 **New User?** Check out the [Visual User Guide & Walkthrough](docs/USER_GUIDE.md) for step-by-step pairing, backup setup, and troubleshooting.

## Key Features

- ⚡ **Gigabit Camera Roll Backup**: Zero-copy stream upload from Android `MediaStore`, SHA-256 bit-for-bit deduplication, and 4x parallel coroutine uploads.
- 🚀 **Zero-Cloud Quick-Drop**: Drag-and-drop any file on the PC dashboard to stream directly over Wi-Fi into your phone's `Downloads` folder.
- 📋 **Seamless Device Continuity**: Instant bidirectional clipboard sync and Android notification mirroring to desktop dashboard.
- 🔒 **Privacy-First Architecture**: Operates 100% on your local Wi-Fi. PIN pairing is loopback-protected; high-risk operations require authenticated Bearer tokens.

## Quick start

### Server (Windows)

Run `run_server.bat`, or start manually:

```powershell
python -m uvicorn server.main:app --host 0.0.0.0 --port 8080 --reload
```

The server listens on port `8080`. Keep it on a trusted network; it binds to all interfaces.

### Desktop (Windows)

From `desktop-app`:

```powershell
npm install
npm start
```

Build installer and portable packages with `npm run build`. Packaging scripts are defined in [`desktop-app/package.json`](desktop-app/package.json).

### Android

Install/configure Android SDK and Java 17, then from `android`:

```powershell
..\gradle-8.7\bin\gradle.bat assembleDebug
```

Android SDK location is machine-specific; configure it in untracked `android/local.properties`.

## Tests

From the repository root:

```powershell
python -m pytest tests/
```

A root Python dependency manifest is not currently included. Install the project's required Python packages in your environment before starting the server or tests.

## Network binding & threat model

The server binds to `0.0.0.0` (all interfaces) by design: phones on your LAN must
be able to reach it. This is a local-network product, not an internet service —
run it only on networks you trust.

- **Bind address is configurable.** Set `FREELANSYNC_HOST` (or the legacy
  `PHOTOSYNC_HOST`) before launching the server or the desktop app; both honor
  it. To restrict the server to this machine only:

  ```powershell
  $env:FREELANSYNC_HOST = "127.0.0.1"; python -m uvicorn server.main:app --host 127.0.0.1 --port 8080
  ```

  The desktop launcher reads the same variable. With `127.0.0.1`, phones and
  other LAN devices cannot connect — pairing, backup, and continuity all stop.

- **Unauthenticated by design (public LAN routes).** Read-only dashboard and
  LAN features are intentionally open so an unpaired browser/phone can discover
  and pair: `/api/v1/ping`, pairing metadata (the live PIN itself is
  loopback-only, TD-012), device/media/thumbnail reads, Quick-Drop get/delete,
  transfer list/downloads, clipboard/continuity state (TD-008 classification).
  Any LAN client can therefore read backups stored on this machine — treat the
  LAN as the trust boundary.

- **Authenticated routes** (backup upload, hash batch checks) require a
  `Bearer` token issued during PIN pairing; PINs expire and are rate-limited
  (TD-001). Transport is currently plain HTTP/WS; TLS is tracked in
  `docs/superpowers/tech-debt.md` (TD-028 Phase B).

## Architecture

- `server/` — FastAPI routes, authentication, persistence, discovery, transfers, WebSocket state, and static UI.
- `desktop-app/` — Electron tray/window and server process launcher.
- `android/` — Kotlin/Jetpack Compose app, background sync, and network client.
- `tests/` — Python unit and integration simulations.
- `storage/` — runtime-managed file storage; contents are local data, not source.

## Project notes

- Runtime configuration and database files may be created at the repository root or in the OS application-data directory. Set `FREELANSYNC_DATA_DIR` to choose a writable data directory.
- The desktop launcher expects Python/Uvicorn to be available at runtime.
- Core Android source files use canonical naming (`FreeLanSyncApplication.kt`, `FreeLanSyncApiClient.kt`, `FreeLanSyncWorker.kt`, `FreeLanSyncNotificationListener.kt`). The underlying package ID remains `com.photosync.app` for installed app continuity.
- Documentation includes historical PhotoSync naming. Current product branding is FreeLanSync.

## Further reading

- [Photo-sync design](docs/superpowers/specs/2026-10-07-photo-sync-design.md)
- [Photo-sync implementation plan](docs/superpowers/plans/2026-10-07-photo-sync-implementation-plan.md)
- [LAN sync integration plan](docs/superpowers/plans/2026-10-07-freelansync-lansync-integration-plan.md)
- [Device continuity plan](docs/superpowers/plans/2026-10-07-device-continuity-ecosystem-plan.md)
- [Release notes and artifacts](releases/README.md)

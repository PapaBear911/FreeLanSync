# FreeLanSync

FreeLanSync synchronizes files and device state across devices on a local network. The repository contains a FastAPI server, an Electron desktop host, and an Android client.

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

## Architecture

- `server/` — FastAPI routes, authentication, persistence, discovery, transfers, WebSocket state, and static UI.
- `desktop-app/` — Electron tray/window and server process launcher.
- `android/` — Kotlin/Jetpack Compose app, background sync, and network client.
- `tests/` — Python unit and integration simulations.
- `storage/` — runtime-managed file storage; contents are local data, not source.

## Project notes

- Runtime configuration and database files may be created at the repository root or in the OS application-data directory. Set `FREELANSYNC_DATA_DIR` to choose a writable data directory.
- The desktop launcher expects Python/Uvicorn to be available at runtime.
- The Android package namespace still uses the legacy `com.photosync.app` identifier.
- Documentation includes historical PhotoSync naming. Current product branding is FreeLanSync.

## Further reading

- [Photo-sync design](docs/superpowers/specs/2026-10-07-photo-sync-design.md)
- [Photo-sync implementation plan](docs/superpowers/plans/2026-10-07-photo-sync-implementation-plan.md)
- [LAN sync integration plan](docs/superpowers/plans/2026-10-07-freelansync-lansync-integration-plan.md)
- [Device continuity plan](docs/superpowers/plans/2026-10-07-device-continuity-ecosystem-plan.md)
- [Release notes and artifacts](releases/README.md)

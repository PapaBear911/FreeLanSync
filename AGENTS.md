# Agent guide

FreeLanSync is a local-network file-sync and device-continuity project: FastAPI server, Electron desktop shell, Android Kotlin/Compose client.

## Before changing code

- Read the relevant design or plan under [`docs/superpowers`](docs/superpowers); these docs use both FreeLanSync and legacy PhotoSync naming.
- Keep server APIs and Android/desktop behavior aligned. Server routes and lifecycle live in `server/main.py`; real-time client state in `server/websocket_manager.py`.
- Runtime database/config may be created in the repository root during development. Treat them as user data, not source.
- Do not commit generated build output, packaged installers, local machine configuration, or storage contents.

## Checks and run commands

- Server: `run_server.bat` (Windows) or `python -m uvicorn server.main:app --host 0.0.0.0 --port 8080 --reload`.
- Tests: `python -m pytest tests/`; focused tests: `python -m pytest tests/<test_file>.py -q`.
- Desktop: from `desktop-app`, run `npm install`, `npm start`; package with `npm run build` (Windows NSIS + portable).
- Android: from `android`, run `../gradle-8.7/bin/gradle assembleDebug`. `local.properties` is machine-specific. No Gradle wrapper is currently present.
- No root Python dependency manifest is present; do not invent or assume one. Confirm required packages from imports/environment before modifying setup.

## Boundaries

- Keep server implementation in `server/`, tests in `tests/`, Android code/config in `android/`, Electron code in `desktop-app/`.
- `desktop-app/package.json` is authoritative for desktop scripts and packaging resources.
- Avoid editing `build/`, `dist/`, `dist-electron/`, `dist-package/`, and generated release artifacts unless explicitly asked.
- Prefer targeted tests for the changed subsystem, then run the full pytest suite when practical.

# Implementation Plan: Local Wi-Fi Photo Sync & Backup System

## Phase 1: Desktop Server Development & Responsive Dashboard
- [x] Create project structure (`server/`, `server/static/`, `android/`)
- [ ] Implement server core configuration (`server/config.py`)
- [ ] Implement SQLite metadata database manager (`server/database.py`)
- [ ] Implement Zeroconf mDNS advertisement service (`server/discovery.py`)
- [ ] Implement QR code generator and PIN pairing manager (`server/auth.py`)
- [ ] Implement photo backup file manager with date-based folder hierarchy and SHA-256 deduplication (`server/storage.py`)
- [ ] Build FastAPI REST API endpoints (`server/main.py`)
  - Health (`/api/v1/ping`)
  - Pairing (`/api/v1/pairing/*`)
  - Batch hash check (`/api/v1/photos/check-batch`)
  - Chunked/Multipart upload (`/api/v1/photos/upload`)
  - Devices & Gallery (`/api/v1/devices`, `/api/v1/photos/recent`)
- [ ] Create responsive Web UI (`server/static/index.html`, modern responsive layout, mobile & desktop optimized)
- [ ] Create Windows launcher scripts (`run_server.bat`, `install_service.bat`)

## Phase 2: Server Automated Verification & Testing
- [ ] Create comprehensive pytest test suite (`tests/test_server.py`)
- [ ] Test pairing flow with PIN validation
- [ ] Test batch check deduplication logic
- [ ] Test single and multi-photo uploads with SHA-256 verification
- [ ] Test corrupt upload handling and rollback
- [ ] Run pytest and confirm 100% pass

## Phase 3: Android Client Development
- [ ] Set up Gradle build configuration (`android/build.gradle.kts`, `android/app/build.gradle.kts`, `android/settings.gradle.kts`)
- [ ] Configure AndroidManifest with permissions, services, and network security
- [ ] Implement Android Data Layer:
  - Room / SQLite entities (`MediaItemEntity`, `SyncLogEntity`)
  - MediaStore scanner querying images and videos
  - Local hash calculator (SHA-256)
- [ ] Implement Network & Discovery:
  - `NsdDiscoveryManager` for mDNS `_photosync._tcp` resolution
  - Retrofit / OkHttp REST API client
- [ ] Implement Sync Engine:
  - Jetpack WorkManager `PhotoSyncWorker`
  - Wi-Fi unmetered constraints & battery optimizations
  - Foreground notification support with real-time progress
- [ ] Implement Jetpack Compose UI:
  - Pairing screen (QR scanner / 6-digit PIN input / auto-discovery card)
  - Dashboard screen (Server connection status, Wi-Fi badge, sync stats, storage used)
  - Manual "Sync Now" button with animated progress
  - Settings screen (Auto-sync toggle, Charging-only toggle, include videos toggle)

## Phase 4: Android App Compilation & Packaging
- [ ] Run Gradle build via standalone wrapper (`gradle-8.7`)
- [ ] Compile debug and release APKs (`android/app/build/outputs/apk/`)
- [ ] Verify APK existence, size, and manifest alignment

## Phase 5: End-to-End Simulation & Double Verification
- [ ] Run automated E2E simulation script:
  - Start Desktop Server
  - Execute simulated Android sync client uploading batch test images & videos
  - Verify files created in `storage/Backups/<DeviceName>/YYYY/MM/`
  - Verify deduplication on re-sync
- [ ] Verification Loop 1: Verify all unit tests, server endpoints, and generated APK
- [ ] Verification Loop 2: Independent verification of responsive UI, cross-platform behavior, and error handling

---

# Revision 2 — Design Review, Best Practices & UX Roadmap (2026-10-07)

> Review scope: `server/`, `android/`, `desktop-app/`, `tests/`, spec + plan. **No code was changed**; everything below is planned work.

## R0. Plan hygiene (do first)
- [ ] Reconcile the checklist above with reality. Code for Phases 1–4 already exists (server modules, Compose screens, worker, Electron shell in `desktop-app/`) but boxes are unchecked. Re-verify each item by running tests/build, then tick.
- [ ] Add the **Electron desktop shell** (`desktop-app/main.js`: tray, single-instance, spawns `python -m uvicorn`) to the spec — it is currently undocumented ("Windows Service / tray daemon" is the only mention).
- [ ] Spec/code drift to resolve (pick spec or code, then align):
  - Spec says Room DB (`MediaItemEntity`, `SyncLogEntity`); code only has `PreferencesManager` → see R2.
  - Spec says `check-batch` takes `{sha256,size,filename}`; code takes `hashes: List[str]` only.
  - Spec says *streaming* upload; code does `await file.read()` (whole file in RAM).
  - Spec says `/pairing/verify`; fine, but add API versioning/compat policy (R1.7).
- [ ] Fix `.gitignore` hygiene: `photosync.db*`, `photosync_config.json`, `storage/`, `dist/`, `gradle-8.7/` must not be tracked/committed (use Gradle wrapper instead of a vendored distribution).

## R1. Security & correctness hardening (P0 — blocks release)
Findings from the review, in priority order:

| # | Finding | Location | Fix (planned) |
|---|---|---|---|
| 1 | Dashboard/admin endpoints are **unauthenticated** (`/devices`, `/photos/recent`, `/photos/view/*`, **`POST /settings`** can change storage dir) and CORS is `*` with credentials | `server/main.py` | Bind admin API to localhost-only *or* require an admin session (local password / one-time token printed in tray). Phone API stays bearer-token. Restrict CORS to the server's own origin |
| 2 | `view_photo` joins user path without containment check → **path traversal** (`..`) | `view_photo` | Resolve and assert `is_relative_to(backup_dir)`; reject otherwise; add test |
| 3 | PIN has no **rate-limit / lockout** (6 digits = 1M guesses) | `auth.py` | Max 5 attempts → regenerate PIN + 60 s backoff per IP; log attempts |
| 4 | Auth token stored plaintext, `allowBackup=true`, cleartext HTTP | `PreferencesManager`, manifest | Encrypted storage (Keystore + `EncryptedSharedPreferences`/DataStore+Tink), `allowBackup=false`/data-extraction rules, `network_security_config` limiting cleartext to RFC1918 ranges; plan TLS (self-signed cert, fingerprint pinned from QR) as v2 |
| 5 | Upload buffers whole file in memory | `upload_photo` | Stream to `*.part` temp file in chunks while hashing, `fsync`, atomic `os.replace`; enforce max size; verify hash before commit |
| 6 | Worker returns `success` even when uploads fail; failures only `printStackTrace` | `PhotoSyncWorker` | Track per-item result; `Result.retry()` with exponential backoff when any failed; persist error reason for UI |
| 7 | No API compatibility handshake | `/ping` | Return `api_version`, `min_client_version`; client shows "update required" instead of obscure errors |
| 8 | Token cannot be revoked / devices cannot be un-paired | server | `DELETE /devices/{id}` + "Revoke" button in dashboard; client handles 401 by returning to pairing |
| 9 | Dedup is per-device (`check_existing_hashes(device_id…)`) | `database.py` | Decide intentionally: global dedup (saves space) vs per-device. Recommend **global hash index, per-device folder link** |
| 10 | Filename collisions / unsafe names | `storage.py` | Sanitize (strip separators, reserved Windows names `CON`, `NUL`…, trailing dots), collision suffix `_1`, long-path (`\\?\`) handling |

## R2. Android sync engine — best practices (P0/P1)
- [ ] **Introduce Room** as per spec: `MediaItem(mediaStoreId, uri, sha256, size, dateModified, state[PENDING|UPLOADING|SYNCED|FAILED], attempts, lastError)`. Today every run re-scans up to 1000 items and **re-hashes every file** — the biggest battery/time cost.
- [ ] **Incremental scan**: query MediaStore by `DATE_ADDED/_ID > lastSeen` (+ `MediaStore.getVersion/getGeneration` on API 30+); hash only new/changed items; cache by `(id, size, dateModified)`.
- [ ] **Remove the `limit = 1000` cap** — page through MediaStore (e.g. 200/page) so large libraries fully sync.
- [ ] **Two-stage pipeline**: (1) scan+hash worker → (2) upload worker; each resumable. Hash in chunks with `DigestInputStream`, never load files fully.
- [ ] **Resumable uploads** (chunked with offset: `HEAD/PATCH` or tus-style) so a 2 GB video interrupted at 90 % resumes instead of restarting.
- [ ] **Throughput**: parallel uploads (2–3), OkHttp streaming `RequestBody` (no buffering), progress callbacks.
- [ ] **Triggers**: `PeriodicWorkRequest` (15 min min) + `ContentObserver`/`Constraints.addContentUriTrigger` on MediaStore for "new photo taken → sync soon"; `OneTimeWork` for Sync Now; unique work names + `KEEP/REPLACE` policy.
- [ ] **Constraints**: unmetered Wi-Fi, optional charging, battery-not-low, *and* "only on home Wi-Fi (SSID/BSSID allow-list)" or "only when server reachable".
- [ ] **Reachability**: try cached host first → NSD re-resolve → fallback manual IP; handle DHCP IP change automatically. Hold `WifiManager.MulticastLock` during NSD.
- [ ] **Foreground service**: manifest declare `SystemForegroundService` with `tools:node="merge"` + `dataSync` type; handle Android 14 `FOREGROUND_SERVICE_DATA_SYNC` timeout (`onTimeout`) and Android 15 6-hour limit by re-enqueuing.
- [ ] **Permissions**: support Android 14 **partial media access** (`READ_MEDIA_VISUAL_USER_SELECTED`) with UI nudge to grant full access; request `ACCESS_MEDIA_LOCATION` only if preserving GPS EXIF; ask `POST_NOTIFICATIONS` contextually, not at launch; guide user to battery-optimization exemption only if sync is being killed (OEM-specific help links: Xiaomi/Oppo/Samsung).
- [ ] **Folder selection**: choose which albums/buckets to back up (Camera, Screenshots, WhatsApp…) using `BUCKET_DISPLAY_NAME`; default = Camera only.
- [ ] **Preserve metadata**: send original `DATE_TAKEN`, timezone, and set server file mtime accordingly; keep Live Photo/motion-photo pairs together.
- [ ] Migrate to Hilt/Koin DI + a single `SyncRepository` (spec'd but not present); `ViewModel` + `StateFlow` + `collectAsStateWithLifecycle`; no work/IO inside composables.

## R3. Server best practices (P1)
- [ ] Split `main.py` into routers (`pairing`, `photos`, `admin`) + `services`; typed settings via `pydantic-settings`; structured logging with rotation (`%LOCALAPPDATA%\PhotoSync\logs`).
- [ ] **Run data in `%APPDATA%/PhotoSync`**, not the repo root (`photosync.db`, config currently live beside source). DB: WAL (already), `PRAGMA foreign_keys=ON`, schema migrations table, indexes on `sha256`, `device_id`, `taken_at`.
- [ ] Background tasks: thumbnail generation (Pillow, 320/1080 px WebP + video poster via ffmpeg if present), EXIF extraction; thumbnails served with `Cache-Control`/ETag; paginate `/photos` (cursor) — current `recent` is hard-capped at 60 and returns originals.
- [ ] Free-disk guard: refuse uploads below N GB free; surface "PC disk almost full" to phones and tray.
- [ ] Integrity: periodic **scrub** (re-hash vs DB) + "Verify library" button; never delete server copies automatically (retain spec decision).
- [ ] Windows service: replace "bat file" with Electron auto-start (`app.setLoginItemSettings`) **and/or** NSSM/`pywin32` service; add Windows Firewall rule prompt (private-network inbound 8080 + UDP 5353 mDNS) in installer.
- [ ] Packaging: PyInstaller server + `electron-builder` NSIS installer (single `PhotoSync-Setup.exe`); remove dependency on a system `python` (main.js spawns `python`). Code-sign when possible; auto-update via `electron-updater`.
- [ ] Electron hardening: `sandbox:true`, CSP, block navigation outside `localhost`, `setWindowOpenHandler`; replace hand-drawn tray bitmap with real `.ico` assets; `waitForServer` should show a splash/error page, not open a blank window after timeout.
- [ ] Observability: `/api/v1/health` (db ok, disk free, mDNS up), `/api/v1/stats`; optional `/metrics`.

## R4. Windows desktop — "best Windows features" (P1/P2)
- [ ] **System tray**: live status icon (idle / receiving / error), tooltip "Receiving 12/340 from Pixel 8", menu: Open Dashboard · Open Backup Folder (`shell.openPath`) · Pair New Phone · Pause 1 h · Start with Windows · Quit.
- [ ] **Native toast notifications** (Windows `Notification`): "Backup complete — 128 photos from Pixel 8", errors with action buttons.
- [ ] **Open in Explorer** / "Show in folder" on every photo; drag-out of files from the web gallery; Windows **file-association/jump list** ("Open Backups", "Pair phone").
- [ ] **Start with Windows** toggle (minimized to tray) + **single-instance** (already done).
- [ ] **First-run wizard**: (1) choose backup folder (default `Pictures\PhotoSync`, show free space) → (2) firewall check/auto-fix → (3) QR to pair + QR to install APK → (4) success screen "Waiting for phone…" with live detection.
- [ ] **Storage management**: drive/free-space meter, per-device usage, retention info, "move library" with progress (rename-safe), optional second-copy target (external drive / NAS).
- [ ] **Power**: prevent system sleep while a transfer is active (`powerSaveBlocker`); warn if on Wi-Fi power-saving adapter.
- [ ] **Network UX**: show all LAN IPs / pick adapter; detect "Public" network profile and explain how to switch to Private; show "phone and PC must be on same Wi-Fi" diagnostics page.
- [ ] Dark/light follows `nativeTheme`; high-DPI icons; Windows 11 Mica/rounded look (`backgroundMaterial: 'mica'`).
- [ ] Keyboard: `Ctrl+K` command palette/search, `Ctrl+R` rescan, `Esc` closes viewer, arrow keys navigate gallery.

## R5. UX / UI design system (web dashboard + Android, shared language)
**Principles**: one clear primary action per screen · status always visible · plain language ("Backed up", not "SYNCED/200 OK") · never leave the user guessing why sync isn't running · progressive disclosure for settings.

### Shared design tokens (keep web & Android visually identical)
- Color: Material 3 dynamic color on Android 12+ (fallback seed `#6366F1` indigo, matches tray/web); semantic status colors — Success `#22C55E`, Syncing `#6366F1`, Warning `#F59E0B`, Error `#EF4444`, Offline `#64748B`. Verify **WCAG AA** contrast in both themes.
- Type: Inter (web) / Roboto Flex or system (Android); scale 12/14/16/20/24/32; tabular numerals for counters.
- Spacing 4-pt grid; radius 12/16/24; elevation via tonal surfaces (M3), not heavy shadows. Icons: Lucide (web) ↔ Material Symbols (Android) mapped 1:1.
- Motion: 150–250 ms ease-out; progress uses determinate bars with ETA; honor `prefers-reduced-motion` / Android animator scale.
- Accessibility: min 48 dp / 44 px targets, content descriptions, semantic roles, TalkBack/keyboard/focus-ring tested, text scaling to 200 %, never color-only status.

### Android app — recommended layout
Replace the two-screen flow with **M3 bottom navigation (3 tabs)** + onboarding:
1. **Onboarding (first run, 4 steps max)**: Welcome → Grant media access (explain why, handle partial access) → Find your PC (auto-discovery card + "Scan QR" + "Enter PIN/IP" fallback) → Choose albums & Wi-Fi-only → Done. Skip-able, resumable.
2. **Home (Backup)** — hero status card: big ring/progress ("12,480 of 12,600 backed up"), state line ("Up to date · last sync 10 min ago" / "Waiting for Wi-Fi" / "PC not found"), **primary FAB/button: Back up now**, secondary: Pause. Below: connected-PC chip (name, IP, signal), Wi-Fi badge, storage on PC, "needs attention (3)" row that opens failures with Retry.
3. **Activity**: timeline of sync sessions (date, count, size, duration), failed items with reason + per-item retry, share log for support.
4. **Settings**: grouped lists — *Backup* (albums, include videos, Wi-Fi/SSID rules, charging-only, battery-not-low, upload quality = original), *Server* (change/unpair PC, test connection), *Notifications* (summary only vs progress), *Privacy* (app lock), *About* (version, diagnostics, licenses).
- Add: **Quick Settings tile** (Back up now), **home-screen widget** (status + button), **notification actions** (Pause/Resume), **share-sheet target** ("Send to PC" for any photo/video from other apps), **app shortcuts**.
- Empty/error states for every case: no permission, no Wi-Fi, PC asleep/not found, firewall blocked, token revoked, PC disk full, server too old — each with a one-tap fix.
- **Tablet/foldable & landscape**: `WindowSizeClass` → navigation rail ≥ 600 dp, two-pane settings. Edge-to-edge + predictive back; dark theme; localization (string resources, no hard-coded text); app icon = adaptive + monochrome (themed) icon (replace `@android:drawable/ic_menu_camera` placeholder).

### Web dashboard — recommended layout
- **Responsive shell**: left sidebar (≥1024 px) → bottom tab bar (mobile). Sections: **Overview · Library · Devices · Settings**.
- **Overview**: status banner (Server online · IP:port · "Phones on same Wi-Fi can connect"), live transfer card (per device progress via SSE/WebSocket instead of polling), storage donut (used / free / backups), "Pair a phone" card (QR + PIN with countdown and copy button), recent activity.
- **Library (gallery)**: virtualized masonry/grid grouped by day/month with sticky date headers, **thumbnails only** in grid, lightbox with keyboard/swipe, zoom, metadata panel (EXIF, device, hash, path), filters (device, type, date range), search, multi-select → download ZIP / open folder / (never auto-delete). Infinite scroll via cursor pagination; skeleton loaders; lazy `<img loading="lazy" decoding="async">`; video poster + streaming (`Range` requests).
- **Devices**: card per phone (last seen, app version, count, size, trust status), Rename, Revoke, "Pair another".
- **Settings**: backup folder (with validation + free space), retention note, auto-start, network/diagnostics, about/update.
- PWA: manifest + service worker so the dashboard can be "installed" and opened from the phone browser; offline shell with "server unreachable" state.
- Quality: semantic HTML + ARIA, focus management in modals, CSP, no inline `onclick`, Tailwind built at build time (not CDN) so the app works **offline on LAN**; self-host Lucide/Inter.
- **Admin auth**: first-run "set dashboard password / localhost-only" choice (ties to R1.1).

## R6. High-value feature backlog (ranked by ease-of-use gain ÷ effort)
| Rank | Feature | Platform | Effort |
|---|---|---|---|
| 1 | Zero-config pairing: single QR carries host+port+PIN+cert fingerprint → one scan completes pairing | Both | S |
| 2 | Incremental scan + Room cache (battery/time) | Android | M |
| 3 | Live progress (SSE) on desktop + notification progress on phone | Both | S |
| 4 | Album picker + "Camera only" default | Android | S |
| 5 | Troubleshooter (firewall/network profile/IP changed) with auto-fix | Desktop+Android | M |
| 6 | Resumable chunked upload | Both | M |
| 7 | Thumbnail pipeline + paginated gallery | Server+Web | M |
| 8 | Installer + auto-start + auto-update | Desktop | M |
| 9 | Share-sheet "Send to PC", Quick Settings tile, widget | Android | S–M |
| 10 | Free-up-space on phone (delete **only** items verified on PC by hash, with confirm + `MediaStore.createDeleteRequest`) — opt-in | Android | M |
| 11 | Multi-destination (secondary drive/NAS mirror) | Server | M |
| 12 | Restore/browse from phone (stream originals back, "download to phone") | Both | M |
| 13 | Duplicate/similar-photo cleanup view; Live Photo grouping | Server+Web | L |
| 14 | Remote access via Tailscale/WireGuard guidance (not a cloud) | Docs | S |
| 15 | Optional at-rest encryption of library / app lock (biometric) | Both | L |

## R7. Testing & quality gates
- [ ] **Server**: extend `tests/test_server.py` for path traversal, PIN lockout, unauthenticated-admin rejection, oversized/partial/corrupt upload, filename sanitization, concurrent duplicate upload (same hash twice), disk-full, token revocation. Add `ruff` + `mypy` + coverage threshold (≥85 %).
- [ ] **Android**: unit tests (scanner paging, hashing, repository state machine) with JUnit + Turbine; `WorkManager` `TestListenableWorkerBuilder`; Compose UI tests for onboarding/home states; screenshot tests (Paparazzi/Roborazzi) for light/dark/large-font; `ktlint`/`detekt`; Android Lint with `warningsAsErrors`; R8 release build smoke test with ProGuard rules verified.
- [ ] **Instrumented device matrix**: API 26, 30, 33, 34, 35; Pixel + one aggressive-OEM (Xiaomi/Samsung) for background-kill behavior.
- [ ] **E2E**: extend `tests/e2e_simulation.py` — kill network mid-upload and assert resume; 5k-file library timing; re-sync idempotency; server restart during sync.
- [ ] **Accessibility audit**: axe/Lighthouse ≥ 95 on dashboard; TalkBack pass on Android.
- [ ] **CI** (GitHub Actions): server tests, `assembleDebug` via **Gradle wrapper**, lint, artifact upload; Windows runner builds installer.
- [ ] Performance budgets: dashboard LCP < 2 s on LAN; sync of 100 new photos < 60 s on 5 GHz Wi-Fi; hashing throughput logged.

## R8. Revised phase order
1. **Phase 0 – Hygiene**: R0 (plan/spec sync, `.gitignore`, gradle wrapper).
2. **Phase 1 – Safety**: R1 (auth on admin, traversal, PIN lockout, streamed atomic upload, token storage, revoke) + tests (R7 server).
3. **Phase 2 – Engine**: R2 (Room, incremental scan, retries, resumable upload, triggers, FGS compliance).
4. **Phase 3 – UX**: R5 Android onboarding/Home/Activity/Settings; web Overview/Library/Devices; shared tokens.
5. **Phase 4 – Windows polish**: R4 tray/toasts/wizard/installer/auto-start/auto-update.
6. **Phase 5 – Delight**: R6 ranks 7–15 as capacity allows.
7. **Phase 6 – Release gates**: R7 CI, device matrix, a11y, signed APK (release keystore, `minifyEnabled`, versioning) + signed installer; update docs/README (setup, firewall, troubleshooting).

## R9. Definition of done (per phase)
- All new behavior has tests; CI green; no P0 items from R1 open at release.
- Every user-visible state has a designed empty/error/loading variant.
- Spec and this plan updated in the same PR as the change.
- Open decisions to confirm with owner: global vs per-device dedup · TLS in v1 or v2 · "free up phone space" in scope? · Windows service vs Electron-autostart only · minimum supported Android (keep 26?).

---

# Revision 3 — OpenDesign UI/UX Review, Modal Bugfixes & Ponytail Audit (2026-10-07)

## R10. Modal Structure Bugfixes (Resolved)
- **Bug 1: "Clicking Change Folder shows QR Android"**
  - **Root Cause**: In `server/static/index.html`, `<div id="welcomeModal">` was inadvertently embedded inside `<div id="settingsModal">` due to missing closing tags and missing buttons (`saveSettingsBtn`). Opening the settings modal rendered the nested child welcome/QR modal.
  - **Fix**: Separated `settingsModal` and `welcomeModal` into clean top-level modal containers. Restored `Save Settings` and `Cancel` buttons with proper IDs and event bindings.
- **Bug 2: "Clicking Get Android App Now shows nothing happen"**
  - **Root Cause**: Because `welcomeModal` was nested inside `settingsModal` (which had `class="hidden"`), removing the `hidden` class from `welcomeModal` failed to display anything on screen because its parent container was still hidden.
  - **Fix**: Moving `welcomeModal` to root level allows `openWelcomeModal()` to immediately display the direct APK download & QR code modal.

## R11. OpenDesign UI/UX & Design-Engineering Recommendations
Guided by OpenDesign's `emil-design-eng` craft principles and responsive design systems:

### Web Dashboard Polish (Before / After / Why)
| Before | After | Why |
|---|---|---|
| Hand-rolled QR `<rect>` loops (`~30` lines) | Vector `qrcode.image.svg.SvgPathImage` path | Crisp scalable rendering at all display scalings; 10x smaller DOM payload |
| `transition: all 0.2s` on buttons & cards | `transition: transform 150ms ease-out, border-color 150ms ease-out` | Explicit transition properties prevent layout reflows and feel snappier |
| Static image load in gallery without skeleton | Aspect-ratio container with blurred low-res placeholder or tonal skeleton | Prevents cumulative layout shift (CLS) during batch sync |
| No active press feedback on actions | `:active` transform scale (`scale(0.97)`) on buttons | Physical feedback confirms user clicks immediately before network responds |
| Raw error strings in settings modal | Inline toast feedback banner with dismiss and auto-fade | Non-intrusive feedback preserves form focus |

### Android App UI/UX Polish
| Area | Recommendation | Details |
|---|---|---|
| **Pairing Screen** | Unified Auto-Pairing View | Show mDNS discovered PC card with 1-tap "Connect", accompanied by QR camera scanner and 6-digit manual fallback tab. |
| **Sync Visualizer** | Circular Arc Determinate Progress | Replace indeterminate spinner with animated SVG/Canvas arc showing `N/M` photos, transfer speed (MB/s), and estimated time remaining. |
| **Material 3 Theming** | Dynamic Color + Dark Mode | Support Material You color extraction from wallpaper; enforce WCAG AA contrast for status badges (Syncing `#6366F1`, Success `#22C55E`, Warning `#F59E0B`). |
| **Edge-to-Edge** | System Bars Transparency | Use Compose `WindowInsets` padding for status bar and navigation bar to deliver full-bleed immersive visuals. |

## R12. Ponytail Audit & Karpathy Guidelines Verification
Codebase audited repo-wide for over-engineering, speculative abstractions, and hand-rolled standard library features:

- `stdlib:` Hand-rolled loop building SVG rects for QR codes in `_matrix_to_svg`. Replaced with `qrcode.image.svg.SvgPathImage`. `[server/auth.py]`
- `delete:` Dead `HashCheckItem` unused Pydantic model (`-5 lines`). `[server/main.py]`
- `stdlib:` `os.path.basename` in `sanitize_filename`. Replaced with `Path(filename).name`. `[server/storage.py]`
- `shrink:` Modernized imports and typing wrappers (`tuple`, `str | None`). `[server/auth.py, server/storage.py]`
- **Net Impact**: `-32 lines`, cleaner single-pass execution, 100% test pass rate (`4/4` pytest passed).

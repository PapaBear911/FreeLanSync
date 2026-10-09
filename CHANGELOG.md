# Changelog

All notable changes to **FreeLanSync** are documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.2.0] - 2026-10-09

### Added

- **Gigabit Parallel Concurrency**:
  - Android client upload worker (`FreeLanSyncWorker.kt`) upgraded to bounded 4x parallel coroutine dispatch using `Semaphore(permits = 4)` with `supervisorScope`.
  - Thread-safe atomic counters (`AtomicInteger`, `AtomicReference`, `AtomicBoolean`) managing upload progress and status notifications.
- **Zero-Copy Stream Upload**:
  - Direct streaming from Android `ContentResolver` to OkHttp `BufferedSink` via `ContentUriRequestBody`.
  - Completely eliminated disk `cacheDir` temporary staging file allocation, preventing ENOSPC errors on large multi-gigabyte video transfers.
- **In-App User Guides & Onboarding**:
  - Interactive User Guide modal added to Desktop Web Dashboard (`openGuideModal()`).
  - Native `UserGuideDialog` added to Android client with 1-tap triggers on Pairing and Dashboard screens.
  - Server route `GET /api/v1/guide` serving structured guide chapters and network troubleshooting tips.
  - Comprehensive standalone guide published in `docs/USER_GUIDE.md` with ASCII network topology and optical QR pairing flow.
- **"The Mobius HyperLink" Visual Branding**:
  - Brand identity unified with a modern horizontal continuous-curvature 3D sync knot representing Mobile Link (Electric Cyan `#38BDF8`) and PC Vault (Hyper Indigo `#6366F1`) with physical air-gap overpass.
  - Adaptive Android Vector Icons (`ic_launcher_foreground.xml`, `ic_launcher_background.xml`) and Material You themed icon support (`<monochrome>`).
  - High-res vector preview and generator in `android/tools/generate_vector_layers.py`.
- **Database Concurrency & Lock Resilience (TD-019)**:
  - Enabled `PRAGMA busy_timeout = 5000;` on all SQLite connections to eliminate contention locks under concurrent write bursts.
  - Cached schema DDL initialization across sessions in `_initialized_dbs` to prevent redundant `init_db()` runs on every connection.
  - Challenge stress test added in `tests/test_database_concurrency.py` verifying 25 concurrent writer threads without `OperationalError: database is locked`.

### Changed

- **Standardized Project Naming**:
  - Full codebase standardization from legacy `PhotoSync` to canonical **`FreeLanSync`**.
  - Renamed core Android source files: `FreeLanSyncApplication.kt`, `FreeLanSyncApiClient.kt`, `FreeLanSyncNotificationListener.kt`, `FreeLanSyncWorker.kt`.
  - Updated Android manifest application name, service declarations, and UI bindings.
  - Added architectural invariant test in `tests/test_rebranding.py` guarding against residual legacy files.
- **Upload Limit & Error Matrix Hardening**:
  - Configurable `FREELANSYNC_MAX_UPLOAD_MB` (default 4096 MB) with early 413 Content-Length rejection before buffering.
  - Error classification matrix: HTTP 400 triggers single SHA-256 rehash retry, HTTP 413 logs warning and skips item, HTTP 401/403 triggers immediate run abort and user notification.
- **Dashboard UX & Connection Polish (TD-040)**:
  - Eliminated automatic 12s toast spam; toast triggers exclusively from manual refresh.
  - Added persistent reconnecting/unreachable status banner driven by consecutive fetch failures.
  - Implemented exponential WebSocket backoff capped between 1s and 30s.
  - Added visibility-aware polling that pauses when the tab is hidden and refreshes on tab activation.

### Fixed

- **Quick-Drop Path Traversal Vulnerability (TD-030)**:
  - Sanitized incoming drop filenames via `File(filename).name` and strictly asserted containment within the device Downloads folder (`canonicalPath.startsWith(...)`).
- **Atomic Staged Downloads (TD-034)**:
  - Drop downloads now stage to temporary files (`.tmp_{fileId}_{ts}`) before atomic rename; corrupt or interrupted streams are deleted on failure.
- **Drop Authentication Gap (TD-031)**:
  - Centralized `Authorization: Bearer` authentication headers across all Quick-Drop retrieval and download endpoints.
- **Upload Staging Collisions**:
  - Appended random UUID suffixes (`.tmp_{pid}_{uuid}`) to upload staging paths to avoid collision during concurrent multi-client uploads.

---

## [1.1.0] - 2026-10-08

### Added

- **LANSync Gigabit Transfer Engine**: 1 MB chunk streaming, pre-flight disk space validation with 250MB safety margin.
- **Synco Device Continuity Suite**: Real-time notification mirroring, phone call HUD alerts, media playback control, and shared clipboard.
- **Deduplicated Media Vault**: SHA-256 cryptographic hashing to eliminate duplicate uploads and save disk space.
- **Optical QR Pairing**: Instant optical pairing handshake with 6-digit PIN rotation.

---

## [1.0.0] - 2026-10-07

### Added

- Initial release of local-network camera roll synchronization and desktop dashboard.

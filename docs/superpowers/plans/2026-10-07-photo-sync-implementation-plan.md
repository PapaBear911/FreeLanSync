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

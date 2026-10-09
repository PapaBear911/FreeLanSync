# FreeLanSync User Guide & Best Practices

Welcome to **FreeLanSync** — a private, high-speed, local-network file sync and device continuity hub for Windows PC and Android.

---

## 1. System Architecture & Network Topology

FreeLanSync operates **100% locally**. No third-party servers, no accounts, and no internet access required.

```
+-----------------------------------------------------------------+
|                       Local Wi-Fi Network                       |
|                                                                 |
|   +-----------------------+           +---------------------+   |
|   |      Windows PC       |           |   Android Device    |   |
|   |                       |           |                     |   |
|   |  - Desktop App / Tray |  mDNS/UDP |  - Camera Roll Sync |   |
|   |  - FastAPI Backend    |<=========>|  - Quick-Drop Rx    |   |
|   |  - Web Dashboard      |  Gigabit  |  - Clipboard Mirror |   |
|   |  - Storage Vault      |  Stream   |  - Notif Listener   |   |
|   +-----------------------+           +---------------------+   |
+-----------------------------------------------------------------+
```

---

## 2. Prerequisites Checklist

Before you start, ensure:
- [ ] Both your **PC** and your **Android phone** are connected to the **same Wi-Fi network** (or phone mobile hotspot).
- [ ] Windows Firewall allows FreeLanSync on Private Networks.
- [ ] The FreeLanSync Android APK is downloaded on your phone (available directly from the PC dashboard).

---

## 3. Step-by-Step Setup & Pairing

### Step 1: Launch FreeLanSync on PC
- Open the FreeLanSync Desktop App (or run `run_server.bat` in the repository).
- The desktop dashboard will appear, or you can open your browser to:
  `http://localhost:8080`

### Step 2: Install Android App
- On your phone browser, open `http://<PC-IP>:8080` or download the APK directly from the Desktop Dashboard pairing screen.
- Install `FreeLanSync.apk` and grant required permissions:
  - **Photos and Videos** (to scan and back up your media).
  - **Notifications** (optional, for desktop continuity and backup progress).

### Step 3: Fast Optical QR Pairing

```
   Desktop Screen                         Android Screen
+--------------------+                 +--------------------+
|  [ FreeLanSync ]   |                 |  [ FreeLanSync ]   |
|                    |     Optical     |                    |
|    +----------+    |     Scan        |  +--------------+  |
|    |  QR CODE |    |<----------------|  | [Scan QR]    |  |
|    +----------+    |                 |  +--------------+  |
|  PIN: 8 4 9 2 0 1  |                 |  or enter PIN      |
+--------------------+                 +--------------------+
```

1. Open **FreeLanSync** on your phone.
2. Tap **"Scan Desktop QR Code"**.
3. Point your camera at the QR code displayed on your PC screen.
4. **Done!** The device securely exchanges a local authentication token and immediately connects.

> **Manual Pairing Fallback**: If camera access is disabled, tap **"Manual Server Entry"**, enter your PC's IP address (e.g. `192.168.1.100`), port `8080`, and the 6-digit PIN displayed on your PC.

---

## 4. Features & How to Use Them

### 📸 1. Gigabit Camera Roll Backup
- **Automatic Deduplication**: Media files are hashed via SHA-256 before upload. Files already stored on your PC vault are skipped instantly.
- **Parallel Speed**: Uploads up to 4 items simultaneously across gigabit Wi-Fi.
- **Zero Disk Waste**: Direct stream upload without temporary file duplication.
- **Battery Saver**: Configure auto-backup preferences:
  - *Only when connected to Wi-Fi*.
  - *Only while charging*.

### 🚀 2. PC-to-Phone Quick-Drop
1. Drag and drop any file (PDF, APK, ZIP, video) onto the PC Dashboard tab.
2. A popup notification appears on your Android phone.
3. Tap **"Receive"** on the Android Dashboard to save directly to your **Downloads** folder.
4. All downloads are protected against file corruption and path traversal.

### 📋 3. Universal Shared Clipboard
- Copy text on your PC $\rightarrow$ instant notification & clipboard update on your phone.
- Copy text on your phone $\rightarrow$ paste directly on PC.

### 🔔 4. Real-Time Notification Mirroring
- Incoming Android notifications (WhatsApp, Messages, Calls) mirror seamlessly to your desktop dashboard.

---

## 5. Network Security & Privacy Boundary

- **Local Trust Boundary**: FreeLanSync runs exclusively over your local area network (LAN).
- **Authentication**: High-risk actions (media uploads, batch inspection) require an authenticated Bearer token.
- **Loopback Protection**: Pairing PINs and sensitive pairing controls are restricted to the host machine.
- **Host Restriction**: If running on a public Wi-Fi network (coffee shop, airport), restrict binding to loopback only:
  ```powershell
  $env:FREELANSYNC_HOST = "127.0.0.1"
  ```

---

## 6. Troubleshooting & FAQ

| Problem | Root Cause | Solution |
|---|---|---|
| **Android cannot discover PC** | Wi-Fi Client Isolation or Firewall | Ensure your router does not have "AP Isolation" enabled. Check that Windows Firewall allows Python/Node on Port 8080 and UDP 8079. |
| **QR code won't scan** | Low monitor brightness or glare | Increase monitor brightness, or tap "Manual Server Entry" on Android and type the 6-digit PIN. |
| **Backup paused with 401 error** | Pairing expired or revoked | Tap "Unpair Device" in Android settings and re-scan the Desktop QR code. |
| **Oversized file skipped (413)** | Video exceeds max limit | Server default limit is 4096 MB (4 GB). Increase `FREELANSYNC_MAX_UPLOAD_MB` in PC environment variables if needed. |

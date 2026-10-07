# FreeLanSync v1.1.0 Release Package

> **Zero-Cloud Gigabit P2P File Transfer, Backup & Device Continuity Suite**  
> Move GB files across local Wi-Fi / LAN in seconds without Internet or cloud accounts.

---

## 📦 Published Installers & Artifacts

| Binary | Target | Size | Description |
| :--- | :--- | :--- | :--- |
| **`FreeLanSync-Desktop-Setup-1.1.0.exe`** | Windows 10/11 | ~257 MB | Full NSIS Visual Wizard Installer with Start Menu, Desktop shortcut, and uninstaller. |
| **`FreeLanSync-Desktop-Portable-1.1.0.exe`** | Windows 10/11 | ~257 MB | Standalone portable executable. Zero installation required, runs directly from USB or drive. |
| **`FreeLanSync-v1.1.0.apk`** | Android 8.0+ | ~10.8 MB | Android Client with High-Performance Wi-Fi Lock, Camera Roll sync, and Synco notification mirroring. |
| **`SHA256SUMS.txt`** | All Platforms | < 1 KB | Cryptographic SHA-256 hashes for binary authenticity verification. |

---

## 🔒 Verification (SHA-256 Checksums)

Verify your downloaded binary via PowerShell:
```powershell
Get-FileHash -Algorithm SHA256 <filename>
```

Checksums:
```text
cd3fc3dd6d04e99749c2c6a4b7940ff17e76a2ce4f431e56c367cf077414b16f  FreeLanSync-Desktop-Setup-1.1.0.exe
e79a6baa400518a533cf2a335e32f69e78ce3fea37953f3f8e6cb0f2b7452149  FreeLanSync-Desktop-Portable-1.1.0.exe
1f919c7292c1708f974e0262fc7640b40e5e4df1a963307f40eb9ce8026989d6  FreeLanSync-v1.1.0.apk
```

---

## 🚀 Quick Start Guide

### 1. Windows Desktop Host
1. Run **`FreeLanSync-Desktop-Setup-1.1.0.exe`** (or launch portable).
2. Choose installation folder or accept defaults.
3. Upon launch, FreeLanSync opens the Dashboard on `http://localhost:8080` and minimizes to the system tray.
4. Storage folder defaults to `Pictures/FreeLanSync` and can be adjusted anytime via the **Storage Vault Setup** modal.

### 2. Android Phone Client
1. Install **`FreeLanSync-v1.1.0.apk`** on your Android device (or scan the QR code displayed on the desktop dashboard).
2. Ensure both PC and Phone are on the same Wi-Fi / Local Area Network.
3. Launch app and scan the Desktop QR code or enter the 6-digit pairing PIN.
4. Camera Roll synchronization, Gigabit file transfer, notification mirroring, and clipboard sharing are instantly live.

---

## ✨ Features Included

- **LANSync Gigabit Transfer Engine**: 1 MB chunk streaming, pre-flight disk space validation with 250MB safety margin, cancellation rollback, and recursive folder preservation.
- **Synco Device Continuity**: Real-time notification mirroring, incoming phone call HUD alerts, media playback control, and bidirectional clipboard synchronization.
- **Deduplicated Media Vault**: SHA-256 cryptographic hashing to eliminate duplicate uploads and save disk space.
- **Zero-Cloud Privacy**: 100% peer-to-peer over local network. No external servers, logins, or subscription fees.

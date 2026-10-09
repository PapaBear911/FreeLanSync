package com.photosync.app

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.core.content.ContextCompat
import androidx.lifecycle.lifecycleScope
import androidx.work.WorkInfo
import com.journeyapps.barcodescanner.ScanContract
import com.journeyapps.barcodescanner.ScanOptions
import com.photosync.app.data.PreferencesManager
import com.photosync.app.data.ServerConfig
import com.photosync.app.network.LanDiscoveryManager
import com.photosync.app.network.PairingPayload
import com.photosync.app.network.PairingPayloadParser
import com.photosync.app.network.PhotoSyncApiClient
import com.photosync.app.sync.PhotoSyncWorker
import com.photosync.app.sync.SyncManager
import com.photosync.app.ui.DashboardScreen
import com.photosync.app.ui.PairingScreen
import kotlinx.coroutines.launch

class MainActivity : ComponentActivity() {

    private lateinit var prefs: PreferencesManager
    private lateinit var syncManager: SyncManager
    private lateinit var discoveryManager: LanDiscoveryManager

    /** Set from freelansync:// deep links (onCreate/onNewIntent), consumed by the pairing UI. */
    private var pendingDeepLink by mutableStateOf<String?>(null)
    private var telemetryManager: com.photosync.app.service.DeviceTelemetryManager? = null
    private val apiClient = PhotoSyncApiClient()

    private val permissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions()
    ) { permissions ->
        val allGranted = permissions.values.all { it }
        if (!allGranted) {
            Toast.makeText(this, "Storage and notification permissions are required to back up photos & videos", Toast.LENGTH_LONG).show()
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        prefs = PreferencesManager(this)
        syncManager = SyncManager(this)
        discoveryManager = LanDiscoveryManager(this)

        val initialConfig = prefs.getServerConfig()
        if (initialConfig.isPaired) {
            telemetryManager = com.photosync.app.service.DeviceTelemetryManager(this).also { it.startTelemetry() }
            com.photosync.app.network.DeviceBridgeWebSocket.getInstance().connect(initialConfig.host, initialConfig.port, initialConfig.authToken)
        }

        requestRequiredPermissions()
        handleDeepLink(intent)

        setContent {
            com.photosync.app.ui.FreeLanSyncTheme {
                Surface(
                    modifier = Modifier.fillMaxSize(),
                    color = MaterialTheme.colorScheme.background
                ) {
                    var serverConfig by remember { mutableStateOf(prefs.getServerConfig()) }
                    var lastSyncTime by remember { mutableLongStateOf(prefs.getLastSyncTime()) }
                    var isPairingLoading by remember { mutableStateOf(false) }
                    var pairingError by remember { mutableStateOf<String?>(null) }
                    var isSyncing by remember { mutableStateOf(false) }
                    var progressCurrent by remember { mutableIntStateOf(0) }
                    var progressTotal by remember { mutableIntStateOf(0) }
                    var autoSync by remember { mutableStateOf(prefs.isAutoSyncEnabled) }
                    var chargingOnly by remember { mutableStateOf(prefs.isChargingOnly) }

                    var scannedPayload by remember { mutableStateOf<PairingPayload?>(null) }
                    val discoveredServers by discoveryManager.discoveredServers.collectAsState()

                    // Single pairing path reused by the manual button, QR scan results,
                    // pasted links, and freelansync:// deep links.
                    val performPairing: (String, Int, String) -> Unit = { host, port, pin ->
                        isPairingLoading = true
                        pairingError = null
                        lifecycleScope.launch {
                            val result = apiClient.pairWithServer(
                                host = host,
                                port = port,
                                pin = pin,
                                deviceName = serverConfig.deviceName,
                                deviceId = serverConfig.deviceId
                            )
                            isPairingLoading = false
                            result.onSuccess { token ->
                                prefs.savePairing(host, port, token, serverConfig.deviceName)
                                serverConfig = prefs.getServerConfig()
                                telemetryManager = com.photosync.app.service.DeviceTelemetryManager(this@MainActivity).also { it.startTelemetry() }
                                com.photosync.app.network.DeviceBridgeWebSocket.getInstance().connect(host, port, token)
                                syncManager.schedulePeriodicSync()
                                discoveryManager.stopDiscovery()
                                Toast.makeText(this@MainActivity, "Paired successfully!", Toast.LENGTH_SHORT).show()
                            }.onFailure { err ->
                                pairingError = err.message ?: "Pairing failed"
                            }
                        }
                    }

                    val handlePairingPayload: (String) -> Unit = { raw ->
                        val payload = PairingPayloadParser.parse(raw)
                        when {
                            payload == null ->
                                pairingError = "That code isn't a FreeLanSync pairing QR or link."
                            payload.canAutoConnect ->
                                performPairing(payload.host, payload.port, payload.pin!!)
                            else -> {
                                scannedPayload = payload
                                pairingError = if (payload.pin == null) {
                                    "Code read — enter the 6-digit PIN shown on the desktop to connect."
                                } else {
                                    "Code read — check the details below and tap Connect."
                                }
                            }
                        }
                    }

                    val qrScanOptions = remember {
                        ScanOptions()
                            .setDesiredBarcodeFormats(ScanOptions.QR_CODE)
                            .setPrompt("Point at the pairing QR shown on the desktop dashboard")
                            .setBeepEnabled(true)
                            .setOrientationLocked(false)
                    }

                    val scanLauncher = rememberLauncherForActivityResult(ScanContract()) { result ->
                        // null contents = user cancelled the scanner (camera access itself
                        // is pre-checked below, so denial never reaches this branch).
                        result.contents?.let(handlePairingPayload)
                    }

                    val cameraPermissionLauncher = rememberLauncherForActivityResult(
                        ActivityResultContracts.RequestPermission()
                    ) { granted ->
                        if (granted) {
                            scanLauncher.launch(qrScanOptions)
                        } else {
                            pairingError = "Camera permission denied — paste the pairing link below or enter the host, port and PIN manually."
                        }
                    }

                    val startQrScan: () -> Unit = {
                        val cameraGranted = ContextCompat.checkSelfPermission(
                            this@MainActivity, Manifest.permission.CAMERA
                        ) == PackageManager.PERMISSION_GRANTED
                        if (cameraGranted) scanLauncher.launch(qrScanOptions)
                        else cameraPermissionLauncher.launch(Manifest.permission.CAMERA)
                    }

                    // Consumes freelansync:// deep links tapped on this device.
                    LaunchedEffect(pendingDeepLink) {
                        val raw = pendingDeepLink ?: return@LaunchedEffect
                        pendingDeepLink = null
                        handlePairingPayload(raw)
                    }

                    if (!serverConfig.isPaired) {
                        LaunchedEffect(Unit) {
                            discoveryManager.startDiscovery()
                        }
                        PairingScreen(
                            discoveredServers = discoveredServers,
                            isLoading = isPairingLoading,
                            errorMessage = pairingError,
                            scannedPayload = scannedPayload,
                            onScanQrClicked = startQrScan,
                            onPayloadSubmitted = { raw -> handlePairingPayload(raw) },
                            onPairSubmitted = performPairing
                        )
                    } else {
                        DisposableEffect(Unit) {
                            onDispose { discoveryManager.stopDiscovery() }
                        }
                        DashboardScreen(
                            serverConfig = serverConfig,
                            lastSyncTimestamp = lastSyncTime,
                            isSyncing = isSyncing,
                            syncProgressCurrent = progressCurrent,
                            syncProgressTotal = progressTotal,
                            autoSyncEnabled = autoSync,
                            chargingOnlyEnabled = chargingOnly,
                            onAutoSyncToggled = { enabled ->
                                autoSync = enabled
                                prefs.isAutoSyncEnabled = enabled
                                syncManager.schedulePeriodicSync()
                            },
                            onChargingOnlyToggled = { charging ->
                                chargingOnly = charging
                                prefs.isChargingOnly = charging
                                syncManager.schedulePeriodicSync()
                            },
                            onSyncNowClicked = {
                                isSyncing = true
                                progressCurrent = 0
                                progressTotal = 0
                                syncManager.triggerImmediateSync().observe(this) { workInfo ->
                                    if (workInfo != null) {
                                        val cur = workInfo.progress.getInt(PhotoSyncWorker.KEY_PROGRESS_CURRENT, 0)
                                        val tot = workInfo.progress.getInt(PhotoSyncWorker.KEY_PROGRESS_TOTAL, 0)
                                        progressCurrent = cur
                                        progressTotal = tot

                                        if (workInfo.state == WorkInfo.State.SUCCEEDED) {
                                            isSyncing = false
                                            lastSyncTime = prefs.getLastSyncTime()
                                            Toast.makeText(this, "Backup finished successfully!", Toast.LENGTH_SHORT).show()
                                        } else if (workInfo.state == WorkInfo.State.FAILED) {
                                            isSyncing = false
                                            val reason = workInfo.outputData.getString(PhotoSyncWorker.KEY_FAILURE_REASON)
                                            Toast.makeText(this, reason ?: "Backup failed. Ensure server is online.", Toast.LENGTH_SHORT).show()
                                        }
                                    }
                                }
                            },
                            onUnpairClicked = {
                                prefs.clearPairing()
                                syncManager.cancelPeriodicSync()
                                telemetryManager?.stopTelemetry()
                                telemetryManager = null
                                com.photosync.app.network.DeviceBridgeWebSocket.getInstance().disconnect()
                                serverConfig = prefs.getServerConfig()
                                discoveryManager.startDiscovery()
                            }
                        )
                    }
                }
            }
        }
    }

    private fun requestRequiredPermissions() {
        val permissions = mutableListOf<String>()

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            permissions.add(Manifest.permission.READ_MEDIA_IMAGES)
            permissions.add(Manifest.permission.READ_MEDIA_VIDEO)
            permissions.add(Manifest.permission.POST_NOTIFICATIONS)
        } else {
            permissions.add(Manifest.permission.READ_EXTERNAL_STORAGE)
        }

        val needed = permissions.filter {
            ContextCompat.checkSelfPermission(this, it) != PackageManager.PERMISSION_GRANTED
        }

        if (needed.isNotEmpty()) {
            permissionLauncher.launch(needed.toTypedArray())
        }
    }

    /** Delivers freelansync:// links to an already-running instance (singleTask). */
    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        handleDeepLink(intent)
    }

    /** Extracts freelansync:// (or legacy photosync://) pairing URIs from a launch intent. */
    private fun handleDeepLink(intent: Intent?) {
        val data = intent?.data ?: return
        when (data.scheme?.lowercase()) {
            PairingPayloadParser.SCHEME, PairingPayloadParser.LEGACY_SCHEME ->
                pendingDeepLink = data.toString()
        }
    }

    override fun onDestroy() {
        super.onDestroy()
        telemetryManager?.stopTelemetry()
        com.photosync.app.network.DeviceBridgeWebSocket.getInstance().disconnect()
        discoveryManager.stopDiscovery()
    }
}

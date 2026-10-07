package com.photosync.app

import android.Manifest
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.widget.Toast
import androidx.activity.ComponentActivity
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
import com.photosync.app.data.PreferencesManager
import com.photosync.app.data.ServerConfig
import com.photosync.app.network.NsdDiscoveryManager
import com.photosync.app.network.PhotoSyncApiClient
import com.photosync.app.sync.PhotoSyncWorker
import com.photosync.app.sync.SyncManager
import com.photosync.app.ui.DashboardScreen
import com.photosync.app.ui.PairingScreen
import kotlinx.coroutines.launch

class MainActivity : ComponentActivity() {

    private lateinit var prefs: PreferencesManager
    private lateinit var syncManager: SyncManager
    private lateinit var nsdManager: NsdDiscoveryManager
    private val apiClient = PhotoSyncApiClient()

    private val permissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions()
    ) { permissions ->
        val allGranted = permissions.values.all { it }
        if (!allGranted) {
            Toast.makeText(this, "Storage and notification permissions are required to back up photos", Toast.LENGTH_LONG).show()
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        prefs = PreferencesManager(this)
        syncManager = SyncManager(this)
        nsdManager = NsdDiscoveryManager(this)

        requestRequiredPermissions()

        setContent {
            MaterialTheme {
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

                    val discoveredServers by nsdManager.discoveredServers.collectAsState()

                    if (!serverConfig.isPaired) {
                        LaunchedEffect(Unit) {
                            nsdManager.startDiscovery()
                        }
                        PairingScreen(
                            discoveredServers = discoveredServers,
                            isLoading = isPairingLoading,
                            errorMessage = pairingError,
                            onPairSubmitted = { host, port, pin ->
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
                                        syncManager.schedulePeriodicSync()
                                        nsdManager.stopDiscovery()
                                        Toast.makeText(this@MainActivity, "Paired successfully!", Toast.LENGTH_SHORT).show()
                                    }.onFailure { err ->
                                        pairingError = err.message ?: "Pairing failed"
                                    }
                                }
                            }
                        )
                    } else {
                        DisposableEffect(Unit) {
                            onDispose { nsdManager.stopDiscovery() }
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
                                            Toast.makeText(this, "Backup failed. Ensure server is online.", Toast.LENGTH_SHORT).show()
                                        }
                                    }
                                }
                            },
                            onUnpairClicked = {
                                prefs.clearPairing()
                                syncManager.cancelPeriodicSync()
                                serverConfig = prefs.getServerConfig()
                                nsdManager.startDiscovery()
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

    override fun onDestroy() {
        super.onDestroy()
        nsdManager.stopDiscovery()
    }
}

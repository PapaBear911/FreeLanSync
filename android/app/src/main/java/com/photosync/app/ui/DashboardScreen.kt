package com.photosync.app.ui

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CloudDone
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.Sync
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.photosync.app.data.ServerConfig
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DashboardScreen(
    serverConfig: ServerConfig,
    lastSyncTimestamp: Long,
    isSyncing: Boolean,
    syncProgressCurrent: Int,
    syncProgressTotal: Int,
    onSyncNowClicked: () -> Unit,
    onUnpairClicked: () -> Unit,
    autoSyncEnabled: Boolean,
    onAutoSyncToggled: (Boolean) -> Unit,
    chargingOnlyEnabled: Boolean,
    onChargingOnlyToggled: (Boolean) -> Unit
) {
    val dateFormat = remember { SimpleDateFormat("yyyy-MM-dd HH:mm", Locale.getDefault()) }
    val lastSyncStr = if (lastSyncTimestamp > 0) dateFormat.format(Date(lastSyncTimestamp)) else "Never"

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("PhotoSync", fontWeight = FontWeight.Bold) },
                actions = {
                    TextButton(onClick = onUnpairClicked) {
                        Text("Unpair", color = MaterialTheme.colorScheme.error)
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.surfaceVariant
                )
            )
        }
    ) { padding ->
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(horizontal = 20.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            item {
                Spacer(modifier = Modifier.height(8.dp))
                // Status Card
                Card(
                    modifier = Modifier.fillMaxWidth(),
                    colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.primaryContainer),
                    shape = RoundedCornerShape(16.dp)
                ) {
                    Column(
                        modifier = Modifier.padding(20.dp),
                        verticalArrangement = Arrangement.spacedBy(10.dp)
                    ) {
                        Row(
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.spacedBy(8.dp)
                        ) {
                            Icon(Icons.Default.CloudDone, contentDescription = null, tint = MaterialTheme.colorScheme.primary)
                            Text(
                                text = "Connected to Desktop Server",
                                style = MaterialTheme.typography.titleMedium,
                                fontWeight = FontWeight.Bold
                            )
                        }

                        Text(
                            text = "Server: http://${serverConfig.host}:${serverConfig.port}",
                            style = MaterialTheme.typography.bodySmall
                        )
                        Text(
                            text = "Device Name: ${serverConfig.deviceName}",
                            style = MaterialTheme.typography.bodySmall
                        )
                        Text(
                            text = "Last Successful Sync: $lastSyncStr",
                            style = MaterialTheme.typography.bodySmall,
                            fontWeight = FontWeight.SemiBold
                        )
                    }
                }
            }

            // Sync Action Card
            item {
                Card(
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(16.dp),
                    colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface)
                ) {
                    Column(
                        modifier = Modifier.padding(20.dp),
                        verticalArrangement = Arrangement.spacedBy(16.dp)
                    ) {
                        Text(
                            text = "Manual Backup",
                            style = MaterialTheme.typography.titleSmall,
                            fontWeight = FontWeight.Bold
                        )

                        if (isSyncing) {
                            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                                LinearProgressIndicator(
                                    progress = if (syncProgressTotal > 0) syncProgressCurrent.toFloat() / syncProgressTotal else 0f,
                                    modifier = Modifier.fillMaxWidth()
                                )
                                Text(
                                    text = if (syncProgressTotal > 0) "Uploading $syncProgressCurrent / $syncProgressTotal photos..." else "Analyzing local camera roll...",
                                    style = MaterialTheme.typography.bodySmall,
                                    color = MaterialTheme.colorScheme.primary
                                )
                            }
                        }

                        Button(
                            onClick = onSyncNowClicked,
                            enabled = !isSyncing,
                            modifier = Modifier
                                .fillMaxWidth()
                                .height(48.dp)
                        ) {
                            Icon(Icons.Default.Sync, contentDescription = null, modifier = Modifier.size(18.dp))
                            Spacer(modifier = Modifier.width(8.dp))
                            Text(if (isSyncing) "Syncing..." else "Sync Now")
                        }
                    }
                }
            }

            // Settings & Preferences
            item {
                Card(
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(16.dp),
                    colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface)
                ) {
                    Column(
                        modifier = Modifier.padding(20.dp),
                        verticalArrangement = Arrangement.spacedBy(16.dp)
                    ) {
                        Text(
                            text = "Automatic Sync Settings",
                            style = MaterialTheme.typography.titleSmall,
                            fontWeight = FontWeight.Bold
                        )

                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.SpaceBetween
                        ) {
                            Column(modifier = Modifier.weight(1f)) {
                                Text("Auto-Sync on Home Wi-Fi", fontWeight = FontWeight.SemiBold, style = MaterialTheme.typography.bodyMedium)
                                Text("Sync periodically in the background when connected to Wi-Fi", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                            }
                            Switch(
                                checked = autoSyncEnabled,
                                onCheckedChange = onAutoSyncToggled
                            )
                        }

                        Divider()

                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.SpaceBetween
                        ) {
                            Column(modifier = Modifier.weight(1f)) {
                                Text("Only When Charging", fontWeight = FontWeight.SemiBold, style = MaterialTheme.typography.bodyMedium)
                                Text("Save battery by postponing automatic sync until phone is plugged in", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                            }
                            Switch(
                                checked = chargingOnlyEnabled,
                                onCheckedChange = onChargingOnlyToggled
                            )
                        }
                    }
                }
            }
        }
    }
}

package com.photosync.app.ui

import android.content.Context
import android.content.Intent
import android.os.Environment
import android.provider.Settings
import android.widget.Toast
import androidx.compose.animation.*
import androidx.compose.animation.core.*
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.scale
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.photosync.app.data.ServerConfig
import com.photosync.app.network.DeviceBridgeWebSocket
import com.photosync.app.network.PhotoSyncApiClient
import com.photosync.app.service.PhotoSyncNotificationListener
import kotlinx.coroutines.launch
import org.json.JSONObject
import java.io.File
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
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val apiClient = remember { PhotoSyncApiClient() }
    val dateFormat = remember { SimpleDateFormat("yyyy-MM-dd HH:mm", Locale.getDefault()) }
    val lastSyncStr = if (lastSyncTimestamp > 0) dateFormat.format(Date(lastSyncTimestamp)) else "Never"

    var pendingDrops by remember { mutableStateOf<List<JSONObject>>(emptyList()) }
    var isCheckingDrops by remember { mutableStateOf(false) }

    // Infinite breathing pulse for live connection beacon
    val infiniteTransition = rememberInfiniteTransition(label = "pulse")
    val beaconAlpha by infiniteTransition.animateFloat(
        initialValue = 0.35f,
        targetValue = 1f,
        animationSpec = infiniteRepeatable(
            animation = tween(1200, easing = EaseInOutSine),
            repeatMode = RepeatMode.Reverse
        ),
        label = "beaconAlpha"
    )
    val beaconScale by infiniteTransition.animateFloat(
        initialValue = 0.85f,
        targetValue = 1.15f,
        animationSpec = infiniteRepeatable(
            animation = tween(1200, easing = EaseInOutSine),
            repeatMode = RepeatMode.Reverse
        ),
        label = "beaconScale"
    )

    Scaffold(
        topBar = {
            TopAppBar(
                title = { 
                    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                        // Glowing pulse status orb
                        Box(contentAlignment = Alignment.Center) {
                            Box(
                                modifier = Modifier
                                    .size(14.dp)
                                    .scale(beaconScale)
                                    .clip(CircleShape)
                                    .background(Color(0xFF38BDF8).copy(alpha = beaconAlpha * 0.4f))
                            )
                            Box(
                                modifier = Modifier
                                    .size(8.dp)
                                    .clip(CircleShape)
                                    .background(Color(0xFF30D158))
                            )
                        }
                        Column {
                            Text("FreeLanSync", fontWeight = FontWeight.Bold, fontSize = 18.sp, color = Color.White)
                            Text("Gigabit Mesh & Continuity Active", style = MaterialTheme.typography.bodySmall, color = Color(0xFF38BDF8))
                        }
                    }
                },
                actions = {
                    TextButton(onClick = onUnpairClicked) {
                        Text("Unpair", color = MaterialTheme.colorScheme.error, fontWeight = FontWeight.SemiBold)
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.surface
                )
            )
        }
    ) { padding ->
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(horizontal = 18.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            item {
                Spacer(modifier = Modifier.height(6.dp))
                
                // Status Card with Gigabit Badges
                Card(
                    modifier = Modifier
                        .fillMaxWidth()
                        .border(1.dp, Color.White.copy(alpha = 0.08f), RoundedCornerShape(20.dp)),
                    colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant),
                    shape = RoundedCornerShape(20.dp)
                ) {
                    Column(
                        modifier = Modifier.padding(18.dp),
                        verticalArrangement = Arrangement.spacedBy(12.dp)
                    ) {
                        Row(
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.SpaceBetween,
                            modifier = Modifier.fillMaxWidth()
                        ) {
                            Row(
                                verticalAlignment = Alignment.CenterVertically,
                                horizontalArrangement = Arrangement.spacedBy(8.dp)
                            ) {
                                Icon(Icons.Default.CloudDone, contentDescription = null, tint = Color(0xFF38BDF8), modifier = Modifier.size(20.dp))
                                Text(
                                    text = "Connected to FreeLanSync PC",
                                    style = MaterialTheme.typography.titleMedium,
                                    fontWeight = FontWeight.Bold,
                                    color = Color.White
                                )
                            }
                            
                            // High-perf pill tag
                            Surface(
                                shape = RoundedCornerShape(12.dp),
                                color = Color(0xFF30D158).copy(alpha = 0.15f),
                                border = androidx.compose.foundation.BorderStroke(1.dp, Color(0xFF30D158).copy(alpha = 0.3f))
                            ) {
                                Text(
                                    text = "1000 Mbps",
                                    color = Color(0xFF30D158),
                                    fontSize = 11.sp,
                                    fontWeight = FontWeight.Bold,
                                    modifier = Modifier.padding(horizontal = 8.dp, vertical = 2.dp)
                                )
                            }
                        }

                        Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                            Text(
                                text = "Host: http://${serverConfig.host}:${serverConfig.port}",
                                style = MaterialTheme.typography.bodySmall,
                                color = Color(0xFFBAE6FD)
                            )
                            Text(
                                text = "Device: ${serverConfig.deviceName}",
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant
                            )
                            Text(
                                text = "Protocol: Gigabit LANSync (WakeLock + High-Perf Wi-Fi)",
                                style = MaterialTheme.typography.bodySmall,
                                color = Color(0xFF818CF8),
                                fontWeight = FontWeight.Medium
                            )
                            Text(
                                text = "Last Backup: $lastSyncStr",
                                style = MaterialTheme.typography.bodySmall,
                                fontWeight = FontWeight.SemiBold,
                                color = Color(0xFFE2E8F0)
                            )
                        }

                        // Feature Badges Row
                        Row(
                            horizontalArrangement = Arrangement.spacedBy(8.dp),
                            modifier = Modifier.fillMaxWidth()
                        ) {
                            BadgeChip(icon = Icons.Default.Bolt, label = "Zero Internet")
                            BadgeChip(icon = Icons.Default.Lock, label = "Wi-Fi Lock")
                            BadgeChip(icon = Icons.Default.Security, label = "Local E2E")
                        }
                    }
                }
            }

            // Synco Continuity Services Card
            item {
                Card(
                    modifier = Modifier
                        .fillMaxWidth()
                        .border(1.dp, Color.White.copy(alpha = 0.08f), RoundedCornerShape(20.dp)),
                    shape = RoundedCornerShape(20.dp),
                    colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface)
                ) {
                    Column(
                        modifier = Modifier.padding(18.dp),
                        verticalArrangement = Arrangement.spacedBy(12.dp)
                    ) {
                        Row(
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.spacedBy(8.dp)
                        ) {
                            Icon(Icons.Default.NotificationsActive, contentDescription = null, tint = Color(0xFFA855F7), modifier = Modifier.size(20.dp))
                            Text(
                                text = "Notification & Alert Mirroring",
                                style = MaterialTheme.typography.titleSmall,
                                fontWeight = FontWeight.Bold,
                                color = Color.White
                            )
                        }

                        Text(
                            text = "Streams WhatsApp, SMS, and incoming call alerts directly to your desktop browser with zero cloud intermediaries.",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )

                        FilledTonalButton(
                            onClick = {
                                val intent = Intent(Settings.ACTION_NOTIFICATION_LISTENER_SETTINGS)
                                context.startActivity(intent)
                            },
                            shape = RoundedCornerShape(12.dp),
                            modifier = Modifier.fillMaxWidth()
                        ) {
                            Icon(Icons.Default.Settings, contentDescription = null, modifier = Modifier.size(16.dp))
                            Spacer(modifier = Modifier.width(8.dp))
                            Text("Grant / Verify Notification Access", fontWeight = FontWeight.Medium)
                        }
                    }
                }
            }

            // Universal Quick-Drop (PC -> Phone) Card
            item {
                Card(
                    modifier = Modifier
                        .fillMaxWidth()
                        .border(1.dp, Color.White.copy(alpha = 0.08f), RoundedCornerShape(20.dp)),
                    shape = RoundedCornerShape(20.dp),
                    colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface)
                ) {
                    Column(
                        modifier = Modifier.padding(18.dp),
                        verticalArrangement = Arrangement.spacedBy(12.dp)
                    ) {
                        Row(
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.SpaceBetween,
                            modifier = Modifier.fillMaxWidth()
                        ) {
                            Row(
                                verticalAlignment = Alignment.CenterVertically,
                                horizontalArrangement = Arrangement.spacedBy(8.dp)
                            ) {
                                Icon(Icons.Default.Download, contentDescription = null, tint = Color(0xFF38BDF8), modifier = Modifier.size(20.dp))
                                Text(
                                    text = "Quick-Drop from PC",
                                    style = MaterialTheme.typography.titleSmall,
                                    fontWeight = FontWeight.Bold,
                                    color = Color.White
                                )
                            }

                            IconButton(
                                onClick = {
                                    isCheckingDrops = true
                                    scope.launch {
                                        val res = apiClient.getPendingDrops(serverConfig.host, serverConfig.port)
                                        isCheckingDrops = false
                                        res.onSuccess { drops ->
                                            pendingDrops = drops
                                            if (drops.isEmpty()) {
                                                Toast.makeText(context, "No pending drops on PC", Toast.LENGTH_SHORT).show()
                                            }
                                        }.onFailure {
                                            Toast.makeText(context, "Error checking drops: ${it.message}", Toast.LENGTH_SHORT).show()
                                        }
                                    }
                                }
                            ) {
                                Icon(Icons.Default.Refresh, contentDescription = "Refresh Drops", tint = Color(0xFF94A3B8))
                            }
                        }

                        if (pendingDrops.isEmpty()) {
                            Text(
                                text = "Drag and drop any files or nested folders on your PC dashboard to stream them instantly to this phone.",
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant
                            )
                        } else {
                            // Animated transition for list items
                            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                                pendingDrops.forEach { drop ->
                                    val fileId = drop.optString("file_id")
                                    val filename = drop.optString("filename")
                                    val size = drop.optLong("size", 0)

                                    AnimatedVisibility(
                                        visible = true,
                                        enter = fadeIn() + expandVertically(),
                                        exit = fadeOut() + shrinkVertically()
                                    ) {
                                        Card(
                                            modifier = Modifier
                                                .fillMaxWidth()
                                                .border(1.dp, Color.White.copy(alpha = 0.05f), RoundedCornerShape(14.dp)),
                                            shape = RoundedCornerShape(14.dp),
                                            colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant)
                                        ) {
                                            Row(
                                                modifier = Modifier
                                                    .fillMaxWidth()
                                                    .padding(12.dp),
                                                verticalAlignment = Alignment.CenterVertically,
                                                horizontalArrangement = Arrangement.SpaceBetween
                                            ) {
                                                Row(
                                                    verticalAlignment = Alignment.CenterVertically,
                                                    horizontalArrangement = Arrangement.spacedBy(10.dp),
                                                    modifier = Modifier.weight(1f)
                                                ) {
                                                    Icon(
                                                        imageVector = getFileIcon(filename),
                                                        contentDescription = null,
                                                        tint = Color(0xFF38BDF8),
                                                        modifier = Modifier.size(24.dp)
                                                    )
                                                    Column {
                                                        Text(filename, fontWeight = FontWeight.Bold, style = MaterialTheme.typography.bodyMedium, color = Color.White)
                                                        Text(formatBytesKotlin(size), style = MaterialTheme.typography.bodySmall, color = Color(0xFF94A3B8))
                                                    }
                                                }

                                                Button(
                                                    onClick = {
                                                        scope.launch {
                                                            val downloadsDir = Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DOWNLOADS)
                                                            val targetFile = File(downloadsDir, filename)
                                                            val dlRes = apiClient.downloadDropFile(serverConfig.host, serverConfig.port, fileId, targetFile)
                                                            dlRes.onSuccess {
                                                                Toast.makeText(context, "Saved to Downloads: $filename", Toast.LENGTH_LONG).show()
                                                                pendingDrops = pendingDrops.filter { it.optString("file_id") != fileId }
                                                            }.onFailure {
                                                                Toast.makeText(context, "Failed: ${it.message}", Toast.LENGTH_SHORT).show()
                                                            }
                                                        }
                                                    },
                                                    shape = RoundedCornerShape(10.dp),
                                                    colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF6366F1))
                                                ) {
                                                    Icon(Icons.Default.Download, contentDescription = null, modifier = Modifier.size(14.dp))
                                                    Spacer(modifier = Modifier.width(4.dp))
                                                    Text("Save")
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }

            // Sync Action Card (Camera Roll Backup)
            item {
                Card(
                    modifier = Modifier
                        .fillMaxWidth()
                        .border(1.dp, Color.White.copy(alpha = 0.08f), RoundedCornerShape(20.dp)),
                    shape = RoundedCornerShape(20.dp),
                    colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface)
                ) {
                    Column(
                        modifier = Modifier.padding(18.dp),
                        verticalArrangement = Arrangement.spacedBy(14.dp)
                    ) {
                        Text(
                            text = "Camera Roll Full-Res Backup",
                            style = MaterialTheme.typography.titleSmall,
                            fontWeight = FontWeight.Bold,
                            color = Color.White
                        )

                        AnimatedVisibility(
                            visible = isSyncing,
                            enter = fadeIn() + expandVertically(),
                            exit = fadeOut() + shrinkVertically()
                        ) {
                            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                                LinearProgressIndicator(
                                    progress = if (syncProgressTotal > 0) syncProgressCurrent.toFloat() / syncProgressTotal else 0f,
                                    modifier = Modifier.fillMaxWidth().clip(RoundedCornerShape(6.dp)),
                                    color = Color(0xFF6366F1),
                                    trackColor = Color(0xFF1E293B)
                                )
                                Text(
                                    text = if (syncProgressTotal > 0) "Streaming $syncProgressCurrent / $syncProgressTotal photos at gigabit speed..." else "Analyzing local camera roll...",
                                    style = MaterialTheme.typography.bodySmall,
                                    color = Color(0xFF38BDF8)
                                )
                            }
                        }

                        Button(
                            onClick = onSyncNowClicked,
                            enabled = !isSyncing,
                            shape = RoundedCornerShape(14.dp),
                            colors = ButtonDefaults.buttonColors(
                                containerColor = Color(0xFF6366F1),
                                disabledContainerColor = Color(0xFF334155)
                            ),
                            modifier = Modifier
                                .fillMaxWidth()
                                .height(50.dp)
                        ) {
                            Icon(Icons.Default.Sync, contentDescription = null, modifier = Modifier.size(18.dp))
                            Spacer(modifier = Modifier.width(8.dp))
                            Text(if (isSyncing) "Backing Up Photos..." else "Sync Camera Roll Now", fontWeight = FontWeight.Bold)
                        }
                    }
                }
            }

            // Settings & Preferences
            item {
                Card(
                    modifier = Modifier
                        .fillMaxWidth()
                        .border(1.dp, Color.White.copy(alpha = 0.08f), RoundedCornerShape(20.dp)),
                    shape = RoundedCornerShape(20.dp),
                    colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface)
                ) {
                    Column(
                        modifier = Modifier.padding(18.dp),
                        verticalArrangement = Arrangement.spacedBy(14.dp)
                    ) {
                        Text(
                            text = "Autonomous Sync Preferences",
                            style = MaterialTheme.typography.titleSmall,
                            fontWeight = FontWeight.Bold,
                            color = Color.White
                        )

                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.SpaceBetween
                        ) {
                            Column(modifier = Modifier.weight(1f)) {
                                Text("Auto-Sync on Home Wi-Fi", fontWeight = FontWeight.SemiBold, style = MaterialTheme.typography.bodyMedium, color = Color.White)
                                Text("Sync automatically in background when connected to home LAN", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                            }
                            Switch(
                                checked = autoSyncEnabled,
                                onCheckedChange = onAutoSyncToggled,
                                colors = SwitchDefaults.colors(checkedThumbColor = Color.White, checkedTrackColor = Color(0xFF6366F1))
                            )
                        }

                        Divider(color = Color.White.copy(alpha = 0.06f))

                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.SpaceBetween
                        ) {
                            Column(modifier = Modifier.weight(1f)) {
                                Text("Only When Plugged In", fontWeight = FontWeight.SemiBold, style = MaterialTheme.typography.bodyMedium, color = Color.White)
                                Text("Preserve battery life by backing up only while charging", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                            }
                            Switch(
                                checked = chargingOnlyEnabled,
                                onCheckedChange = onChargingOnlyToggled,
                                colors = SwitchDefaults.colors(checkedThumbColor = Color.White, checkedTrackColor = Color(0xFF6366F1))
                            )
                        }
                    }
                }
                Spacer(modifier = Modifier.height(20.dp))
            }
        }
    }
}

@Composable
fun BadgeChip(icon: androidx.compose.ui.graphics.vector.ImageVector, label: String) {
    Surface(
        shape = RoundedCornerShape(8.dp),
        color = Color(0xFF1E293B),
        border = androidx.compose.foundation.BorderStroke(1.dp, Color.White.copy(alpha = 0.05f))
    ) {
        Row(
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(4.dp),
            modifier = Modifier.padding(horizontal = 7.dp, vertical = 3.dp)
        ) {
            Icon(icon, contentDescription = null, tint = Color(0xFF38BDF8), modifier = Modifier.size(11.dp))
            Text(label, color = Color(0xFF94A3B8), fontSize = 10.sp, fontWeight = FontWeight.Medium)
        }
    }
}

fun getFileIcon(filename: String): androidx.compose.ui.graphics.vector.ImageVector {
    val lower = filename.lowercase(Locale.ROOT)
    return when {
        lower.endsWith(".jpg") || lower.endsWith(".jpeg") || lower.endsWith(".png") || lower.endsWith(".webp") || lower.endsWith(".gif") -> Icons.Default.Image
        lower.endsWith(".mp4") || lower.endsWith(".mkv") || lower.endsWith(".mov") || lower.endsWith(".webm") -> Icons.Default.VideoLibrary
        lower.endsWith(".zip") || lower.endsWith(".rar") || lower.endsWith(".tar") || lower.endsWith(".gz") -> Icons.Default.FolderZip
        lower.endsWith(".pdf") || lower.endsWith(".txt") || lower.endsWith(".doc") || lower.endsWith(".docx") -> Icons.Default.Description
        else -> Icons.Default.InsertDriveFile
    }
}

fun formatBytesKotlin(bytes: Long): String {
    if (bytes <= 0) return "0 B"
    val k = 1024.0
    val sizes = arrayOf("B", "KB", "MB", "GB", "TB")
    val i = (Math.log(bytes.toDouble()) / Math.log(k)).toInt().coerceIn(0, sizes.size - 1)
    val num = bytes / Math.pow(k, i.toDouble())
    return String.format(Locale.US, "%.1f %s", num, sizes[i])
}

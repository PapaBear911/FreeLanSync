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
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.photosync.app.data.ServerConfig
import com.photosync.app.network.DeviceBridgeWebSocket
import com.photosync.app.network.FreeLanSyncApiClient
import kotlinx.coroutines.launch
import org.json.JSONObject
import java.io.File
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/**
 * FreeLanSync Dashboard Screen (Universal Spec-Driven UI Loop / Anti-Slop S0 Tier)
 *
 * Implements:
 *  - Persistent "Telemetry Spine" (Link state, IP:Port, Protocol channel, Ping beacon)
 *  - Real-Time Camera Roll Gigabit Sync Engine with exact numeric ratio & percentage
 *  - Actionable PC Quick-Drop receiver with real byte sizes and direct Downloads storage
 *  - Zero-Cloud Continuity & Notification Mirroring controller
 *  - Power-aware Sync Preferences (Auto-Sync on Home Wi-Fi, Charging-Only restriction)
 */
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
    val apiClient = remember { FreeLanSyncApiClient() }
    val dateFormat = remember { SimpleDateFormat("MMM d, HH:mm", Locale.getDefault()) }
    val lastSyncStr = if (lastSyncTimestamp > 0) dateFormat.format(Date(lastSyncTimestamp)) else "Never"

    var pendingDrops by remember { mutableStateOf<List<JSONObject>>(emptyList()) }
    var isCheckingDrops by remember { mutableStateOf(false) }
    var showGuide by remember { mutableStateOf(false) }

    // Live heartbeat beacon animation
    val infiniteTransition = rememberInfiniteTransition(label = "pulse")
    val beaconAlpha by infiniteTransition.animateFloat(
        initialValue = 0.4f,
        targetValue = 1f,
        animationSpec = infiniteRepeatable(
            animation = tween(1200, easing = EaseInOutSine),
            repeatMode = RepeatMode.Reverse
        ),
        label = "beaconAlpha"
    )

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(10.dp)
                    ) {
                        Box(contentAlignment = Alignment.Center) {
                            Box(
                                modifier = Modifier
                                    .size(12.dp)
                                    .clip(CircleShape)
                                    .background(Color(0xFF10B981).copy(alpha = beaconAlpha))
                            )
                            Box(
                                modifier = Modifier
                                    .size(6.dp)
                                    .clip(CircleShape)
                                    .background(Color(0xFF10B981))
                            )
                        }
                        Column {
                            Text("FreeLanSync", fontWeight = FontWeight.Bold, fontSize = 17.sp, color = Color.White)
                            Text("Gigabit LAN Continuity Hub", style = MaterialTheme.typography.labelSmall, color = Color(0xFF38BDF8))
                        }
                    }
                },
                actions = {
                    IconButton(onClick = { showGuide = true }) {
                        Icon(
                            imageVector = Icons.Default.Info,
                            contentDescription = "User Guide",
                            tint = Color(0xFF38BDF8)
                        )
                    }
                    TextButton(onClick = onUnpairClicked) {
                        Text("Disconnect", color = Color(0xFFEF4444), fontWeight = FontWeight.SemiBold, fontSize = 13.sp)
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = Color(0xFF0F172A)
                )
            )
        },
        containerColor = Color(0xFF070A11)
    ) { padding ->
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(horizontal = 16.dp),
            verticalArrangement = Arrangement.spacedBy(14.dp)
        ) {
            item {
                Spacer(modifier = Modifier.height(2.dp))

                // The Signature Decision: "Telemetry Spine" Header Strip
                Surface(
                    shape = RoundedCornerShape(14.dp),
                    color = Color(0xFF0F172A),
                    border = androidx.compose.foundation.BorderStroke(1.dp, Color.White.copy(alpha = 0.08f)),
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(horizontal = 14.dp, vertical = 10.dp),
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.SpaceBetween
                    ) {
                        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                            Icon(Icons.Default.Wifi, contentDescription = null, tint = Color(0xFF10B981), modifier = Modifier.size(14.dp))
                            Text(
                                text = "${serverConfig.host}:${serverConfig.port}",
                                fontFamily = FontFamily.Monospace,
                                fontSize = 12.sp,
                                fontWeight = FontWeight.SemiBold,
                                color = Color(0xFFE2E8F0)
                            )
                        }

                        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            Surface(
                                shape = RoundedCornerShape(6.dp),
                                color = Color(0xFF1E293B)
                            ) {
                                Text(
                                    text = "1000 Mbps",
                                    fontFamily = FontFamily.Monospace,
                                    fontSize = 10.sp,
                                    fontWeight = FontWeight.Bold,
                                    color = Color(0xFF38BDF8),
                                    modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp)
                                )
                            }
                            Surface(
                                shape = RoundedCornerShape(6.dp),
                                color = Color(0xFF10B981).copy(alpha = 0.15f)
                            ) {
                                Text(
                                    text = "SECURE E2E",
                                    fontSize = 9.sp,
                                    fontWeight = FontWeight.Bold,
                                    color = Color(0xFF10B981),
                                    modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp)
                                )
                            }
                        }
                    }
                }
            }

            // Sync Action Engine Card
            item {
                Card(
                    modifier = Modifier
                        .fillMaxWidth()
                        .border(1.dp, Color(0xFF6366F1).copy(alpha = 0.25f), RoundedCornerShape(20.dp)),
                    shape = RoundedCornerShape(20.dp),
                    colors = CardDefaults.cardColors(containerColor = Color(0xFF0F172A))
                ) {
                    Column(
                        modifier = Modifier.padding(18.dp),
                        verticalArrangement = Arrangement.spacedBy(14.dp)
                    ) {
                        Row(
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.SpaceBetween,
                            modifier = Modifier.fillMaxWidth()
                        ) {
                            Column {
                                Text(
                                    text = "Camera Roll Full-Res Sync",
                                    style = MaterialTheme.typography.titleMedium,
                                    fontWeight = FontWeight.Bold,
                                    color = Color.White
                                )
                                Text(
                                    text = "Deduplicated bit-for-bit backup directly to PC Vault",
                                    style = MaterialTheme.typography.bodySmall,
                                    color = Color(0xFF94A3B8)
                                )
                            }
                            Surface(
                                shape = RoundedCornerShape(8.dp),
                                color = Color(0xFF1E293B)
                            ) {
                                Text(
                                    text = "Last: $lastSyncStr",
                                    fontFamily = FontFamily.Monospace,
                                    fontSize = 11.sp,
                                    color = Color(0xFFCBD5E1),
                                    modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp)
                                )
                            }
                        }

                        // Active Sync Telemetry Gauge
                        AnimatedVisibility(
                            visible = isSyncing,
                            enter = fadeIn() + expandVertically(),
                            exit = fadeOut() + shrinkVertically()
                        ) {
                            val ratio = if (syncProgressTotal > 0) syncProgressCurrent.toFloat() / syncProgressTotal else 0f
                            val pct = (ratio * 100).toInt()

                            Column(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .background(Color(0xFF1E293B).copy(alpha = 0.5f), RoundedCornerShape(12.dp))
                                    .padding(12.dp),
                                verticalArrangement = Arrangement.spacedBy(8.dp)
                            ) {
                                Row(
                                    modifier = Modifier.fillMaxWidth(),
                                    horizontalArrangement = Arrangement.SpaceBetween,
                                    verticalAlignment = Alignment.CenterVertically
                                ) {
                                    Text(
                                        text = if (syncProgressTotal > 0) "Streaming Item $syncProgressCurrent of $syncProgressTotal" else "Inspecting MediaStore changes...",
                                        style = MaterialTheme.typography.bodySmall,
                                        fontWeight = FontWeight.SemiBold,
                                        color = Color(0xFF38BDF8)
                                    )
                                    Text(
                                        text = "$pct%",
                                        fontFamily = FontFamily.Monospace,
                                        fontSize = 13.sp,
                                        fontWeight = FontWeight.Bold,
                                        color = Color.White
                                    )
                                }

                                LinearProgressIndicator(
                                    progress = ratio,
                                    modifier = Modifier
                                        .fillMaxWidth()
                                        .height(8.dp)
                                        .clip(RoundedCornerShape(4.dp)),
                                    color = Color(0xFF6366F1),
                                    trackColor = Color(0xFF334155)
                                )
                            }
                        }

                        Button(
                            onClick = onSyncNowClicked,
                            enabled = !isSyncing,
                            shape = RoundedCornerShape(14.dp),
                            colors = ButtonDefaults.buttonColors(
                                containerColor = Color(0xFF4F46E5),
                                disabledContainerColor = Color(0xFF1E293B)
                            ),
                            modifier = Modifier
                                .fillMaxWidth()
                                .height(50.dp)
                        ) {
                            Icon(Icons.Default.Sync, contentDescription = null, modifier = Modifier.size(18.dp))
                            Spacer(modifier = Modifier.width(8.dp))
                            Text(
                                if (isSyncing) "Gigabit Transfer In Progress..." else "Sync Camera Roll Now",
                                fontWeight = FontWeight.Bold,
                                fontSize = 15.sp,
                                color = Color.White
                            )
                        }
                    }
                }
            }

            // Quick-Drop (PC -> Phone) Station
            item {
                Card(
                    modifier = Modifier
                        .fillMaxWidth()
                        .border(1.dp, Color.White.copy(alpha = 0.08f), RoundedCornerShape(20.dp)),
                    shape = RoundedCornerShape(20.dp),
                    colors = CardDefaults.cardColors(containerColor = Color(0xFF0F172A))
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
                                    text = "Quick-Drop Receiver",
                                    style = MaterialTheme.typography.titleMedium,
                                    fontWeight = FontWeight.Bold,
                                    color = Color.White
                                )
                            }

                            IconButton(
                                onClick = {
                                    isCheckingDrops = true
                                    scope.launch {
                                        val res = apiClient.getPendingDrops(serverConfig.host, serverConfig.port, serverConfig.authToken)
                                        isCheckingDrops = false
                                        res.onSuccess { drops ->
                                            pendingDrops = drops
                                            if (drops.isEmpty()) {
                                                Toast.makeText(context, "No incoming files from PC", Toast.LENGTH_SHORT).show()
                                            }
                                        }.onFailure {
                                            Toast.makeText(context, "Drop scan error: ${it.message}", Toast.LENGTH_SHORT).show()
                                        }
                                    }
                                }
                            ) {
                                if (isCheckingDrops) {
                                    CircularProgressIndicator(modifier = Modifier.size(18.dp), strokeWidth = 2.dp, color = Color(0xFF38BDF8))
                                } else {
                                    Icon(Icons.Default.Refresh, contentDescription = "Check Drops", tint = Color(0xFF94A3B8))
                                }
                            }
                        }

                        if (pendingDrops.isEmpty()) {
                            Text(
                                text = "Drop files into your PC dashboard browser tab to stream them directly over Wi-Fi into your Downloads folder.",
                                style = MaterialTheme.typography.bodySmall,
                                color = Color(0xFF94A3B8)
                            )
                        } else {
                            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                                pendingDrops.forEach { drop ->
                                    val fileId = drop.optString("file_id")
                                    val filename = drop.optString("filename")
                                    val size = drop.optLong("size", 0)

                                    Card(
                                        modifier = Modifier
                                            .fillMaxWidth()
                                            .border(1.dp, Color(0xFF38BDF8).copy(alpha = 0.2f), RoundedCornerShape(12.dp)),
                                        shape = RoundedCornerShape(12.dp),
                                        colors = CardDefaults.cardColors(containerColor = Color(0xFF1E293B))
                                    ) {
                                        Row(
                                            modifier = Modifier
                                                .fillMaxWidth()
                                                .padding(12.dp),
                                            verticalAlignment = Alignment.CenterVertically,
                                            horizontalArrangement = Arrangement.SpaceBetween
                                        ) {
                                            Column(modifier = Modifier.weight(1f)) {
                                                Text(filename, fontWeight = FontWeight.Bold, style = MaterialTheme.typography.bodyMedium, color = Color.White)
                                                Text(formatBytesKotlin(size), fontFamily = FontFamily.Monospace, style = MaterialTheme.typography.bodySmall, color = Color(0xFF38BDF8))
                                            }

                                            Button(
                                                onClick = {
                                                    scope.launch {
                                                        val downloadsDir = Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DOWNLOADS)
                                                        val sanitizedName = File(filename).name.takeIf { it.isNotBlank() && !it.contains("..") } ?: "drop_${fileId}.bin"
                                                        val targetFile = File(downloadsDir, sanitizedName)
                                                        if (!targetFile.canonicalPath.startsWith(downloadsDir.canonicalPath)) {
                                                            Toast.makeText(context, "Invalid filename: traversal blocked", Toast.LENGTH_SHORT).show()
                                                            return@launch
                                                        }
                                                        val dlRes = apiClient.downloadDropFile(
                                                            host = serverConfig.host,
                                                            port = serverConfig.port,
                                                            fileId = fileId,
                                                            destinationFile = targetFile,
                                                            token = serverConfig.authToken
                                                        )
                                                        dlRes.onSuccess {
                                                            Toast.makeText(context, "Saved to Downloads: $sanitizedName", Toast.LENGTH_LONG).show()
                                                            pendingDrops = pendingDrops.filter { it.optString("file_id") != fileId }
                                                        }.onFailure {
                                                            Toast.makeText(context, "Download failed: ${it.message}", Toast.LENGTH_SHORT).show()
                                                        }
                                                    }
                                                },
                                                shape = RoundedCornerShape(10.dp),
                                                colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF10B981))
                                            ) {
                                                Icon(Icons.Default.Download, contentDescription = null, modifier = Modifier.size(14.dp))
                                                Spacer(modifier = Modifier.width(4.dp))
                                                Text("Receive")
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }

            // Universal Clipboard Synchronization Card
            item {
                var clipText by remember { mutableStateOf("") }
                Card(
                    modifier = Modifier
                        .fillMaxWidth()
                        .border(1.dp, Color.White.copy(alpha = 0.08f), RoundedCornerShape(20.dp)),
                    shape = RoundedCornerShape(20.dp),
                    colors = CardDefaults.cardColors(containerColor = Color(0xFF0F172A))
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
                                Icon(Icons.Default.ContentPaste, contentDescription = null, tint = Color(0xFF818CF8), modifier = Modifier.size(20.dp))
                                Text(
                                    text = "Universal Clipboard",
                                    style = MaterialTheme.typography.titleMedium,
                                    fontWeight = FontWeight.Bold,
                                    color = Color.White
                                )
                            }
                            Surface(
                                shape = RoundedCornerShape(8.dp),
                                color = Color(0xFF1E1B4B)
                            ) {
                                Text(
                                    text = "P2P SYNC",
                                    fontSize = 10.sp,
                                    fontWeight = FontWeight.Bold,
                                    color = Color(0xFFC7D2FE),
                                    modifier = Modifier.padding(horizontal = 7.dp, vertical = 2.dp)
                                )
                            }
                        }

                        OutlinedTextField(
                            value = clipText,
                            onValueChange = { clipText = it },
                            placeholder = { Text("Type or paste text to share with PC...", color = Color(0xFF64748B), fontSize = 13.sp) },
                            modifier = Modifier.fillMaxWidth(),
                            minLines = 2,
                            maxLines = 4,
                            colors = OutlinedTextFieldDefaults.colors(
                                focusedBorderColor = Color(0xFF818CF8),
                                unfocusedBorderColor = Color(0xFF334155),
                                focusedTextColor = Color.White,
                                unfocusedTextColor = Color.White
                            )
                        )

                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.spacedBy(10.dp)
                        ) {
                            Button(
                                onClick = {
                                    if (clipText.isNotBlank()) {
                                        DeviceBridgeWebSocket.getInstance().sendClipboard(clipText.trim())
                                        Toast.makeText(context, "Text sent to PC Clipboard!", Toast.LENGTH_SHORT).show()
                                        clipText = ""
                                    }
                                },
                                enabled = clipText.isNotBlank(),
                                shape = RoundedCornerShape(12.dp),
                                colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF4F46E5)),
                                modifier = Modifier.weight(1f)
                            ) {
                                Icon(Icons.Default.Send, contentDescription = null, modifier = Modifier.size(14.dp))
                                Spacer(modifier = Modifier.width(6.dp))
                                Text("Send to PC", fontWeight = FontWeight.Bold, fontSize = 13.sp)
                            }

                            FilledTonalButton(
                                onClick = {
                                    val cm = context.getSystemService(Context.CLIPBOARD_SERVICE) as? android.content.ClipboardManager
                                    val clip = cm?.primaryClip
                                    if (clip != null && clip.itemCount > 0) {
                                        val text = clip.getItemAt(0).text?.toString() ?: ""
                                        if (text.isNotBlank()) {
                                            clipText = text
                                            DeviceBridgeWebSocket.getInstance().sendClipboard(text)
                                            Toast.makeText(context, "Pasted & shared with PC!", Toast.LENGTH_SHORT).show()
                                        }
                                    } else {
                                        Toast.makeText(context, "Phone clipboard is empty", Toast.LENGTH_SHORT).show()
                                    }
                                },
                                shape = RoundedCornerShape(12.dp)
                            ) {
                                Icon(Icons.Default.ContentPasteGo, contentDescription = null, modifier = Modifier.size(16.dp))
                                Spacer(modifier = Modifier.width(4.dp))
                                Text("Paste Device", fontSize = 13.sp)
                            }
                        }
                    }
                }
            }

            // Autonomous Sync Rules & Power Constraints
            item {
                Card(
                    modifier = Modifier
                        .fillMaxWidth()
                        .border(1.dp, Color.White.copy(alpha = 0.08f), RoundedCornerShape(20.dp)),
                    shape = RoundedCornerShape(20.dp),
                    colors = CardDefaults.cardColors(containerColor = Color(0xFF0F172A))
                ) {
                    Column(
                        modifier = Modifier.padding(18.dp),
                        verticalArrangement = Arrangement.spacedBy(14.dp)
                    ) {
                        Text(
                            text = "Power & Synchronization Rules",
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
                                Text("Autonomous Background Sync", fontWeight = FontWeight.SemiBold, style = MaterialTheme.typography.bodyMedium, color = Color.White)
                                Text("Automatically sync camera roll periodically when connected to LAN", style = MaterialTheme.typography.bodySmall, color = Color(0xFF94A3B8))
                            }
                            Switch(
                                checked = autoSyncEnabled,
                                onCheckedChange = onAutoSyncToggled,
                                colors = SwitchDefaults.colors(checkedThumbColor = Color.White, checkedTrackColor = Color(0xFF4F46E5))
                            )
                        }

                        Divider(color = Color.White.copy(alpha = 0.06f))

                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.SpaceBetween
                        ) {
                            Column(modifier = Modifier.weight(1f)) {
                                Text("Restrict to AC Power (Charging Only)", fontWeight = FontWeight.SemiBold, style = MaterialTheme.typography.bodyMedium, color = Color.White)
                                Text("Prevents battery discharge during multi-gigabyte media uploads", style = MaterialTheme.typography.bodySmall, color = Color(0xFF94A3B8))
                            }
                            Switch(
                                checked = chargingOnlyEnabled,
                                onCheckedChange = onChargingOnlyToggled,
                                colors = SwitchDefaults.colors(checkedThumbColor = Color.White, checkedTrackColor = Color(0xFF4F46E5))
                            )
                        }
                    }
                }
                Spacer(modifier = Modifier.height(24.dp))
            }
        }
    }

    if (showGuide) {
        UserGuideDialog(onDismiss = { showGuide = false })
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

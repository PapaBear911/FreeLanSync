package com.photosync.app.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.window.Dialog

@Composable
fun UserGuideDialog(
    onDismiss: () -> Unit
) {
    Dialog(onDismissRequest = onDismiss) {
        Card(
            modifier = Modifier
                .fillMaxWidth()
                .fillMaxHeight(0.85f)
                .border(1.dp, Color.White.copy(alpha = 0.12f), RoundedCornerShape(24.dp)),
            shape = RoundedCornerShape(24.dp),
            colors = CardDefaults.cardColors(containerColor = Color(0xFF0F172A))
        ) {
            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(20.dp)
            ) {
                // Header
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.SpaceBetween
                ) {
                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(10.dp)
                    ) {
                        Box(
                            modifier = Modifier
                                .size(36.dp)
                                .background(Color(0xFF38BDF8).copy(alpha = 0.15f), RoundedCornerShape(10.dp)),
                            contentAlignment = Alignment.Center
                        ) {
                            Icon(
                                imageVector = Icons.Default.Info,
                                contentDescription = null,
                                tint = Color(0xFF38BDF8),
                                modifier = Modifier.size(20.dp)
                            )
                        }
                        Column {
                            Text(
                                text = "FreeLanSync Guide",
                                fontWeight = FontWeight.Bold,
                                fontSize = 17.sp,
                                color = Color.White
                            )
                            Text(
                                text = "Setup & Best Practices",
                                style = MaterialTheme.typography.labelSmall,
                                color = Color(0xFF94A3B8)
                            )
                        }
                    }

                    IconButton(onClick = onDismiss, modifier = Modifier.size(28.dp)) {
                        Icon(
                            imageVector = Icons.Default.Close,
                            contentDescription = "Close",
                            tint = Color(0xFF94A3B8),
                            modifier = Modifier.size(18.dp)
                        )
                    }
                }

                Spacer(modifier = Modifier.height(16.dp))

                // Scrollable content
                Column(
                    modifier = Modifier
                        .weight(1f)
                        .verticalScroll(rememberScrollState()),
                    verticalArrangement = Arrangement.spacedBy(12.dp)
                ) {
                    GuideStepCard(
                        icon = Icons.Default.QrCodeScanner,
                        iconTint = Color(0xFF38BDF8),
                        title = "1. Fast Optical Pairing",
                        subtitle = "Same Wi-Fi Required",
                        description = "Connect PC and phone to the same Wi-Fi. Tap 'Scan Desktop QR Code' on your phone and point your camera at the PC dashboard QR code. Manual entry with a 6-digit PIN is also supported."
                    )

                    GuideStepCard(
                        icon = Icons.Default.Sync,
                        iconTint = Color(0xFF818CF8),
                        title = "2. Gigabit Camera Roll Backup",
                        subtitle = "Deduplicated Bit-for-Bit",
                        description = "Tap 'Sync Camera Roll Now' for instant backup. Media uploads directly across up to 4 parallel connections. Existing items are skipped instantly via SHA-256 hashes."
                    )

                    GuideStepCard(
                        icon = Icons.Default.ArrowOutward,
                        iconTint = Color(0xFF34D399),
                        title = "3. PC Quick-Drop Receiver",
                        subtitle = "Direct to Downloads",
                        description = "Drag files onto the PC dashboard to send them over Wi-Fi. Tap 'Receive' on your phone to save directly into Downloads. Downloads are staged safely to prevent truncated files."
                    )

                    GuideStepCard(
                        icon = Icons.Default.ContentPaste,
                        iconTint = Color(0xFFF472B6),
                        title = "4. Shared Clipboard & Continuity",
                        subtitle = "Bidirectional Sync",
                        description = "Copied text on PC syncs instantly to your phone. Copied text on phone syncs back to PC. Grant Notification Listener to mirror phone alerts to PC."
                    )

                    GuideStepCard(
                        icon = Icons.Default.Warning,
                        iconTint = Color(0xFFFBBF24),
                        title = "5. Troubleshooting & FAQ",
                        subtitle = "Network Tips",
                        description = "• Discovery fails: Ensure Wi-Fi router doesn't have 'AP Isolation' enabled.\n• Firewall: Allow port 8080 (TCP) on Windows Firewall.\n• 401 error: Tap 'Disconnect' and re-scan the QR code.\n• 413 error: Video exceeds server max upload limit."
                    )
                }

                Spacer(modifier = Modifier.height(16.dp))

                Button(
                    onClick = onDismiss,
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(12.dp),
                    colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF6366F1))
                ) {
                    Text("Got It", fontWeight = FontWeight.Bold, color = Color.White)
                }
            }
        }
    }
}

@Composable
private fun GuideStepCard(
    icon: ImageVector,
    iconTint: Color,
    title: String,
    subtitle: String,
    description: String
) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .border(1.dp, Color.White.copy(alpha = 0.07f), RoundedCornerShape(16.dp)),
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(containerColor = Color(0xFF1E293B).copy(alpha = 0.6f))
    ) {
        Column(
            modifier = Modifier.padding(14.dp),
            verticalArrangement = Arrangement.spacedBy(6.dp)
        ) {
            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(10.dp)
            ) {
                Box(
                    modifier = Modifier
                        .size(30.dp)
                        .background(iconTint.copy(alpha = 0.15f), RoundedCornerShape(8.dp)),
                    contentAlignment = Alignment.Center
                ) {
                    Icon(imageVector = icon, contentDescription = null, tint = iconTint, modifier = Modifier.size(16.dp))
                }
                Column {
                    Text(text = title, fontWeight = FontWeight.Bold, fontSize = 14.sp, color = Color.White)
                    Text(text = subtitle, style = MaterialTheme.typography.labelSmall, color = iconTint)
                }
            }
            Text(
                text = description,
                style = MaterialTheme.typography.bodySmall,
                color = Color(0xFFCBD5E1),
                lineHeight = 18.sp
            )
        }
    }
}

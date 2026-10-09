package com.photosync.app.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.QrCodeScanner
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Wifi
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.photosync.app.network.DiscoveredServer
import com.photosync.app.network.PairingPayload

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun PairingScreen(
    discoveredServers: List<DiscoveredServer>,
    onPairSubmitted: (host: String, port: Int, pin: String) -> Unit,
    onScanQrClicked: () -> Unit,
    onPayloadSubmitted: (String) -> Unit,
    scannedPayload: PairingPayload?,
    isLoading: Boolean,
    errorMessage: String?
) {
    var hostInput by remember { mutableStateOf("") }
    var portInput by remember { mutableStateOf("8080") }
    var pinInput by remember { mutableStateOf("") }
    var linkInput by remember { mutableStateOf("") }

    // A payload from a QR scan / pasted link / deep link pre-fills the form so
    // the user only has to confirm (or complete the PIN).
    LaunchedEffect(scannedPayload) {
        val payload = scannedPayload ?: return@LaunchedEffect
        hostInput = payload.host
        portInput = payload.port.toString()
        payload.pin?.let { pinInput = it.take(6) }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Pair with Desktop Server", fontWeight = FontWeight.Bold) },
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
                Button(
                    onClick = onScanQrClicked,
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(52.dp),
                    enabled = !isLoading
                ) {
                    Icon(
                        Icons.Default.QrCodeScanner,
                        contentDescription = "Scan QR code"
                    )
                    Spacer(modifier = Modifier.width(10.dp))
                    Text("Scan QR Code to Pair", fontSize = 16.sp, fontWeight = FontWeight.Bold)
                }
                Text(
                    text = "Scan the QR code shown on the desktop dashboard for one-tap pairing. " +
                        "If the camera is unavailable, paste the pairing link below instead.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }

            item {
                Text(
                    text = "Discovered Servers on Wi-Fi",
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.SemiBold
                )
                Text(
                    text = "Tap a discovered PC server to auto-fill its connection details.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }

            if (discoveredServers.isEmpty()) {
                item {
                    Card(
                        modifier = Modifier.fillMaxWidth(),
                        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface)
                    ) {
                        Row(
                            modifier = Modifier
                                .fillMaxWidth()
                                .padding(16.dp),
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.spacedBy(12.dp)
                        ) {
                            CircularProgressIndicator(modifier = Modifier.size(20.dp), strokeWidth = 2.dp)
                            Text(
                                text = "Scanning local Wi-Fi for PC server...",
                                style = MaterialTheme.typography.bodyMedium,
                                color = MaterialTheme.colorScheme.onSurfaceVariant
                            )
                        }
                    }
                }
            } else {
                items(discoveredServers) { server ->
                    Card(
                        modifier = Modifier
                            .fillMaxWidth()
                            .clickable {
                                hostInput = server.host
                                portInput = server.port.toString()
                            },
                        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.primaryContainer)
                    ) {
                        Row(
                            modifier = Modifier
                                .fillMaxWidth()
                                .padding(16.dp),
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.SpaceBetween
                        ) {
                            Column {
                                Text(
                                    text = server.serviceName,
                                    fontWeight = FontWeight.Bold,
                                    style = MaterialTheme.typography.titleSmall
                                )
                                Text(
                                    text = "http://${server.host}:${server.port}",
                                    style = MaterialTheme.typography.bodySmall
                                )
                            }
                            Icon(Icons.Default.Wifi, contentDescription = "Wi-Fi Server")
                        }
                    }
                }
            }

            item {
                Divider(modifier = Modifier.padding(vertical = 8.dp))
                Text(
                    text = "Manual Connection & PIN",
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.SemiBold
                )
            }

            item {
                OutlinedTextField(
                    value = hostInput,
                    onValueChange = { hostInput = it },
                    label = { Text("Server IP Address") },
                    placeholder = { Text("e.g. 192.168.1.50") },
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true
                )
            }

            item {
                OutlinedTextField(
                    value = portInput,
                    onValueChange = { portInput = it },
                    label = { Text("Server Port") },
                    placeholder = { Text("8080") },
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true
                )
            }

            item {
                OutlinedTextField(
                    value = pinInput,
                    onValueChange = { if (it.length <= 6) pinInput = it },
                    label = { Text("6-Digit PIN from Desktop Screen") },
                    placeholder = { Text("123456") },
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true
                )
            }

            item {
                OutlinedTextField(
                    value = linkInput,
                    onValueChange = { linkInput = it },
                    label = { Text("or paste pairing link / code") },
                    placeholder = { Text("freelansync://192.168.1.50:8080?pin=123456") },
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true
                )
                TextButton(
                    onClick = { onPayloadSubmitted(linkInput.trim()) },
                    enabled = !isLoading && linkInput.isNotBlank()
                ) {
                    Text("Use Pasted Link")
                }
            }

            if (errorMessage != null) {
                item {
                    Text(
                        text = errorMessage,
                        color = MaterialTheme.colorScheme.error,
                        style = MaterialTheme.typography.bodySmall
                    )
                }
            }

            item {
                Button(
                    onClick = {
                        val port = portInput.toIntOrNull() ?: 8080
                        onPairSubmitted(hostInput.trim(), port, pinInput.trim())
                    },
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(50.dp),
                    enabled = !isLoading && hostInput.isNotBlank() && pinInput.length == 6
                ) {
                    if (isLoading) {
                        CircularProgressIndicator(modifier = Modifier.size(24.dp), color = Color.White)
                    } else {
                        Text("Connect & Pair Device", fontSize = 16.sp, fontWeight = FontWeight.Bold)
                    }
                }
                Spacer(modifier = Modifier.height(24.dp))
            }
        }
    }
}

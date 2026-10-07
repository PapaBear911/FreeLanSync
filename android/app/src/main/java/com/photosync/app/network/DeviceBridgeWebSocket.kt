package com.photosync.app.network

import android.util.Log
import kotlinx.coroutines.*
import okhttp3.*
import org.json.JSONObject
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicBoolean

class DeviceBridgeWebSocket(
    private val onMessageReceived: ((event: String, data: JSONObject) -> Unit)? = null
) {
    companion object {
        private const val TAG = "DeviceBridgeWS"
        @Volatile
        private var instance: DeviceBridgeWebSocket? = null

        fun getInstance(): DeviceBridgeWebSocket {
            return instance ?: synchronized(this) {
                instance ?: DeviceBridgeWebSocket().also { instance = it }
            }
        }
    }

    private val client = OkHttpClient.Builder()
        .readTimeout(0, TimeUnit.MILLISECONDS) // Keep alive
        .pingInterval(25, TimeUnit.SECONDS)
        .build()

    private var webSocket: WebSocket? = null
    private val isConnected = AtomicBoolean(false)
    private var currentHost: String = ""
    private var currentPort: Int = 8080
    private var currentToken: String = ""

    private val scope = CoroutineScope(Dispatchers.IO + SupervisorJob())
    private var reconnectJob: Job? = null

    fun connect(host: String, port: Int, token: String) {
        if (host.isEmpty() || token.isEmpty()) return
        currentHost = host
        currentPort = port
        currentToken = token

        if (isConnected.get() && webSocket != null) return

        val wsUrl = "ws://$host:$port/api/v1/ws/device-bridge?client_type=device&token=$token"
        val request = Request.Builder().url(wsUrl).build()

        webSocket = client.newWebSocket(request, object : WebSocketListener() {
            override fun onOpen(webSocket: WebSocket, response: Response) {
                Log.i(TAG, "Device Bridge WebSocket Connected to $host:$port")
                isConnected.set(true)
                reconnectJob?.cancel()
            }

            override fun onMessage(webSocket: WebSocket, text: String) {
                try {
                    val json = JSONObject(text)
                    val event = json.optString("event")
                    val data = json.optJSONObject("data") ?: JSONObject()
                    Log.d(TAG, "WS Message: $event")
                    onMessageReceived?.invoke(event, data)
                } catch (e: Exception) {
                    Log.e(TAG, "Error parsing WS message", e)
                }
            }

            override fun onClosing(webSocket: WebSocket, code: Int, reason: String) {
                isConnected.set(false)
            }

            override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
                Log.w(TAG, "WebSocket Closed: $reason")
                isConnected.set(false)
                scheduleReconnect()
            }

            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                Log.e(TAG, "WebSocket Failure: ${t.message}")
                isConnected.set(false)
                scheduleReconnect()
            }
        })
    }

    private fun scheduleReconnect() {
        reconnectJob?.cancel()
        reconnectJob = scope.launch {
            delay(5000)
            if (!isConnected.get() && currentHost.isNotEmpty() && currentToken.isNotEmpty()) {
                Log.i(TAG, "Attempting WebSocket Reconnect...")
                connect(currentHost, currentPort, currentToken)
            }
        }
    }

    fun isBridgeConnected(): Boolean = isConnected.get()

    private fun sendEvent(event: String, data: JSONObject) {
        if (!isConnected.get() || webSocket == null) return
        scope.launch {
            try {
                val payload = JSONObject().apply {
                    put("event", event)
                    put("data", data)
                }
                webSocket?.send(payload.toString())
            } catch (e: Exception) {
                Log.e(TAG, "Error sending event $event", e)
            }
        }
    }

    fun sendBatteryStatus(level: Int, isCharging: Boolean, health: String = "GOOD") {
        val data = JSONObject().apply {
            put("level", level)
            put("is_charging", isCharging)
            put("health", health)
            put("timestamp", System.currentTimeMillis())
        }
        sendEvent("BATTERY_STATUS", data)
    }

    fun sendNotification(
        id: String,
        packageName: String,
        appName: String,
        title: String,
        text: String,
        canReply: Boolean = false
    ) {
        val data = JSONObject().apply {
            put("id", id)
            put("package", packageName)
            put("app_name", appName)
            put("title", title)
            put("text", text)
            put("can_reply", canReply)
            put("timestamp", System.currentTimeMillis())
        }
        sendEvent("NOTIFICATION_POSTED", data)
    }

    fun sendNotificationDismissed(id: String) {
        val data = JSONObject().apply {
            put("id", id)
        }
        sendEvent("NOTIFICATION_DISMISSED", data)
    }

    fun sendIncomingCall(callerName: String, phoneNumber: String) {
        val data = JSONObject().apply {
            put("caller_name", callerName)
            put("phone_number", phoneNumber)
            put("timestamp", System.currentTimeMillis())
        }
        sendEvent("CALL_INCOMING", data)
    }

    fun sendMediaPlayback(
        title: String,
        artist: String,
        album: String = "",
        isPlaying: Boolean
    ) {
        val data = JSONObject().apply {
            put("title", title)
            put("artist", artist)
            put("album", album)
            put("is_playing", isPlaying)
        }
        sendEvent("MEDIA_PLAYBACK_STATUS", data)
    }

    fun sendClipboard(text: String) {
        val data = JSONObject().apply {
            put("text", text)
            put("source", "phone")
            put("timestamp", System.currentTimeMillis())
        }
        sendEvent("CLIPBOARD_UPDATE", data)
    }

    fun disconnect() {
        reconnectJob?.cancel()
        webSocket?.close(1000, "App closed")
        isConnected.set(false)
        webSocket = null
    }
}

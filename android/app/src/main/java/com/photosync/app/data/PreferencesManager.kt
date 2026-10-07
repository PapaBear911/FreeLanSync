package com.photosync.app.data

import android.content.Context
import android.content.SharedPreferences

data class ServerConfig(
    val host: String,
    val port: Int,
    val authToken: String,
    val deviceName: String,
    val deviceId: String,
    val isPaired: Boolean
)

class PreferencesManager(context: Context) {
    private val prefs: SharedPreferences = context.getSharedPreferences("photosync_prefs", Context.MODE_PRIVATE)

    companion object {
        private const val KEY_HOST = "server_host"
        private const val KEY_PORT = "server_port"
        private const val KEY_TOKEN = "auth_token"
        private const val KEY_DEVICE_NAME = "device_name"
        private const val KEY_DEVICE_ID = "device_id"
        private const val KEY_LAST_SYNC_TIME = "last_sync_time"
        private const val KEY_AUTO_SYNC_ENABLED = "auto_sync_enabled"
        private const val KEY_CHARGING_ONLY = "charging_only"
    }

    fun getServerConfig(): ServerConfig {
        val host = prefs.getString(KEY_HOST, "") ?: ""
        val port = prefs.getInt(KEY_PORT, 8080)
        val token = prefs.getString(KEY_TOKEN, "") ?: ""
        val deviceName = prefs.getString(KEY_DEVICE_NAME, android.os.Build.MODEL) ?: android.os.Build.MODEL
        var deviceId = prefs.getString(KEY_DEVICE_ID, "") ?: ""
        if (deviceId.isEmpty()) {
            deviceId = java.util.UUID.randomUUID().toString()
            prefs.edit().putString(KEY_DEVICE_ID, deviceId).apply()
        }
        return ServerConfig(
            host = host,
            port = port,
            authToken = token,
            deviceName = deviceName,
            deviceId = deviceId,
            isPaired = token.isNotEmpty() && host.isNotEmpty()
        )
    }

    fun savePairing(host: String, port: Int, token: String, deviceName: String) {
        prefs.edit()
            .putString(KEY_HOST, host)
            .putInt(KEY_PORT, port)
            .putString(KEY_TOKEN, token)
            .putString(KEY_DEVICE_NAME, deviceName)
            .apply()
    }

    fun clearPairing() {
        prefs.edit()
            .remove(KEY_HOST)
            .remove(KEY_PORT)
            .remove(KEY_TOKEN)
            .apply()
    }

    fun setLastSyncTime(timestamp: Long) {
        prefs.edit().putLong(KEY_LAST_SYNC_TIME, timestamp).apply()
    }

    fun getLastSyncTime(): Long = prefs.getLong(KEY_LAST_SYNC_TIME, 0L)

    var isAutoSyncEnabled: Boolean
        get() = prefs.getBoolean(KEY_AUTO_SYNC_ENABLED, true)
        set(value) = prefs.edit().putBoolean(KEY_AUTO_SYNC_ENABLED, value).apply()

    var isChargingOnly: Boolean
        get() = prefs.getBoolean(KEY_CHARGING_ONLY, false)
        set(value) = prefs.edit().putBoolean(KEY_CHARGING_ONLY, value).apply()
}

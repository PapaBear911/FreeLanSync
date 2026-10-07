package com.photosync.app.service

import android.content.Context
import android.net.wifi.WifiManager
import android.os.PowerManager
import android.util.Log

/**
 * Manages CPU Partial WakeLock and High-Performance Wi-Fi Lock
 * to ensure multi-gigabyte transfers run at full speed without OS throttling
 * when the screen turns off or device enters low-power state.
 */
class TransferWakeManager(private val context: Context) {

    companion object {
        private const val TAG = "TransferWakeManager"
        private const val WAKE_LOCK_TAG = "FreeLanSync:TransferWakeLock"
        private const val WIFI_LOCK_TAG = "FreeLanSync:TransferWifiLock"
        private const val DEFAULT_TIMEOUT_MS = 30 * 60 * 1000L // 30 minutes max safety limit
    }

    private var wakeLock: PowerManager.WakeLock? = null
    private var wifiLock: WifiManager.WifiLock? = null

    /**
     * Acquire CPU WakeLock and High-Performance Wi-Fi Lock.
     */
    @Synchronized
    fun acquireLocks(timeoutMs: Long = DEFAULT_TIMEOUT_MS) {
        try {
            // 1. CPU Partial WakeLock
            if (wakeLock == null) {
                val powerManager = context.getSystemService(Context.POWER_SERVICE) as? PowerManager
                wakeLock = powerManager?.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, WAKE_LOCK_TAG)?.apply {
                    setReferenceCounted(false)
                }
            }

            wakeLock?.let {
                if (!it.isHeld) {
                    it.acquire(timeoutMs)
                    Log.i(TAG, "Acquired CPU Partial WakeLock (timeout=$timeoutMs ms)")
                }
            }

            // 2. High-Performance Wi-Fi Lock
            if (wifiLock == null) {
                val wifiManager = context.applicationContext.getSystemService(Context.WIFI_SERVICE) as? WifiManager
                @Suppress("DEPRECATION")
                val mode = WifiManager.WIFI_MODE_FULL_HIGH_PERF
                wifiLock = wifiManager?.createWifiLock(mode, WIFI_LOCK_TAG)?.apply {
                    setReferenceCounted(false)
                }
            }

            wifiLock?.let {
                if (!it.isHeld) {
                    it.acquire()
                    Log.i(TAG, "Acquired High-Performance Wi-Fi Lock")
                }
            }
        } catch (e: Exception) {
            Log.e(TAG, "Error acquiring transfer wake locks", e)
        }
    }

    /**
     * Release locks immediately upon transfer completion or cancellation to save battery.
     */
    @Synchronized
    fun releaseLocks() {
        try {
            wakeLock?.let {
                if (it.isHeld) {
                    it.release()
                    Log.i(TAG, "Released CPU WakeLock")
                }
            }
            wifiLock?.let {
                if (it.isHeld) {
                    it.release()
                    Log.i(TAG, "Released Wi-Fi Lock")
                }
            }
        } catch (e: Exception) {
            Log.e(TAG, "Error releasing transfer wake locks", e)
        }
    }
}

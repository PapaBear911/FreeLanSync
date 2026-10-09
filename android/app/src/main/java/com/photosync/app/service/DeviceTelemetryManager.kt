package com.photosync.app.service

import android.content.*
import android.os.BatteryManager
import android.telephony.TelephonyManager
import android.util.Log
import com.photosync.app.network.DeviceBridgeWebSocket

class DeviceTelemetryManager(private val context: Context) {

    companion object {
        private const val TAG = "DeviceTelemetryMgr"
    }

    private var batteryReceiver: BroadcastReceiver? = null
    private var clipboardListener: ClipboardManager.OnPrimaryClipChangedListener? = null
    private var lastClipboardText: String = ""

    fun startTelemetry() {
        registerBatteryReceiver()
        registerClipboardListener()
    }

    fun stopTelemetry() {
        try {
            batteryReceiver?.let { context.unregisterReceiver(it) }
            val clipboard = context.getSystemService(Context.CLIPBOARD_SERVICE) as? ClipboardManager
            clipboardListener?.let { clipboard?.removePrimaryClipChangedListener(it) }
        } catch (e: Exception) {
            Log.e(TAG, "Error stopping telemetry", e)
        }
    }

    private fun registerBatteryReceiver() {
        batteryReceiver = object : BroadcastReceiver() {
            override fun onReceive(context: Context?, intent: Intent?) {
                if (intent?.action == Intent.ACTION_BATTERY_CHANGED) {
                    val level = intent.getIntExtra(BatteryManager.EXTRA_LEVEL, -1)
                    val scale = intent.getIntExtra(BatteryManager.EXTRA_SCALE, -1)
                    val status = intent.getIntExtra(BatteryManager.EXTRA_STATUS, -1)
                    val isCharging = status == BatteryManager.BATTERY_STATUS_CHARGING ||
                            status == BatteryManager.BATTERY_STATUS_FULL

                    val batteryPct = if (level != -1 && scale != -1) {
                        (level * 100 / scale.toFloat()).toInt()
                    } else level

                    DeviceBridgeWebSocket.getInstance().sendBatteryStatus(
                        level = batteryPct,
                        isCharging = isCharging
                    )
                }
            }
        }
        val filter = IntentFilter(Intent.ACTION_BATTERY_CHANGED)
        context.registerReceiver(batteryReceiver, filter)
    }

    private fun registerClipboardListener() {
        val clipboard = context.getSystemService(Context.CLIPBOARD_SERVICE) as? ClipboardManager ?: return
        clipboardListener = ClipboardManager.OnPrimaryClipChangedListener {
            val clip = clipboard.primaryClip
            if (clip != null && clip.itemCount > 0) {
                val text = clip.getItemAt(0).text?.toString() ?: ""
                if (text.isNotEmpty() && text != lastClipboardText) {
                    lastClipboardText = text
                    Log.d(TAG, "Syncing clipboard to desktop: $text")
                    DeviceBridgeWebSocket.getInstance().sendClipboard(text)
                }
            }
        }
        clipboard.addPrimaryClipChangedListener(clipboardListener)
    }

    fun setPhoneClipboard(text: String) {
        val clipboard = context.getSystemService(Context.CLIPBOARD_SERVICE) as? ClipboardManager ?: return
        lastClipboardText = text
        val clip = ClipData.newPlainText("FreeLanSync", text)
        clipboard.setPrimaryClip(clip)
    }
}

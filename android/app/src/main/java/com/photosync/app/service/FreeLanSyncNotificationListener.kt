package com.photosync.app.service

import android.app.Notification
import android.content.pm.PackageManager
import android.service.notification.NotificationListenerService
import android.service.notification.StatusBarNotification
import android.util.Log
import com.photosync.app.data.PreferencesManager
import com.photosync.app.network.DeviceBridgeWebSocket

class FreeLanSyncNotificationListener : NotificationListenerService() {

    companion object {
        private const val TAG = "FreeLanSyncNotifListener"
        var isListenerActive: Boolean = false
    }

    override fun onListenerConnected() {
        super.onListenerConnected()
        isListenerActive = true
        Log.i(TAG, "FreeLanSync Notification Listener connected")

        // Ensure WebSocket is connected using saved preferences
        val prefs = PreferencesManager(applicationContext)
        val config = prefs.getServerConfig()
        if (config.isPaired) {
            DeviceBridgeWebSocket.getInstance().connect(config.host, config.port, config.authToken)
        }
    }

    override fun onListenerDisconnected() {
        super.onListenerDisconnected()
        isListenerActive = false
        Log.w(TAG, "FreeLanSync Notification Listener disconnected")
    }

    override fun onNotificationPosted(sbn: StatusBarNotification?) {
        if (sbn == null) return
        val packageName = sbn.packageName ?: return

        // Ignore our own notifications to prevent loop
        if (packageName == applicationContext.packageName) return

        val notification = sbn.notification ?: return
        val extras = notification.extras ?: return

        val title = extras.getCharSequence(Notification.EXTRA_TITLE)?.toString() ?: ""
        val text = extras.getCharSequence(Notification.EXTRA_TEXT)?.toString() ?: ""

        // Skip blank notifications
        if (title.isBlank() && text.isBlank()) return

        // Resolve App Name
        val pm = packageManager
        val appName = try {
            val appInfo = pm.getApplicationInfo(packageName, 0)
            pm.getApplicationLabel(appInfo).toString()
        } catch (e: PackageManager.NameNotFoundException) {
            packageName
        }

        // Check if user has active quick reply action
        val canReply = notification.actions?.any { action ->
            action.remoteInputs != null && action.remoteInputs.isNotEmpty()
        } ?: false

        Log.d(TAG, "Mirroring notification from $appName: $title")
        DeviceBridgeWebSocket.getInstance().sendNotification(
            id = sbn.key,
            packageName = packageName,
            appName = appName,
            title = title,
            text = text,
            canReply = canReply
        )
    }

    override fun onNotificationRemoved(sbn: StatusBarNotification?) {
        if (sbn == null) return
        DeviceBridgeWebSocket.getInstance().sendNotificationDismissed(sbn.key)
    }
}

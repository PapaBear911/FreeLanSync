package com.photosync.app

import android.app.Application
import com.photosync.app.data.PreferencesManager
import com.photosync.app.sync.SyncManager

class PhotoSyncApplication : Application() {
    override fun onCreate() {
        super.onCreate()
        val prefs = PreferencesManager(this)
        if (prefs.getServerConfig().isPaired) {
            SyncManager(this).schedulePeriodicSync()
        }
    }
}

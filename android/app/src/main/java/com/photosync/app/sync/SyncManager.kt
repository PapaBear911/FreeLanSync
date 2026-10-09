package com.photosync.app.sync

import android.content.Context
import androidx.work.*
import com.photosync.app.data.PreferencesManager
import java.util.concurrent.TimeUnit

class SyncManager(private val context: Context) {
    private val workManager = WorkManager.getInstance(context)
    private val prefs = PreferencesManager(context)

    companion object {
        const val UNIQUE_PERIODIC_WORK = "photosync_periodic_work"
        const val UNIQUE_ONE_TIME_WORK = "photosync_manual_work"
    }

    fun schedulePeriodicSync() {
        if (!prefs.isAutoSyncEnabled) {
            cancelPeriodicSync()
            return
        }

        val constraintsBuilder = Constraints.Builder()
            .setRequiredNetworkType(NetworkType.UNMETERED) // Wi-Fi only

        if (prefs.isChargingOnly) {
            constraintsBuilder.setRequiresCharging(true)
        }

        val periodicRequest = PeriodicWorkRequestBuilder<FreeLanSyncWorker>(1, TimeUnit.HOURS)
            .setConstraints(constraintsBuilder.build())
            .setBackoffCriteria(BackoffPolicy.EXPONENTIAL, 15, TimeUnit.MINUTES)
            .build()

        workManager.enqueueUniquePeriodicWork(
            UNIQUE_PERIODIC_WORK,
            ExistingPeriodicWorkPolicy.UPDATE,
            periodicRequest
        )
    }

    fun triggerImmediateSync(): androidx.lifecycle.LiveData<WorkInfo?> {
        val constraints = Constraints.Builder()
            .setRequiredNetworkType(NetworkType.CONNECTED)
            .build()

        val oneTimeRequest = OneTimeWorkRequestBuilder<FreeLanSyncWorker>()
            .setConstraints(constraints)
            .build()

        workManager.enqueueUniqueWork(
            UNIQUE_ONE_TIME_WORK,
            ExistingWorkPolicy.REPLACE,
            oneTimeRequest
        )

        return workManager.getWorkInfoByIdLiveData(oneTimeRequest.id)
    }

    fun cancelPeriodicSync() {
        workManager.cancelUniqueWork(UNIQUE_PERIODIC_WORK)
    }
}

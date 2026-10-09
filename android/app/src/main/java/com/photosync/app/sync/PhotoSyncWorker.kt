package com.photosync.app.sync

import android.app.NotificationChannel
import android.app.NotificationManager
import android.content.Context
import android.content.pm.ServiceInfo
import android.os.Build
import androidx.core.app.NotificationCompat
import androidx.work.CoroutineWorker
import androidx.work.ForegroundInfo
import androidx.work.WorkerParameters
import androidx.work.workDataOf
import com.photosync.app.data.MediaStoreScanner
import com.photosync.app.data.PreferencesManager
import com.photosync.app.network.PhotoSyncApiClient
import com.photosync.app.network.HttpStatusException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

class PhotoSyncWorker(
    private val context: Context,
    params: WorkerParameters
) : CoroutineWorker(context, params) {

    private val prefs = PreferencesManager(context)
    private val scanner = MediaStoreScanner(context)
    private val apiClient = PhotoSyncApiClient()

    companion object {
        const val CHANNEL_ID = "photosync_backup_channel"
        const val NOTIFICATION_ID = 1001
        const val KEY_PROGRESS_CURRENT = "progress_current"
        const val KEY_PROGRESS_TOTAL = "progress_total"
        const val KEY_FAILURE_REASON = "failure_reason"

        /** 4xx responses are permanent for this pairing; retrying cannot succeed. */
        private fun isPermanentHttpError(e: Throwable?): Boolean =
            e is HttpStatusException && e.code in 400..499

        private fun failureResult(e: Throwable?): Result =
            Result.failure(workDataOf(KEY_FAILURE_REASON to (e?.message ?: "Unknown backup error")))
    }

    override suspend fun doWork(): Result = withContext(Dispatchers.IO) {
        val config = prefs.getServerConfig()
        if (!config.isPaired) {
            return@withContext Result.failure()
        }

        createNotificationChannel()
        setForeground(createForegroundInfo(0, 0, "Scanning photos & videos..."))

        try {
            // 1. Scan local photos & videos from MediaStore (both collections, TD-039)
            val mediaItems = scanner.queryMediaItems(limit = 1000)
            if (mediaItems.isEmpty()) {
                return@withContext Result.success()
            }

            // 2. Compute local hashes and prepare batch
            val hashMap = mutableMapOf<String, com.photosync.app.data.LocalMediaItem>()
            val hashList = mutableListOf<String>()

            for (item in mediaItems) {
                val hash = scanner.calculateSha256(item.uri)
                if (hash != null) {
                    hashMap[hash] = item
                    hashList.add(hash)
                }
            }

            if (hashList.isEmpty()) {
                return@withContext Result.success()
            }

            // 3. Batch check missing hashes on Desktop Server
            val checkResult = apiClient.checkBatchHashes(
                host = config.host,
                port = config.port,
                token = config.authToken,
                hashes = hashList
            )

            val missingHashes = checkResult.getOrNull()
                ?: return@withContext if (isPermanentHttpError(checkResult.exceptionOrNull())) {
                    failureResult(checkResult.exceptionOrNull())
                } else {
                    Result.retry()
                }

            if (missingHashes.isEmpty()) {
                prefs.setLastSyncTime(System.currentTimeMillis())
                return@withContext Result.success()
            }

            // 4. Upload missing files
            val totalToUpload = missingHashes.size
            var uploadedCount = 0
            var transientFailures = 0
            var permanentFailures = 0
            var lastFailure: Throwable? = null

            val isoFormat = SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss'Z'", Locale.US)

            for (missingHash in missingHashes) {
                val item = hashMap[missingHash] ?: continue
                uploadedCount++

                val progressMsg = "Backing up $uploadedCount of $totalToUpload items"
                setForeground(createForegroundInfo(uploadedCount, totalToUpload, progressMsg))
                setProgress(workDataOf(
                    KEY_PROGRESS_CURRENT to uploadedCount,
                    KEY_PROGRESS_TOTAL to totalToUpload
                ))

                val takenIso = if (item.dateTaken > 0) isoFormat.format(Date(item.dateTaken)) else null

                val uploadResult = apiClient.uploadPhoto(
                    context = context,
                    host = config.host,
                    port = config.port,
                    token = config.authToken,
                    uri = item.uri,
                    filename = item.displayName,
                    sha256 = missingHash,
                    mimeType = item.mimeType,
                    takenAtIso = takenIso
                )

                if (uploadResult.isFailure) {
                    // Track failures: 4xx is permanent (retrying cannot help),
                    // anything else (network/5xx) is transient.
                    val err = uploadResult.exceptionOrNull()
                    err?.printStackTrace()
                    if (isPermanentHttpError(err)) {
                        permanentFailures++
                        lastFailure = err
                        val code = (err as? HttpStatusException)?.code
                        if (code == 401 || code == 403) break // bad credential: stop the run
                    } else {
                        transientFailures++
                        lastFailure = err
                    }
                }
            }

            // TD-033: success only when every item actually uploaded.
            when {
                transientFailures == 0 && permanentFailures == 0 -> {
                    prefs.setLastSyncTime(System.currentTimeMillis())
                    Result.success()
                }
                transientFailures > 0 -> Result.retry()
                else -> failureResult(lastFailure)
            }
        } catch (e: Exception) {
            e.printStackTrace()
            if (isPermanentHttpError(e)) failureResult(e) else Result.retry()
        }
    }

    private fun createForegroundInfo(current: Int, total: Int, text: String): ForegroundInfo {
        val notification = NotificationCompat.Builder(context, CHANNEL_ID)
            .setContentTitle("FreeLanSync Backup")
            .setContentText(text)
            .setSmallIcon(android.R.drawable.ic_menu_upload)
            .setOngoing(true)
            .setProgress(total, current, total == 0)
            .build()

        return if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            ForegroundInfo(NOTIFICATION_ID, notification, ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC)
        } else {
            ForegroundInfo(NOTIFICATION_ID, notification)
        }
    }

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val name = "FreeLanSync Backup Service"
            val importance = NotificationManager.IMPORTANCE_LOW
            val channel = NotificationChannel(CHANNEL_ID, name, importance)
            val manager = context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
            manager.createNotificationChannel(channel)
        }
    }
}

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
    }

    override suspend fun doWork(): Result = withContext(Dispatchers.IO) {
        val config = prefs.getServerConfig()
        if (!config.isPaired) {
            return@withContext Result.failure()
        }

        createNotificationChannel()
        setForeground(createForegroundInfo(0, 0, "Scanning photos..."))

        try {
            // 1. Scan local photos from MediaStore
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

            val missingHashes = checkResult.getOrNull() ?: return@withContext Result.retry()

            if (missingHashes.isEmpty()) {
                prefs.setLastSyncTime(System.currentTimeMillis())
                return@withContext Result.success()
            }

            // 4. Upload missing files
            val totalToUpload = missingHashes.size
            var uploadedCount = 0

            val isoFormat = SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss'Z'", Locale.US)

            for (missingHash in missingHashes) {
                val item = hashMap[missingHash] ?: continue
                uploadedCount++

                val progressMsg = "Backing up $uploadedCount of $totalToUpload photos"
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
                    // Log error and continue with next file
                    uploadResult.exceptionOrNull()?.printStackTrace()
                }
            }

            prefs.setLastSyncTime(System.currentTimeMillis())
            Result.success()
        } catch (e: Exception) {
            e.printStackTrace()
            Result.retry()
        }
    }

    private fun createForegroundInfo(current: Int, total: Int, text: String): ForegroundInfo {
        val notification = NotificationCompat.Builder(context, CHANNEL_ID)
            .setContentTitle("PhotoSync Backup")
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
            val name = "PhotoSync Backup Service"
            val importance = NotificationManager.IMPORTANCE_LOW
            val channel = NotificationChannel(CHANNEL_ID, name, importance)
            val manager = context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
            manager.createNotificationChannel(channel)
        }
    }
}

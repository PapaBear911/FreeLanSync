package com.photosync.app.sync

import android.app.NotificationChannel
import android.app.NotificationManager
import android.content.Context
import android.content.pm.ServiceInfo
import android.os.Build
import android.util.Log
import androidx.core.app.NotificationCompat
import androidx.work.CoroutineWorker
import androidx.work.ForegroundInfo
import androidx.work.WorkerParameters
import androidx.work.workDataOf
import com.photosync.app.data.MediaStoreScanner
import com.photosync.app.data.PreferencesManager
import com.photosync.app.network.DeviceBridgeWebSocket
import com.photosync.app.network.FreeLanSyncApiClient
import com.photosync.app.network.HttpStatusException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.supervisorScope
import kotlinx.coroutines.sync.Semaphore
import kotlinx.coroutines.sync.withPermit
import kotlinx.coroutines.withContext
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicInteger
import java.util.concurrent.atomic.AtomicReference

class FreeLanSyncWorker(
    private val context: Context,
    params: WorkerParameters
) : CoroutineWorker(context, params) {

    private val prefs = PreferencesManager(context)
    private val scanner = MediaStoreScanner(context)
    private val apiClient = FreeLanSyncApiClient()

    companion object {
        private const val TAG = "FreeLanSyncWorker"
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

            // 4. Upload missing files via parallel coroutine pool (concurrency = 4)
            val totalToUpload = missingHashes.size
            val uploadedCount = AtomicInteger(0)
            val transFailuresCount = AtomicInteger(0)
            val permFailuresCount = AtomicInteger(0)
            val lastFailureRef = AtomicReference<Throwable?>(null)
            val authAborted = AtomicBoolean(false)

            val isoFormat = SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss'Z'", Locale.US)
            val semaphore = Semaphore(permits = 4)

            supervisorScope {
                missingHashes.map { missingHash ->
                    async {
                        if (authAborted.get()) return@async
                        val item = hashMap[missingHash] ?: return@async

                        semaphore.withPermit {
                            if (authAborted.get()) return@withPermit
                            val currentCount = uploadedCount.incrementAndGet()

                            val progressMsg = "Backing up $currentCount of $totalToUpload items"
                            setForeground(createForegroundInfo(currentCount, totalToUpload, progressMsg))
                            setProgress(workDataOf(
                                KEY_PROGRESS_CURRENT to currentCount,
                                KEY_PROGRESS_TOTAL to totalToUpload
                            ))

                            val takenIso = if (item.dateTaken > 0) isoFormat.format(Date(item.dateTaken)) else null

                            var currentHash = missingHash
                            var uploadResult = apiClient.uploadPhoto(
                                context = context,
                                host = config.host,
                                port = config.port,
                                token = config.authToken,
                                uri = item.uri,
                                filename = item.displayName,
                                sha256 = currentHash,
                                mimeType = item.mimeType,
                                takenAtIso = takenIso,
                                size = item.size
                            )

                            if (uploadResult.isFailure) {
                                var err = uploadResult.exceptionOrNull()
                                var statusCode = (err as? HttpStatusException)?.code

                                // 400: Retry item once (recomputing hash). If 400 persists, mark failed and continue.
                                if (statusCode == 400) {
                                    val recomputedHash = scanner.calculateSha256(item.uri)
                                    if (recomputedHash != null) {
                                        currentHash = recomputedHash
                                    }
                                    uploadResult = apiClient.uploadPhoto(
                                        context = context,
                                        host = config.host,
                                        port = config.port,
                                        token = config.authToken,
                                        uri = item.uri,
                                        filename = item.displayName,
                                        sha256 = currentHash,
                                        mimeType = item.mimeType,
                                        takenAtIso = takenIso,
                                        size = item.size
                                    )
                                    if (uploadResult.isFailure) {
                                        err = uploadResult.exceptionOrNull()
                                        statusCode = (err as? HttpStatusException)?.code
                                    }
                                }

                                if (uploadResult.isFailure) {
                                    err?.printStackTrace()
                                    when (statusCode) {
                                        413 -> {
                                            // 413: Log warning, permanently skip item (mark processed/continue to next item)
                                            Log.w(TAG, "Item ${item.displayName} exceeds server upload limits (HTTP 413). Skipping.")
                                        }
                                        401, 403 -> {
                                            // 401/403: Stop batch immediately, post telemetry/notification, return Result.failure()
                                            if (authAborted.compareAndSet(false, true)) {
                                                val errorMsg = "Authentication failed (HTTP $statusCode) during backup"
                                                DeviceBridgeWebSocket.getInstance().sendNotification(
                                                    id = "auth_failure_${System.currentTimeMillis()}",
                                                    packageName = context.packageName,
                                                    appName = "FreeLanSync",
                                                    title = "Backup Paused",
                                                    text = errorMsg
                                                )
                                                postAuthErrorNotification(errorMsg)
                                                lastFailureRef.set(err)
                                            }
                                        }
                                        in 400..499 -> {
                                            permFailuresCount.incrementAndGet()
                                            lastFailureRef.compareAndSet(null, err)
                                        }
                                        else -> {
                                            // 5xx / IOException / Timeout: Record transient failure and trigger Result.retry()
                                            transFailuresCount.incrementAndGet()
                                            lastFailureRef.compareAndSet(null, err)
                                        }
                                    }
                                }
                            }
                        }
                    }
                }.awaitAll()
            }

            if (authAborted.get()) {
                return@withContext failureResult(lastFailureRef.get())
            }

            // TD-033: success only when every item actually uploaded.
            val transientFailures = transFailuresCount.get()
            val permanentFailures = permFailuresCount.get()
            val lastFailure = lastFailureRef.get()
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

    private fun postAuthErrorNotification(message: String) {
        val notification = NotificationCompat.Builder(context, CHANNEL_ID)
            .setContentTitle("FreeLanSync Authentication Error")
            .setContentText(message)
            .setSmallIcon(android.R.drawable.ic_dialog_alert)
            .setAutoCancel(true)
            .build()
        val manager = context.getSystemService(Context.NOTIFICATION_SERVICE) as? NotificationManager
        manager?.notify(1002, notification)
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

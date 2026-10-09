package com.photosync.app.network

import android.content.ContentResolver
import android.content.Context
import android.net.Uri
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.*
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.RequestBody.Companion.toRequestBody
import okio.BufferedSink
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.io.FileOutputStream
import java.io.IOException
import java.util.concurrent.TimeUnit

/** HTTP status surfaced so callers can separate permanent 4xx from transient errors. */
class HttpStatusException(val code: Int, message: String) : Exception(message)

class ContentUriRequestBody(
    private val contentResolver: ContentResolver,
    private val uri: Uri,
    private val mimeType: String,
    private val size: Long = -1L
) : RequestBody() {
    override fun contentType(): MediaType? = mimeType.toMediaType()

    override fun contentLength(): Long = if (size >= 0) size else -1L

    override fun writeTo(sink: BufferedSink) {
        val inputStream = contentResolver.openInputStream(uri)
            ?: throw IOException("Cannot open input stream for $uri")
        inputStream.use { input ->
            val buffer = ByteArray(8192)
            var bytesRead: Int
            while (input.read(buffer).also { bytesRead = it } != -1) {
                sink.write(buffer, 0, bytesRead)
            }
        }
    }
}

class FreeLanSyncApiClient {
    private val client = OkHttpClient.Builder()
        .connectTimeout(15, TimeUnit.SECONDS)
        .writeTimeout(60, TimeUnit.SECONDS)
        .readTimeout(60, TimeUnit.SECONDS)
        .build()

    suspend fun pairWithServer(
        host: String,
        port: Int,
        pin: String,
        deviceName: String,
        deviceId: String
    ): Result<String> = withContext(Dispatchers.IO) {
        try {
            val json = JSONObject().apply {
                put("pin", pin)
                put("device_name", deviceName)
                put("device_id", deviceId)
            }
            val requestBody = json.toString().toRequestBody("application/json".toMediaType())
            val request = Request.Builder()
                .url("http://$host:$port/api/v1/pairing/verify")
                .post(requestBody)
                .build()

            client.newCall(request).execute().use { response ->
                val body = response.body?.string() ?: ""
                val respJson = JSONObject(body)
                if (response.isSuccessful && respJson.optBoolean("success")) {
                    val token = respJson.getString("auth_token")
                    Result.success(token)
                } else {
                    val msg = respJson.optString("message", "Pairing failed")
                    Result.failure(Exception(msg))
                }
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun checkBatchHashes(
        host: String,
        port: Int,
        token: String,
        hashes: List<String>
    ): Result<List<String>> = withContext(Dispatchers.IO) {
        try {
            val jsonArray = JSONArray(hashes)
            val json = JSONObject().apply {
                put("hashes", jsonArray)
            }
            val requestBody = json.toString().toRequestBody("application/json".toMediaType())
            val request = Request.Builder()
                .url("http://$host:$port/api/v1/photos/check-batch")
                .header("Authorization", "Bearer $token")
                .post(requestBody)
                .build()

            client.newCall(request).execute().use { response ->
                if (!response.isSuccessful) {
                    return@withContext Result.failure(
                        HttpStatusException(response.code, "HTTP error ${response.code}")
                    )
                }
                val body = response.body?.string() ?: ""
                val respJson = JSONObject(body)
                val missingArray = respJson.getJSONArray("missing_hashes")
                val missingList = mutableListOf<String>()
                for (i in 0 until missingArray.length()) {
                    missingList.add(missingArray.getString(i))
                }
                Result.success(missingList)
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun uploadPhoto(
        context: Context,
        host: String,
        port: Int,
        token: String,
        uri: Uri,
        filename: String,
        sha256: String,
        mimeType: String,
        takenAtIso: String?,
        size: Long = -1L
    ): Result<Unit> = withContext(Dispatchers.IO) {
        try {
            val fileBody = ContentUriRequestBody(
                contentResolver = context.contentResolver,
                uri = uri,
                mimeType = mimeType,
                size = size
            )
            val multipartBuilder = MultipartBody.Builder()
                .setType(MultipartBody.FORM)
                .addFormDataPart("sha256", sha256)
                .addFormDataPart("file", filename, fileBody)

            if (takenAtIso != null) {
                multipartBuilder.addFormDataPart("taken_at", takenAtIso)
            }

            val request = Request.Builder()
                .url("http://$host:$port/api/v1/photos/upload")
                .header("Authorization", "Bearer $token")
                .post(multipartBuilder.build())
                .build()

            client.newCall(request).execute().use { response ->
                if (response.isSuccessful) {
                    Result.success(Unit)
                } else {
                    Result.failure(
                        HttpStatusException(response.code, "Upload failed with HTTP ${response.code}")
                    )
                }
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun getPendingDrops(
        host: String,
        port: Int,
        token: String? = null
    ): Result<List<JSONObject>> = withContext(Dispatchers.IO) {
        try {
            val reqBuilder = Request.Builder()
                .url("http://$host:$port/api/v1/drop/pending")
                .get()
            if (!token.isNullOrBlank()) {
                reqBuilder.header("Authorization", "Bearer $token")
            }

            client.newCall(reqBuilder.build()).execute().use { response ->
                if (response.isSuccessful) {
                    val body = response.body?.string() ?: ""
                    val json = JSONObject(body)
                    val array = json.optJSONArray("pending") ?: JSONArray()
                    val list = mutableListOf<JSONObject>()
                    for (i in 0 until array.length()) {
                        list.add(array.getJSONObject(i))
                    }
                    Result.success(list)
                } else {
                    Result.failure(HttpStatusException(response.code, "Failed to fetch pending drops HTTP ${response.code}"))
                }
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun downloadDropFile(
        host: String,
        port: Int,
        fileId: String,
        destinationFile: File,
        token: String? = null
    ): Result<File> = withContext(Dispatchers.IO) {
        val parentDir = destinationFile.parentFile ?: destinationFile
        val tempFile = File(parentDir, ".tmp_${fileId}_${System.currentTimeMillis()}")
        try {
            val reqBuilder = Request.Builder()
                .url("http://$host:$port/api/v1/drop/download/$fileId")
                .get()
            if (!token.isNullOrBlank()) {
                reqBuilder.header("Authorization", "Bearer $token")
            }

            client.newCall(reqBuilder.build()).execute().use { response ->
                if (!response.isSuccessful) {
                    return@withContext Result.failure(
                        HttpStatusException(response.code, "Download failed with HTTP ${response.code}")
                    )
                }
                val body = response.body ?: throw IOException("Empty response body")
                body.byteStream().use { input ->
                    FileOutputStream(tempFile).use { output ->
                        input.copyTo(output)
                    }
                }
                if (destinationFile.exists()) {
                    destinationFile.delete()
                }
                if (!tempFile.renameTo(destinationFile)) {
                    tempFile.copyTo(destinationFile, overwrite = true)
                    tempFile.delete()
                }
                Result.success(destinationFile)
            }
        } catch (e: Exception) {
            tempFile.delete()
            Result.failure(e)
        }
    }
}

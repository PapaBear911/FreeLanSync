package com.photosync.app.network

import android.content.Context
import android.net.Uri
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.*
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.RequestBody.Companion.asRequestBody
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.io.FileOutputStream
import java.util.concurrent.TimeUnit

/** HTTP status surfaced so callers can separate permanent 4xx from transient errors. */
class HttpStatusException(val code: Int, message: String) : Exception(message)

class PhotoSyncApiClient {
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
        takenAtIso: String?
    ): Result<Unit> = withContext(Dispatchers.IO) {
        var tempFile: File? = null
        try {
            // Read content into temp file for OkHttp streaming upload
            tempFile = File.createTempFile("upload_", ".tmp", context.cacheDir)
            context.contentResolver.openInputStream(uri)?.use { input ->
                FileOutputStream(tempFile).use { output ->
                    input.copyTo(output)
                }
            } ?: return@withContext Result.failure(Exception("Cannot open media stream"))

            val fileBody = tempFile.asRequestBody(mimeType.toMediaType())
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
        } finally {
            tempFile?.delete()
        }
    }

    suspend fun getPendingDrops(host: String, port: Int): Result<List<JSONObject>> = withContext(Dispatchers.IO) {
        try {
            val request = Request.Builder()
                .url("http://$host:$port/api/v1/drop/pending")
                .get()
                .build()

            client.newCall(request).execute().use { response ->
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
                    Result.failure(Exception("Failed to fetch pending drops HTTP ${response.code}"))
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
        destinationFile: File
    ): Result<File> = withContext(Dispatchers.IO) {
        try {
            val request = Request.Builder()
                .url("http://$host:$port/api/v1/drop/download/$fileId")
                .get()
                .build()

            client.newCall(request).execute().use { response ->
                if (response.isSuccessful) {
                    response.body?.byteStream()?.use { input ->
                        FileOutputStream(destinationFile).use { output ->
                            input.copyTo(output)
                        }
                    }
                    Result.success(destinationFile)
                } else {
                    Result.failure(Exception("Download failed with HTTP ${response.code}"))
                }
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }
}

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
                    return@withContext Result.failure(Exception("HTTP error ${response.code}"))
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
                    Result.failure(Exception("Upload failed with HTTP ${response.code}"))
                }
            }
        } catch (e: Exception) {
            Result.failure(e)
        } finally {
            tempFile?.delete()
        }
    }
}

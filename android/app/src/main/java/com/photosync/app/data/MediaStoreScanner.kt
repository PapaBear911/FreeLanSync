package com.photosync.app.data

import android.content.ContentUris
import android.content.Context
import android.net.Uri
import android.provider.MediaStore
import java.io.InputStream
import java.security.MessageDigest

data class LocalMediaItem(
    val id: Long,
    val uri: Uri,
    val displayName: String,
    val mimeType: String,
    val size: Long,
    val dateAdded: Long,
    val dateTaken: Long
)

class MediaStoreScanner(private val context: Context) {

    fun queryMediaItems(limit: Int = 500): List<LocalMediaItem> {
        val items = mutableListOf<LocalMediaItem>()
        val collection = MediaStore.Images.Media.EXTERNAL_CONTENT_URI

        val projection = arrayOf(
            MediaStore.Images.Media._ID,
            MediaStore.Images.Media.DISPLAY_NAME,
            MediaStore.Images.Media.MIME_TYPE,
            MediaStore.Images.Media.SIZE,
            MediaStore.Images.Media.DATE_ADDED,
            MediaStore.Images.Media.DATE_TAKEN
        )

        val sortOrder = "${MediaStore.Images.Media.DATE_TAKEN} DESC"

        try {
            context.contentResolver.query(collection, projection, null, null, sortOrder)?.use { cursor ->
                val idCol = cursor.getColumnIndexOrThrow(MediaStore.Images.Media._ID)
                val nameCol = cursor.getColumnIndexOrThrow(MediaStore.Images.Media.DISPLAY_NAME)
                val mimeCol = cursor.getColumnIndexOrThrow(MediaStore.Images.Media.MIME_TYPE)
                val sizeCol = cursor.getColumnIndexOrThrow(MediaStore.Images.Media.SIZE)
                val addedCol = cursor.getColumnIndexOrThrow(MediaStore.Images.Media.DATE_ADDED)
                val takenCol = cursor.getColumnIndexOrThrow(MediaStore.Images.Media.DATE_TAKEN)

                while (cursor.moveToNext() && items.size < limit) {
                    val id = cursor.getLong(idCol)
                    val name = cursor.getString(nameCol) ?: "unnamed_image.jpg"
                    val mime = cursor.getString(mimeCol) ?: "image/jpeg"
                    val size = cursor.getLong(sizeCol)
                    val added = cursor.getLong(addedCol)
                    val taken = cursor.getLong(takenCol)
                    val uri = ContentUris.withAppendedId(collection, id)

                    items.add(LocalMediaItem(id, uri, name, mime, size, added, taken))
                }
            }
        } catch (e: Exception) {
            e.printStackTrace()
        }

        return items
    }

    fun calculateSha256(uri: Uri): String? {
        return try {
            context.contentResolver.openInputStream(uri)?.use { inputStream ->
                val digest = MessageDigest.getInstance("SHA-256")
                val buffer = ByteArray(8192)
                var bytesRead: Int
                while (inputStream.read(buffer).also { bytesRead = it } != -1) {
                    digest.update(buffer, 0, bytesRead)
                }
                digest.digest().joinToString("") { "%02x".format(it) }
            }
        } catch (e: Exception) {
            null
        }
    }
}

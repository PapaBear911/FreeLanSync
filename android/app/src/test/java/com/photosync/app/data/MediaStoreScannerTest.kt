package com.photosync.app.data

import android.content.ContentProvider
import android.content.ContentValues
import android.database.Cursor
import android.database.MatrixCursor
import android.net.Uri
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.RuntimeEnvironment
import org.robolectric.annotation.Config
import org.robolectric.shadows.ShadowContentResolver

/**
 * TD-039 guard: MediaStoreScanner must enumerate the VIDEO collection, not just
 * images. The fake provider answers image-collection queries with an image row
 * and video-collection queries with a video row — an images-only scanner can
 * never see the video row, so this test fails on a regression to that bug.
 */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class MediaStoreScannerTest {

    private class FakeMediaProvider : ContentProvider() {
        override fun onCreate(): Boolean = true

        override fun query(
            uri: Uri,
            projection: Array<out String>?,
            selection: String?,
            selectionArgs: Array<out String>?,
            sortOrder: String?
        ): Cursor {
            val cursor = MatrixCursor(projection ?: emptyArray())
            val path = uri.path.orEmpty()
            if (path.contains("/video/")) {
                cursor.addRow(
                    arrayOf(2L, "VID_0002.mp4", "video/mp4", 2048L, 1_700_000_100L, 1_700_000_100_000L)
                )
            } else {
                cursor.addRow(
                    arrayOf(1L, "IMG_0001.jpg", "image/jpeg", 1024L, 1_700_000_000L, 1_700_000_000_000L)
                )
            }
            return cursor
        }

        override fun getType(uri: Uri): String = "vnd.android.cursor.dir/media"
        override fun insert(uri: Uri, values: ContentValues?): Uri? = null
        override fun delete(uri: Uri, selection: String?, selectionArgs: Array<out String>?): Int = 0
        override fun update(
            uri: Uri,
            values: ContentValues?,
            selection: String?,
            selectionArgs: Array<out String>?
        ): Int = 0
    }

    private fun registerFakeMediaStore(): MediaStoreScanner {
        ShadowContentResolver.registerProviderInternal("media", FakeMediaProvider())
        return MediaStoreScanner(RuntimeEnvironment.getApplication())
    }

    @Test
    fun test_scanner_enumerates_video_items() {
        val scanner = registerFakeMediaStore()

        val items = scanner.queryMediaItems()

        assertTrue(
            "image row missing — scanner lost the images collection",
            items.any { it.mimeType == "image/jpeg" && it.displayName == "IMG_0001.jpg" }
        )
        val video = items.firstOrNull { it.mimeType == "video/mp4" }
        assertNotNull(
            "TD-039: scanner never queried MediaStore.Video — videos cannot back up",
            video
        )
        assertEquals("VID_0002.mp4", video!!.displayName)
        assertEquals(2048L, video.size)
        assertTrue(
            "video URI must point at the video collection",
            video.uri.toString().contains("video")
        )
        assertEquals("content://media/external/video/media/2", video.uri.toString())
    }

    @Test
    fun queryMediaItems_mergesNewestFirstAcrossCollections() {
        val scanner = registerFakeMediaStore()

        val items = scanner.queryMediaItems()

        // The video row carries the later DATE_TAKEN, so it must sort first.
        assertEquals("video/mp4", items.first().mimeType)
        assertEquals("image/jpeg", items.last().mimeType)
    }

    @Test
    fun queryMediaItems_capsNewestItemsAcrossBothCollections() {
        val scanner = registerFakeMediaStore()

        val items = scanner.queryMediaItems(limit = 1)

        assertEquals(1, items.size)
        assertEquals(
            "limit must keep the newest item across collections, not fill up with images",
            "video/mp4",
            items.first().mimeType
        )
    }
}

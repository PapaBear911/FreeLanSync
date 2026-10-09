package com.photosync.app.network

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Parser tests for every pairing payload shape the desktop server can emit
 * (see server/auth.py build_pairing_uri + get_pairing_info qr_payload) plus
 * adversarial/non-pairing QR contents.
 */
class PairingPayloadParserTest {

    // --- 1. Deep link (server pairing_uri) ---

    @Test
    fun parsesServerDeepLink() {
        val payload = PairingPayloadParser.parse("freelansync://192.168.1.42:8080?pin=654321&service=freelansync")
        assertNotNull(payload)
        assertEquals("192.168.1.42", payload!!.host)
        assertEquals(8080, payload.port)
        assertEquals("654321", payload.pin)
        assertTrue(payload.canAutoConnect)
    }

    @Test
    fun parsesDeepLinkWithTokenAlias() {
        // Task spec mentions ?token=... as an alternative query key.
        val payload = PairingPayloadParser.parse("freelansync://10.0.0.5:9000?token=111222")
        assertNotNull(payload)
        assertEquals("10.0.0.5", payload!!.host)
        assertEquals(9000, payload.port)
        assertEquals("111222", payload.pin)
    }

    @Test
    fun parsesLegacyPhotosyncScheme() {
        val payload = PairingPayloadParser.parse("photosync://192.168.0.7:8080?pin=999888")
        assertNotNull(payload)
        assertEquals("192.168.0.7", payload!!.host)
        assertEquals("999888", payload.pin)
    }

    @Test
    fun deepLinkWithoutPinIsValidButCannotAutoConnect() {
        val payload = PairingPayloadParser.parse("freelansync://192.168.1.42:8080")
        assertNotNull(payload)
        assertNull(payload!!.pin)
        assertFalse(payload.canAutoConnect)
    }

    // --- 2. JSON QR payload (server qr_payload) ---

    @Test
    fun parsesJsonQrPayload() {
        val json = """{"version":1,"host":"192.168.1.42","port":8080,"pin":"123456","service":"freelansync"}"""
        val payload = PairingPayloadParser.parse(json)
        assertNotNull(payload)
        assertEquals("192.168.1.42", payload!!.host)
        assertEquals(8080, payload.port)
        assertEquals("123456", payload.pin)
        assertTrue(payload.canAutoConnect)
    }

    @Test
    fun rejectsForeignJsonPayload() {
        // The APK-download QR encodes a URL, but guard the JSON shape too.
        val json = """{"service":"apk-download","url":"http://192.168.1.42:8080/static/FreeLanSync.apk"}"""
        assertNull(PairingPayloadParser.parse(json))
    }

    @Test
    fun rejectsJsonWithInvalidPort() {
        assertNull(PairingPayloadParser.parse("""{"host":"192.168.1.42","port":0,"service":"freelansync"}"""))
        assertNull(PairingPayloadParser.parse("""{"host":"192.168.1.42","port":70000,"service":"freelansync"}"""))
        assertNull(PairingPayloadParser.parse("""{"host":"192.168.1.42","port":-5,"service":"freelansync"}"""))
    }

    @Test
    fun rejectsJsonWithMissingHost() {
        assertNull(PairingPayloadParser.parse("""{"port":8080,"pin":"123456","service":"freelansync"}"""))
    }

    // --- 3. Bare host:port ---

    @Test
    fun parsesBareHostPortWithPin() {
        val payload = PairingPayloadParser.parse("192.168.1.42:8080?pin=555444")
        assertNotNull(payload)
        assertEquals("192.168.1.42", payload!!.host)
        assertEquals(8080, payload.port)
        assertEquals("555444", payload.pin)
    }

    // --- 4. Adversarial / non-pairing inputs ---

    @Test
    fun rejectsEmptyAndBlankInput() {
        assertNull(PairingPayloadParser.parse(null))
        assertNull(PairingPayloadParser.parse(""))
        assertNull(PairingPayloadParser.parse("   "))
    }

    @Test
    fun rejectsApkDownloadUrl() {
        assertNull(PairingPayloadParser.parse("http://192.168.1.42:8080/static/FreeLanSync.apk"))
        assertNull(PairingPayloadParser.parse("https://example.com/some/page"))
    }

    @Test
    fun rejectsMalformedJson() {
        assertNull(PairingPayloadParser.parse("{not json at all"))
        assertNull(PairingPayloadParser.parse("{\"host\":"))
    }

    @Test
    fun rejectsPortOutOfRangeInUri() {
        assertNull(PairingPayloadParser.parse("freelansync://192.168.1.42:70000?pin=123456"))
        assertNull(PairingPayloadParser.parse("freelansync://192.168.1.42:0?pin=123456"))
    }

    @Test
    fun rejectsUnknownScheme() {
        assertNull(PairingPayloadParser.parse("evilapp://192.168.1.42:8080?pin=123456"))
    }

    @Test
    fun trimsSurroundingWhitespace() {
        val payload = PairingPayloadParser.parse("  freelansync://192.168.1.9:8080?pin=121212  ")
        assertNotNull(payload)
        assertEquals("192.168.1.9", payload!!.host)
    }

    @Test
    fun pinWithWrongLengthStillParsesButCannotAutoConnect() {
        // Server always emits 6 digits; a tampered 4-digit pin must not auto-connect.
        val payload = PairingPayloadParser.parse("freelansync://192.168.1.9:8080?pin=1212")
        assertNotNull(payload)
        assertEquals("1212", payload!!.pin)
        assertFalse(payload.canAutoConnect)
    }
}

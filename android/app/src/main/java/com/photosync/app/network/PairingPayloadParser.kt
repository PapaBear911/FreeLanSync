package com.photosync.app.network

import org.json.JSONObject

/**
 * Result of parsing a pairing payload from a QR code or a freelansync:// deep link.
 *
 * @param host IPv4/hostname of the desktop server
 * @param port HTTP port of the desktop server
 * @param pin 6-digit pairing PIN (present when the payload came from the local operator)
 */
data class PairingPayload(
    val host: String,
    val port: Int,
    val pin: String?
) {
    val canAutoConnect: Boolean
        get() = host.isNotBlank() && port in 1..65535 && pin != null && pin.length == 6
}

/**
 * Parses the pairing payloads emitted by the FreeLanSync desktop server.
 *
 * Supported encodings:
 *  1. Deep link:  freelansync://192.168.1.10:8080?pin=123456  (?token= is accepted as an alias)
 *  2. JSON QR:    {"service":"freelansync","host":"...","port":8080,"pin":"123456","version":1}
 *  3. Bare host:port with an optional pin query: 192.168.1.10:8080?pin=123456
 *
 * Anything else (APK download URLs, random QR codes, malformed input) returns null so the
 * caller can show a "not a pairing code" message instead of failing silently.
 */
object PairingPayloadParser {

    const val SCHEME = "freelansync"
    const val LEGACY_SCHEME = "photosync"
    private val HOST_PORT_REGEX = Regex("""^([\w.-]+):(\d{1,5})(?:\?.*)?$""")

    fun parse(raw: String?): PairingPayload? {
        val text = raw?.trim().orEmpty()
        if (text.isEmpty()) return null

        // 1. Explicit scheme (freelansync://... or legacy photosync://...)
        val lower = text.lowercase()
        for (scheme in listOf(SCHEME, LEGACY_SCHEME)) {
            if (lower.startsWith("$scheme://")) {
                return parseUriBody(text.substring(scheme.length + 3))
            }
        }

        // 2. JSON payload
        if (text.startsWith("{")) {
            return parseJson(text)
        }

        // 3. Bare host:port[?pin=...]
        return parseUriBody(text)
    }

    private fun parseUriBody(body: String): PairingPayload? {
        val (authority, query) = splitQuery(body)
        if (authority.isBlank()) return null

        val hostPort = HOST_PORT_REGEX.find(authority) ?: return null
        val host = hostPort.groupValues[1]
        val port = hostPort.groupValues[2].toIntOrNull() ?: return null
        if (port !in 1..65535) return null

        val pin = queryParam(query, "pin") ?: queryParam(query, "token")
        return PairingPayload(host = host, port = port, pin = pin)
    }

    private fun parseJson(text: String): PairingPayload? {
        return try {
            val json = JSONObject(text)
            val service = json.optString("service", "")
            // Reject foreign QR payloads (e.g. the APK download QR) explicitly.
            if (service.isNotEmpty() && service != "freelansync" && service != "photosync") {
                null
            } else {
                val host = json.optString("host", "")
                val port = json.optInt("port", -1)
                if (host.isBlank() || port !in 1..65535) {
                    null
                } else {
                    val pin = json.optString("pin", "").ifBlank { null }
                    PairingPayload(host = host, port = port, pin = pin)
                }
            }
        } catch (e: Exception) {
            null
        }
    }

    private fun splitQuery(body: String): Pair<String, String> {
        val idx = body.indexOf('?')
        return if (idx >= 0) body.substring(0, idx) to body.substring(idx + 1)
        else body to ""
    }

    private fun queryParam(query: String, key: String): String? {
        if (query.isEmpty()) return null
        for (pair in query.split('&')) {
            val eq = pair.indexOf('=')
            if (eq <= 0) continue
            if (pair.substring(0, eq).trim().equals(key, ignoreCase = true)) {
                val value = pair.substring(eq + 1).trim()
                if (value.isNotEmpty()) return value
            }
        }
        return null
    }
}

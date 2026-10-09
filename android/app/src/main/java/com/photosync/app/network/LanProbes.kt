package com.photosync.app.network

import android.util.Log
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request
import org.json.JSONObject
import java.net.DatagramPacket
import java.net.DatagramSocket
import java.net.Inet4Address
import java.net.InetAddress
import java.net.InetSocketAddress
import java.net.NetworkInterface
import java.net.Socket
import java.net.SocketTimeoutException
import java.util.concurrent.TimeUnit

/**
 * Fast verifier for a candidate FreeLanSync server: `GET /api/v1/ping` must answer
 * `status=online` with a FreeLanSync/PhotoSync service name (server/main.py:ping).
 * Short timeouts keep discovery snappy and bounded on unreachable hosts.
 */
object ServerPingVerifier {

    private const val TAG = "ServerPingVerifier"

    private val client: OkHttpClient = OkHttpClient.Builder()
        .connectTimeout(400, TimeUnit.MILLISECONDS)
        .readTimeout(600, TimeUnit.MILLISECONDS)
        .callTimeout(1_000, TimeUnit.MILLISECONDS)
        .retryOnConnectionFailure(false)
        .build()

    fun verify(host: String, port: Int): Boolean {
        if (host.isBlank() || port !in 1..65535) return false
        return try {
            val request = Request.Builder().url("http://$host:$port/api/v1/ping").build()
            client.newCall(request).execute().use { resp ->
                if (!resp.isSuccessful) return@use false
                val body = resp.body?.string().orEmpty()
                val json = JSONObject(body)
                val service = json.optString("service")
                json.optString("status") == "online" &&
                    (service.contains("FreeLanSync", ignoreCase = true) ||
                        service.contains("PhotoSync", ignoreCase = true))
            }
        } catch (t: Throwable) {
            Log.d(TAG, "verify($host:$port) failed: ${t.message}")
            false
        }
    }
}

/**
 * UDP broadcast fallback for networks where mDNS/NSD is broken (dual-band routers,
 * AP/client isolation). Mirrors `server/udp_discovery.py`:
 * send `FREELANSYNC_DISCOVER_V1` to port 8079, parse the JSON envelope, then
 * confirm the hit with [ServerPingVerifier] before exposing it.
 *
 * All failures (no Wi-Fi, no route, permission issues) collapse to an empty list —
 * discovery degrades instead of crashing.
 */
object UdpBroadcastProber {

    const val MAGIC = "FREELANSYNC_DISCOVER_V1"
    const val DEFAULT_PORT = 8079 // server config.DISCOVERY_UDP_PORT default
    private const val TAG = "UdpProber"
    private const val RECEIVE_TIMEOUT_MS = 250

    suspend fun probe(
        port: Int = DEFAULT_PORT,
        attempts: Int = 2,
        windowMs: Long = 800
    ): List<DiscoveredServer> = withContext(Dispatchers.IO) {
        try {
            val payload = MAGIC.toByteArray(Charsets.US_ASCII)
            val targets = broadcastTargets()
            val found = linkedMapOf<String, DiscoveredServer>()

            DatagramSocket().use { sock ->
                sock.broadcast = true
                sock.soTimeout = RECEIVE_TIMEOUT_MS
                repeat(attempts) {
                    targets.forEach { target ->
                        try {
                            sock.send(DatagramPacket(payload, payload.size, target, port))
                        } catch (e: Exception) {
                            // Network unreachable / no Wi-Fi — keep going, receive window still open.
                            Log.d(TAG, "probe send to ${target.hostAddress} failed: ${e.message}")
                        }
                    }
                    val deadline = System.currentTimeMillis() + windowMs
                    while (System.currentTimeMillis() < deadline) {
                        val buf = ByteArray(2048)
                        val packet = DatagramPacket(buf, buf.size)
                        try {
                            sock.receive(packet)
                        } catch (e: SocketTimeoutException) {
                            continue
                        }
                        parseEnvelope(buf, packet.length)?.let { server ->
                            found.putIfAbsent("${server.host}:${server.port}", server)
                        }
                    }
                }
            }

            // Envelope is spoofable on an open LAN — confirm each hit speaks FreeLanSync.
            found.values.filter { ServerPingVerifier.verify(it.host, it.port) }
        } catch (t: Throwable) {
            Log.d(TAG, "probe aborted: ${t.message}")
            emptyList()
        }
    }

    private fun parseEnvelope(data: ByteArray, length: Int): DiscoveredServer? {
        return try {
            val json = JSONObject(String(data, 0, length, Charsets.UTF_8))
            val service = json.optString("service")
            if (service != "freelansync" && service != "photosync") return null
            val host = json.optString("host")
            val port = json.optInt("port", -1)
            if (host.isBlank() || port !in 1..65535) return null
            DiscoveredServer(
                serviceName = json.optString("name").ifBlank { "FreeLanSync Desktop" },
                host = host,
                port = port,
                source = "udp"
            )
        } catch (t: Throwable) {
            null
        }
    }

    private fun broadcastTargets(): List<InetAddress> {
        val targets = linkedSetOf<InetAddress>()
        try {
            targets.add(InetAddress.getByName("255.255.255.255"))
        } catch (e: Exception) {
            Log.d(TAG, "default broadcast unavailable: ${e.message}")
        }
        try {
            NetworkInterface.getNetworkInterfaces()?.toList()?.forEach { nif ->
                if (!nif.isUp || nif.isLoopback) return@forEach
                nif.interfaceAddresses?.forEach { ia ->
                    ia.broadcast?.let { targets.add(it) } // e.g. 192.168.1.255
                }
            }
        } catch (e: Exception) {
            Log.d(TAG, "interface broadcast enumeration failed: ${e.message}")
        }
        return targets.toList()
    }
}

/**
 * Last-resort discovery: bounded TCP port sweep of the local subnet, verified with
 * [ServerPingVerifier]. Runs only when mDNS and UDP probing found nothing.
 *
 * Safety bounds: only /24-/30 subnets, 48 parallel connects, 250 ms connect timeout,
 * early exit on first verified server, own addresses excluded.
 */
object PortPinger {

    private const val TAG = "PortPinger"
    private val DEFAULT_PORTS = listOf(8080, 8081, 8000)
    private const val CONNECT_TIMEOUT_MS = 250
    private const val PARALLEL = 48
    private const val MAX_HOSTS = 510

    suspend fun sweepSubnet(ports: List<Int> = DEFAULT_PORTS): List<DiscoveredServer> =
        withContext(Dispatchers.IO) {
            try {
                val hosts = subnetHosts()
                if (hosts.isEmpty()) return@withContext emptyList()
                val candidates = hosts.flatMap { host -> ports.map { port -> host to port } }
                Log.d(TAG, "sweeping ${candidates.size} candidates (${hosts.size} hosts)")

                for (batch in candidates.chunked(PARALLEL)) {
                    val hits = coroutineScope {
                        batch.map { (host, port) ->
                            async { if (tcpConnect(host, port)) host to port else null }
                        }.awaitAll().filterNotNull()
                    }
                    for ((host, port) in hits) {
                        if (ServerPingVerifier.verify(host, port)) {
                            return@withContext listOf(
                                DiscoveredServer("FreeLanSync Desktop", host, port, source = "ping")
                            )
                        }
                    }
                }
                emptyList()
            } catch (t: Throwable) {
                Log.d(TAG, "sweep aborted: ${t.message}")
                emptyList()
            }
        }

    private fun tcpConnect(host: String, port: Int): Boolean = try {
        Socket().use { sock ->
            sock.connect(InetSocketAddress(host, port), CONNECT_TIMEOUT_MS)
            true
        }
    } catch (t: Throwable) {
        false
    }

    /** Site-local IPv4 hosts of this device's up interfaces, excluding self. */
    private fun subnetHosts(): List<String> {
        val hosts = linkedSetOf<String>()
        val self = linkedSetOf<String>()
        try {
            NetworkInterface.getNetworkInterfaces()?.toList()?.forEach { nif ->
                if (!nif.isUp || nif.isLoopback) return@forEach
                nif.inetAddresses?.toList()?.forEach { addr ->
                    if (addr is Inet4Address && !addr.isLoopbackAddress && !addr.isAnyLocalAddress) {
                        addr.hostAddress?.let { self.add(it) }
                    }
                }
                nif.interfaceAddresses?.forEach { ia ->
                    val addr = ia.address as? Inet4Address ?: return@forEach
                    if (addr.isLoopbackAddress || addr.isAnyLocalAddress) return@forEach
                    val prefix = ia.networkPrefixLength.toInt()
                    if (prefix < 24 || prefix > 30) return@forEach // too broad or degenerate
                    hosts.addAll(enumerateSubnet(addr, prefix))
                }
            }
        } catch (t: Throwable) {
            Log.d(TAG, "subnet enumeration failed: ${t.message}")
            return emptyList()
        }
        return hosts.minus(self).toList()
    }

    private fun enumerateSubnet(ip: Inet4Address, prefix: Int): List<String> {
        val b = ip.address
        val ipInt = ((b[0].toInt() and 0xff) shl 24) or
            ((b[1].toInt() and 0xff) shl 16) or
            ((b[2].toInt() and 0xff) shl 8) or
            (b[3].toInt() and 0xff)
        val mask = (-1) shl (32 - prefix)
        val network = ipInt and mask
        val broadcast = network or mask.inv()
        val hostCount = (broadcast - network) - 1
        if (hostCount <= 0 || hostCount > MAX_HOSTS) return emptyList()
        return (1 until hostCount).map { intToIp(network + it) }
    }

    private fun intToIp(value: Int): String =
        "${(value ushr 24) and 0xff}.${(value ushr 16) and 0xff}.${(value ushr 8) and 0xff}.${value and 0xff}"
}

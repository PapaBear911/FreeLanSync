package com.photosync.app.network

import android.content.Context
import android.net.nsd.NsdManager
import android.net.nsd.NsdServiceInfo
import android.os.Handler
import android.os.Looper
import android.util.Log
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

data class DiscoveredServer(
    val serviceName: String,
    val host: String,
    val port: Int,
    /** How the server was found: "mdns", "udp" or "ping". */
    val source: String = "mdns"
)

/**
 * mDNS/NSD discovery for the desktop server.
 *
 * Enhancements over the original single-type listener:
 *  - discovers BOTH service types the server advertises (`_freelansync._tcp.` and
 *    legacy `_photosync._tcp.`) — see server/discovery.py;
 *  - resolve failures retry with exponential backoff instead of dropping the server;
 *  - a guard prevents NsdManager's "already resolving" IllegalArgumentException storm;
 *  - discovery-start failures (e.g. ERROR_ALREADY_DISCOVERY) retry with backoff
 *    instead of silently stopping forever.
 */
class NsdDiscoveryManager(context: Context) {

    private val nsdManager = context.getSystemService(Context.NSD_SERVICE) as? NsdManager
    private val handler = Handler(Looper.getMainLooper())

    /** Service types registered by server/discovery.py. */
    private val serviceTypes = listOf("_freelansync._tcp.", "_photosync._tcp.")

    private val _discoveredServers = MutableStateFlow<List<DiscoveredServer>>(emptyList())
    val discoveredServers: StateFlow<List<DiscoveredServer>> = _discoveredServers.asStateFlow()

    private val activeListeners = mutableMapOf<String, NsdManager.DiscoveryListener>()
    private val resolving = mutableSetOf<String>()
    private val pendingRetries = mutableMapOf<String, Runnable>()

    @Volatile
    private var running = false

    private var startRetryCount = 0

    fun startDiscovery() {
        if (nsdManager == null || running) return
        running = true
        startRetryCount = 0
        serviceTypes.forEach { type -> discover(type) }
    }

    private fun discover(serviceType: String) {
        if (activeListeners.containsKey(serviceType)) return

        val listener = object : NsdManager.DiscoveryListener {
            override fun onDiscoveryStarted(regType: String) {
                startRetryCount = 0
                Log.d(TAG, "mDNS discovery started for $regType")
            }

            override fun onServiceFound(found: NsdServiceInfo) {
                // Only accept the two types we asked for (a discovery listener for
                // one type can still report others on some OEM builds).
                if (serviceTypes.any { found.serviceType.startsWith(it.trimEnd('.')) || found.serviceType.startsWith(it) }) {
                    resolveService(found, attempt = 0)
                }
            }

            override fun onServiceLost(lost: NsdServiceInfo) {
                removeByName(lost.serviceName)
            }

            override fun onDiscoveryStopped(regType: String) {
                activeListeners.remove(regType)
            }

            override fun onStartDiscoveryFailed(regType: String, errorCode: Int) {
                Log.w(TAG, "mDNS start failed for $regType code=$errorCode")
                activeListeners.remove(regType)
                // Retry with backoff instead of giving up permanently
                // (busy handler / transient failures recover on their own; a
                // duplicate-discovery rejection also clears after a pause).
                if (running && startRetryCount < MAX_START_RETRIES) {
                    val delay = START_RETRY_BACKOFF_MS[startRetryCount.coerceAtMost(START_RETRY_BACKOFF_MS.size - 1)]
                    startRetryCount++
                    schedule("start:$regType", delay) {
                        if (running) discover(regType)
                    }
                }
            }

            override fun onStopDiscoveryFailed(regType: String, errorCode: Int) {
                activeListeners.remove(regType)
            }
        }

        try {
            nsdManager?.discoverServices(serviceType, NsdManager.PROTOCOL_DNS_SD, listener)
            activeListeners[serviceType] = listener
        } catch (e: Exception) {
            Log.w(TAG, "discoverServices($serviceType) threw", e)
        }
    }

    private fun resolveService(info: NsdServiceInfo, attempt: Int) {
        val nsd = nsdManager ?: return
        val key = "${info.serviceName}/${info.serviceType}"
        if (!resolving.add(key)) return // already in flight — NsdManager throws on double-resolve

        try {
            nsd.resolveService(info, object : NsdManager.ResolveListener {
                override fun onResolveFailed(failed: NsdServiceInfo, errorCode: Int) {
                    resolving.remove("${failed.serviceName}/${failed.serviceType}")
                    if (!running) return
                    if (attempt < MAX_RESOLVE_RETRIES) {
                        val delay = RESOLVE_BACKOFF_MS[attempt.coerceAtMost(RESOLVE_BACKOFF_MS.size - 1)]
                        Log.d(TAG, "resolve failed (${failed.serviceName} code=$errorCode), retry ${attempt + 1} in ${delay}ms")
                        schedule("resolve:$key", delay) {
                            if (running) resolveService(failed, attempt + 1)
                        }
                    } else {
                        Log.w(TAG, "resolve gave up on ${failed.serviceName} after ${attempt + 1} attempts")
                    }
                }

                override fun onServiceResolved(resolved: NsdServiceInfo) {
                    resolving.remove("${resolved.serviceName}/${resolved.serviceType}")
                    val host = resolved.host?.hostAddress ?: return
                    val server = DiscoveredServer(
                        serviceName = resolved.serviceName,
                        host = host,
                        port = resolved.port,
                        source = "mdns"
                    )
                    val current = _discoveredServers.value
                    if (current.none { it.host == host && it.port == resolved.port }) {
                        _discoveredServers.value = current + server
                    }
                }
            })
        } catch (e: Exception) {
            // IllegalArgumentException: already resolving, or service vanished.
            resolving.remove(key)
            Log.d(TAG, "resolveService threw for ${info.serviceName}: ${e.message}")
        }
    }

    private fun removeByName(serviceName: String?) {
        if (serviceName == null) return
        _discoveredServers.value = _discoveredServers.value.filterNot { it.serviceName == serviceName }
    }

    private fun schedule(key: String, delayMs: Long, block: () -> Unit) {
        cancel(key)
        val runnable = Runnable { pendingRetries.remove(key); block() }
        pendingRetries[key] = runnable
        handler.postDelayed(runnable, delayMs)
    }

    private fun cancel(key: String) {
        pendingRetries.remove(key)?.let(handler::removeCallbacks)
    }

    fun stopDiscovery() {
        running = false
        pendingRetries.keys.toList().forEach(::cancel)
        pendingRetries.clear()
        activeListeners.values.toList().forEach { listener ->
            try {
                nsdManager?.stopServiceDiscovery(listener)
            } catch (e: Exception) {
                Log.d(TAG, "stopServiceDiscovery: ${e.message}")
            }
        }
        activeListeners.clear()
        resolving.clear()
    }

    companion object {
        private const val TAG = "NsdDiscovery"
        private const val MAX_RESOLVE_RETRIES = 3
        private const val MAX_START_RETRIES = 3
        private val RESOLVE_BACKOFF_MS = longArrayOf(500L, 1_500L, 3_500L)
        private val START_RETRY_BACKOFF_MS = longArrayOf(1_000L, 3_000L, 8_000L)
    }
}

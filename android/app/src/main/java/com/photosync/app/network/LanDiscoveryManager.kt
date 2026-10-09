package com.photosync.app.network

import android.content.Context
import android.util.Log
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlin.coroutines.coroutineContext

/**
 * Layered LAN discovery:
 *
 *   1. mDNS/NSD (both service types, retry/backoff) — fast when it works;
 *   2. UDP broadcast probe (port 8079) — every cycle, survives broken mDNS;
 *   3. subnet port sweep — only while nothing is found.
 *
 * Empty cycles back off (4s -> 8s -> 15s) so a phone on a foreign network does not
 * burn battery; once a server is listed the cycle relaxes to a 30s refresh that
 * re-verifies non-mDNS entries and drops stale hits. Everything degrades to an
 * empty list rather than throwing (no-network case).
 */
class LanDiscoveryManager(context: Context) {

    private val nsdManager = NsdDiscoveryManager(context)
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)

    private val _discoveredServers = MutableStateFlow<List<DiscoveredServer>>(emptyList())
    val discoveredServers: StateFlow<List<DiscoveredServer>> = _discoveredServers.asStateFlow()

    private var nsdCollectJob: Job? = null
    private var probeLoopJob: Job? = null

    fun startDiscovery() {
        nsdManager.startDiscovery()
        if (nsdCollectJob?.isActive != true) {
            nsdCollectJob = scope.launch {
                nsdManager.discoveredServers.collect { nsdList -> reconcileNsd(nsdList) }
            }
        }
        if (probeLoopJob?.isActive != true) {
            probeLoopJob = scope.launch { probeLoop() }
        }
    }

    private suspend fun probeLoop() {
        var emptyCycles = 0
        var lastPruneMs = 0L
        while (coroutineContext.isActive) {
            // Phase 1: cheap UDP probe (idempotent; answers only real FreeLanSync servers).
            merge(UdpBroadcastProber.probe())

            // Phase 2: bounded port sweep only while we have nothing.
            if (_discoveredServers.value.isEmpty()) {
                merge(PortPinger.sweepSubnet())
                emptyCycles++
            } else {
                emptyCycles = 0
            }

            // Phase 3: periodic liveness prune of non-mDNS hits (server restarted/died).
            val now = System.currentTimeMillis()
            if (now - lastPruneMs > PRUNE_INTERVAL_MS && _discoveredServers.value.isNotEmpty()) {
                lastPruneMs = now
                pruneUnverified()
            }

            val delayMs = if (_discoveredServers.value.isEmpty()) {
                EMPTY_BACKOFF_MS[emptyCycles.coerceAtMost(EMPTY_BACKOFF_MS.lastIndex)]
            } else {
                FOUND_REFRESH_MS
            }
            delay(delayMs)
        }
    }

    private fun reconcileNsd(nsdList: List<DiscoveredServer>) {
        val current = _discoveredServers.value
        val nsdKeys = nsdList.map { it.host to it.port }.toSet()
        val kept = current.filterNot { it.source == "mdns" && (it.host to it.port) !in nsdKeys }
        val result = kept.toMutableList()
        nsdList.forEach { server ->
            if (result.none { it.host == server.host && it.port == server.port }) result.add(server)
        }
        if (result != current) _discoveredServers.value = result
    }

    private fun pruneUnverified() {
        val current = _discoveredServers.value
        val survivors = current.filter {
            it.source == "mdns" || ServerPingVerifier.verify(it.host, it.port)
        }
        if (survivors.size != current.size) {
            Log.d(TAG, "pruned ${current.size - survivors.size} stale discovery hit(s)")
            _discoveredServers.value = survivors
        }
    }

    private fun merge(list: List<DiscoveredServer>) {
        if (list.isEmpty()) return
        val current = _discoveredServers.value
        val additions = list.filter { s -> current.none { it.host == s.host && it.port == s.port } }
        if (additions.isNotEmpty()) _discoveredServers.value = current + additions
    }

    fun stopDiscovery() {
        probeLoopJob?.cancel()
        probeLoopJob = null
        nsdCollectJob?.cancel()
        nsdCollectJob = null
        nsdManager.stopDiscovery()
    }

    companion object {
        private const val TAG = "LanDiscovery"
        private val EMPTY_BACKOFF_MS = longArrayOf(4_000L, 8_000L, 15_000L)
        private const val FOUND_REFRESH_MS = 30_000L
        private const val PRUNE_INTERVAL_MS = 30_000L
    }
}

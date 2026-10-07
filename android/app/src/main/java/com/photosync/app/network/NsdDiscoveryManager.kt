package com.photosync.app.network

import android.content.Context
import android.net.nsd.NsdManager
import android.net.nsd.NsdServiceInfo
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

data class DiscoveredServer(
    val serviceName: String,
    val host: String,
    val port: Int
)

class NsdDiscoveryManager(context: Context) {
    private val nsdManager = context.getSystemService(Context.NSD_SERVICE) as? NsdManager
    private val serviceType = "_photosync._tcp."

    private val _discoveredServers = MutableStateFlow<List<DiscoveredServer>>(emptyList())
    val discoveredServers: StateFlow<List<DiscoveredServer>> = _discoveredServers.asStateFlow()

    private var discoveryListener: NsdManager.DiscoveryListener? = null

    fun startDiscovery() {
        if (discoveryListener != null || nsdManager == null) return

        discoveryListener = object : NsdManager.DiscoveryListener {
            override fun onDiscoveryStarted(regType: String) {}

            override fun onServiceFound(serviceInfo: NsdServiceInfo) {
                if (serviceInfo.serviceType.contains("photosync")) {
                    resolveService(serviceInfo)
                }
            }

            override fun onServiceLost(serviceInfo: NsdServiceInfo) {
                val current = _discoveredServers.value.toMutableList()
                current.removeAll { it.serviceName == serviceInfo.serviceName }
                _discoveredServers.value = current
            }

            override fun onDiscoveryStopped(serviceType: String) {}

            override fun onStartDiscoveryFailed(serviceType: String, errorCode: Int) {
                stopDiscovery()
            }

            override fun onStopDiscoveryFailed(serviceType: String, errorCode: Int) {
                stopDiscovery()
            }
        }

        try {
            nsdManager.discoverServices(serviceType, NsdManager.PROTOCOL_DNS_SD, discoveryListener)
        } catch (e: Exception) {
            e.printStackTrace()
        }
    }

    private fun resolveService(serviceInfo: NsdServiceInfo) {
        nsdManager?.resolveService(serviceInfo, object : NsdManager.ResolveListener {
            override fun onResolveFailed(serviceInfo: NsdServiceInfo, errorCode: Int) {}

            override fun onServiceResolved(resolvedInfo: NsdServiceInfo) {
                val host = resolvedInfo.host?.hostAddress ?: return
                val port = resolvedInfo.port
                val server = DiscoveredServer(
                    serviceName = resolvedInfo.serviceName,
                    host = host,
                    port = port
                )
                val current = _discoveredServers.value.toMutableList()
                if (current.none { it.host == host && it.port == port }) {
                    current.add(server)
                    _discoveredServers.value = current
                }
            }
        })
    }

    fun stopDiscovery() {
        discoveryListener?.let {
            try {
                nsdManager?.stopServiceDiscovery(it)
            } catch (e: Exception) {
                e.printStackTrace()
            }
        }
        discoveryListener = null
    }
}

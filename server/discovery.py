"""Zeroconf mDNS advertisement for local network auto-discovery."""
import socket
from zeroconf import Zeroconf, ServiceInfo
from .config import SERVICE_NAME, MDNS_SERVICE_TYPE, LEGACY_MDNS_SERVICE_TYPE, SERVER_PORT, get_local_ip

class MDNSAdvertiser:
    def __init__(self):
        self.zeroconf: Zeroconf | None = None
        self.services: list[ServiceInfo] = []

    def start(self):
        try:
            local_ip = get_local_ip()
            desc = {'path': '/api/v1', 'version': '1.1.0'}
            self.zeroconf = Zeroconf()
            self.services = []
            
            # Primary FreeLanSync service
            primary_info = ServiceInfo(
                type_=MDNS_SERVICE_TYPE,
                name=f"{socket.gethostname()} - {SERVICE_NAME}.{MDNS_SERVICE_TYPE}",
                addresses=[socket.inet_aton(local_ip)],
                port=SERVER_PORT,
                properties=desc,
                server=f"{socket.gethostname().lower()}.local.",
            )
            self.zeroconf.register_service(primary_info)
            self.services.append(primary_info)
            print(f"[mDNS] Registered service '{primary_info.name}' on {local_ip}:{SERVER_PORT}")

            # Legacy PhotoSync service for backward compatibility
            try:
                legacy_info = ServiceInfo(
                    type_=LEGACY_MDNS_SERVICE_TYPE,
                    name=f"{socket.gethostname()} - PhotoSync.{LEGACY_MDNS_SERVICE_TYPE}",
                    addresses=[socket.inet_aton(local_ip)],
                    port=SERVER_PORT,
                    properties=desc,
                    server=f"{socket.gethostname().lower()}.local.",
                )
                self.zeroconf.register_service(legacy_info)
                self.services.append(legacy_info)
            except Exception:
                pass
        except Exception as e:
            print(f"[mDNS] Warning: Failed to register mDNS service: {e}")

    def stop(self):
        if self.zeroconf:
            try:
                for s in self.services:
                    try:
                        self.zeroconf.unregister_service(s)
                    except Exception:
                        pass
                self.zeroconf.close()
                print("[mDNS] Services unregistered.")
            except Exception as e:
                print(f"[mDNS] Warning: Failed to unregister mDNS service: {e}")
            finally:
                self.zeroconf = None
                self.services = []

mdns_advertiser = MDNSAdvertiser()

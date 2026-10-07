"""Zeroconf mDNS advertisement for local network auto-discovery."""
import socket
from zeroconf import Zeroconf, ServiceInfo
from .config import SERVICE_NAME, MDNS_SERVICE_TYPE, SERVER_PORT, get_local_ip

class MDNSAdvertiser:
    def __init__(self):
        self.zeroconf: Zeroconf | None = None
        self.service_info: ServiceInfo | None = None

    def start(self):
        try:
            local_ip = get_local_ip()
            desc = {'path': '/api/v1', 'version': '1.0.0'}
            
            # Construct service info
            self.service_info = ServiceInfo(
                type_=MDNS_SERVICE_TYPE,
                name=f"{socket.gethostname()} - {SERVICE_NAME}.{MDNS_SERVICE_TYPE}",
                addresses=[socket.inet_aton(local_ip)],
                port=SERVER_PORT,
                properties=desc,
                server=f"{socket.gethostname().lower()}.local.",
            )
            
            self.zeroconf = Zeroconf()
            self.zeroconf.register_service(self.service_info)
            print(f"[mDNS] Registered service '{self.service_info.name}' on {local_ip}:{SERVER_PORT}")
        except Exception as e:
            print(f"[mDNS] Warning: Failed to register mDNS service: {e}")

    def stop(self):
        if self.zeroconf and self.service_info:
            try:
                self.zeroconf.unregister_service(self.service_info)
                self.zeroconf.close()
                print("[mDNS] Service unregistered.")
            except Exception as e:
                print(f"[mDNS] Warning: Failed to unregister mDNS service: {e}")
            finally:
                self.zeroconf = None
                self.service_info = None

mdns_advertiser = MDNSAdvertiser()
